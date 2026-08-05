"""Execution API endpoints — Task + Execution + ExecutionCase model."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException, Query
from app.services.executor import execution_manager
from app.db import crud
from app.api.common import ok

router = APIRouter(prefix='/api/executions', tags=['executions'])


# ── Collection endpoints ──

@router.get('')
async def list_executions(limit: int = Query(default=20, ge=1, le=100), project_id: int = Query(default=None), version: int = Query(default=0)):
    """List recent test executions."""
    branch_id = await crud.resolve_branch_id(project_id, version)
    data = await crud.get_all_executions(limit=limit, project_id=project_id, branch_id=branch_id)
    return ok({'items': data, 'total': len(data)})


@router.post('')
async def create_execution(req: dict):
    """Create a test execution and start it."""
    task_id = req.get('task_id') or req.get('taskId')
    concurrency = req.get('concurrency', 2)
    sequential = req.get('sequential', False)
    version = req.get('version', 0)

    if not task_id:
        raise HTTPException(status_code=400, detail='task_id 不能为空')

    # 1. Resolve branch_id from task
    task_info = await crud.get_task(int(task_id))
    project_id = (task_info or {}).get('project_id', 0)
    branch_id = await crud.resolve_branch_id(project_id, version)

    # 2. Create Execution + all ExecutionCase (status=waiting) in DB
    execution_id = await crud.create_execution(
        task_id=int(task_id),
        concurrency=concurrency,
        sequential=sequential,
        branch_id=branch_id,
    )

    # 2. Update status to running
    await crud.update_execution_status(execution_id, 'running')

    # 3. Get discovery info for uid->fullName mapping and build uid list
    cases = await crud.get_all_execution_case_uids(execution_id)
    uids = [c['uid'] for c in cases]

    # Update running_count (set to min(concurrency, len(uids)) since pytest-xdist handles parallelism)
    await crud.update_execution_counts(execution_id, running=min(concurrency, len(uids)))

    # 4. Start async execution
    # Create state and start execution directly
    from app.services.executor import RunState
    import time
    state = RunState(
        run_id=execution_id,
        uids=uids,
        started_at=time.time(),
    )
    execution_manager._runs[execution_id] = state
    # Run execute in background using ensure_future
    import asyncio
    asyncio.ensure_future(execution_manager._execute(state, concurrency, req.get('env', 'test'), req.get('smoke_only', False), sequential))

    return ok({
        'execution_id': execution_id,
        'status': 'running',
        'ws_url': f'/ws/run/{execution_id}',
    }, msg='执行已启动')


# ── Nested resources ──

@router.get('/{execution_id}/cases')
async def get_execution_cases(execution_id: str, page: int = Query(default=1, ge=1), size: int = Query(default=50, ge=1, le=200)):
    """Paginated list of execution case statuses."""
    data = await crud.get_execution_cases(execution_id, page=page, size=size)
    return ok(data)


@router.get('/{execution_id}/cases/all')
async def get_all_execution_cases(execution_id: str):
    """Get all execution cases without pagination."""
    data = await crud.get_execution_cases(execution_id, page=1, size=10000)
    return ok(data)


@router.get('/{execution_id}/statistics')
async def get_execution_statistics(execution_id: str):
    """Get execution case statistics grouped by status."""
    data = await crud.get_execution_case_statistics(execution_id)
    return ok(data)


# ── Single resource endpoints ──

@router.get('/{execution_id}')
async def get_execution(execution_id: str):
    """Get execution summary with counts."""
    data = await crud.get_execution(execution_id)
    if data is None:
        raise HTTPException(status_code=404, detail='执行记录不存在')
    return ok(data)


@router.post('/{execution_id}/stop')
async def stop_execution(execution_id: str):
    """Stop a running execution."""
    stopped = await execution_manager.stop_run(execution_id)
    if not stopped:
        # Check if execution exists in DB
        db_exec = await crud.get_execution(execution_id)
        if db_exec is None:
            raise HTTPException(status_code=404, detail='执行记录不存在')
        # Already finished — still ok, just update DB status
        if db_exec.get('status') in ('running', 'pending'):
            await crud.update_execution_status(execution_id, 'stopped')
        return ok(None, msg='已停止')
    await crud.update_execution_status(execution_id, 'stopped')
    return ok(None, msg='已停止')


@router.get('/cases/{case_id}/log')
async def get_case_log(case_id: int):
    """Get execution log for a single test case."""
    data = await crud.get_execution_case_log(case_id)
    if data is None:
        raise HTTPException(status_code=404, detail='执行用例不存在')
    return ok(data)
