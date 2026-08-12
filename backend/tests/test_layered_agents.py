"""#21 分层智能体契约测试 — 10 个服务函数 + 智能体动作端点 + AITask 状态机。

服务函数通过 httpx MockTransport 模拟 LLM（不发起真实请求），走完整
prompt → JSON 解析 → 结构校验链路；端点测试 monkeypatch _build_llm_client，
验证落库（资产 / 审计 / AITask 状态机 / 权限）。
"""
import json

import httpx
import pytest
from httpx import MockTransport

from app.db import crud
from app.services import llm_client
from app.services import layered_agent
from app.api import requirement_layers as layers_api

REQ = {'id': 1, 'project_id': 1, 'branch_id': 1, 'title': '订单退款',
       'summary': '支持订单退款流程', 'priority': 'P1'}
SOURCES = [{'link': 'https://x', 'text_content': '订单支持 3 天无理由退款，退款原路返回'}]
STORIES = [
    {'id': 11, 'title': '申请退款', 'description': '用户申请退款', 'acceptance_criteria': ['3 天无理由']},
    {'id': 12, 'title': '退款到账', 'description': '退款原路返回', 'acceptance_criteria': ['原路返回']},
]
TEST_POINTS = [
    {'id': 21, 'requirement_id': 1, 'story_id': 11, 'parent_id': 0,
     'category': 'Functional', 'title': '退款资格', 'description': '验证资格',
     'story_index': 0, 'parent_index': -1},
    {'id': 22, 'requirement_id': 1, 'story_id': 11, 'parent_id': 21,
     'category': 'Boundary', 'title': '金额边界', 'description': '边界金额',
     'story_index': 0, 'parent_index': 0},
]
SCENARIOS = [
    {'id': 31, 'test_point_id': 21, 'title': '正常退款', 'description': '登录申请',
     'coverage_dim': '正常', 'test_point_index': 0},
    {'id': 32, 'test_point_id': 21, 'title': '退款超时', 'description': '网关超时',
     'coverage_dim': '异常', 'test_point_index': 0},
]
CASES = [
    {'id': 41, 'story_id': 11, 'title': '退款-正常', 'preconditions': '已登录',
     'steps': ['申请退款'], 'expected': '退款成功'},
]


# ── 按 prompt 角色关键词返回固定 JSON 的 fake LLM ──


def _fake_transport() -> MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        prompt = json.loads(request.content)['messages'][0]['content']
        if 'Requirement Analyzer' in prompt:
            data = {
                'elements': {
                    'business_goal': '支持订单退款', 'roles': ['用户'], 'entities': ['订单'],
                    'flows': ['申请退款'], 'rules': ['3 天无理由'], 'states': ['待退款', '已退款'],
                    'inputs_outputs': ['退款单'], 'exceptions': ['退款失败'],
                    'permissions': ['仅本人'], 'dependencies': ['支付网关'],
                    'risks': ['资金风险'],
                },
                'information_gaps': [
                    {'gap_type': 'BUSINESS_RULE_MISSING', 'severity': 'CRITICAL',
                     'description': '退款时限未定义', 'question': '退款需在多少天内完成？'},
                ],
                'score': 82, 'score_reason': '规则细节略少',
            }
        elif 'Story Reviewer' in prompt:
            data = {
                'reviews': [
                    {'story_index': 0, 'dimension_scores': {'需求覆盖度': 90, '可测试性': 88},
                     'score': 83, 'issues': [], 'suggestions': ['补充依赖说明'], 'gate_status': 'PASS'},
                    {'story_index': 1, 'dimension_scores': {'需求覆盖度': 70, '可测试性': 60},
                     'score': 62, 'issues': [{'title': '验收标准缺失', 'detail': 'x'}],
                     'suggestions': [], 'gate_status': 'WARNING'},
                ],
                'score': 78, 'score_reason': '整体良好',
            }
        elif 'TestPoint Designer' in prompt:
            data = {
                'test_points': [
                    {'title': '退款资格-正常', 'description': '验证正常退款',
                     'category': 'Functional', 'story_index': 0, 'parent_index': -1},
                    {'title': '退款资格-金额边界', 'description': '验证边界金额',
                     'category': 'Boundary', 'story_index': 0, 'parent_index': 0},
                    {'title': '退款到账-并发', 'description': '并发退款到账',
                     'category': 'Concurrency', 'story_index': 1, 'parent_index': -1},
                ],
                'score': 86, 'score_reason': '覆盖正常/边界/并发',
            }
        elif 'TestPoint Reviewer' in prompt:
            data = {
                'dimension_scores': {'Story覆盖': 90, '业务规则覆盖': 85},
                'score': 84,
                'coverage': {'total': 3, 'covered_stories': ['Story0', 'Story1'],
                             'missing_dimensions': ['性能']},
                'issues': [{'title': '性能维度缺失', 'detail': '无性能测试点'}],
                'suggestions': ['新增退款并发压测测试点'],
                'gate_status': 'PASS',
            }
        elif 'Scenario Designer' in prompt:
            data = {
                'scenarios': [
                    {'test_point_index': 0, 'title': '正常退款流程',
                     'description': '用户登录后申请退款', 'coverage_dim': '正常'},
                    {'test_point_index': 1, 'title': '退款网关超时',
                     'description': '支付网关无响应', 'coverage_dim': '异常'},
                ],
                'score': 88, 'score_reason': '场景完整',
            }
        elif 'Scenario Reviewer' in prompt:
            data = {
                'score': 75,
                'coverage': {'total': 2, 'normal': 1, 'exception': 1,
                             'boundary': 0, 'state': 0, 'uncovered_tps': [2]},
                'issues': [{'title': '状态分支缺失', 'detail': '未覆盖已退款状态'}],
                'suggestions': ['补充状态类场景'],
                'gate_status': 'WARNING',
            }
        elif 'TestCase Reviewer' in prompt:
            data = {
                'checks': {'步骤': True, '预期': True, '数据': True, '业务规则': False},
                'score': 77,
                'issues': [{'title': '业务规则未校验', 'detail': 'x', 'case_index': 0}],
                'suggestions': ['补充规则校验步骤'],
                'gate_status': 'WARNING',
            }
        elif 'Strategy Advisor' in prompt:
            data = {
                'automation_ratio': 60,
                'result': {'level': '半自动化', 'rationale': '回归高频',
                           'per_case': [{'case_index': 0, 'approach': 'automation',
                                         'reason': 'UI 稳定'}]},
            }
        elif 'Coverage Analyzer' in prompt:
            data = {
                'coverage': {'requirement': 100, 'story': 80, 'test_point': 70,
                             'scenario': 60, 'case': 50, 'automation': 30, 'risk': 40},
                'test_gaps': [
                    {'layer': 'case', 'severity': 'P0', 'description': '关键路径用例缺失',
                     'source_ref': 'story:0'},
                    {'layer': 'automation', 'severity': 'P1', 'description': '回归用例未自动化'},
                ],
                'suggestions': ['补充关键路径用例并接入自动化'],
            }
        else:  # 补充用例
            data = {
                'cases': [
                    {'title': '退款-网关超时重试', 'preconditions': '存在待退款订单',
                     'steps': ['触发网关超时', '重试'], 'expected': '提示稍后重试'},
                ],
                'score': 90, 'score_reason': '针对缺口',
            }
        return httpx.Response(
            200,
            json={'choices': [{'message': {'content': json.dumps(data, ensure_ascii=False)}}]},
        )

    return MockTransport(handler)


def _make_client() -> llm_client.LLMClient:
    return llm_client.LLMClient(
        {'provider': 'deepseek', 'api_base': 'http://fake-llm',
         'text_model': 'fake-model', 'vision_model': '', 'api_key': 'fake-key'},
        transport=_fake_transport(),
    )


# ══════════════════════════════════════════════════════════
# 服务函数契约测试（纯服务层，不落库）
# ══════════════════════════════════════════════════════════


async def test_analyze_requirement_contract():
    client = _make_client()
    result = await layered_agent.analyze_requirement(client, REQ, SOURCES)
    elems = result['elements']
    for key in ('business_goal', 'roles', 'entities', 'flows', 'rules', 'states',
                'inputs_outputs', 'exceptions', 'permissions', 'dependencies', 'risks'):
        assert key in elems, f'elements 缺少 {key}'
    assert isinstance(elems['roles'], list)
    gap = result['information_gaps'][0]
    assert gap['severity'] == 'CRITICAL'
    assert result['score'] == 82
    assert result['gate_status'] == 'PASS'


# ── #12 视觉模型分析：多模态 content + image_url ──


def _vision_transport() -> MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        content = body['messages'][0]['content']
        assert isinstance(content, list), '视觉调用应为多模态 content'
        assert any(part.get('type') == 'image_url' and 'data:image/png;base64' in part.get('image_url', {}).get('url', '')
                   for part in content), '应含 base64 图片'
        assert body['model'] == 'vision-model'
        data = {
            'elements': {'business_goal': '图片需求', 'roles': [], 'entities': [], 'flows': [],
                         'rules': [], 'states': [], 'inputs_outputs': [], 'exceptions': [],
                         'permissions': [], 'dependencies': [], 'risks': []},
            'information_gaps': [], 'score': 80, 'score_reason': '图片需求',
        }
        return httpx.Response(200, json={
            'choices': [{'message': {'content': json.dumps(data, ensure_ascii=False)}}],
        })
    return MockTransport(handler)


async def test_analyze_requirement_vision_contract():
    """#12 视觉模型分析：images 非空时走多模态 vision 调用并解析 JSON。"""
    client = llm_client.LLMClient(
        {'provider': 'x', 'api_base': 'http://fake', 'text_model': 'text-model',
         'vision_model': 'vision-model', 'api_key': 'k'},
        transport=_vision_transport(),
    )
    result = await layered_agent.analyze_requirement(
        client, REQ, SOURCES, images=[{'data': 'aGVsbG8=', 'mime_type': 'image/png'}],
    )
    assert result['elements']['business_goal'] == '图片需求'
    assert result['score'] == 80


async def test_analyze_requirement_vision_requires_vision_model():
    """未配置 vision_model 时带图片分析应抛 LLMConfigError。"""
    client = _make_client()  # vision_model=''
    with pytest.raises(llm_client.LLMConfigError):
        await layered_agent.analyze_requirement(
            client, REQ, SOURCES, images=[{'data': 'x', 'mime_type': 'image/png'}],
        )


async def test_review_stories_contract():
    client = _make_client()
    result = await layered_agent.review_stories(client, REQ, SOURCES, STORIES)
    assert len(result['reviews']) == 2
    r0 = result['reviews'][0]
    assert r0['story_index'] == 0
    assert r0['dimension_scores']['需求覆盖度'] == 90
    assert r0['gate_status'] == 'PASS'
    assert result['score'] == 78
    assert result['gate_status'] == 'WARNING'  # 60-79 → WARNING


async def test_generate_test_points_contract():
    client = _make_client()
    result = await layered_agent.generate_test_points(client, REQ, STORIES)
    tps = result['test_points']
    assert len(tps) == 3
    assert tps[0]['category'] == 'Functional'
    assert tps[1]['parent_index'] == 0
    assert result['score'] == 86
    assert result['gate_status'] == 'PASS'


async def test_review_test_points_contract():
    client = _make_client()
    result = await layered_agent.review_test_points(client, REQ, STORIES, TEST_POINTS)
    assert result['dimension_scores']['Story覆盖'] == 90
    assert result['coverage']['missing_dimensions'] == ['性能']
    assert result['gate_status'] == 'PASS'


async def test_generate_scenarios_contract():
    client = _make_client()
    result = await layered_agent.generate_scenarios(client, REQ, TEST_POINTS)
    scenarios = result['scenarios']
    assert len(scenarios) == 2
    assert scenarios[0]['coverage_dim'] == '正常'
    assert scenarios[1]['test_point_index'] == 1
    assert result['gate_status'] == 'PASS'


async def test_review_scenarios_contract():
    client = _make_client()
    result = await layered_agent.review_scenarios(client, REQ, TEST_POINTS, SCENARIOS)
    assert result['coverage']['uncovered_tps'] == [2]
    assert result['score'] == 75
    assert result['gate_status'] == 'WARNING'


async def test_review_cases_contract():
    client = _make_client()
    result = await layered_agent.review_cases(client, REQ, STORIES, TEST_POINTS,
                                              SCENARIOS, CASES)
    assert result['checks']['业务规则'] is False
    assert result['issues'][0]['case_index'] == 0
    assert result['gate_status'] == 'WARNING'


async def test_recommend_strategy_contract():
    client = _make_client()
    result = await layered_agent.recommend_strategy(client, REQ, CASES)
    assert result['automation_ratio'] == 60
    assert result['result']['level'] == '半自动化'
    assert result['result']['per_case'][0]['approach'] == 'automation'


async def test_analyze_coverage_contract():
    client = _make_client()
    stats = {'stories': 2, 'test_points': 3, 'test_scenarios': 2, 'cases': 1}
    result = await layered_agent.analyze_coverage(client, REQ, stats)
    assert result['coverage']['case'] == 50
    gaps = result['test_gaps']
    assert gaps[0]['severity'] == 'P0'
    assert gaps[1]['severity'] == 'P1'
    assert gaps[0]['source_ref'] == 'story:0'
    assert isinstance(result['suggestions'], list)


async def test_generate_supplement_cases_contract():
    client = _make_client()
    gap = {'layer': 'case', 'severity': 'P0', 'description': '关键路径用例缺失',
           'source_ref': 'story:0'}
    result = await layered_agent.generate_supplement_cases(client, REQ, gap, CASES)
    assert result['cases'][0]['title'] == '退款-网关超时重试'
    assert result['cases'][0]['steps'] == ['触发网关超时', '重试']
    assert result['score'] == 90


# ══════════════════════════════════════════════════════════
# 端点测试：monkeypatch _build_llm_client → fake LLM
# ══════════════════════════════════════════════════════════


def _auth(user: dict) -> dict:
    return {'Authorization': f'Bearer {user["token"]}'}


async def _enable_fake_llm(monkeypatch):
    async def fake_build():
        return _make_client()
    monkeypatch.setattr(layers_api, '_build_llm_client', fake_build)


async def _create_req(client, user, project_id, branch_id) -> int:
    resp = await client.post('/api/requirements',
                             json={'project_id': project_id, 'branch_id': branch_id,
                                   'title': '订单退款'},
                             headers=_auth(user))
    return resp.json()['data']['id']


async def _seed_stories(req_id):
    await crud.replace_requirement_stories(req_id, [
        {'title': '申请退款', 'description': '用户申请退款', 'acceptance_criteria': ['3 天无理由']},
        {'title': '退款到账', 'description': '退款原路返回', 'acceptance_criteria': ['原路返回']},
    ])


async def _seed_source(req_id, user_id):
    from app.db.database import session_ctx
    from app.db.models import RequirementSource
    async with session_ctx() as session:
        session.add(RequirementSource(
            requirement_id=req_id, type='lark_link', link='https://x',
            text_content='订单支持 3 天无理由退款，退款原路返回', created_by=user_id))
        await session.commit()


async def test_analyze_endpoint_persists(client, ctx, monkeypatch):
    """需求分析端点：analysis + 信息缺口覆盖 + 审计 + AITask REVIEW。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_source(req_id, ctx['member']['id'])

    resp = await client.post(f'/api/requirements/{req_id}/analysis/analyze', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['score'] == 82
    assert body['data']['task']['stage'] == 'analyze'
    assert body['data']['task']['status'] == 'REVIEW'

    analysis = (await client.get(f'/api/requirements/{req_id}/analysis',
                                 headers=_auth(ctx['member']))).json()['data']
    assert 'business_goal' in json.loads(analysis['elements'])
    assert analysis['score'] == 82

    gaps = (await client.get(f'/api/requirements/{req_id}/information-gaps',
                             headers=_auth(ctx['member']))).json()['data']
    assert len(gaps) == 1
    assert gaps[0]['severity'] == 'CRITICAL'

    audits = (await client.get(f'/api/requirements/{req_id}/review-audits',
                               headers=_auth(ctx['member']))).json()['data']
    assert any(a['artifact_type'] == 'analysis' for a in audits)

    tasks = (await client.get(f'/api/requirements/{req_id}/ai-tasks',
                              headers=_auth(ctx['member']))).json()['data']
    assert tasks[0]['status'] == 'REVIEW'


async def test_story_review_endpoint_blocked_by_critical_gap(client, ctx, monkeypatch):
    """存在未确认 CRITICAL 缺口时 Story 评审 gate 强制 BLOCKED（AITask WAITING_HUMAN）。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_source(req_id, ctx['member']['id'])
    await _seed_stories(req_id)
    await crud.create_information_gap(req_id, ctx['project_id'], ctx['branch_id'],
                                      'BUSINESS_RULE_MISSING', 'CRITICAL', '时限未定义')

    resp = await client.post(f'/api/requirements/{req_id}/stories/review', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['gate_status'] == 'BLOCKED'
    assert body['data']['task']['status'] == 'WAITING_HUMAN'

    stories = await crud.list_requirement_stories(req_id)
    assert stories[0]['gate_status'] == 'PASS'  # 单条 gate 按评分，组级被强制
    assert json.loads(stories[0]['dimension_scores'])['需求覆盖度'] == 90


async def test_test_points_generate_overwrites_with_tree(client, ctx, monkeypatch):
    """测试点生成：覆盖旧测试点、parent 树映射、AITask REVIEW。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_stories(req_id)
    await crud.create_test_point(req_id, 0, 0, 'Functional', '旧测试点')  # 将被覆盖

    resp = await client.post(f'/api/requirements/{req_id}/test-points/generate', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    tps = body['data']['test_points']
    assert len(tps) == 3
    assert tps[0]['title'] == '退款资格-正常'
    assert tps[1]['parent_id'] == tps[0]['id']  # 树形父级映射
    assert tps[0]['story_id'] != 0

    tasks = (await client.get(f'/api/requirements/{req_id}/ai-tasks',
                              headers=_auth(ctx['member']))).json()['data']
    assert tasks[0]['status'] == 'REVIEW'


async def test_review_test_points_endpoint(client, ctx, monkeypatch):
    """测试点评审：评审落库 + 审计 + PASS → CONFIRMED。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_stories(req_id)
    await crud.create_test_point(req_id, 0, 0, 'Functional', '退款资格', '', 0)

    resp = await client.post(f'/api/requirements/{req_id}/test-points/review', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['score'] == 84
    assert body['data']['gate_status'] == 'PASS'
    assert body['data']['task']['status'] == 'CONFIRMED'

    review = (await client.get(f'/api/requirements/{req_id}/layers',
                               headers=_auth(ctx['member']))).json()['data']
    assert review['test_point_review']['score'] == 84
    assert review['test_point_review']['gate_status'] == 'PASS'


async def test_scenario_generate_and_review(client, ctx, monkeypatch):
    """场景生成（覆盖式 + 归属测试点）→ 场景评审（WARNING → WAITING_HUMAN）。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_stories(req_id)
    await crud.create_test_point(req_id, 0, 0, 'Functional', '退款资格', '', 0)
    tp_id = (await crud.list_test_points(req_id))[0]['id']
    await crud.create_test_scenario(req_id, tp_id, '旧场景', '', 'normal')  # 将被覆盖

    resp = await client.post(f'/api/requirements/{req_id}/test-scenarios/generate', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    scenarios = body['data']['scenarios']
    assert len(scenarios) == 2
    assert scenarios[0]['test_point_id'] == tp_id
    assert scenarios[1]['coverage_dim'] == '异常'

    resp = await client.post(f'/api/requirements/{req_id}/test-scenarios/review', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['score'] == 75
    assert body['data']['gate_status'] == 'WARNING'
    assert body['data']['task']['status'] == 'WAITING_HUMAN'


async def test_case_review_endpoint(client, ctx, monkeypatch):
    """用例评审：9 维 checks + WARNING → WAITING_HUMAN。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_stories(req_id)
    await crud.replace_generated_cases(req_id, [
        {'story_id': 0, 'title': '退款-正常', 'preconditions': '已登录',
         'steps': ['申请'], 'expected': '成功'},
    ])

    resp = await client.post(f'/api/requirements/{req_id}/cases/review', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['checks']['业务规则'] is False
    assert body['data']['task']['status'] == 'WAITING_HUMAN'


async def test_strategy_and_coverage_endpoints(client, ctx, monkeypatch):
    """策略推荐 + 覆盖率分析：落库 + TestGap 覆盖式重写 + 审计。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_stories(req_id)
    await crud.create_test_point(req_id, 0, 0, 'Functional', '退款资格', '', 0)
    await crud.replace_generated_cases(req_id, [
        {'story_id': 0, 'title': '退款-正常', 'preconditions': '', 'steps': [], 'expected': 'ok'},
    ])

    resp = await client.post(f'/api/requirements/{req_id}/strategy/recommend',
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['automation_ratio'] == 60
    assert body['data']['task']['status'] == 'CONFIRMED'

    await crud.create_test_gap(req_id, 'case', '旧缺口', 'P0')  # 将被覆盖
    resp = await client.post(f'/api/requirements/{req_id}/coverage/analyze', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['coverage']['case'] == 50

    layers = (await client.get(f'/api/requirements/{req_id}/layers',
                               headers=_auth(ctx['member']))).json()['data']
    assert layers['coverage']['case_coverage'] == 50
    gaps = layers['test_gaps']
    assert len(gaps) == 2
    assert {g['severity'] for g in gaps} == {'P0', 'P1'}
    assert layers['strategy']['automation_ratio'] == 60


async def test_supplement_cases_endpoint(client, ctx, monkeypatch):
    """AI 补测：TestGap → 追加补充用例（不覆盖既有用例）。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await crud.replace_generated_cases(req_id, [
        {'story_id': 0, 'title': '退款-正常', 'preconditions': '', 'steps': [], 'expected': 'ok'},
    ])
    gap = await crud.create_test_gap(req_id, 'case', '关键路径用例缺失', 'P0', 'story:0')

    resp = await client.post(f'/api/test-gaps/{gap["id"]}/generate', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['cases'][0]['title'] == '退款-网关超时重试'
    assert body['data']['task']['status'] == 'CONFIRMED'

    cases = await crud.list_requirement_cases(req_id)
    assert len(cases) == 2  # 追加而非覆盖
    assert cases[0]['title'] == '退款-网关超时重试'


async def test_agent_requires_llm_config_sets_failed_task(client, ctx):
    """未配置 LLM：端点 400 且 AITask 置 FAILED（含错误信息）。"""
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    resp = await client.post(f'/api/requirements/{req_id}/analysis/analyze', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 400
    assert 'LLM' in body['msg']

    tasks = (await client.get(f'/api/requirements/{req_id}/ai-tasks',
                              headers=_auth(ctx['member']))).json()['data']
    assert tasks[0]['status'] == 'FAILED'
    assert tasks[0]['error']


async def test_agent_endpoint_permissions(client, ctx, monkeypatch):
    """非成员 403、需求不存在 404、前置条件缺失 400。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])

    resp = await client.post(f'/api/requirements/{req_id}/analysis/analyze', json={},
                             headers=_auth(ctx['outsider']))
    assert resp.json()['code'] == 403

    resp = await client.post('/api/requirements/999999/analysis/analyze', json={},
                             headers=_auth(ctx['member']))
    assert resp.json()['code'] == 404

    # 未拆 Story 直接生成测试点 → 400
    resp = await client.post(f'/api/requirements/{req_id}/test-points/generate', json={},
                             headers=_auth(ctx['member']))
    assert resp.json()['code'] == 400

    # 不存在的测试缺口 → 404
    resp = await client.post('/api/test-gaps/999999/generate', json={},
                             headers=_auth(ctx['member']))
    assert resp.json()['code'] == 404


# ══════════════════════════════════════════════════════════
# AITask 状态机：确认 / 推进 / 重试（#21）
# ══════════════════════════════════════════════════════════


async def test_ai_task_confirm_and_advance(client, ctx, monkeypatch):
    """REVIEW → confirm → CONFIRMED → advance → NEXT_STAGE，非法流转 400。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_source(req_id, ctx['member']['id'])

    resp = await client.post(f'/api/requirements/{req_id}/analysis/analyze', json={},
                             headers=_auth(ctx['member']))
    task = resp.json()['data']['task']
    task_id = task['id']
    assert task['status'] == 'REVIEW'

    # 确认 → CONFIRMED
    resp = await client.post(f'/api/ai-tasks/{task_id}/confirm', json={'perspective': 'product'},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['status'] == 'CONFIRMED'

    # 重复确认 → 400
    resp = await client.post(f'/api/ai-tasks/{task_id}/confirm', json={},
                             headers=_auth(ctx['member']))
    assert resp.json()['code'] == 400

    # 推进 → NEXT_STAGE
    resp = await client.post(f'/api/ai-tasks/{task_id}/advance',
                             headers=_auth(ctx['member']))
    assert resp.json()['code'] == 200
    assert resp.json()['data']['status'] == 'NEXT_STAGE'

    # 再次推进 → 400
    resp = await client.post(f'/api/ai-tasks/{task_id}/advance',
                             headers=_auth(ctx['member']))
    assert resp.json()['code'] == 400

    # 确认动作落审计
    audits = (await client.get(f'/api/requirements/{req_id}/review-audits',
                               headers=_auth(ctx['member']))).json()['data']
    assert any(a['artifact_type'] == 'ai_task' for a in audits)


async def test_ai_task_retry_reruns_failed_stage(client, ctx, monkeypatch):
    """FAILED → retry → 重新执行该 stage 并成功（新任务终态 REVIEW）。"""
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_source(req_id, ctx['member']['id'])

    # 未配置 LLM → analyze 失败，任务 FAILED
    resp = await client.post(f'/api/requirements/{req_id}/analysis/analyze', json={},
                             headers=_auth(ctx['member']))
    assert resp.json()['code'] == 400
    tasks = (await client.get(f'/api/requirements/{req_id}/ai-tasks',
                              headers=_auth(ctx['member']))).json()['data']
    failed_id = tasks[0]['id']
    assert tasks[0]['status'] == 'FAILED'

    # 配置 fake LLM 后重试 → 重新执行成功
    await _enable_fake_llm(monkeypatch)
    resp = await client.post(f'/api/ai-tasks/{failed_id}/retry',
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body

    tasks = (await client.get(f'/api/requirements/{req_id}/ai-tasks',
                              headers=_auth(ctx['member']))).json()['data']
    assert any(t['id'] == failed_id and t['status'] == 'RETRY' for t in tasks)
    assert any(t['status'] == 'REVIEW' for t in tasks)  # 新任务已成功

    # 非 FAILED 任务不可重试 → 400
    review_task_id = next(t['id'] for t in tasks if t['status'] == 'REVIEW')
    resp = await client.post(f'/api/ai-tasks/{review_task_id}/retry',
                             headers=_auth(ctx['member']))
    assert resp.json()['code'] == 400
