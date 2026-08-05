"""缺陷管理 API 路由 — 缺陷模块、缺陷记录、附件、日志、状态转换。"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi import HTTPException

from app.api.common import ok, fail
from app.api.auth import get_current_user
from app.config import PROJECTS_DATA_DIR
from app.db import crud
from app.models.schemas import (
    DefectModuleCreate,
    DefectCreate,
    DefectUpdate,
    DefectTransition,
    DefectCommentCreate,
)

router = APIRouter(prefix='/api/defects', tags=['缺陷管理'])


# ── Helper: build module tree ──


def _build_module_tree(modules: list[dict]) -> list[dict]:
    """Build a nested tree structure from a flat list of modules."""
    tree = []
    children_map: dict[int, list[dict]] = {}
    for m in modules:
        m['children'] = []
        children_map[m['id']] = m['children']

    for m in modules:
        if m['parent_id'] == 0:
            tree.append(m)
        else:
            parent = children_map.get(m['parent_id'])
            if parent is not None:
                parent.append(m)
            else:
                tree.append(m)

    return tree


# ── Helper: get bug_type display name ──

BUG_TYPE_NAMES = {
    'code_error': '代码错误',
    'config_error': '配置错误',
    'ui_error': '界面错误',
    'performance': '性能问题',
    'security': '安全问题',
    'compatibility': '兼容性问题',
    'document_error': '文档错误',
}


def _bug_type_name(bug_type: str) -> str:
    """Get Chinese display name for a bug_type value."""
    return BUG_TYPE_NAMES.get(bug_type, bug_type)


# ── Helper: get defect detail with user/module names ──


async def _enrich_defect(defect: dict) -> dict:
    """Enrich a defect dict with user names, module name, and branch name."""
    module_name = ''
    if defect.get('module_id'):
        try:
            modules = await crud.get_defect_modules(defect['project_id'])
            for m in modules:
                if m['id'] == defect['module_id']:
                    module_name = m['name']
                    break
        except Exception:
            pass

    assignee_name = ''
    if defect.get('assignee_id'):
        try:
            user = await crud.get_user_by_id(defect['assignee_id'])
            if user:
                assignee_name = user.get('nickname', '')
        except Exception:
            pass

    creator_name = ''
    if defect.get('creator_id'):
        try:
            user = await crud.get_user_by_id(defect['creator_id'])
            if user:
                creator_name = user.get('nickname', '')
        except Exception:
            pass

    branch_name = ''
    if defect.get('branch_id'):
        try:
            branches = await crud.list_branches(defect['project_id'])
            for b in branches:
                if b['id'] == defect['branch_id']:
                    branch_name = b['name']
                    break
        except Exception:
            pass

    resolved_version_name = ''
    if defect.get('resolved_version'):
        try:
            branches_for_resolve = await crud.list_branches(defect['project_id'])
            for b in branches_for_resolve:
                if b['id'] == defect['resolved_version']:
                    resolved_version_name = b['name']
                    break
        except Exception:
            pass

    return {
        **defect,
        'module_name': module_name,
        'assignee_name': assignee_name,
        'creator_name': creator_name,
        'branch_name': branch_name,
        'bug_type_name': _bug_type_name(defect.get('bug_type', '')),
        'resolved_version_name': resolved_version_name,
    }


# ══════════════════════════════════════════════
# Module Routes
# ══════════════════════════════════════════════


@router.get('/modules')
async def get_modules(project_id: int):
    """获取项目模块树（树形结构）"""
    modules = await crud.get_defect_modules(project_id)
    tree = _build_module_tree(modules)
    return ok(tree)


@router.post('/modules')
async def create_module(request: Request, project_id: int, data: DefectModuleCreate):
    """创建模块"""
    user = await get_current_user(request)
    # Get project_id from query
    module_id = await crud.create_defect_module(project_id, data)
    return ok({'id': module_id}, msg='模块创建成功')


@router.put('/modules/{module_id}')
async def update_module(module_id: int, data: DefectModuleCreate):
    """更新模块"""
    success = await crud.update_defect_module(module_id, data)
    if not success:
        return fail(404, '模块不存在')
    return ok(None, msg='模块更新成功')


@router.delete('/modules/{module_id}')
async def delete_module(module_id: int):
    """删除模块"""
    success = await crud.delete_defect_module(module_id)
    if not success:
        return fail(404, '模块不存在')
    return ok(None, msg='模块删除成功')


# ══════════════════════════════════════════════
# Defect Routes
# ══════════════════════════════════════════════


@router.get('')
async def list_defects(
    project_id: int,
    branch_id: int,
    status: str = None,
    severity: str = None,
    priority: str = None,
    module_id: int = None,
    assignee_id: int = None,
    creator_id: int = None,
    search: str = None,
    page: int = 1,
    page_size: int = 20,
):
    """Defect list."""
    result = await crud.get_defects(
        project_id=project_id,
        branch_id=branch_id,
        status=status,
        severity=severity,
        priority=priority,
        module_id=module_id,
        assignee_id=assignee_id,
        creator_id=creator_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    # Enrich items with user/module names
    items = []
    for d in result['items']:
        enriched = await _enrich_defect(d)
        items.append(enriched)

    return ok({
        'total': result['total'],
        'items': items,
        'page': result['page'],
        'page_size': result['page_size'],
        'pages': result['pages'],
    })


@router.post('')
async def create_defect(request: Request, data: DefectCreate):
    """创建缺陷"""
    user = await get_current_user(request)
    defect_id = await crud.create_defect(data, user['id'])

    # Log creation
    await crud.create_defect_log(
        defect_id=defect_id,
        field='status',
        old_value='',
        new_value='unconfirmed',
        operator_id=user['id'],
    )

    return ok({'id': defect_id}, msg='缺陷创建成功')


@router.get('/recent')
async def recent_defects(project_id: int, branch_id: int, limit: int = 2):
    """最近缺陷"""
    defects = await crud.get_recent_defects(project_id, branch_id, limit)
    items = [await _enrich_defect(d) for d in defects]
    return ok(items)


@router.get('/my')
async def my_defects(request: Request, project_id: int, branch_id: int):
    """我的缺陷"""
    user = await get_current_user(request)
    defects = await crud.get_my_defects(user['id'], project_id, branch_id)
    items = [await _enrich_defect(d) for d in defects]
    return ok(items)


@router.get('/{defect_id}')
async def get_defect(defect_id: int):
    """缺陷详情"""
    defect = await crud.get_defect(defect_id)
    if defect is None:
        return fail(404, '缺陷不存在')
    enriched = await _enrich_defect(defect)
    return ok(enriched)


@router.put('/{defect_id}')
async def update_defect(request: Request, defect_id: int, data: DefectUpdate):
    """更新缺陷"""
    user = await get_current_user(request)

    # Get original defect for logging
    old_defect = await crud.get_defect(defect_id)
    if old_defect is None:
        return fail(404, '缺陷不存在')

    success = await crud.update_defect(defect_id, data)
    if not success:
        return fail(404, '缺陷不存在')

    # Log field changes
    field_map = {
        'title': 'title',
        'description': 'description',
        'steps': 'steps',
        'module_id': 'module_id',
        'severity': 'severity',
        'priority': 'priority',
        'assignee_id': 'assignee_id',
        'bug_type': 'bug_type',
        'deadline': 'deadline',
    }
    for field, attr in field_map.items():
        new_val = getattr(data, attr, None)
        old_val = old_defect.get(field, '')
        if new_val is not None and str(new_val) != str(old_val):
            await crud.create_defect_log(
                defect_id=defect_id,
                field=field,
                old_value=str(old_val),
                new_value=str(new_val),
                operator_id=user['id'],
            )

    return ok(None, msg='缺陷更新成功')


@router.post('/{defect_id}/transition')
async def transition_defect(request: Request, defect_id: int, data: DefectTransition):
    """状态转换"""
    user = await get_current_user(request)

    try:
        kwargs = {}
        if data.assignee_id:
            kwargs['assignee_id'] = data.assignee_id
        if data.resolution:
            kwargs['resolution'] = data.resolution
        if data.comment:
            kwargs['comment'] = data.comment
        if getattr(data, 'resolved_version', 0):
            kwargs['resolved_version'] = data.resolved_version
        if getattr(data, 'bug_type', ''):
            kwargs['bug_type'] = data.bug_type
        if getattr(data, 'priority', ''):
            kwargs['priority'] = data.priority
        if getattr(data, 'deadline', ''):
            kwargs['deadline'] = data.deadline

        success = await crud.transition_defect(
            defect_id=defect_id,
            action=data.action,
            operator_id=user['id'],
            **kwargs,
        )
        if not success:
            return fail(404, '缺陷不存在')

        defect = await crud.get_defect(defect_id)
        return ok(defect, msg='状态转换成功')
    except ValueError as e:
        return fail(400, str(e))


@router.post('/{defect_id}/copy')
async def copy_defect(request: Request, defect_id: int):
    """复制缺陷"""
    user = await get_current_user(request)

    try:
        new_id = await crud.copy_defect(defect_id, user['id'])
        defect = await crud.get_defect(new_id)
        if defect is None:
            return fail(404, '复制失败')

        # Log creation
        await crud.create_defect_log(
            defect_id=new_id,
            field='status',
            old_value='',
            new_value='unconfirmed',
            operator_id=user['id'],
        )
        return ok({'id': new_id}, msg='缺陷复制成功')
    except ValueError as e:
        return fail(400, str(e))


# ══════════════════════════════════════════════
# Log Routes
# ══════════════════════════════════════════════


@router.get('/{defect_id}/logs')
async def get_logs(defect_id: int):
    """操作日志"""
    defect = await crud.get_defect(defect_id)
    if defect is None:
        return fail(404, '缺陷不存在')

    logs = await crud.get_defect_logs(defect_id)
    # Enrich with operator names
    enriched = []
    for log in logs:
        operator_name = ''
        if log['operator_id']:
            try:
                user = await crud.get_user_by_id(log['operator_id'])
                if user:
                    operator_name = user.get('nickname', '')
            except Exception:
                pass
        enriched.append({
            **log,
            'operator_name': operator_name,
        })
    return ok(enriched)


# ══════════════════════════════════════════════
# Attachment Routes
# ══════════════════════════════════════════════


@router.get('/{defect_id}/attachments')
async def get_attachments(defect_id: int):
    """附件列表"""
    defect = await crud.get_defect(defect_id)
    if defect is None:
        return fail(404, '缺陷不存在')

    attachments = await crud.get_defect_attachments(defect_id)
    return ok(attachments)


@router.post('/{defect_id}/attachments')
async def upload_attachment(request: Request, defect_id: int, file: UploadFile = File(...)):
    """上传附件 (multipart/form-data)"""
    user = await get_current_user(request)

    defect = await crud.get_defect(defect_id)
    if defect is None:
        return fail(404, '缺陷不存在')

    # Create upload directory
    upload_dir = PROJECTS_DATA_DIR / 'defects' / str(defect_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    content = await file.read()
    filename = file.filename or 'unnamed'
    filepath = str(upload_dir / filename)
    with open(filepath, 'wb') as f:
        f.write(content)

    file_size = len(content)
    mime_type = file.content_type or 'application/octet-stream'

    attachment_id = await crud.create_defect_attachment(
        defect_id=defect_id,
        filename=filename,
        filepath=filepath,
        file_size=file_size,
        mime_type=mime_type,
        created_by=user['id'],
    )

    return ok({'id': attachment_id}, msg='附件上传成功')


@router.delete('/attachments/{attachment_id}')
async def delete_attachment(attachment_id: int):
    """删除附件"""
    success = await crud.delete_defect_attachment(attachment_id)
    if not success:
        return fail(404, '附件不存在')
    return ok(None, msg='附件删除成功')


# ── 评论路由 ──

@router.get('/{defect_id}/comments')
async def get_comments(defect_id: int):
    """获取缺陷的所有评论"""
    defect = await crud.get_defect(defect_id)
    if defect is None:
        return fail(404, '缺陷不存在')
    comments = await crud.get_defect_comments(defect_id)
    return ok(comments)


@router.post('/{defect_id}/comments')
async def create_comment(request: Request, defect_id: int, data: DefectCommentCreate):
    """创建缺陷评论"""
    user = await get_current_user(request)
    defect = await crud.get_defect(defect_id)
    if defect is None:
        return fail(404, '缺陷不存在')
    comment_id = await crud.create_defect_comment(
        defect_id=defect_id,
        content=data.content,
        author_id=user['id'],
    )
    return ok({'id': comment_id}, msg='评论创建成功')


@router.put('/comments/{comment_id}')
async def update_comment(request: Request, comment_id: int, data: DefectCommentCreate):
    """更新评论"""
    user = await get_current_user(request)
    # TODO: 检查用户是否是作者或管理员
    success = await crud.update_defect_comment(comment_id, data.content)
    if not success:
        return fail(404, '评论不存在')
    return ok(None, msg='评论更新成功')


@router.delete('/comments/{comment_id}')
async def delete_comment(request: Request, comment_id: int):
    """删除评论"""
    user = await get_current_user(request)
    # TODO: 检查用户是否是作者或管理员
    success = await crud.delete_defect_comment(comment_id)
    if not success:
        return fail(404, '评论不存在')
    return ok(None, msg='评论删除成功')