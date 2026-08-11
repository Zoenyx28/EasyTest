"""PRD V2.0 分层测试设计 API 路由（#20）— 需求分析 / 信息缺口 / 测试点 / 场景 /
各层评审 / 策略 / 覆盖率 / 测试缺口的 CRUD 与查询。

按 (project_id, branch_id) 隔离；仅项目成员可读写（非成员 403）。
智能体动作（生成 / 评审 / 重新生成 / 确认）由 #21 分层智能体服务提供。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request, Query, Body
from pydantic import BaseModel

from app.api.common import ok, fail
from app.api.auth import get_current_user
from app.db import crud
from app.services import llm_client, layered_agent

router = APIRouter(prefix='/api', tags=['需求分层'])


# ── 权限辅助 ──


async def _guard(request: Request, req_id: int) -> tuple[dict | None, int]:
    """校验需求存在且当前用户是项目成员。

    返回 (ctx, err_code)：ctx 为 {'user','req'}；err_code 为 0 表示通过，
    404（需求不存在）/ 403（非成员）。
    """
    user = await get_current_user(request)
    req = await crud.get_requirement(req_id)
    if req is None:
        return None, 404
    if not await crud.is_project_member(req['project_id'], user['id']):
        return None, 403
    return {'user': user, 'req': req}, 0


# ── 请求模型 ──


class AnalysisSave(BaseModel):
    elements: str = ''          # JSON 字符串
    score: int = 0
    score_reason: str = ''


class GapCreate(BaseModel):
    gap_type: str = 'BUSINESS_RULE_MISSING'
    severity: str = 'HIGH'      # CRITICAL/HIGH/MEDIUM/LOW
    description: str = ''
    question: str = ''


class TestPointCreate(BaseModel):
    story_id: int = 0
    parent_id: int = 0
    category: str = 'Functional'
    title: str
    description: str = ''
    sort_order: int = 0


class TestPointUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    status: str | None = None


class ScenarioCreate(BaseModel):
    test_point_id: int
    title: str
    description: str = ''
    coverage_dim: str = ''
    sort_order: int = 0


class ScenarioUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    coverage_dim: str | None = None


# ══════════════════════════════════════════════════════════
# 工作台一屏加载：某需求全部分层资产
# ══════════════════════════════════════════════════════════


@router.get('/requirements/{req_id}/layers')
async def get_requirement_layers(request: Request, req_id: int):
    """一次返回需求的全部分层资产，供测试设计工作台（#22）一屏渲染。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    result = {
        'requirement': ctx['req'],
        'analysis': await crud.get_latest_requirement_analysis(req_id),
        'information_gaps': await crud.list_information_gaps(req_id),
        'test_points': await crud.list_test_points(req_id),
        'test_point_review': await crud.get_latest_test_point_review(req_id),
        'test_scenarios': await crud.list_test_scenarios(req_id),
        'scenario_review': await crud.get_latest_scenario_review(req_id),
        'case_review': await crud.get_latest_case_review(req_id),
        'strategy': await crud.get_latest_test_strategy(req_id),
        'coverage': await crud.get_latest_coverage_snapshot(req_id),
        'test_gaps': await crud.list_test_gaps(req_id),
    }
    return ok(result)


# ══════════════════════════════════════════════════════════
# 需求分析
# ══════════════════════════════════════════════════════════


@router.get('/requirements/{req_id}/analysis')
async def get_analysis(request: Request, req_id: int):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    return ok(await crud.get_latest_requirement_analysis(req_id))


@router.post('/requirements/{req_id}/analysis')
async def save_analysis(request: Request, req_id: int, data: AnalysisSave = Body(...)):
    """保存需求分析（覆盖式，ADR-0015）。#21 智能体生成后写入。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req = ctx['req']
    user = ctx['user']
    row = await crud.save_requirement_analysis(
        req_id, req['project_id'], req['branch_id'],
        data.elements, data.score, data.score_reason, user['id'],
    )
    return ok(row, msg='需求分析已保存')


# ══════════════════════════════════════════════════════════
# 信息缺口
# ══════════════════════════════════════════════════════════


@router.get('/requirements/{req_id}/information-gaps')
async def list_gaps(request: Request, req_id: int):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    return ok(await crud.list_information_gaps(req_id))


@router.post('/requirements/{req_id}/information-gaps')
async def create_gap(request: Request, req_id: int, data: GapCreate = Body(...)):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req = ctx['req']
    row = await crud.create_information_gap(
        req_id, req['project_id'], req['branch_id'],
        data.gap_type, data.severity, data.description, data.question,
    )
    return ok(row, msg='信息缺口已创建')


@router.post('/information-gaps/{gap_id}/confirm')
async def confirm_gap(request: Request, gap_id: int):
    """产品确认缺口。"""
    user = await get_current_user(request)
    row = await crud.update_information_gap_status(gap_id, 'confirmed', user['id'])
    if row is None:
        return fail(404, '缺口不存在')
    return ok(row, msg='缺口已确认')


@router.post('/information-gaps/{gap_id}/ignore')
async def ignore_gap(request: Request, gap_id: int):
    user = await get_current_user(request)
    row = await crud.update_information_gap_status(gap_id, 'ignored', user['id'])
    if row is None:
        return fail(404, '缺口不存在')
    return ok(row, msg='缺口已忽略')


@router.delete('/information-gaps/{gap_id}')
async def delete_gap(request: Request, gap_id: int):
    if not await crud.delete_information_gap(gap_id):
        return fail(404, '缺口不存在')
    return ok(None, msg='缺口已删除')


# ══════════════════════════════════════════════════════════
# 测试点
# ══════════════════════════════════════════════════════════


@router.get('/requirements/{req_id}/test-points')
async def list_test_points(request: Request, req_id: int):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    return ok(await crud.list_test_points(req_id))


@router.post('/requirements/{req_id}/test-points')
async def create_test_point(request: Request, req_id: int, data: TestPointCreate = Body(...)):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    row = await crud.create_test_point(
        req_id, data.story_id, data.parent_id, data.category,
        data.title, data.description, data.sort_order,
    )
    return ok(row, msg='测试点已创建')


@router.put('/test-points/{tp_id}')
async def update_test_point(request: Request, tp_id: int, data: TestPointUpdate = Body(...)):
    fields = {k: v for k, v in data.dict().items() if v is not None}
    row = await crud.update_test_point(tp_id, fields)
    if row is None:
        return fail(404, '测试点不存在')
    return ok(row, msg='测试点已更新')


@router.delete('/test-points/{tp_id}')
async def delete_test_point(request: Request, tp_id: int):
    if not await crud.delete_test_point(tp_id):
        return fail(404, '测试点不存在')
    return ok(None, msg='测试点已删除')


# ══════════════════════════════════════════════════════════
# 测试场景
# ══════════════════════════════════════════════════════════


@router.get('/requirements/{req_id}/test-scenarios')
async def list_test_scenarios(request: Request, req_id: int,
                              test_point_id: int = Query(0, description='按测试点过滤')):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    return ok(await crud.list_test_scenarios(req_id, test_point_id))


@router.post('/requirements/{req_id}/test-scenarios')
async def create_test_scenario(request: Request, req_id: int,
                               data: ScenarioCreate = Body(...)):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    row = await crud.create_test_scenario(
        req_id, data.test_point_id, data.title, data.description,
        data.coverage_dim, data.sort_order,
    )
    return ok(row, msg='测试场景已创建')


@router.put('/test-scenarios/{scenario_id}')
async def update_test_scenario(request: Request, scenario_id: int,
                               data: ScenarioUpdate = Body(...)):
    fields = {k: v for k, v in data.dict().items() if v is not None}
    row = await crud.update_test_scenario(scenario_id, fields)
    if row is None:
        return fail(404, '测试场景不存在')
    return ok(row, msg='测试场景已更新')


@router.delete('/test-scenarios/{scenario_id}')
async def delete_test_scenario(request: Request, scenario_id: int):
    if not await crud.delete_test_scenario(scenario_id):
        return fail(404, '测试场景不存在')
    return ok(None, msg='测试场景已删除')


# ══════════════════════════════════════════════════════════
# 测试缺口
# ══════════════════════════════════════════════════════════


@router.get('/requirements/{req_id}/test-gaps')
async def list_test_gaps(request: Request, req_id: int):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    return ok(await crud.list_test_gaps(req_id))


@router.post('/test-gaps/{gap_id}/status')
async def update_test_gap_status(request: Request, gap_id: int, body: dict = Body(...)):
    status = body.get('status', '')
    if status not in ('open', 'closed'):
        return fail(400, 'status 必须为 open/closed')
    row = await crud.update_test_gap_status(gap_id, status)
    if row is None:
        return fail(404, '测试缺口不存在')
    return ok(row, msg='测试缺口状态已更新')


@router.delete('/test-gaps/{gap_id}')
async def delete_test_gap(request: Request, gap_id: int):
    if not await crud.delete_test_gap(gap_id):
        return fail(404, '测试缺口不存在')
    return ok(None, msg='测试缺口已删除')


# ══════════════════════════════════════════════════════════
# AI Review 审计
# ══════════════════════════════════════════════════════════


@router.get('/requirements/{req_id}/review-audits')
async def list_review_audits(request: Request, req_id: int,
                             artifact_type: str = ''):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    # 审计记录按需求聚合：查询该需求关联的全部评审
    audits = []
    for atype in ('requirement', 'analysis', 'story', 'test_points',
                  'scenarios', 'cases', 'strategy', 'coverage'):
        if artifact_type and atype != artifact_type:
            continue
        rows = await crud.list_review_audits(atype, req_id)
        audits.extend(rows)
    audits.sort(key=lambda a: a.get('created_at', ''), reverse=True)
    return ok(audits)


# ══════════════════════════════════════════════════════════
# 智能体动作（#21）：生成 / 评审 / 重新生成 / 确认
# 每个动作落一条 AITask（PENDING→RUNNING→终态），并在成功时写审计
# ══════════════════════════════════════════════════════════


class ReviewCommentBody(BaseModel):
    review_comment: str = ''


async def _build_llm_client() -> llm_client.LLMClient:
    settings = await crud.get_llm_settings()
    if not settings:
        raise llm_client.LLMConfigError('尚未配置 LLM，请先在「设置」中填写')
    return llm_client.LLMClient(settings)


def _final_status(gate: str, *, generated: bool = False) -> str:
    """AI 任务终态：生成类产物 → REVIEW（待人工确认）；
    评审类 PASS → CONFIRMED，WARNING/BLOCKED → WAITING_HUMAN。"""
    if generated:
        return 'REVIEW'
    return 'CONFIRMED' if gate == 'PASS' else 'WAITING_HUMAN'


async def _run_ai_task(req_id: int, stage: str, user_id: int, action,
                       build_client=None) -> tuple[dict, Any, Any, str]:
    """创建 AI 任务（PENDING→RUNNING）并执行 action(client)。

    返回 (task, result, client, error)：error 为空表示成功；
    LLM 未配置 / 调用失败 / 输出非法时任务置 FAILED 并附错误信息。
    """
    task = await crud.create_ai_task(req_id, stage, user_id)
    await crud.update_ai_task_status(task['id'], 'RUNNING')
    try:
        client = await build_client() if build_client else None
        result = await action(client)
    except (llm_client.LLMConfigError, llm_client.LLMCallError, ValueError) as exc:
        await crud.update_ai_task_status(task['id'], 'FAILED', error=str(exc))
        return task, None, None, str(exc)
    return task, result, client, ''


async def _finish_ai_task(task_id: int, status: str,
                          client: llm_client.LLMClient) -> dict:
    """推进 AI 任务到终态，记录模型/提示词版本，返回最新任务记录。"""
    updated = await crud.update_ai_task_status(
        task_id, status, model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION)
    return updated or {'id': task_id}


def _tp_rows_indexed(test_points: list[dict], stories: list[dict]) -> list[dict]:
    """DB 测试点行 → 智能体输入（附 story_index / parent_index 供 LLM 引用）。"""
    story_id2idx = {s['id']: i for i, s in enumerate(stories)}
    id2idx = {t['id']: i for i, t in enumerate(test_points)}
    return [
        {**t,
         'story_index': story_id2idx.get(t.get('story_id') or 0, 0),
         'parent_index': id2idx.get(t.get('parent_id') or 0, -1)}
        for t in test_points
    ]


def _scenario_rows_indexed(scenarios: list[dict], test_points: list[dict]) -> list[dict]:
    id2idx = {t['id']: i for i, t in enumerate(test_points)}
    return [
        {**s, 'test_point_index': id2idx.get(s.get('test_point_id') or 0, 0)}
        for s in scenarios
    ]


# ── AI 任务列表（前端轮询展示进度）──


@router.get('/requirements/{req_id}/ai-tasks')
async def list_ai_tasks(request: Request, req_id: int):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    return ok(await crud.list_ai_tasks_by_requirement(req_id))


# ── 1. 需求分析（Requirement Analyzer）──


@router.post('/requirements/{req_id}/analysis/analyze')
async def analyze_requirement_agent(request: Request, req_id: int,
                                    data: ReviewCommentBody = Body(...)):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req, user = ctx['req'], ctx['user']
    sources = await crud.list_requirement_sources(req_id)
    comment = (data.review_comment or '').strip()
    task, result, client, error = await _run_ai_task(
        req_id, 'analyze', user['id'],
        lambda c: layered_agent.analyze_requirement(c, req, sources, comment),
        build_client=_build_llm_client,
    )
    if error:
        return fail(400, error)
    await crud.save_requirement_analysis(
        req_id, req['project_id'], req['branch_id'],
        json.dumps(result.get('elements') or {}, ensure_ascii=False),
        result.get('score', 0), result.get('score_reason', ''), user['id'],
    )
    # 信息缺口覆盖式重写
    await crud.delete_information_gaps_by_requirement(req_id)
    for g in result.get('information_gaps') or []:
        await crud.create_information_gap(
            req_id, req['project_id'], req['branch_id'],
            g.get('gap_type', ''), g.get('severity', 'HIGH'),
            g.get('description', ''), g.get('question', ''),
        )
    await crud.create_review_audit(
        artifact_type='analysis', artifact_id=req_id, score=result.get('score', 0),
        dimension_scores=json.dumps(result.get('elements') or {}, ensure_ascii=False),
        information_gaps=json.dumps(result.get('information_gaps') or [], ensure_ascii=False),
        gate_status=result.get('gate_status', ''), model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION, user_id=user['id'],
    )
    task = await _finish_ai_task(task['id'], _final_status(
        result.get('gate_status', ''), generated=True), client)
    return ok({**result, 'task': task}, msg='需求分析完成')


# ── 2. Story 评审（7 维，Story Reviewer）──


@router.post('/requirements/{req_id}/stories/review')
async def review_stories_agent(request: Request, req_id: int,
                               data: ReviewCommentBody = Body(...)):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req, user = ctx['req'], ctx['user']
    sources = await crud.list_requirement_sources(req_id)
    stories = await crud.list_requirement_stories(req_id)
    if not stories:
        return fail(400, '请先完成 Story 拆解')
    comment = (data.review_comment or '').strip()
    task, result, client, error = await _run_ai_task(
        req_id, 'review_stories', user['id'],
        lambda c: layered_agent.review_stories(c, req, sources, stories, comment),
        build_client=_build_llm_client,
    )
    if error:
        return fail(400, error)
    # 每条 Story 落 7 维评分 / 单条 gate
    for r in result.get('reviews') or []:
        idx = int(r.get('story_index') or 0)
        if 0 <= idx < len(stories):
            await crud.update_story(stories[idx]['id'], {
                'score': r.get('score', 0),
                'dimension_scores': json.dumps(
                    r.get('dimension_scores') or {}, ensure_ascii=False),
                'gate_status': r.get('gate_status', ''),
            })
    # 存在未确认的 CRITICAL 缺口 → 强制 BLOCKED
    gaps = await crud.list_information_gaps(req_id)
    if any(g.get('severity') == 'CRITICAL' and g.get('status') == 'pending' for g in gaps):
        gate = 'BLOCKED'
    else:
        gate = result.get('gate_status', 'PASS')
    await crud.create_review_audit(
        artifact_type='story', artifact_id=req_id, score=result.get('score', 0),
        dimension_scores=json.dumps(result.get('reviews') or [], ensure_ascii=False),
        suggestions=json.dumps(
            [s for r in result.get('reviews') or [] for s in r.get('suggestions') or []],
            ensure_ascii=False),
        gate_status=gate, model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION, user_id=user['id'],
    )
    task = await _finish_ai_task(task['id'], _final_status(gate), client)
    return ok({**result, 'gate_status': gate, 'task': task}, msg='Story 评审完成')


# ── 3. 测试点生成（TestPoint Designer，覆盖式）──


@router.post('/requirements/{req_id}/test-points/generate')
async def generate_test_points_agent(request: Request, req_id: int,
                                     data: ReviewCommentBody = Body(...)):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req, user = ctx['req'], ctx['user']
    stories = await crud.list_requirement_stories(req_id)
    if not stories:
        return fail(400, '请先完成 Story 拆解')
    comment = (data.review_comment or '').strip()
    task, result, client, error = await _run_ai_task(
        req_id, 'test_points', user['id'],
        lambda c: layered_agent.generate_test_points(c, req, stories, comment),
        build_client=_build_llm_client,
    )
    if error:
        return fail(400, error)
    # 覆盖式：清空旧测试点（含场景/评审）后按 tree 重建
    await crud.delete_test_points_by_requirement(req_id)
    id_map: dict[int, int] = {}
    tps = result.get('test_points') or []
    for i, t in enumerate(tps):
        sidx = int(t.get('story_index', 0))
        pidx = int(t.get('parent_index', -1))
        parent_id = id_map.get(pidx, 0)
        row = await crud.create_test_point(
            req_id,
            stories[sidx]['id'] if 0 <= sidx < len(stories) else 0,
            parent_id, t.get('category', 'Functional'),
            t.get('title', ''), t.get('description', ''), i,
        )
        id_map[i] = row['id']
    await crud.create_review_audit(
        artifact_type='test_points', artifact_id=req_id, score=result.get('score', 0),
        dimension_scores=json.dumps(tps, ensure_ascii=False),
        gate_status=result.get('gate_status', ''), model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION, user_id=user['id'],
    )
    task = await _finish_ai_task(task['id'], _final_status(
        result.get('gate_status', ''), generated=True), client)
    saved = await crud.list_test_points(req_id)
    return ok({'test_points': saved, 'score': result.get('score', 0),
               'score_reason': result.get('score_reason', ''),
               'gate_status': result.get('gate_status', ''), 'task': task},
              msg='测试点生成完成')


# ── 4. 测试点评审（11 维，TestPoint Reviewer）──


@router.post('/requirements/{req_id}/test-points/review')
async def review_test_points_agent(request: Request, req_id: int,
                                   data: ReviewCommentBody = Body(...)):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req, user = ctx['req'], ctx['user']
    stories = await crud.list_requirement_stories(req_id)
    tps = await crud.list_test_points(req_id)
    if not tps:
        return fail(400, '请先生成测试点')
    comment = (data.review_comment or '').strip()
    indexed = _tp_rows_indexed(tps, stories)
    task, result, client, error = await _run_ai_task(
        req_id, 'review_test_points', user['id'],
        lambda c: layered_agent.review_test_points(c, req, stories, indexed, comment),
        build_client=_build_llm_client,
    )
    if error:
        return fail(400, error)
    await crud.save_test_point_review(
        req_id, result.get('score', 0),
        json.dumps(result.get('dimension_scores') or {}, ensure_ascii=False),
        json.dumps(result.get('coverage') or {}, ensure_ascii=False),
        json.dumps(result.get('issues') or [], ensure_ascii=False),
        json.dumps(result.get('suggestions') or [], ensure_ascii=False),
        result.get('gate_status', ''), comment, user['id'],
    )
    await crud.create_review_audit(
        artifact_type='test_points', artifact_id=req_id, score=result.get('score', 0),
        dimension_scores=json.dumps(result.get('dimension_scores') or {}, ensure_ascii=False),
        issues=json.dumps(result.get('issues') or [], ensure_ascii=False),
        suggestions=json.dumps(result.get('suggestions') or [], ensure_ascii=False),
        gate_status=result.get('gate_status', ''), model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION, user_id=user['id'],
    )
    gate = result.get('gate_status', 'PASS')
    task = await _finish_ai_task(task['id'], _final_status(gate), client)
    return ok({**result, 'task': task}, msg='测试点评审完成')


# ── 5. 测试场景生成（Scenario Designer，覆盖式）──


@router.post('/requirements/{req_id}/test-scenarios/generate')
async def generate_scenarios_agent(request: Request, req_id: int,
                                   data: ReviewCommentBody = Body(...)):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req, user = ctx['req'], ctx['user']
    tps = await crud.list_test_points(req_id)
    if not tps:
        return fail(400, '请先生成测试点')
    comment = (data.review_comment or '').strip()
    indexed = _tp_rows_indexed(tps, [])
    task, result, client, error = await _run_ai_task(
        req_id, 'scenarios', user['id'],
        lambda c: layered_agent.generate_scenarios(c, req, indexed, comment),
        build_client=_build_llm_client,
    )
    if error:
        return fail(400, error)
    # 覆盖式重建场景
    await crud.delete_test_scenarios_by_requirement(req_id)
    scenarios = result.get('scenarios') or []
    for i, s in enumerate(scenarios):
        tpidx = int(s.get('test_point_index') or 0)
        tp_id = tps[tpidx]['id'] if 0 <= tpidx < len(tps) else 0
        await crud.create_test_scenario(
            req_id, tp_id, s.get('title', ''), s.get('description', ''),
            s.get('coverage_dim', ''), i,
        )
    await crud.create_review_audit(
        artifact_type='scenarios', artifact_id=req_id, score=result.get('score', 0),
        dimension_scores=json.dumps(scenarios, ensure_ascii=False),
        gate_status=result.get('gate_status', ''), model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION, user_id=user['id'],
    )
    task = await _finish_ai_task(task['id'], _final_status(
        result.get('gate_status', ''), generated=True), client)
    saved = await crud.list_test_scenarios(req_id)
    return ok({'scenarios': saved, 'score': result.get('score', 0),
               'score_reason': result.get('score_reason', ''),
               'gate_status': result.get('gate_status', ''), 'task': task},
              msg='测试场景生成完成')


# ── 6. 场景评审（Scenario Reviewer）──


@router.post('/requirements/{req_id}/test-scenarios/review')
async def review_scenarios_agent(request: Request, req_id: int,
                                 data: ReviewCommentBody = Body(...)):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req, user = ctx['req'], ctx['user']
    tps = await crud.list_test_points(req_id)
    scenarios = await crud.list_test_scenarios(req_id)
    if not scenarios:
        return fail(400, '请先生成测试场景')
    comment = (data.review_comment or '').strip()
    indexed = _scenario_rows_indexed(scenarios, tps)
    task, result, client, error = await _run_ai_task(
        req_id, 'review_scenarios', user['id'],
        lambda c: layered_agent.review_scenarios(
            c, req, _tp_rows_indexed(tps, []), indexed, comment),
        build_client=_build_llm_client,
    )
    if error:
        return fail(400, error)
    await crud.save_scenario_review(
        req_id, result.get('score', 0),
        json.dumps(result.get('coverage') or {}, ensure_ascii=False),
        json.dumps(result.get('issues') or [], ensure_ascii=False),
        json.dumps(result.get('suggestions') or [], ensure_ascii=False),
        result.get('gate_status', ''), comment, user['id'],
    )
    await crud.create_review_audit(
        artifact_type='scenarios', artifact_id=req_id, score=result.get('score', 0),
        dimension_scores=json.dumps(result.get('coverage') or {}, ensure_ascii=False),
        issues=json.dumps(result.get('issues') or [], ensure_ascii=False),
        suggestions=json.dumps(result.get('suggestions') or [], ensure_ascii=False),
        gate_status=result.get('gate_status', ''), model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION, user_id=user['id'],
    )
    gate = result.get('gate_status', 'PASS')
    task = await _finish_ai_task(task['id'], _final_status(gate), client)
    return ok({**result, 'task': task}, msg='场景评审完成')


# ── 7. 用例评审（9 维，TestCase Reviewer）──


@router.post('/requirements/{req_id}/cases/review')
async def review_cases_agent(request: Request, req_id: int,
                             data: ReviewCommentBody = Body(...)):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req, user = ctx['req'], ctx['user']
    stories = await crud.list_requirement_stories(req_id)
    tps = await crud.list_test_points(req_id)
    scenarios = await crud.list_test_scenarios(req_id)
    cases = await crud.list_requirement_cases(req_id)
    if not cases:
        return fail(400, '请先生成用例')
    comment = (data.review_comment or '').strip()
    task, result, client, error = await _run_ai_task(
        req_id, 'cases', user['id'],
        lambda c: layered_agent.review_cases(
            c, req, stories, _tp_rows_indexed(tps, stories),
            _scenario_rows_indexed(scenarios, tps), cases, comment),
        build_client=_build_llm_client,
    )
    if error:
        return fail(400, error)
    await crud.save_case_review(
        req_id, result.get('score', 0),
        json.dumps(result.get('checks') or {}, ensure_ascii=False),
        json.dumps(result.get('issues') or [], ensure_ascii=False),
        json.dumps(result.get('suggestions') or [], ensure_ascii=False),
        result.get('gate_status', ''), comment, user['id'],
    )
    await crud.create_review_audit(
        artifact_type='cases', artifact_id=req_id, score=result.get('score', 0),
        dimension_scores=json.dumps(result.get('checks') or {}, ensure_ascii=False),
        issues=json.dumps(result.get('issues') or [], ensure_ascii=False),
        suggestions=json.dumps(result.get('suggestions') or [], ensure_ascii=False),
        gate_status=result.get('gate_status', ''), model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION, user_id=user['id'],
    )
    gate = result.get('gate_status', 'PASS')
    task = await _finish_ai_task(task['id'], _final_status(gate), client)
    return ok({**result, 'task': task}, msg='用例评审完成')


# ── 8. 自动化策略推荐（Strategy Advisor）──


@router.post('/requirements/{req_id}/strategy/recommend')
async def recommend_strategy_agent(request: Request, req_id: int):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req, user = ctx['req'], ctx['user']
    cases = await crud.list_requirement_cases(req_id)
    if not cases:
        return fail(400, '请先生成用例')
    task, result, client, error = await _run_ai_task(
        req_id, 'strategy', user['id'],
        lambda c: layered_agent.recommend_strategy(c, req, cases),
        build_client=_build_llm_client,
    )
    if error:
        return fail(400, error)
    await crud.save_test_strategy(
        req_id, result.get('automation_ratio', 0),
        json.dumps(result.get('result') or {}, ensure_ascii=False), user['id'],
    )
    await crud.create_review_audit(
        artifact_type='strategy', artifact_id=req_id, score=result.get('automation_ratio', 0),
        dimension_scores=json.dumps(result.get('result') or {}, ensure_ascii=False),
        gate_status='PASS', model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION, user_id=user['id'],
    )
    task = await _finish_ai_task(task['id'], 'CONFIRMED', client)
    return ok({**result, 'task': task}, msg='自动化策略推荐完成')


# ── 9. 覆盖率分析（Coverage Analyzer，覆盖式 TestGap）──


@router.post('/requirements/{req_id}/coverage/analyze')
async def analyze_coverage_agent(request: Request, req_id: int,
                                 data: ReviewCommentBody = Body(...)):
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req, user = ctx['req'], ctx['user']
    comment = (data.review_comment or '').strip()
    stats = {
        'stories': len(await crud.list_requirement_stories(req_id)),
        'test_points': len(await crud.list_test_points(req_id)),
        'test_scenarios': len(await crud.list_test_scenarios(req_id)),
        'cases': len(await crud.list_requirement_cases(req_id)),
    }
    client = None
    task, result, client, error = await _run_ai_task(
        req_id, 'coverage', user['id'],
        lambda c: layered_agent.analyze_coverage(c, req, stats, comment),
        build_client=_build_llm_client,
    )
    if error:
        return fail(400, error)
    cov = result.get('coverage') or {}
    values = {
        'requirement_coverage': int(cov.get('requirement') or 0),
        'story_coverage': int(cov.get('story') or 0),
        'test_point_coverage': int(cov.get('test_point') or 0),
        'scenario_coverage': int(cov.get('scenario') or 0),
        'case_coverage': int(cov.get('case') or 0),
        'automation_coverage': int(cov.get('automation') or 0),
        'risk_coverage': int(cov.get('risk') or 0),
    }
    await crud.save_coverage_snapshot(req_id, values, json.dumps(result, ensure_ascii=False))
    # 测试缺口覆盖式重写
    await crud.delete_test_gaps_by_requirement(req_id)
    for g in result.get('test_gaps') or []:
        await crud.create_test_gap(
            req_id, g.get('layer', ''), g.get('description', ''),
            g.get('severity', 'P1'), g.get('source_ref', ''),
        )
    await crud.create_review_audit(
        artifact_type='coverage', artifact_id=req_id, score=0,
        dimension_scores=json.dumps(cov, ensure_ascii=False),
        information_gaps=json.dumps(result.get('test_gaps') or [], ensure_ascii=False),
        suggestions=json.dumps(result.get('suggestions') or [], ensure_ascii=False),
        gate_status='', model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION, user_id=user['id'],
    )
    task = await _finish_ai_task(task['id'], 'CONFIRMED', client)
    return ok({**result, 'task': task}, msg='覆盖率分析完成')


# ── 10. AI 补测（TestGap → 补充用例，覆盖率闭环）──


@router.post('/test-gaps/{gap_id}/generate')
async def generate_supplement_cases_agent(request: Request, gap_id: int,
                                          data: ReviewCommentBody = Body(...)):
    gap = await crud.get_test_gap(gap_id)
    if gap is None:
        return fail(404, '测试缺口不存在')
    ctx, err = await _guard(request, gap['requirement_id'])
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req, user = ctx['req'], ctx['user']
    cases = await crud.list_requirement_cases(gap['requirement_id'])
    comment = (data.review_comment or '').strip()
    client = None
    task, result, client, error = await _run_ai_task(
        gap['requirement_id'], 'supplement', user['id'],
        lambda c: layered_agent.generate_supplement_cases(c, req, gap, cases, comment),
        build_client=_build_llm_client,
    )
    if error:
        return fail(400, error)
    added = []
    for c in result.get('cases') or []:
        row = await crud.create_generated_case(
            gap['requirement_id'], 0, {**c, 'score': result.get('score', 0),
                                       'score_reason': result.get('score_reason', '')})
        added.append(row)
    await crud.create_review_audit(
        artifact_type='cases', artifact_id=gap['requirement_id'],
        score=result.get('score', 0),
        dimension_scores=json.dumps(result.get('cases') or [], ensure_ascii=False),
        gate_status='PASS', model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION, user_id=user['id'],
    )
    task = await _finish_ai_task(task['id'], 'CONFIRMED', client)
    return ok({'cases': added, 'score': result.get('score', 0),
               'score_reason': result.get('score_reason', ''), 'task': task},
              msg='补充用例已生成')
