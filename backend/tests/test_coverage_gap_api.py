"""#23 覆盖率/风险/缺口/AI补测闭环 API 测试（System B：/api/req）。

覆盖 #23 验收：覆盖率计算（7 层字段 + 自动化覆盖率基于绑定数）、
TestGap P0/P1 分级（CRITICAL 缺口归 P0）、AI 补测全链
（TestPoint→Scenario→Case 挂载 + 缺口关闭）、执行历史反哺（失败 Execution→P0 缺口）。
覆盖率/缺口为确定性计算（不调 LLM）；AI 补测用 fake LLM（MockTransport）注入。
"""
import json

import httpx
import pytest
from httpx import MockTransport

from app.db import crud_requirements
from app.services import llm_client
from app.domains.requirement_design import api as req_api


@pytest.fixture(autouse=True)
async def _cleanup_system_b_tables():
    """每个测试后清理本文件创建的 System B 数据。

    conftest 的 DB 是 session 级共享；cascade 测试断言全局 case_bindings 为空，
    因此本文件的绑定/执行/缺口/任务等必须在测试后清掉，避免污染后续测试。
    """
    yield
    from app.db.database import session_ctx
    from app.domains.requirement_design.models import (
        Requirement, RequirementAsset, CaseBinding, AITask,
        ReviewAudit, CoverageSnapshot, TestGap,
    )
    from app.db.models import Execution
    from app.domains.test_execution.models import ExecutionCase
    from sqlalchemy import delete as sa_delete

    async with session_ctx() as session:
        for model in (ExecutionCase, Execution, CaseBinding, TestGap,
                      CoverageSnapshot, ReviewAudit, AITask, RequirementAsset, Requirement):
            await session.execute(sa_delete(model))
        await session.commit()


def _auth(user: dict) -> dict:
    return {'Authorization': f'Bearer {user["token"]}'}


async def _create_req(client, user, project_id, branch_id,
                      content='订单支持 3 天无理由退款，退款原路返回') -> int:
    resp = await client.post('/api/req', json={
        'project_id': project_id, 'branch_id': branch_id,
        'title': '订单退款', 'content': content, 'source_type': 'text',
    }, headers=_auth(user))
    body = resp.json()
    assert body['code'] == 200, body
    return body['data']['id']


async def _seed_stories(client, user, req_id, confirmed: bool = True) -> None:
    status = 'confirmed' if confirmed else 'generated'
    items = [
        {'title': '申请退款', 'description': '用户申请退款', 'status': status,
         'content': json.dumps(
             {'acceptance_criteria': ['3 天无理由'],
              'confirmations': {'product': True, 'testing': True}}, ensure_ascii=False)},
        {'title': '退款到账', 'description': '退款原路返回', 'status': status,
         'content': json.dumps(
             {'acceptance_criteria': ['原路返回'],
              'confirmations': {'product': True, 'testing': True}}, ensure_ascii=False)},
    ]
    await crud_requirements.upsert_assets(req_id, 'story', items, created_by=user['id'])


async def _seed_case(client, user, req_id, bound_uid: str | None = None) -> None:
    await crud_requirements.upsert_assets(req_id, 'case', [
        {'title': '退款校验-金额', 'status': 'confirmed',
         'content': json.dumps(
             {'preconditions': '已登录', 'steps': ['申请退款'], 'expected': '退款成功'},
             ensure_ascii=False)},
    ], created_by=user['id'])
    if bound_uid:
        cases = await crud_requirements.get_assets(req_id, 'case')
        await crud_requirements.create_binding(cases[0]['id'], bound_uid, 0, 0)


async def _analyze(client, user, req_id) -> dict:
    resp = await client.post(f'/api/req/{req_id}/coverage/analyze', json={},
                             headers=_auth(user))
    body = resp.json()
    assert body['code'] == 200, body
    return body['data']


# ══════════════════════════════════════════════════════════
# 1. 覆盖率契约 + 自动化覆盖率基于绑定数
# ══════════════════════════════════════════════════════════


async def test_coverage_contract_and_automation_from_bindings(client, ctx):
    """7 层覆盖率字段齐全；automation 覆盖率 = 绑定用例数 / 总用例数。"""
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_stories(client, ctx['member'], req_id)
    await _seed_case(client, ctx['member'], req_id, bound_uid=None)

    data = await _analyze(client, ctx['member'], req_id)
    cov = data['coverage']
    for k in ('requirement_coverage', 'story_coverage', 'test_point_coverage',
              'scenario_coverage', 'case_coverage', 'automation_coverage', 'risk_coverage'):
        assert k in cov, f'缺少覆盖率字段 {k}'
    assert cov['requirement_coverage'] == 0      # 无分析资产
    assert cov['story_coverage'] == 100          # 2/2 Story 已确认
    assert cov['case_coverage'] == 100           # 1/1 用例已确认
    assert cov['automation_coverage'] == 0       # 未绑定
    assert any(g['layer'] == 'automation' and g['severity'] == 'P1'
               for g in data['test_gaps'])       # 未绑定 → P1 缺口

    # 绑定后重新分析 → automation 100，automation 缺口消失
    cases = await crud_requirements.get_assets(req_id, 'case')
    await crud_requirements.create_binding(cases[0]['id'], 'test::refund_001', 0, 0)
    data2 = await _analyze(client, ctx['member'], req_id)
    assert data2['coverage']['automation_coverage'] == 100
    assert not any(g['layer'] == 'automation' for g in data2['test_gaps'])


# ══════════════════════════════════════════════════════════
# 2. TestGap P0/P1 分级（CRITICAL 信息缺口 → P0）
# ══════════════════════════════════════════════════════════


async def test_test_gap_p0_critical_information_gap(client, ctx):
    """未确认 CRITICAL 信息缺口 → P0 缺口；确认后消失。"""
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_stories(client, ctx['member'], req_id)
    await crud_requirements.upsert_assets(req_id, 'gap', [
        {'title': 'BUSINESS_RULE_MISSING', 'description': '退款时限未定义',
         'content': json.dumps({'severity': 'CRITICAL', 'question': '退款需在多少天内完成？'},
                               ensure_ascii=False),
         'gate_status': 'CRITICAL', 'status': 'pending'},
    ], created_by=ctx['member']['id'])

    data = await _analyze(client, ctx['member'], req_id)
    assert any(g['severity'] == 'P0' and g['layer'] == 'information_gap'
               for g in data['test_gaps'])

    # 确认缺口后重新分析 → P0 消失
    gaps = await crud_requirements.get_assets(req_id, 'gap')
    resp = await client.put(f"/api/req/{req_id}/assets/{gaps[0]['id']}",
                            json={'status': 'confirmed'}, headers=_auth(ctx['member']))
    assert resp.json()['code'] == 200, resp.text
    data2 = await _analyze(client, ctx['member'], req_id)
    assert not any(g['layer'] == 'information_gap' for g in data2['test_gaps'])


# ══════════════════════════════════════════════════════════
# 3. AI 补测全链：TestPoint → Scenario → Case 挂载 + 缺口关闭
# ══════════════════════════════════════════════════════════


def _supplement_transport() -> MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        data = {
            'test_points': [{'title': '退款-金额边界', 'category': 'Boundary',
                             'description': '校验边界金额'}],
            'scenarios': [{'title': '金额边界-异常', 'test_point_index': 0,
                           'coverage_dim': '异常', 'description': '超界金额'}],
            'cases': [{'title': '金额边界-拒绝', 'preconditions': '已登录',
                       'steps': ['输入超界金额'], 'expected': '拒绝入账',
                       'scenario_index': 0}],
            'score': 90, 'score_reason': '补充完整',
        }
        return httpx.Response(200, json={
            'choices': [{'message': {'content': json.dumps(data, ensure_ascii=False)}}],
        })
    return MockTransport(handler)


async def test_supplement_full_chain_mounts_and_closes_gap(client, ctx, monkeypatch):
    """AI 补测生成 TestPoint→Scenario→Case 挂载到需求，缺口关闭。"""
    real_llm = llm_client.LLMClient
    monkeypatch.setattr(
        req_api.llm_client, 'LLMClient',
        lambda *a, **k: real_llm(
            {'provider': 'deepseek', 'api_base': 'http://fake',
             'text_model': 'fake-model', 'vision_model': '', 'api_key': 'k'},
            transport=_supplement_transport()))

    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_stories(client, ctx['member'], req_id)

    data = await _analyze(client, ctx['member'], req_id)
    assert data['test_gaps'], '应产生缺口供补测'
    gap = data['test_gaps'][0]

    resp = await client.post(f'/api/req/{req_id}/test-gaps/{gap["id"]}/generate', json={},
                             headers=_auth(ctx['member']))
    body = resp.json()
    assert body['code'] == 200, body
    assert body['data']['gap']['status'] == 'closed'     # 缺口关闭
    assert len(body['data']['added']) == 1               # 补充 1 条用例

    tps = await crud_requirements.get_assets(req_id, 'test_point')
    scs = await crud_requirements.get_assets(req_id, 'scenario')
    cases = await crud_requirements.get_assets(req_id, 'case')
    assert len(tps) == 1
    assert len(scs) == 1
    assert len(cases) == 1
    assert scs[0]['parent_id'] == tps[0]['id']          # 场景挂测试点
    assert cases[0]['parent_id'] == scs[0]['id']        # 用例挂场景
    assert cases[0]['story_id']  # 用例关联 Story


# ══════════════════════════════════════════════════════════
# 4. 执行历史反哺：失败 Execution → P0 缺口
# ══════════════════════════════════════════════════════════


async def test_execution_feedback_creates_p0_gap(client, ctx):
    """最近失败执行（ExecutionCase.status=failed）→ 绑定用例 → P0 缺口。"""
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await _seed_stories(client, ctx['member'], req_id)
    await _seed_case(client, ctx['member'], req_id, bound_uid='test::fail_001')

    from datetime import datetime, timedelta
    from app.db.database import session_ctx
    from app.db.models import Execution
    from app.domains.test_execution.models import ExecutionCase

    async with session_ctx() as session:
        session.add(Execution(
            execution_id='E000001', task_id=1, project_id=ctx['project_id'],
            branch_id=ctx['branch_id'], task_name='需求执行', status='finished',
            total_count=1, success_count=0, fail_count=1,
            start_time=datetime.utcnow() - timedelta(minutes=1),
        ))
        session.add(ExecutionCase(
            execution_id='E000001', uid='test::fail_001', branch_id=ctx['branch_id'],
            case_name='退款校验', status='failed',
        ))
        await session.commit()

    data = await _analyze(client, ctx['member'], req_id)
    assert any(g['severity'] == 'P0' and g['layer'] == 'case'
               and g['source_ref'].startswith('exec:') for g in data['test_gaps'])
