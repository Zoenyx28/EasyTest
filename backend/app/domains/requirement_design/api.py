"""Requirement Design API — requirements CRUD, workbench, AI agent triggers."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, Form, Body, Query
from pydantic import BaseModel

from app.api.common import ok, fail
from app.api.auth import get_current_user
from app.config import PROJECTS_DATA_DIR
from app.domains.requirement_design import crud as req_crud
from app.services import lark_cli, llm_client, layered_agent, requirement_agent
from app.services.file_signer import build_signed_url, verify_signature

router = APIRouter(prefix='/api/req', tags=['需求设计'])


# ── Request models ──


class RequirementCreateReq(BaseModel):
    project_id: int
    branch_id: int
    title: str
    content: str = ''
    source_type: str = 'text'
    source_meta: str = ''
    priority: str = 'P2'


class RequirementUpdateReq(BaseModel):
    title: str | None = None
    content: str | None = None
    priority: str | None = None
    status: str | None = None
    source_type: str | None = None
    source_meta: str | None = None


class AssetUpsertReq(BaseModel):
    asset_type: str
    items: list[dict]


class AssetUpdateReq(BaseModel):
    title: str | None = None
    description: str | None = None
    content: str | None = None
    score: int | None = None
    gate_status: str | None = None
    review_comment: str | None = None
    status: str | None = None


class ExecuteReq(BaseModel):
    uids: list[str]
    concurrency: int = 2
    sequential: bool = True


# ── Permission helper ──


async def _guard(request: Request, req_id: int) -> tuple[dict | None, int]:
    """Ensure requirement exists and current user is a project member."""
    user = await get_current_user(request)
    req = await req_crud.get_requirement(req_id)
    if req is None:
        return None, 404
    from app.db import crud
    if not await crud.is_project_member(req['project_id'], user['id']):
        return None, 403
    return {'user': user, 'req': req}, 0


# ── Requirement CRUD ──


@router.get('')
async def list_requirements(
    request: Request,
    project_id: int = Query(...),
    branch_id: int = Query(...),
    status: str = Query(default=''),
    search: str = Query(default=''),
    limit: int = Query(default=100),
):
    """List requirements for a project+branch."""
    user = await get_current_user(request)
    items = await req_crud.list_requirements(
        project_id=project_id, branch_id=branch_id,
        status=status, search=search, limit=limit,
    )
    return ok({'items': items, 'total': len(items)})


@router.post('')
async def create_requirement(request: Request, body: RequirementCreateReq):
    """Create a new requirement. Source info embedded directly."""
    user = await get_current_user(request)
    req = await req_crud.create_requirement(
        project_id=body.project_id,
        branch_id=body.branch_id,
        title=body.title,
        content=body.content,
        source_type=body.source_type,
        source_meta=body.source_meta,
        priority=body.priority,
        created_by=user['id'],
    )
    return ok(req, msg='需求创建成功')


@router.get('/{req_id}')
async def get_requirement(request: Request, req_id: int):
    """Get a single requirement by ID."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    return ok(ctx['req'])


@router.put('/{req_id}')
async def update_requirement(request: Request, req_id: int, body: RequirementUpdateReq):
    """Update requirement fields."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return fail(400, '无更新内容')
    req = await req_crud.update_requirement(req_id, **updates)
    return ok(req, msg='需求已更新')


@router.delete('/{req_id}')
async def delete_requirement(request: Request, req_id: int):
    """Delete a requirement and all its assets."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    await req_crud.delete_requirement(req_id)
    return ok(None, msg='需求已删除')


# ── Workbench aggregate endpoint ──


@router.get('/{req_id}/workbench')
async def get_workbench(request: Request, req_id: int):
    """Return all data needed for the workbench in one call.

    Includes: requirement, all assets, AI tasks, defect summary,
    execution summary, coverage, and case bindings.
    """
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    data = await req_crud.get_workbench_data(req_id)
    if data is None:
        return fail(404, '需求不存在')
    return ok(data)


# ── Asset CRUD ──


@router.get('/{req_id}/assets')
async def list_assets(request: Request, req_id: int, asset_type: str = Query(default='')):
    """List assets for a requirement, optionally filtered by type."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    assets = await req_crud.get_assets(req_id, asset_type)
    return ok(assets)


@router.post('/{req_id}/assets')
async def upsert_assets(request: Request, req_id: int, body: AssetUpsertReq):
    """Replace all assets of a given type (overwrite pattern)."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    assets = await req_crud.upsert_assets(
        req_id, body.asset_type, body.items, created_by=ctx['user']['id'],
    )
    return ok(assets, msg=f'{body.asset_type} 已更新')


@router.put('/{req_id}/assets/{asset_id}')
async def update_asset(request: Request, req_id: int, asset_id: int, body: AssetUpdateReq):
    """Update a single asset."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    asset = await req_crud.update_asset(asset_id, **updates)
    return ok(asset, msg='资产已更新')


# ── Case Binding ──


@router.get('/{req_id}/bindings')
async def list_bindings(request: Request, req_id: int):
    """List all case bindings for a requirement (via its case assets)."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    assets = await req_crud.get_assets(req_id, 'case')
    bindings = []
    for asset in assets:
        bs = await req_crud.get_bindings_for_case(asset['id'])
        for b in bs:
            b['case_title'] = asset.get('title', '')
            bindings.append(b)
    return ok(bindings)


@router.post('/{req_id}/bindings')
async def create_binding(request: Request, req_id: int, body: dict):
    """Bind a generated case to a test case definition uid."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    b = await req_crud.create_binding(
        generated_case_id=body['generated_case_id'],
        uid=body['uid'],
        project_id=ctx['req']['project_id'],
        branch_id=ctx['req']['branch_id'],
    )
    return ok(b, msg='用例已绑定')


@router.delete('/{req_id}/bindings/{binding_id}')
async def delete_binding(request: Request, req_id: int, binding_id: int):
    """Remove a case binding."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    await req_crud.delete_binding(binding_id)
    return ok(None, msg='绑定已取消')


# ── AI Agent Trigger ──


@router.post('/{req_id}/analyze')
async def trigger_analysis(request: Request, req_id: int):
    """Trigger AI requirement analysis."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']

    # Create AI task record
    task = await req_crud.create_ai_task(req_id, 'analyze', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    # Run agent in background
    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            sources = [{'text_content': req.get('content', '') or req.get('title', '')}]
            result = await asyncio.to_thread(
                layered_agent.analyze_requirement, client, requirement, sources,
            )
            items = [
                {
                    'title': '需求分析',
                    'description': result.get('score_reason', ''),
                    'content': json.dumps(result, ensure_ascii=False),
                    'score': result.get('score', 0),
                    'gate_status': result.get('gate_status', ''),
                    'status': 'generated',
                },
            ]
            await req_crud.upsert_assets(req_id, 'analysis', items, created_by=user_id)
            # Add information gaps as separate gap assets
            gaps = result.get('information_gaps', [])
            if gaps:
                gap_items = []
                for g in gaps:
                    gap_items.append({
                        'title': g.get('gap_type', ''),
                        'description': g.get('description', ''),
                        'content': json.dumps(g, ensure_ascii=False),
                        'gate_status': g.get('severity', 'HIGH'),
                        'status': 'pending',
                    })
                await req_crud.upsert_assets(req_id, 'gap', gap_items, created_by=user_id)

            await req_crud.update_ai_task(task['id'], status='REVIEW')
        except Exception as exc:
            await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))

    asyncio.create_task(run())
    return ok({'task_id': task['id'], 'status': 'RUNNING'}, msg='分析已启动')


@router.post('/{req_id}/stories/generate')
async def trigger_stories(request: Request, req_id: int):
    """Trigger AI Story generation."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']

    task = await req_crud.create_ai_task(req_id, 'stories', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            sources = [{'text_content': req.get('content', '') or req.get('title', '')}]
            # Get latest review for context
            tasks = await req_crud.get_ai_tasks(req_id, 'analyze')
            latest_review = tasks[0] if tasks else None
            result = await asyncio.to_thread(
                requirement_agent.split_stories, client, requirement, sources, latest_review,
            )
            items = []
            stories = result.get('stories', [])
            for i, s in enumerate(stories):
                # Build content with acceptance criteria + score details
                content = {
                    'acceptance_criteria': s.get('acceptance_criteria', []),
                    'dimension_scores': {},
                    'dependencies': s.get('dependencies', []),
                }
                items.append({
                    'title': s.get('title', ''),
                    'description': s.get('description', ''),
                    'content': json.dumps(content, ensure_ascii=False),
                    'score': result.get('score', 0) if i == 0 else 0,
                    'gate_status': '',
                    'review_comment': result.get('score_reason', '') if i == 0 else '',
                    'sort_order': i,
                    'status': 'generated',
                })
            await req_crud.upsert_assets(req_id, 'story', items, created_by=user_id)
            await req_crud.update_ai_task(task['id'], status='REVIEW')
        except Exception as exc:
            await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))

    asyncio.create_task(run())
    return ok({'task_id': task['id'], 'status': 'RUNNING'}, msg='Story 生成已启动')


@router.post('/{req_id}/stories/review')
async def trigger_story_review(request: Request, req_id: int):
    """Trigger 7-dimension story review."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']

    # Get existing stories as assets
    stories = await req_crud.get_assets(req_id, asset_type='story')
    if not stories:
        return fail(400, '请先生成 Story')

    task = await req_crud.create_ai_task(req_id, 'story_review', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            sources = [{'text_content': req.get('content', '') or req.get('title', '')}]
            result = await asyncio.to_thread(
                layered_agent.review_stories, client, requirement, sources, stories,
            )
            # Update each story with review results
            reviews = result.get('reviews', [])
            for rv in reviews:
                idx = rv.get('story_index', 0)
                if idx < len(stories):
                    sid = stories[idx]['id']
                    content = json.loads(stories[idx].get('content', '{}') or '{}')
                    content['dimension_scores'] = rv.get('dimension_scores', {})
                    content['issues'] = rv.get('issues', [])
                    content['suggestions'] = rv.get('suggestions', [])
                    await req_crud.update_asset(sid, {
                        'score': rv.get('score', 0),
                        'gate_status': rv.get('gate_status', ''),
                        'content': json.dumps(content, ensure_ascii=False),
                    })
            await req_crud.update_ai_task(task['id'], status='REVIEW')
        except Exception as exc:
            await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))

    asyncio.create_task(run())
    return ok({'task_id': task['id'], 'status': 'RUNNING'}, msg='Story 评审已启动')


# ── Test Points ──


@router.post('/{req_id}/test-points/generate')
async def trigger_test_points(request: Request, req_id: int):
    """Trigger AI test point generation (11 categories, tree structure)."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']

    stories = await req_crud.get_assets(req_id, asset_type='story')
    if not stories:
        return fail(400, '请先生成 Story')

    task = await req_crud.create_ai_task(req_id, 'test_points', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            result = await asyncio.to_thread(
                layered_agent.generate_test_points, client, requirement, stories,
            )
            tps = result.get('test_points') or []
            items = []
            for i, tp in enumerate(tps):
                sidx = int(tp.get('story_index', 0))
                pidx = int(tp.get('parent_index', -1))
                story_id = stories[sidx]['id'] if 0 <= sidx < len(stories) else 0
                parent_id = items[pidx].get('_idx', 0) if 0 <= pidx < len(items) else 0
                content = {
                    'category': tp.get('category', 'Functional'),
                    'story_index': sidx,
                    'parent_index': pidx,
                }
                item = {
                    '_idx': i,
                    'title': tp.get('title', ''),
                    'description': tp.get('description', ''),
                    'content': json.dumps(content, ensure_ascii=False),
                    'score': result.get('score', 0) if i == 0 else 0,
                    'gate_status': '',
                    'parent_id': parent_id,
                    'story_id': story_id,
                    'sort_order': i,
                    'status': 'generated',
                }
                items.append(item)
            # Strip _idx before saving
            for it in items:
                it.pop('_idx', None)
            await req_crud.upsert_assets(req_id, 'test_point', items, created_by=user_id)
            await req_crud.update_ai_task(task['id'], status='REVIEW')
        except Exception as exc:
            await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))

    asyncio.create_task(run())
    return ok({'task_id': task['id'], 'status': 'RUNNING'}, msg='测试点生成已启动')


@router.post('/{req_id}/test-points/review')
async def trigger_test_point_review(request: Request, req_id: int):
    """Trigger 11-dimension test point review."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']

    stories = await req_crud.get_assets(req_id, asset_type='story')
    test_points = await req_crud.get_assets(req_id, asset_type='test_point')
    if not test_points:
        return fail(400, '请先生成测试点')

    task = await req_crud.create_ai_task(req_id, 'test_point_review', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            result = await asyncio.to_thread(
                layered_agent.review_test_points, client, requirement, stories, test_points,
            )
            reviews = result.get('reviews', [])
            for rv in reviews:
                idx = rv.get('test_point_index', 0)
                if idx < len(test_points):
                    tid = test_points[idx]['id']
                    content = json.loads(test_points[idx].get('content', '{}') or '{}')
                    content['dimension_scores'] = rv.get('dimension_scores', {})
                    content['review_score'] = rv.get('score', 0)
                    content['issues'] = rv.get('issues', [])
                    await req_crud.update_asset(tid, {
                        'score': rv.get('score', 0),
                        'gate_status': rv.get('gate_status', ''),
                        'review_comment': rv.get('review_comment', ''),
                        'content': json.dumps(content, ensure_ascii=False),
                    })
            await req_crud.update_ai_task(task['id'], status='REVIEW')
        except Exception as exc:
            await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))

    asyncio.create_task(run())
    return ok({'task_id': task['id'], 'status': 'RUNNING'}, msg='测试点评审已启动')


# ── Scenarios ──


@router.post('/{req_id}/test-scenarios/generate')
async def trigger_scenarios(request: Request, req_id: int):
    """Trigger AI scenario generation."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']

    test_points = await req_crud.get_assets(req_id, asset_type='test_point')
    if not test_points:
        return fail(400, '请先生成测试点')

    task = await req_crud.create_ai_task(req_id, 'scenarios', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            result = await asyncio.to_thread(
                layered_agent.generate_scenarios, client, requirement, test_points,
            )
            scenarios = result.get('scenarios', [])
            items = []
            for i, sc in enumerate(scenarios):
                tpidx = int(sc.get('test_point_index', 0))
                tp_id = test_points[tpidx]['id'] if 0 <= tpidx < len(test_points) else 0
                content = {
                    'coverage_dim': sc.get('coverage_dim', ''),
                    'test_point_index': tpidx,
                    'test_point_id': tp_id,
                }
                items.append({
                    'title': sc.get('title', ''),
                    'description': sc.get('description', ''),
                    'content': json.dumps(content, ensure_ascii=False),
                    'parent_id': tp_id,
                    'sort_order': i,
                    'score': result.get('score', 0) if i == 0 else 0,
                    'status': 'generated',
                })
            await req_crud.upsert_assets(req_id, 'scenario', items, created_by=user_id)
            await req_crud.update_ai_task(task['id'], status='REVIEW')
        except Exception as exc:
            await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))

    asyncio.create_task(run())
    return ok({'task_id': task['id'], 'status': 'RUNNING'}, msg='场景生成已启动')


@router.post('/{req_id}/test-scenarios/review')
async def trigger_scenario_review(request: Request, req_id: int):
    """Trigger scenario review."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']

    test_points = await req_crud.get_assets(req_id, asset_type='test_point')
    scenarios = await req_crud.get_assets(req_id, asset_type='scenario')
    if not scenarios:
        return fail(400, '请先生成场景')

    task = await req_crud.create_ai_task(req_id, 'scenario_review', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            result = await asyncio.to_thread(
                layered_agent.review_scenarios, client, requirement, test_points, scenarios,
            )
            reviews = result.get('reviews', [])
            for rv in reviews:
                idx = rv.get('scenario_index', 0)
                if idx < len(scenarios):
                    sid = scenarios[idx]['id']
                    content = json.loads(scenarios[idx].get('content', '{}') or '{}')
                    content['dimension_scores'] = rv.get('dimension_scores', {})
                    content['review_score'] = rv.get('score', 0)
                    await req_crud.update_asset(sid, {
                        'score': rv.get('score', 0),
                        'gate_status': rv.get('gate_status', ''),
                        'content': json.dumps(content, ensure_ascii=False),
                    })
            await req_crud.update_ai_task(task['id'], status='REVIEW')
        except Exception as exc:
            await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))

    asyncio.create_task(run())
    return ok({'task_id': task['id'], 'status': 'RUNNING'}, msg='场景评审已启动')


# ── Cases ──


@router.post('/{req_id}/cases/generate')
async def trigger_cases(request: Request, req_id: int):
    """Trigger AI test case generation."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']

    stories = await req_crud.get_assets(req_id, asset_type='story')
    if not stories:
        return fail(400, '请先生成 Story')

    task = await req_crud.create_ai_task(req_id, 'cases', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            result = await asyncio.to_thread(
                requirement_agent.generate_cases, client, requirement, stories,
            )
            cases = result.get('cases', [])
            items = []
            for i, c in enumerate(cases):
                sidx = int(c.get('story_index', 0))
                story_id = stories[sidx]['id'] if 0 <= sidx < len(stories) else 0
                content = {
                    'preconditions': c.get('preconditions', ''),
                    'steps': c.get('steps', ''),
                    'expected': c.get('expected', ''),
                    'score_reason': c.get('score_reason', ''),
                    'story_index': sidx,
                }
                items.append({
                    'title': c.get('title', ''),
                    'description': c.get('description', ''),
                    'content': json.dumps(content, ensure_ascii=False),
                    'score': c.get('score', 0),
                    'gate_status': c.get('gate_status', ''),
                    'story_id': story_id,
                    'sort_order': i,
                    'status': 'generated',
                })
            await req_crud.upsert_assets(req_id, 'case', items, created_by=user_id)
            await req_crud.update_ai_task(task['id'], status='REVIEW')
        except Exception as exc:
            await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))

    asyncio.create_task(run())
    return ok({'task_id': task['id'], 'status': 'RUNNING'}, msg='用例生成已启动')


@router.post('/{req_id}/cases/review')
async def trigger_case_review(request: Request, req_id: int):
    """Trigger 9-dimension case review."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']

    stories = await req_crud.get_assets(req_id, asset_type='story')
    cases = await req_crud.get_assets(req_id, asset_type='case')
    if not cases:
        return fail(400, '请先生成用例')

    task = await req_crud.create_ai_task(req_id, 'case_review', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            result = await asyncio.to_thread(
                layered_agent.review_cases, client, requirement, stories, cases,
            )
            reviews = result.get('reviews', [])
            for rv in reviews:
                idx = rv.get('case_index', 0)
                if idx < len(cases):
                    cid = cases[idx]['id']
                    content = json.loads(cases[idx].get('content', '{}') or '{}')
                    content['checks'] = rv.get('checks', {})
                    content['review_score'] = rv.get('score', 0)
                    content['review_comment'] = rv.get('review_comment', '')
                    await req_crud.update_asset(cid, {
                        'score': rv.get('score', 0),
                        'gate_status': rv.get('gate_status', ''),
                        'review_comment': rv.get('review_comment', ''),
                        'content': json.dumps(content, ensure_ascii=False),
                    })
            await req_crud.update_ai_task(task['id'], status='REVIEW')
        except Exception as exc:
            await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))

    asyncio.create_task(run())
    return ok({'task_id': task['id'], 'status': 'RUNNING'}, msg='用例评审已启动')


# ── Execute (in-workbench execution) ──


@router.post('/{req_id}/execute')
async def execute_bound_cases(request: Request, req_id: int, body: ExecuteReq):
    """Execute selected bound test cases within the workbench."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    if not body.uids:
        return fail(400, '请选择要执行的用例')

    user = ctx['user']
    req = ctx['req']

    from app.db import crud
    import uuid

    task_id = await crud.create_task(
        name=f'需求#{req_id} 执行 - {req.get("title", "")}',
        uids=body.uids,
        project_id=req['project_id'],
        branch_id=req['branch_id'],
    )

    from app.services.executor import execution_manager
    run_state = await execution_manager.create_run(
        uids=body.uids,
        concurrency=body.concurrency,
        sequential=body.sequential,
        name=f'需求#{req_id} 执行',
    )

    # Create execution record
    execution_id = run_state.run_id
    from datetime import datetime
    async with app.shared.database.session_ctx() as session:
        from app.domains.test_execution.models import Execution, ExecutionCase
        import json as _json

        exec_rec = Execution(
            execution_id=execution_id,
            task_id=task_id,
            project_id=req['project_id'],
            branch_id=req['branch_id'],
            task_name=f'需求#{req_id} 执行',
            status='running',
            total_count=len(body.uids),
            concurrency=body.concurrency,
            sequential=body.sequential,
            start_time=datetime.utcnow(),
        )
        session.add(exec_rec)
        await session.commit()

    return ok({
        'execution_id': execution_id,
        'task_id': task_id,
        'uids': body.uids,
    }, msg='执行已启动')
