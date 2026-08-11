"""PRD V2.0 分层测试设计 API 契约测试（#20 AC）。

覆盖：
- 迁移创建 11 张新表 + 现有表扩展列（stories / requirement_reviews / generated_cases）
- 分层资源 CRUD（需求分析 / 信息缺口 / 测试点 / 测试场景 / 测试缺口）
- 项目+分支隔离、非成员 403、需求不存在 404
- 需求删除级联清理全部分层表（review_audits 保留）
- 工作台一屏加载 /layers 聚合接口
"""
import pytest
from sqlalchemy import select

from app.db.database import session_ctx, engine
from app.db.models import (
    Requirement, RequirementAnalysis, InformationGap, TestPoint, TestPointReview,
    TestScenario, ScenarioReview, CaseReview, TestStrategy,
    ReviewAudit, CoverageSnapshot, TestGap,
)
from app.db import crud

LAYER_TABLES = [
    'requirement_analyses', 'information_gaps', 'test_points', 'test_point_reviews',
    'test_scenarios', 'scenario_reviews', 'case_reviews', 'test_strategies',
    'review_audits', 'coverage_snapshots', 'test_gaps',
]


def _auth(user: dict) -> dict:
    return {'Authorization': f'Bearer {user["token"]}'}


async def _create_req(client, user, project_id, branch_id, title='分层需求') -> int:
    resp = await client.post(
        '/api/requirements',
        json={'project_id': project_id, 'branch_id': branch_id, 'title': title},
        headers=_auth(user),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['code'] == 200, body
    return body['data']['id']


async def _count(model, **filters) -> int:
    from sqlalchemy import func
    async with session_ctx() as session:
        stmt = select(func.count(model.id))
        for k, v in filters.items():
            stmt = stmt.where(getattr(model, k) == v)
        result = await session.execute(stmt)
        return result.scalar() or 0


# ══════════════════════════════════════════════════════════
# AC1: 迁移创建 11 张新表 + 现有表扩展列
# ══════════════════════════════════════════════════════════


async def test_layers_tables_and_columns_exist(_init_db):
    """11 张新表均存在；stories/requirement_reviews/generated_cases 有扩展列。"""
    from sqlalchemy import text

    async with engine.connect() as conn:
        tables = {
            row[0] for row in (await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )).fetchall()
        }
        for t in LAYER_TABLES:
            assert t in tables, f'缺少分层表 {t}'

        async def _cols(t: str) -> set[str]:
            rows = (await conn.execute(text(f'PRAGMA table_info({t})'))).fetchall()
            return {r[1] for r in rows}

        assert 'dimension_scores' in await _cols('stories')
        assert 'gate_status' in await _cols('stories')
        assert 'dependencies' in await _cols('stories')
        assert 'gate_status' in await _cols('requirement_reviews')
        assert 'gate_status' in await _cols('generated_cases')


# ══════════════════════════════════════════════════════════
# AC2: 需求分析 CRUD（覆盖式）
# ══════════════════════════════════════════════════════════


async def test_analysis_save_get_and_overwrite(client, ctx):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    elements = '{"business_goal":"退款","rules":["3天免运费"]}'

    resp = await client.post(
        f'/api/requirements/{req_id}/analysis',
        json={'elements': elements, 'score': 88, 'score_reason': '要素完整'},
        headers=_auth(ctx['member']),
    )
    assert resp.json()['code'] == 200
    first_id = resp.json()['data']['id']

    # 覆盖式：再次保存后只剩最新一条（SQLite 可能复用 rowid，仅校验行数与最新值）
    resp = await client.post(
        f'/api/requirements/{req_id}/analysis',
        json={'elements': '{"business_goal":"退款V2"}', 'score': 92, 'score_reason': '更新'},
        headers=_auth(ctx['member']),
    )
    assert resp.json()['code'] == 200
    assert await _count(RequirementAnalysis, requirement_id=req_id) == 1

    resp = await client.get(f'/api/requirements/{req_id}/analysis', headers=_auth(ctx['member']))
    assert resp.json()['code'] == 200
    assert resp.json()['data']['score'] == 92


# ══════════════════════════════════════════════════════════
# AC3: 信息缺口（创建 / 产品确认 / 忽略）
# ══════════════════════════════════════════════════════════


async def test_information_gap_flow(client, ctx):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])

    resp = await client.post(
        f'/api/requirements/{req_id}/information-gaps',
        json={'gap_type': 'BUSINESS_RULE_MISSING', 'severity': 'CRITICAL',
              'description': '退款时限未定义', 'question': '退款需在多少天内完成？'},
        headers=_auth(ctx['member']),
    )
    assert resp.json()['code'] == 200
    gap_id = resp.json()['data']['id']

    resp = await client.post(f'/api/information-gaps/{gap_id}/confirm', headers=_auth(ctx['member']))
    assert resp.json()['code'] == 200
    assert resp.json()['data']['status'] == 'confirmed'
    assert resp.json()['data']['confirmed_by'] == ctx['member']['id']

    # 第二个缺口忽略
    resp = await client.post(
        f'/api/requirements/{req_id}/information-gaps',
        json={'gap_type': 'DATA_RULE_MISSING', 'severity': 'LOW',
              'description': '金额精度未定义', 'question': '金额保留几位小数？'},
        headers=_auth(ctx['member']),
    )
    gap2 = resp.json()['data']['id']
    resp = await client.post(f'/api/information-gaps/{gap2}/ignore', headers=_auth(ctx['member']))
    assert resp.json()['code'] == 200
    assert resp.json()['data']['status'] == 'ignored'

    resp = await client.get(f'/api/requirements/{req_id}/information-gaps', headers=_auth(ctx['member']))
    gaps = resp.json()['data']
    assert len(gaps) == 2


# ══════════════════════════════════════════════════════════
# AC4: 测试点 / 测试场景 CRUD
# ══════════════════════════════════════════════════════════


async def test_test_point_and_scenario_crud(client, ctx):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])

    resp = await client.post(
        f'/api/requirements/{req_id}/test-points',
        json={'story_id': 0, 'category': 'Functional', 'title': '退款资格', 'sort_order': 1},
        headers=_auth(ctx['member']),
    )
    assert resp.json()['code'] == 200
    tp_id = resp.json()['data']['id']

    # 更新测试点
    resp = await client.put(
        f'/api/test-points/{tp_id}',
        json={'status': 'confirmed', 'title': '退款资格（已确认）'},
        headers=_auth(ctx['member']),
    )
    assert resp.json()['code'] == 200
    assert resp.json()['data']['status'] == 'confirmed'

    # 子测试点（树形）
    resp = await client.post(
        f'/api/requirements/{req_id}/test-points',
        json={'parent_id': tp_id, 'category': 'Boundary', 'title': '已退款订单再次申请'},
        headers=_auth(ctx['member']),
    )
    child_id = resp.json()['data']['id']

    # 场景创建 + 按测试点过滤
    for title, dim in [('正常退款', 'normal'), ('退款超时', 'exception')]:
        resp = await client.post(
            f'/api/requirements/{req_id}/test-scenarios',
            json={'test_point_id': tp_id, 'title': title, 'coverage_dim': dim},
            headers=_auth(ctx['member']),
        )
        assert resp.json()['code'] == 200

    resp = await client.get(
        f'/api/requirements/{req_id}/test-scenarios?test_point_id={tp_id}',
        headers=_auth(ctx['member']),
    )
    scenarios = resp.json()['data']
    assert len(scenarios) == 2

    # 删除子测试点级联其场景；删除父测试点
    resp = await client.delete(f'/api/test-points/{child_id}', headers=_auth(ctx['member']))
    assert resp.json()['code'] == 200
    resp = await client.delete(f'/api/test-points/{tp_id}', headers=_auth(ctx['member']))
    assert resp.json()['code'] == 200
    resp = await client.get(f'/api/requirements/{req_id}/test-points', headers=_auth(ctx['member']))
    assert resp.json()['data'] == []


# ══════════════════════════════════════════════════════════
# AC5: 隔离与权限（非成员 403、需求不存在 404、跨项目不可见）
# ══════════════════════════════════════════════════════════


async def test_permisssion_isolation(client, ctx):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])

    # 非成员 403
    resp = await client.get(f'/api/requirements/{req_id}/layers', headers=_auth(ctx['outsider']))
    assert resp.json()['code'] == 403, resp.json()

    # 需求不存在 404
    resp = await client.get('/api/requirements/999999/layers', headers=_auth(ctx['member']))
    assert resp.json()['code'] == 404, resp.json()

    # other 是项目成员，可访问
    resp = await client.get(f'/api/requirements/{req_id}/layers', headers=_auth(ctx['other']))
    assert resp.json()['code'] == 200


# ══════════════════════════════════════════════════════════
# AC6: 工作台一屏加载 /layers
# ══════════════════════════════════════════════════════════


async def test_layers_bundle(client, ctx):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    resp = await client.get(f'/api/requirements/{req_id}/layers', headers=_auth(ctx['member']))
    assert resp.json()['code'] == 200
    data = resp.json()['data']
    for key in ('requirement', 'analysis', 'information_gaps', 'test_points',
                'test_point_review', 'test_scenarios', 'scenario_review',
                'case_review', 'strategy', 'coverage', 'test_gaps'):
        assert key in data, f'/layers 缺少 {key}'
    assert data['requirement']['id'] == req_id


# ══════════════════════════════════════════════════════════
# AC7: 需求删除级联清理全部分层表（review_audits 保留）
# ══════════════════════════════════════════════════════════


async def test_delete_requirement_cascades_layers(client, ctx):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])

    # 直接插入各层数据
    await crud.save_requirement_analysis(req_id, ctx['project_id'], ctx['branch_id'],
                                         '{"goal":"x"}', 90, 'ok', ctx['member']['id'])
    await crud.create_information_gap(req_id, ctx['project_id'], ctx['branch_id'],
                                      'RULE', 'HIGH', 'gap')
    tp = await crud.create_test_point(req_id, 0, 0, 'Functional', '退款资格')
    await crud.create_test_scenario(req_id, tp['id'], '正常退款', '', 'normal')
    await crud.save_test_point_review(req_id, 85, '{}', '{}', '[]', '[]', 'PASS', '', ctx['member']['id'])
    await crud.save_scenario_review(req_id, 80, '{}', '[]', '[]', 'PASS', '', ctx['member']['id'])
    await crud.save_case_review(req_id, 75, '{}', '[]', '[]', 'WARNING', '', ctx['member']['id'])
    await crud.save_test_strategy(req_id, 60, '{"ratio":60}', ctx['member']['id'])
    await crud.save_coverage_snapshot(req_id, {'story_coverage': 100, 'case_coverage': 50})
    await crud.create_test_gap(req_id, 'case', '用例未自动化', 'P0')
    await crud.create_review_audit('requirement', req_id, 88, '', '[]', '[]', '', 'PASS',
                                   'deepseek', 'v1', ctx['member']['id'])

    resp = await client.delete(f'/api/requirements/{req_id}', headers=_auth(ctx['member']))
    assert resp.json()['code'] == 200

    assert await _count(Requirement, id=req_id) == 0
    assert await _count(RequirementAnalysis, requirement_id=req_id) == 0
    assert await _count(InformationGap, requirement_id=req_id) == 0
    assert await _count(TestPoint, requirement_id=req_id) == 0
    assert await _count(TestPointReview, requirement_id=req_id) == 0
    assert await _count(TestScenario, requirement_id=req_id) == 0
    assert await _count(ScenarioReview, requirement_id=req_id) == 0
    assert await _count(CaseReview, requirement_id=req_id) == 0
    assert await _count(TestStrategy, requirement_id=req_id) == 0
    assert await _count(CoverageSnapshot, requirement_id=req_id) == 0
    assert await _count(TestGap, requirement_id=req_id) == 0
    # 审计记录保留
    assert await _count(ReviewAudit, artifact_id=req_id, artifact_type='requirement') == 1


# ══════════════════════════════════════════════════════════
# AC8: Review 审计查询
# ══════════════════════════════════════════════════════════


async def test_review_audits_endpoint(client, ctx):
    req_id = await _create_req(client, ctx['member'], ctx['project_id'], ctx['branch_id'])
    await crud.create_review_audit('requirement', req_id, 88, '', '[]', '[]', '', 'PASS',
                                   'deepseek', 'v1', ctx['member']['id'])
    await crud.create_review_audit('test_points', req_id, 80, '{"s":1}', '[]', '[]', '', 'WARNING',
                                   'deepseek', 'v1', ctx['member']['id'])

    resp = await client.get(f'/api/requirements/{req_id}/review-audits', headers=_auth(ctx['member']))
    assert resp.json()['code'] == 200
    audits = resp.json()['data']
    # 注：SQLite 复用 rowid 时可能带上先前保留的审计（MySQL 不复用），
    # 因此仅断言本测试创建的两种类型均已出现
    assert {'requirement', 'test_points'} <= {a['artifact_type'] for a in audits}
