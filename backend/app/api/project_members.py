"""Project member management API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.common import ok, fail
from app.api.auth import get_current_user
from app.db import crud

router = APIRouter(prefix='/api/projects/{project_id}/members', tags=['project_members'])


@router.get('')
async def list_members(project_id: int, request: Request):
    """获取项目成员列表"""
    user = await get_current_user(request)
    _ = user  # Just ensure authenticated
    members = await crud.get_project_members(project_id)
    return ok(members)


@router.post('')
async def add_member(project_id: int, request: Request, data: dict):
    """添加成员"""
    user = await get_current_user(request)
    _ = user
    user_id = data.get('user_id')
    if not user_id:
        return fail(400, '请提供用户ID')
    success = await crud.add_project_member(project_id, user_id)
    if not success:
        return fail(409, '该用户已是项目成员')
    return ok(None, msg='添加成功')


@router.delete('/{user_id}')
async def remove_member(project_id: int, user_id: int, request: Request):
    """移除成员（不能移除创建人）"""
    current_user = await get_current_user(request)
    _ = current_user

    # Check if user is the creator
    project = await crud.get_project(project_id)
    if project is None:
        return fail(404, '项目不存在')
    if project.get('creator_id') == user_id:
        return fail(400, '不能移除项目创建人')

    # Prevent removing self if you're the creator
    if current_user['id'] == user_id and project.get('creator_id') == user_id:
        return fail(400, '不能移除项目创建人')

    success = await crud.remove_project_member(project_id, user_id)
    if not success:
        return fail(404, '该用户不是项目成员')
    return ok(None, msg='移除成功')


@router.get('/search')
async def search_users(project_id: int, request: Request, q: str = ''):
    """搜索可添加的用户（非成员的用户）"""
    user = await get_current_user(request)
    _ = user

    if not q:
        return ok([])

    # Get all users matching search
    users = await crud.search_users(q)
    # Get current member ids
    members = await crud.get_project_members(project_id)
    member_ids = {m['user_id'] for m in members}

    # Filter out existing members
    available = [u for u in users if u['id'] not in member_ids]
    return ok(available)