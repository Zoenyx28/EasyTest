"""Project note API endpoints — get/upsert Markdown notes per project."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.api.common import ok, fail
from app.api.auth import get_current_user
from app.models.schemas import ProjectNoteUpdate
from app.db import crud

router = APIRouter(prefix='/api/projects', tags=['project_notes'])


@router.get('/{project_id}/note')
async def get_project_note(project_id: int, request: Request):
    """获取项目备注"""
    user = await get_current_user(request)
    note = await crud.get_project_note(project_id)
    if note is None:
        return ok(None)
    # Resolve updated_by_name
    updated_by_name = ''
    if note['updated_by']:
        updater = await crud.get_user_by_id(note['updated_by'])
        if updater:
            updated_by_name = updater.get('nickname', '') or updater.get('username', '')
    return ok({
        'id': note['id'],
        'project_id': note['project_id'],
        'content': note['content'],
        'updated_by': note['updated_by'],
        'updated_by_name': updated_by_name,
        'created_at': note['created_at'],
        'updated_at': note['updated_at'],
    })


@router.put('/{project_id}/note')
async def upsert_project_note(project_id: int, request: Request, data: ProjectNoteUpdate):
    """更新/创建项目备注"""
    user = await get_current_user(request)
    note = await crud.upsert_project_note(project_id, data.content, user['id'])
    # Resolve updated_by_name
    updated_by_name = user.get('nickname', '') or user.get('username', '')
    return ok({
        'id': note['id'],
        'project_id': note['project_id'],
        'content': note['content'],
        'updated_by': note['updated_by'],
        'updated_by_name': updated_by_name,
        'created_at': note['created_at'],
        'updated_at': note['updated_at'],
    }, msg='项目备注保存成功')