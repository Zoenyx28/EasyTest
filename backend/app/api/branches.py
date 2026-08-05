"""Branch (version) management API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db import crud
from app.api.common import ok

router = APIRouter(prefix='/api', tags=['branches'])


class BranchCreateRequest(BaseModel):
    name: str
    source_branch_id: int | None = None


@router.get('/projects/{project_id}/branches')
async def list_branches(project_id: int):
    """List all branches for a project."""
    branches = await crud.list_branches(project_id)
    return ok(branches)


@router.post('/projects/{project_id}/branches')
async def create_branch(project_id: int, data: BranchCreateRequest):
    """Create a new branch. Copy TCDs from source_branch_id if provided."""
    try:
        branch_id = await crud.create_branch(
            project_id=project_id,
            name=data.name,
            source_branch_id=data.source_branch_id,
        )
        return ok({'id': branch_id}, msg='分支创建成功')
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete('/branches/{branch_id}')
async def delete_branch(branch_id: int):
    """Delete a branch and all its scoped data."""
    success = await crud.delete_branch(branch_id)
    if not success:
        raise HTTPException(status_code=404, detail='分支不存在')
    return ok(None, msg='分支删除成功')


@router.post('/branches/{branch_id}/set-default')
async def set_default_branch(branch_id: int):
    """Set a branch as the project default."""
    success = await crud.set_default_branch(branch_id)
    if not success:
        raise HTTPException(status_code=404, detail='分支不存在')
    return ok(None, msg='默认分支设置成功')


@router.get('/projects/{project_id}/branches/default')
async def get_default_branch(project_id: int):
    """Get the default branch for a project."""
    branch = await crud.get_default_branch(project_id)
    return ok(branch)
