"""Ticket #15 测试 — LLM 配置 CRUD + 智能体三步流程 + AI 评分 + 状态机 + 绑定。

通过 httpx MockTransport 模拟 LLM（不发起真实请求），完整走 prompt → JSON 解析链路。
"""
import json

import httpx
import pytest
from httpx import MockTransport

from app.db import crud
from app.services import llm_client, requirement_agent
from app.api import requirements as req_api

# ── Mock LLM：按 prompt 关键词返回对应固定 JSON ──


def _fake_llm_transport() -> MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt = body['messages'][0]['content']
        if '评审' in prompt and '可测性打分' in prompt:
            data = {
                'conclusion': '需求整体清晰，可进入测试设计',
                'risks': ['依赖外部数据源'],
                'issues': [{'title': '异常场景缺失', 'detail': '未描述超时处理'}],
                'score': 88,
                'score_reason': '功能完整，边界场景略少',
            }
        elif '生成测试用例' in prompt:  # 批量生成用例（prompt 也含"用户故事"，须先判断）
            data = {
                'cases': [
                    {'story_index': 0, 'title': '查询订单-按订单号',
                     'preconditions': '已登录', 'steps': ['输入订单号', '查询'],
                     'expected': '展示订单详情'},
                    {'story_index': 1, 'title': '导出订单-正常导出',
                     'preconditions': '有查询结果', 'steps': ['点击导出'],
                     'expected': '下载 Excel'},
                ],
                'score': 85,
                'score_reason': '覆盖正常与边界',
            }
        elif '原用例' in prompt:  # 单用例重生成
            data = {
                'title': '查询订单-按订单号查询（重生成）',
                'preconditions': '已登录',
                'steps': ['输入订单号', '点击查询'],
                'expected': '返回该订单',
                'score': 95,
                'score_reason': '步骤精简',
            }
        elif '用户故事' in prompt:
            data = {
                'stories': [
                    {'title': '查询订单', 'description': '按条件查询订单列表',
                     'acceptance_criteria': ['支持按订单号查询', '列表分页']},
                    {'title': '导出订单', 'description': '导出查询结果',
                     'acceptance_criteria': ['支持导出 Excel']},
                ],
                'score': 90,
                'score_reason': '拆解粒度合理',
            }
        else:  # 需求元信息
            data = {'title': '订单管理系统', 'summary': '支持订单查询与导出', 'priority': 'P1'}
        return httpx.Response(
            200,
            json={'choices': [{'message': {'content': json.dumps(data, ensure_ascii=False)}}]},
        )

    return MockTransport(handler)


async def _enable_fake_llm(monkeypatch, score=None):
    transport = _fake_llm_transport()
    async def fake_build():
        return llm_client.LLMClient(
            {'provider': 'deepseek', 'api_base': 'http://fake-llm',
             'text_model': 'fake-model', 'vision_model': '', 'api_key': 'fake-key'},
            transport=transport,
        )
    monkeypatch.setattr(req_api, '_build_llm_client', fake_build)


async def _make_requirement(client, ctx) -> int:
    resp = await client.post('/api/requirements',
                             json={'project_id': ctx['project_id'],
                                   'branch_id': ctx['branch_id'],
                                   'title': '订单需求'},
                             headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    return resp.json()['data']['id']


# ── LLM settings CRUD ──


async def test_llm_settings_crud_not_leak_key(client, ctx):
    """PUT 保存配置；GET 返回打码 key，不泄完整 key。"""
    token = ctx['member']['token']
    headers = {'Authorization': f'Bearer {token}'}
    resp = await client.put('/api/settings/llm',
                            json={'provider': 'deepseek', 'api_base': 'https://x/v1',
                                  'text_model': 'm1', 'vision_model': 'v1', 'api_key': 'sk-secret-12345'},
                            headers=headers)
    assert resp.json()['code'] == 200

    resp = await client.get('/api/settings/llm', headers=headers)
    data = resp.json()['data']
    assert data['provider'] == 'deepseek'
    assert data['has_key'] is True
    assert 'sk-secret-12345' not in json.dumps(data)
    assert '****' in data['api_key_masked']

    # 未登录拒绝
    resp = await client.get('/api/settings/llm')
    assert resp.json()['code'] != 200


async def test_llm_settings_empty_api_key_keeps_existing(client, ctx):
    """PUT 时不传 api_key（或传空串）应保留已保存的 key，不覆盖为空。"""
    token = ctx['member']['token']
    headers = {'Authorization': f'Bearer {token}'}
    await client.put('/api/settings/llm',
                     json={'provider': 'deepseek', 'api_base': 'https://x/v1',
                           'text_model': 'm1', 'vision_model': 'v1', 'api_key': 'sk-secret-12345'},
                     headers=headers)

    # 只更新元数据字段，api_key 留空
    resp = await client.put('/api/settings/llm',
                            json={'provider': 'openai', 'api_base': 'https://y/v1',
                                  'text_model': 'm2', 'vision_model': '', 'api_key': ''},
                            headers=headers)
    assert resp.json()['code'] == 200

    resp = await client.get('/api/settings/llm', headers=headers)
    data = resp.json()['data']
    assert data['provider'] == 'openai'
    assert data['has_key'] is True, '空 api_key 不应覆盖已保存的 key'
    assert '****' in data['api_key_masked']


# ── 三步流程 + 状态机 ──


async def test_agent_full_flow_with_state_machine(client, ctx, monkeypatch):
    """meta → 评审 → Story → 用例：输出 JSON 可解析、评分随环节返回、状态机推进。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _make_requirement(client, ctx)
    headers = {'Authorization': f"Bearer {ctx['member']['token']}"}

    # 添加来源
    resp = await client.post(f'/api/requirements/{req_id}/sources',
                             json={'type': 'lark_link', 'link': 'https://www.baidu.com',
                                   'text_content': '支持查询订单，支持导出'},
                             headers=headers)
    assert resp.json()['code'] == 200

    # meta
    resp = await client.post(f'/api/requirements/{req_id}/meta/generate', headers=headers)
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['title'] == '订单管理系统'
    assert body['data']['priority'] == 'P1'

    # 评审
    resp = await client.post(f'/api/requirements/{req_id}/review', json={}, headers=headers)
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['score'] == 88
    assert body['data']['low_score'] is False
    assert isinstance(body['data']['risks'], list)
    assert isinstance(body['data']['issues'], list)
    req = (await client.get(f'/api/requirements/{req_id}', headers=headers)).json()['data']
    assert req['status'] == 'review_passed'

    # Story
    resp = await client.post(f'/api/requirements/{req_id}/stories/generate', headers=headers)
    body = resp.json()
    assert body['code'] == 200
    assert len(body['data']['stories']) == 2
    assert body['data']['score'] == 90
    req = (await client.get(f'/api/requirements/{req_id}', headers=headers)).json()['data']
    assert req['status'] == 'story_confirmed'

    # 用例（覆盖旧用例）
    resp = await client.post(f'/api/requirements/{req_id}/cases/generate', headers=headers)
    body = resp.json()
    assert body['code'] == 200
    assert len(body['data']['cases']) == 2
    assert body['data']['score'] == 85
    req = (await client.get(f'/api/requirements/{req_id}', headers=headers)).json()['data']
    assert req['status'] == 'cases_generated'

    # 完成
    resp = await client.post(f'/api/requirements/{req_id}/complete', headers=headers)
    assert resp.json()['code'] == 200
    req = (await client.get(f'/api/requirements/{req_id}', headers=headers)).json()['data']
    assert req['status'] == 'done'


async def test_generate_cases_defaults_test_type_and_test_data():
    """generate_cases 解析 LLM 输出中的 test_type/test_data；缺失时安全兜底。"""
    def handler(request: httpx.Request) -> httpx.Response:
        data = {
            'cases': [
                {'story_index': 0, 'title': '查询订单-按订单号', 'preconditions': '已登录',
                 'test_data': '订单号: 2024001', 'steps': ['输入订单号', '查询'],
                 'expected': '展示订单详情', 'test_type': '接口'},
                {'story_index': 0, 'title': '查询订单-异常单号', 'preconditions': '已登录',
                 'steps': ['输入非法单号'], 'expected': '提示错误'},
            ],
            'score': 85, 'score_reason': '覆盖正常与边界',
        }
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(data, ensure_ascii=False)}}]})

    client = llm_client.LLMClient({'provider': 'deepseek', 'api_base': 'http://fake-llm',
                                   'text_model': 'fake-model', 'vision_model': '', 'api_key': 'fake-key'},
                                  transport=MockTransport(handler))
    requirement = {'title': '订单需求', 'content': '支持查询订单'}
    stories = [{'title': '查询订单', 'description': '按条件查询订单列表', 'acceptance_criteria': []}]

    result = await requirement_agent.generate_cases(client, requirement, stories)
    cases = result['cases']
    assert cases[0]['test_type'] == '接口'
    assert cases[0]['test_data'] == '订单号: 2024001'
    # 缺失字段 → 安全兜底，不破坏既有字段
    assert cases[1]['test_type'] == '功能'
    assert cases[1]['test_data'] == ''
    assert cases[1]['preconditions'] == '已登录'


async def test_review_low_score(client, ctx, monkeypatch):
    """评分 < 60 标记 low_score（建议重新评审），不阻断流程。"""
    async def fake_build():
        def handler(request: httpx.Request) -> httpx.Response:
            data = {'conclusion': '需求不清晰', 'risks': [], 'issues': [],
                    'score': 45, 'score_reason': '验收标准缺失'}
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(data, ensure_ascii=False)}}]})
        return llm_client.LLMClient({'provider': 'deepseek', 'api_base': 'http://fake-llm',
                                      'text_model': 'm', 'vision_model': '', 'api_key': 'k'},
                                     transport=MockTransport(handler))
    monkeypatch.setattr(req_api, '_build_llm_client', fake_build)

    req_id = await _make_requirement(client, ctx)
    resp = await client.post(f'/api/requirements/{req_id}/review', json={},
                             headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    body = resp.json()
    assert body['code'] == 200
    assert body['data']['score'] == 45
    assert body['data']['low_score'] is True


async def test_review_with_comment_overwrites(client, ctx, monkeypatch):
    """重审携带 review_comment：覆盖旧评审（仅保留最新一条），评论落库。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _make_requirement(client, ctx)
    headers = {'Authorization': f"Bearer {ctx['member']['token']}"}

    await client.post(f'/api/requirements/{req_id}/review', json={}, headers=headers)
    resp = await client.post(f'/api/requirements/{req_id}/review',
                             json={'review_comment': '请补充并发场景的评审'},
                             headers=headers)
    assert resp.json()['code'] == 200

    reviews = (await client.get(f'/api/requirements/{req_id}/reviews', headers=headers)).json()['data']
    assert len(reviews) == 1
    assert reviews[0]['review_comment'] == '请补充并发场景的评审'


async def test_regenerate_single_case(client, ctx, monkeypatch):
    """单个用例重生成：内容覆盖，其余用例不变。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _make_requirement(client, ctx)
    headers = {'Authorization': f"Bearer {ctx['member']['token']}"}
    await client.post(f'/api/requirements/{req_id}/review', json={}, headers=headers)
    await client.post(f'/api/requirements/{req_id}/stories/generate', headers=headers)
    resp = await client.post(f'/api/requirements/{req_id}/cases/generate', headers=headers)
    case_id = resp.json()['data']['cases'][0]['id']

    resp = await client.post(f'/api/requirements/{req_id}/cases/{case_id}/regenerate', headers=headers)
    body = resp.json()
    assert body['code'] == 200
    assert '重生成' in body['data']['title']

    cases = (await client.get(f'/api/requirements/{req_id}/cases', headers=headers)).json()['data']
    assert cases[0]['title'] == '查询订单-按订单号查询（重生成）'
    assert cases[0]['score'] == 95


# ── CaseBinding ──


async def test_case_binding_crud(client, ctx):
    """绑定/重复绑定/列表/解绑 + 自动化用例不存在校验。"""
    req_id = await _make_requirement(client, ctx)
    headers = {'Authorization': f"Bearer {ctx['member']['token']}"}

    # 直接插入一条自动化用例（TestCaseDefinition 复合主键）
    from app.db.database import session_ctx
    from app.db.models import TestCaseDefinition
    async with session_ctx() as session:
        session.add(TestCaseDefinition(
            uid='tc_001', project_id=ctx['project_id'], branch_id=ctx['branch_id'],
            name='测试-查询订单', full_name='test_query_order', test_type='api',
        ))
        await session.commit()

    # 需要先生成一条用例
    from app.db.models import GeneratedCase
    async with session_ctx() as session:
        gc = GeneratedCase(requirement_id=req_id, story_id=0, title='查询订单-正常',
                           preconditions='', steps='[]', expected='ok')
        session.add(gc)
        await session.commit()
        case_id = gc.id

    # 绑定
    resp = await client.post(f'/api/requirements/{req_id}/cases/{case_id}/bindings',
                             json={'uid': 'tc_001', 'project_id': ctx['project_id'],
                                   'branch_id': ctx['branch_id']},
                             headers=headers)
    assert resp.json()['code'] == 200
    # 重复绑定 → 提示已绑定
    resp = await client.post(f'/api/requirements/{req_id}/cases/{case_id}/bindings',
                             json={'uid': 'tc_001', 'project_id': ctx['project_id'],
                                   'branch_id': ctx['branch_id']},
                             headers=headers)
    assert '已绑定' in resp.json()['msg']

    # 不存在的自动化用例
    resp = await client.post(f'/api/requirements/{req_id}/cases/{case_id}/bindings',
                             json={'uid': 'tc_none', 'project_id': ctx['project_id'],
                                   'branch_id': ctx['branch_id']},
                             headers=headers)
    assert resp.json()['code'] == 400

    # 列表（含名称）
    resp = await client.get(f'/api/requirements/{req_id}/cases/{case_id}/bindings', headers=headers)
    bindings = resp.json()['data']
    assert len(bindings) == 1
    assert bindings[0]['uid'] == 'tc_001'
    assert bindings[0]['case_name'] == '测试-查询订单'

    # 解绑
    binding_id = bindings[0]['id']
    resp = await client.delete(f'/api/requirements/cases/{case_id}/bindings/{binding_id}',
                               headers=headers)
    assert resp.json()['code'] == 200
    resp = await client.get(f'/api/requirements/{req_id}/cases/{case_id}/bindings', headers=headers)
    assert resp.json()['data'] == []


async def test_agent_requires_llm_config(client, ctx):
    """未配置 LLM 时智能体端点返回可读错误。"""
    req_id = await _make_requirement(client, ctx)
    resp = await client.post(f'/api/requirements/{req_id}/review', json={},
                             headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    body = resp.json()
    assert body['code'] == 400
    assert 'LLM' in body['msg']


async def test_cases_require_stories(client, ctx, monkeypatch):
    """未拆 Story 直接生成用例被拒绝。"""
    await _enable_fake_llm(monkeypatch)
    req_id = await _make_requirement(client, ctx)
    resp = await client.post(f'/api/requirements/{req_id}/cases/generate',
                             headers={'Authorization': f"Bearer {ctx['member']['token']}"})
    assert resp.json()['code'] == 400
