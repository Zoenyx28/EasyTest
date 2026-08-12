"""ADR-0016: Workbench API — aggregate endpoint + in-workbench execution."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Request, Query, Body
from pydantic import BaseModel

from app.api.common import ok, fail
from app.api.auth import get_current_user
from app.db import crud, crud_requirements

router = APIRouter(prefix='/api', tags=['工作台'])


# ── Permission helper ──


async def _guard_req(request: Request, req_id: int):
    """Verify requirement exists and user is project member."""
    user = await get_current_user(request)
    from app.db.models import Requirement
    from app.db.database import session_ctx

    async with session_ctx() as session:
        r = await session.get(Requirement, req_id)
        if not r:
            return None, None, 404
        project_id = r.project_id
        is_member = await crud.is_project_member(project_id, user['id'])
        if not is_member:
            return None, None, 403
        return user, {
            'id': r.id, 'project_id': r.project_id, 'branch_id': r.branch_id,
            'title': r.title, 'summary': r.summary,
            'content': getattr(r, 'content', ''),
            'source_type': getattr(r, 'source_type', 'text'),
            'source_meta': getattr(r, 'source_meta', ''),
            'priority': r.priority, 'status': r.status,
            'created_by': r.created_by,
        }, 0


# ── Workbench aggregate ──


@router.get('/requirements/{req_id}/workbench')
async def get_workbench(request: Request, req_id: int):
    """Get all workbench data for a requirement in one call."""
    user, req, err = await _guard_req(request, req_id)
    if user is None:
        return fail(err, '需求不存在或无权访问')

    data = await crud_requirements.get_workbench_data(req_id)
    if data is None:
        return fail(404, '需求不存在')
    return ok(data)


# ── Asset CRUD ──


@router.get('/requirements/{req_id}/assets')
async def list_assets(request: Request, req_id: int, asset_type: str = Query(default='')):
    """List assets for a requirement."""
    user, req, err = await _guard_req(request, req_id)
    if user is None:
        return fail(err, '需求不存在或无权访问')
    assets = await crud_requirements.get_assets(req_id, asset_type)
    return ok(assets)


class AssetUpsertReq(BaseModel):
    asset_type: str
    items: list[dict]


@router.post('/requirements/{req_id}/assets')
async def upsert_assets(request: Request, req_id: int, body: AssetUpsertReq):
    """Replace all assets of a given type (overwrite)."""
    user, req, err = await _guard_req(request, req_id)
    if user is None:
        return fail(err, '需求不存在或无权访问')
    assets = await crud_requirements.upsert_assets(
        req_id, body.asset_type, body.items, created_by=user['id'],
    )
    return ok(assets, msg=f'{body.asset_type} 已更新')


class AssetUpdateReq(BaseModel):
    title: str | None = None
    description: str | None = None
    content: str | None = None
    score: int | None = None
    gate_status: str | None = None
    review_comment: str | None = None
    status: str | None = None
    perspective: str | None = None   # 'product' | 'testing'（双视角确认，#22）


@router.put('/requirements/{req_id}/assets/{asset_id}')
async def update_asset(request: Request, req_id: int, asset_id: int, body: AssetUpdateReq):
    """Update a single asset."""
    user, req, err = await _guard_req(request, req_id)
    if user is None:
        return fail(err, '需求不存在或无权访问')
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return fail(400, '无更新内容')
    if body.perspective is not None and body.perspective not in ('product', 'testing'):
        return fail(400, 'perspective 只能是 product / testing')
    asset = await crud_requirements.update_asset(asset_id, **updates)
    return ok(asset, msg='资产已更新')


# ── Case Binding ──


@router.get('/requirements/{req_id}/bindings')
async def list_bindings(request: Request, req_id: int):
    """List all case bindings for a requirement."""
    user, req, err = await _guard_req(request, req_id)
    if user is None:
        return fail(err, '需求不存在或无权访问')
    assets = await crud_requirements.get_assets(req_id, 'case')
    bindings = []
    for asset in assets:
        bs = await crud_requirements.get_bindings_for_case(asset['id'])
        for b in bs:
            b['case_title'] = asset.get('title', '')
            bindings.append(b)
    return ok(bindings)


@router.post('/requirements/{req_id}/bindings')
async def create_binding(request: Request, req_id: int, body: dict):
    """Bind a generated case to a test case definition."""
    user, req, err = await _guard_req(request, req_id)
    if user is None:
        return fail(err, '需求不存在或无权访问')
    b = await crud_requirements.create_binding(
        generated_case_id=body['generated_case_id'],
        uid=body['uid'],
        project_id=req['project_id'],
        branch_id=req['branch_id'],
    )
    return ok(b, msg='用例已绑定')


@router.delete('/requirements/{req_id}/bindings/{binding_id}')
async def delete_binding(request: Request, req_id: int, binding_id: int):
    """Remove a case binding."""
    user, req, err = await _guard_req(request, req_id)
    if user is None:
        return fail(err, '需求不存在或无权访问')
    await crud_requirements.delete_binding(binding_id)
    return ok(None, msg='绑定已取消')


# ── In-workbench execution ──


class ExecuteReq(BaseModel):
    uids: list[str]
    concurrency: int = 2
    sequential: bool = True


@router.post('/requirements/{req_id}/execute')
async def execute_bound_cases(request: Request, req_id: int, body: ExecuteReq):
    """Execute selected bound test cases within the workbench."""
    user, req, err = await _guard_req(request, req_id)
    if user is None:
        return fail(err, '需求不存在或无权访问')

    if not body.uids:
        return fail(400, '请选择要执行的用例')

    branch_id = await crud.resolve_branch_id(req['project_id'], 0)
    task_id = await crud.create_task(
        name=f'需求#{req_id} 执行 - {req.get("title", "")}',
        uids=body.uids,
        project_id=req['project_id'],
        branch_id=branch_id,
    )

    from app.services.executor import execution_manager
    run_state = await execution_manager.create_run(
        uids=body.uids,
        concurrency=body.concurrency,
        sequential=body.sequential,
        name=f'需求#{req_id} 执行',
    )

    execution_id = run_state.run_id
    from app.db.database import session_ctx
    from app.db.models import Execution

    async with session_ctx() as session:
        exec_rec = Execution(
            execution_id=execution_id,
            task_id=task_id,
            project_id=req['project_id'],
            branch_id=branch_id,
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


# ── AI Task status check ──


@router.get('/requirements/{req_id}/ai-tasks')
async def get_ai_tasks(request: Request, req_id: int, stage: str = Query(default='')):
    """Get AI task status for a requirement."""
    user, req, err = await _guard_req(request, req_id)
    if user is None:
        return fail(err, '需求不存在或无权访问')

    from app.db.database import session_ctx
    from app.db.models import AITask
    from sqlalchemy import select, desc

    async with session_ctx() as session:
        q = select(AITask).where(AITask.requirement_id == req_id)
        if stage:
            q = q.where(AITask.stage == stage)
        q = q.order_by(desc(AITask.updated_at)).limit(10)
        result = await session.execute(q)
        tasks = []
        for t in result.scalars().all():
            tasks.append({
                'id': t.id, 'requirement_id': t.requirement_id, 'stage': t.stage,
                'status': t.status, 'error': t.error,
                'model': t.model, 'prompt_version': t.prompt_version,
                'created_at': t.created_at.isoformat() if t.created_at else '',
                'updated_at': t.updated_at.isoformat() if t.updated_at else '',
            })
        return ok(tasks)
