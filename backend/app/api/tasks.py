"""Task CRUD API endpoints."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from app.db import crud
from app.api.common import ok

router = APIRouter(prefix='/api/tasks', tags=['tasks'])


@router.get('')
async def list_tasks(limit: int = 20, project_id: int = Query(default=None), version: int = Query(default=0)):
    """List test tasks."""
    branch_id = await crud.resolve_branch_id(project_id, version)
    tasks = await crud.get_all_tasks(limit=limit, project_id=project_id, branch_id=branch_id)
    return ok({'items': tasks, 'total': len(tasks)})


@router.post('')
async def create_task(req: dict):
    """Create a task with associated test cases."""
    uids = req.get('uids', [])
    name = req.get('name', '')
    project_id = req.get('project_id', 0)
    version = req.get('version', 0)
    if not uids:
        raise HTTPException(status_code=400, detail='传入的用例id错误')

    branch_id = await crud.resolve_branch_id(project_id, version)
    task_id = await crud.create_task(name=name, uids=uids, project_id=project_id, branch_id=branch_id)
    return ok({'task_id': task_id}, msg='任务创建成功')


@router.get('/{task_id}')
async def get_task(task_id: int):
    """Get task detail including uids."""
    task = await crud.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail='任务不存在')
    return ok(task)


@router.patch('/{task_id}')
async def update_task(task_id: int, req: dict):
    """Update task name."""
    name = req.get('name', '')
    if not name.strip():
        raise HTTPException(status_code=400, detail='任务名称不能为空')
    ok_ = await crud.update_task_name(task_id, name)
    if not ok_:
        raise HTTPException(status_code=404, detail='任务不存在')
    return ok(None)


@router.delete('/{task_id}')
async def delete_task(task_id: int):
    """Delete a task."""
    ok_ = await crud.delete_task(task_id)
    if not ok_:
        raise HTTPException(status_code=404, detail='任务不存在')
    return ok(None, msg='任务已删除')
