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
from app.services import llm_client, layered_agent, requirement_agent
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
    perspective: str | None = None   # 'product' | 'testing'（双视角确认，#22）


class ExecuteReq(BaseModel):
    uids: list[str]
    concurrency: int = 2
    sequential: bool = True


class ReviewCommentBody(BaseModel):
    review_comment: str = ''    # 重审评论（#22）


def _assets_confirmed(assets: list[dict]) -> bool:
    """全部资产均已完成双视角确认（status=confirmed）。"""
    return bool(assets) and all(a.get('status') == 'confirmed' for a in assets)


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
    if body.perspective is not None and body.perspective not in ('product', 'testing'):
        return fail(400, 'perspective 只能是 product / testing')
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
async def trigger_analysis(request: Request, req_id: int,
                           data: ReviewCommentBody = Body(default=ReviewCommentBody())):
    """Trigger AI requirement analysis（可携带 review_comment 重新评审）。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']
    comment = (data.review_comment or '').strip()

    # Create AI task record
    task = await req_crud.create_ai_task(req_id, 'analyze', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    # Run agent in background
    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            sources = [{'text_content': req.get('content', '') or req.get('title', '')}]
            result = await layered_agent.analyze_requirement(
                client, requirement, sources, comment,
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
                        'content': json.dumps({**g, 'thread': []}, ensure_ascii=False),
                        'gate_status': g.get('severity', 'HIGH'),
                        'status': 'pending',
                    })
                await req_crud.upsert_assets(req_id, 'gap', gap_items, created_by=user_id)

            await req_crud.update_ai_task(task['id'], status='REVIEW')
        except Exception as exc:
            await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))

    asyncio.create_task(run())
    return ok({'task_id': task['id'], 'status': 'RUNNING'}, msg='分析已启动')


# ── 需求评审闭环（#25）：问题卡片 评论/忽略/确定 + 重新评审 reconcile ──


class GapActionBody(BaseModel):
    comment: str = ''


def _gap_content(gap: dict) -> dict:
    try:
        return json.loads(gap.get('content') or '{}')
    except (json.JSONDecodeError, TypeError):
        return {}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _make_llm():
    try:
        return llm_client.LLMClient()
    except Exception as exc:
        raise ValueError(f'LLM 配置错误：{exc}')


async def _snapshot_content(req_id: int, content: str) -> None:
    """把旧需求文档快照存入 requirements.source_meta.prev_content。"""
    req = await req_crud.get_requirement(req_id)
    if req is None:
        return
    try:
        meta = json.loads(req.get('source_meta') or '{}')
    except (json.JSONDecodeError, TypeError):
        meta = {}
    meta['prev_content'] = content[:40000]
    await req_crud.update_requirement(req_id, source_meta=json.dumps(meta, ensure_ascii=False))


@router.post('/{req_id}/gaps/{gap_id}/comment')
async def gap_comment(request: Request, req_id: int, gap_id: int,
                      data: GapActionBody = Body(...)):
    """问题卡片评论：追加用户评论 → AI 回复 → 存线程。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    comment = (data.comment or '').strip()
    if not comment:
        return fail(400, '评论不能为空')
    gap = await req_crud.get_asset(gap_id)
    if gap is None or gap['asset_type'] != 'gap' or gap['requirement_id'] != req_id:
        return fail(404, '问题卡片不存在')
    content = _gap_content(gap)
    thread = list(content.get('thread') or [])
    thread.append({'role': 'user', 'text': comment, 'ts': _now_iso()})
    try:
        client = _make_llm()
        reply = await layered_agent.respond_to_gap(
            client, {**content, 'thread': thread}, comment, 'comment')
    except ValueError as exc:
        return fail(400, str(exc))
    except Exception as exc:
        return fail(400, f'AI 回复失败：{exc}')
    thread.append({'role': 'ai', 'text': reply.get('reply', ''), 'ts': _now_iso()})
    content['thread'] = thread
    await req_crud.update_asset(gap_id, content=json.dumps(content, ensure_ascii=False))
    return ok({'thread': thread, 'reply': reply.get('reply', '')}, msg='已回复')


@router.post('/{req_id}/gaps/{gap_id}/ignore')
async def gap_ignore(request: Request, req_id: int, gap_id: int):
    """问题卡片忽略：告知 LLM 该问题被忽略 → 追加 AI 回复 → 状态 ignored。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    gap = await req_crud.get_asset(gap_id)
    if gap is None or gap['asset_type'] != 'gap' or gap['requirement_id'] != req_id:
        return fail(404, '问题卡片不存在')
    content = _gap_content(gap)
    thread = list(content.get('thread') or [])
    try:
        client = _make_llm()
        reply = await layered_agent.respond_to_gap(
            client, {**content, 'thread': thread}, '', 'ignore')
    except ValueError as exc:
        return fail(400, str(exc))
    except Exception as exc:
        return fail(400, f'AI 回复失败：{exc}')
    thread.append({'role': 'ai', 'text': reply.get('reply', ''), 'ts': _now_iso()})
    content['thread'] = thread
    await req_crud.update_asset(gap_id, content=json.dumps(content, ensure_ascii=False),
                                status='ignored')
    return ok({'thread': thread, 'reply': reply.get('reply', ''), 'status': 'ignored'},
              msg='已忽略')


@router.post('/{req_id}/gaps/{gap_id}/confirm')
async def gap_confirm(request: Request, req_id: int, gap_id: int):
    """问题卡片确定：状态→confirmed；若涉及文档变更，AI 整篇覆盖 content（先存快照）。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    req = ctx['req']
    gap = await req_crud.get_asset(gap_id)
    if gap is None or gap['asset_type'] != 'gap' or gap['requirement_id'] != req_id:
        return fail(404, '问题卡片不存在')
    content = _gap_content(gap)
    thread = list(content.get('thread') or [])
    try:
        client = _make_llm()
        result = await layered_agent.confirm_gap_update_doc(
            client, {'content': req.get('content') or ''}, {**content, 'thread': thread})
    except ValueError as exc:
        return fail(400, str(exc))
    except Exception as exc:
        return fail(400, f'AI 更新文档失败：{exc}')
    doc_changed = bool(result.get('doc_changed'))
    if doc_changed and result.get('updated_content'):
        await _snapshot_content(req_id, req.get('content') or '')
        await req_crud.update_requirement(req_id, content=result['updated_content'])
    content['resolved_doc_change'] = doc_changed
    content['resolution_note'] = result.get('note', '')
    await req_crud.update_asset(gap_id, content=json.dumps(content, ensure_ascii=False),
                                status='confirmed')
    return ok({'status': 'confirmed', 'doc_changed': doc_changed,
               'note': result.get('note', '')}, msg='已确定')


@router.post('/{req_id}/analysis/re-review')
async def re_review_requirement_agent(request: Request, req_id: int,
                                      data: ReviewCommentBody = Body(default=ReviewCommentBody())):
    """重新评审（reconcile）：核对旧问题状态 + 产出新分析/新问题，不清空旧问题。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    user, req = ctx['user'], ctx['req']
    comment = (data.review_comment or '').strip()
    old_gaps = await req_crud.get_assets(req_id, 'gap')
    old_gap_dicts = [
        {**_gap_content(g), 'id': g['id'], 'status': g.get('status', 'pending')}
        for g in old_gaps
    ]
    try:
        client = _make_llm()
        result = await layered_agent.re_review_requirement(
            client, req, [{'text_content': req.get('content') or req.get('title', '')}],
            old_gap_dicts, comment,
        )
    except ValueError as exc:
        return fail(400, str(exc))
    except Exception as exc:
        return fail(400, f'重新评审失败：{exc}')

    # 应用 reconcile：更新旧问题状态（已确定不动）
    applied = 0
    for r in result.get('reconciled') or []:
        idx = int(r.get('index', 0))
        if not (0 <= idx < len(old_gaps)):
            continue
        gap = old_gaps[idx]
        if gap.get('status') == 'confirmed':
            continue
        new_status = {'fixed': 'fixed', 'not_applicable': 'not_applicable',
                      'keep': None}.get(r.get('new_status'))
        if not new_status:
            continue
        gc = _gap_content(gap)
        gc['resolution_note'] = r.get('note', '')
        await req_crud.update_asset(gap['id'],
                                    content=json.dumps(gc, ensure_ascii=False),
                                    status=new_status)
        applied += 1

    # 追加新问题（去重 by description，用 create_asset 追加不覆盖旧卡片）
    existing_descs = {g.get('description') for g in old_gap_dicts}
    added = 0
    for g in result.get('information_gaps') or []:
        if g.get('description') in existing_descs:
            continue
        await req_crud.create_asset(req_id, 'gap', {
            'title': g.get('gap_type', ''),
            'description': g.get('description', ''),
            'content': json.dumps({**g, 'thread': []}, ensure_ascii=False),
            'gate_status': g.get('severity', 'HIGH'),
            'status': 'pending',
        }, created_by=user['id'])
        added += 1
        existing_descs.add(g.get('description'))

    # 覆盖式更新综合分析
    await req_crud.upsert_assets(req_id, 'analysis', [{
        'title': '需求分析',
        'description': result.get('score_reason', ''),
        'content': json.dumps(result, ensure_ascii=False),
        'score': result.get('score', 0),
        'gate_status': result.get('gate_status', ''),
        'status': 'generated',
    }], created_by=user['id'])

    return ok({'reconciled': result.get('reconciled', []), 'applied': applied,
               'new_gaps': added, 'score': result.get('score', 0),
               'gate_status': result.get('gate_status', '')}, msg='重新评审完成')


@router.post('/{req_id}/stories/generate')
async def trigger_stories(request: Request, req_id: int):
    """Trigger AI Story generation."""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']
    if not (req.get('content') or '').strip():
        return fail(400, '请先完善需求内容（上传/粘贴需求文档）再拆解 Story')

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
            result = await requirement_agent.split_stories(
                client, requirement, sources, latest_review,
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
async def trigger_story_review(request: Request, req_id: int,
                               data: ReviewCommentBody = Body(default=ReviewCommentBody())):
    """Trigger 7-dimension story review（可携带 review_comment 重新评审）。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']
    comment = (data.review_comment or '').strip()

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
            result = await layered_agent.review_stories(
                client, requirement, sources, stories, comment,
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
    if not _assets_confirmed(stories):
        return fail(400, '请先确认全部 Story（产品+测试双视角确认）后再生成测试点')

    task = await req_crud.create_ai_task(req_id, 'test_points', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            result = await layered_agent.generate_test_points(
                client, requirement, stories,
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
async def trigger_test_point_review(request: Request, req_id: int,
                                    data: ReviewCommentBody = Body(default=ReviewCommentBody())):
    """Trigger 11-dimension test point review（可携带 review_comment 重新评审）。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']
    comment = (data.review_comment or '').strip()

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
            result = await layered_agent.review_test_points(
                client, requirement, stories, test_points, comment,
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
    if not _assets_confirmed(test_points):
        return fail(400, '请先确认全部测试点后再生成场景')

    task = await req_crud.create_ai_task(req_id, 'scenarios', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            result = await layered_agent.generate_scenarios(
                client, requirement, test_points,
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
async def trigger_scenario_review(request: Request, req_id: int,
                                  data: ReviewCommentBody = Body(default=ReviewCommentBody())):
    """Trigger scenario review（可携带 review_comment 重新评审）。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']
    comment = (data.review_comment or '').strip()

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
            result = await layered_agent.review_scenarios(
                client, requirement, test_points, scenarios, comment,
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

    scenarios = await req_crud.get_assets(req_id, asset_type='scenario')
    if not _assets_confirmed(scenarios):
        return fail(400, '请先确认全部场景后再生成用例')

    stories = await req_crud.get_assets(req_id, asset_type='story')
    if not stories:
        return fail(400, '请先生成 Story')

    task = await req_crud.create_ai_task(req_id, 'cases', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            result = await requirement_agent.generate_cases(
                client, requirement, stories,
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
async def trigger_case_review(request: Request, req_id: int,
                              data: ReviewCommentBody = Body(default=ReviewCommentBody())):
    """Trigger 9-dimension case review（可携带 review_comment 重新评审）。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')

    import asyncio
    user_id = ctx['user']['id']
    req = ctx['req']
    comment = (data.review_comment or '').strip()

    stories = await req_crud.get_assets(req_id, asset_type='story')
    test_points = await req_crud.get_assets(req_id, asset_type='test_point')
    scenarios = await req_crud.get_assets(req_id, asset_type='scenario')
    cases = await req_crud.get_assets(req_id, asset_type='case')
    if not cases:
        return fail(400, '请先生成用例')

    task = await req_crud.create_ai_task(req_id, 'case_review', created_by=user_id)
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    async def run():
        try:
            client = llm_client.LLMClient()
            requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
            result = await layered_agent.review_cases(
                client, requirement, stories, test_points, scenarios, cases, comment,
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


# ── 覆盖率 / TestGap / AI 补测（#23）──


@router.post('/{req_id}/coverage/analyze')
async def analyze_coverage(request: Request, req_id: int):
    """确定性覆盖率分析（#23）：7 层覆盖率 + TestGap 推导 + 落快照/审计。不调 LLM。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    user, req = ctx['user'], ctx['req']
    from app.db import crud_requirements

    task = await req_crud.create_ai_task(req_id, 'coverage', created_by=user['id'])
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    values = await crud_requirements.compute_coverage(req_id)
    await crud_requirements.save_coverage_snapshot(
        req_id, values, json.dumps(values, ensure_ascii=False))
    gaps = await crud_requirements.derive_test_gaps(req_id, req['project_id'], req['branch_id'])
    await req_crud.create_review_audit(
        artifact_type='coverage', artifact_id=req_id, score=0,
        dimension_scores=json.dumps(values, ensure_ascii=False),
        information_gaps=json.dumps(gaps, ensure_ascii=False),
        gate_status='', model='deterministic', prompt_version='rule-v1',
        user_id=user['id'],
    )
    updated = await req_crud.update_ai_task(task['id'], status='CONFIRMED')
    return ok({'coverage': values, 'test_gaps': gaps, 'task': updated}, msg='覆盖率分析完成')


@router.get('/{req_id}/test-gaps')
async def list_test_gaps(request: Request, req_id: int):
    """列出需求测试缺口（#23）。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    from app.db import crud_requirements
    return ok(await crud_requirements.list_test_gaps(req_id))


@router.post('/{req_id}/test-gaps/{gap_id}/generate')
async def generate_supplement(request: Request, req_id: int, gap_id: int,
                              data: ReviewCommentBody = Body(default=ReviewCommentBody())):
    """AI 补测全链（#23）：TestPoint → Scenario → Case 挂载到需求，缺口关闭。"""
    ctx, err = await _guard(request, req_id)
    if ctx is None:
        return fail(err, '需求不存在或无权访问')
    user, req = ctx['user'], ctx['req']
    from app.db import crud_requirements

    gap = await crud_requirements.get_test_gap(gap_id)
    if gap is None or gap['requirement_id'] != req_id:
        return fail(404, '测试缺口不存在')

    import asyncio
    comment = (data.review_comment or '').strip()
    task = await req_crud.create_ai_task(req_id, 'supplement', created_by=user['id'])
    await req_crud.update_ai_task(task['id'], status='RUNNING')

    try:
        client = llm_client.LLMClient()
    except Exception as exc:
        await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))
        return fail(400, f'LLM 配置错误：{exc}')

    requirement = {'title': req.get('title', ''), 'summary': req.get('content', '')}
    cases = await req_crud.get_assets(req_id, asset_type='case')
    try:
        result = await layered_agent.generate_supplement_cases(
            client, requirement, gap, cases, comment,
        )
    except Exception as exc:
        await req_crud.update_ai_task(task['id'], status='FAILED', error=str(exc))
        return fail(400, f'AI 补测失败：{exc}')

    # 挂载到需求：story → test_point → scenario → case（parent 链）
    stories = await req_crud.get_assets(req_id, asset_type='story')
    confirmed_stories = [s for s in stories if s['status'] == 'confirmed']
    story_id = (confirmed_stories[0] if confirmed_stories else stories[0] if stories else {}).get('id', 0)

    tp_ids: list[int] = []
    tps = result.get('test_points') or []
    for i, tp in enumerate(tps):
        row = await req_crud.create_asset(req_id, 'test_point', {
            'title': tp.get('title', ''),
            'description': tp.get('description', ''),
            'content': json.dumps({'category': tp.get('category', 'Functional'),
                                   'supplement': True}, ensure_ascii=False),
            'story_id': story_id, 'sort_order': 100 + i, 'status': 'generated',
        }, created_by=user['id'])
        tp_ids.append(row['id'])

    sc_ids: list[int] = []
    scs = result.get('scenarios') or []
    for i, sc in enumerate(scs):
        tpidx = int(sc.get('test_point_index', 0))
        pid = tp_ids[tpidx] if 0 <= tpidx < len(tp_ids) else (tp_ids[0] if tp_ids else 0)
        row = await req_crud.create_asset(req_id, 'scenario', {
            'title': sc.get('title', ''),
            'description': sc.get('description', ''),
            'content': json.dumps({'coverage_dim': sc.get('coverage_dim', ''),
                                   'supplement': True}, ensure_ascii=False),
            'parent_id': pid, 'sort_order': 100 + i, 'status': 'generated',
        }, created_by=user['id'])
        sc_ids.append(row['id'])

    added: list[dict] = []
    cs = result.get('cases') or []
    for i, c in enumerate(cs):
        scidx = int(c.get('scenario_index', 0))
        pid = sc_ids[scidx] if 0 <= scidx < len(sc_ids) else (sc_ids[0] if sc_ids else 0)
        content = {
            'preconditions': c.get('preconditions', ''),
            'steps': c.get('steps', []),
            'expected': c.get('expected', ''),
            'supplement': True,
        }
        row = await req_crud.create_asset(req_id, 'case', {
            'title': c.get('title', ''),
            'description': '',
            'content': json.dumps(content, ensure_ascii=False),
            'parent_id': pid, 'story_id': story_id,
            'score': result.get('score', 0), 'sort_order': 100 + i, 'status': 'generated',
        }, created_by=user['id'])
        added.append(row)

    await crud_requirements.close_test_gap(gap_id)
    await req_crud.create_review_audit(
        artifact_type='cases', artifact_id=req_id, score=result.get('score', 0),
        dimension_scores=json.dumps({'test_points': len(tps), 'scenarios': len(scs),
                                     'cases': len(cs)}, ensure_ascii=False),
        gate_status='PASS', model=client.text_model,
        prompt_version=layered_agent.PROMPT_VERSION, user_id=user['id'],
    )
    updated = await req_crud.update_ai_task(task['id'], status='CONFIRMED')
    return ok({'added': added, 'gap': await crud_requirements.get_test_gap(gap_id),
               'score': result.get('score', 0), 'task': updated}, msg='AI 补测已生成')
