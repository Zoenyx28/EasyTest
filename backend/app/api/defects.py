"""缺陷管理 API 路由 — 缺陷模块、缺陷记录、附件、日志、状态转换。"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, Form, Body
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
    assignee_avatar = ''
    if defect.get('assignee_id'):
        try:
            user = await crud.get_user_by_id(defect['assignee_id'])
            if user:
                assignee_name = user.get('nickname', '') or user.get('username', '')
                assignee_avatar = user.get('avatar_url', '')
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

    duplicate_defect_title = ''
    if defect.get('duplicate_defect_id'):
        try:
            dup = await crud.get_defect(defect['duplicate_defect_id'])
            if dup:
                duplicate_defect_title = dup.get('title', '')
        except Exception:
            pass

    return {
        **defect,
        'module_name': module_name,
        'assignee_name': assignee_name,
        'assignee_avatar': assignee_avatar,
        'creator_name': creator_name,
        'branch_name': branch_name,
        'bug_type_name': _bug_type_name(defect.get('bug_type', '')),
        'resolved_version_name': resolved_version_name,
        'duplicate_defect_title': duplicate_defect_title,
    }


# ══════════════════════════════════════════════
# Module Routes
# ══════════════════════════════════════════════


@router.get('/modules')
async def get_modules(project_id: int, branch_id: int = 0):
    """获取模块树（按版本隔离）"""
    modules = await crud.get_defect_modules(project_id, branch_id)
    tree = _build_module_tree(modules)
    return ok(tree)


@router.post('/modules')
async def create_module(request: Request, project_id: int, branch_id: int = 0, data: DefectModuleCreate = Body(...)):
    """创建模块（按版本隔离）"""
    user = await get_current_user(request)
    module_id = await crud.create_defect_module(project_id, data, branch_id)
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


@router.get('/by-case')
async def list_defects_by_case(project_id: int, case_uid: str):
    """Get defects referencing a given test case."""
    defects = await crud.get_defects_by_case_uid(project_id, case_uid)
    enriched = []
    for d in defects:
        enriched.append(await _enrich_defect(d))
    return ok(enriched)


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

    # Process attachments — move from temp to defect dir and create records
    if data.attachments:
        import shutil
        defect_dir = PROJECTS_DATA_DIR / 'defects' / str(defect_id)
        defect_dir.mkdir(parents=True, exist_ok=True)
        for att in data.attachments:
            src = att.get('filepath', '')
            filename = att.get('filename', '')
            if src and os.path.exists(src):
                dst = str(defect_dir / filename)
                shutil.move(src, dst)
                await crud.create_defect_attachment(
                    defect_id=defect_id,
                    filename=filename,
                    filepath=dst,
                    file_size=att.get('file_size', 0),
                    mime_type=att.get('mime_type', ''),
                    created_by=user['id'],
                )

    # Finalize pasted images inside steps HTML — move temp files to defect dir
    if data.steps:
        final_steps = await _finalize_steps_images(defect_id, data.steps, user['id'])
        if final_steps != data.steps:
            await crud.update_defect(defect_id, DefectUpdate(steps=final_steps))

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


@router.get('/{defect_id}/detail')
async def get_defect_detail(defect_id: int):
    """缺陷完整详情 — 合并 defect + logs + attachments + comments 一次返回"""
    import asyncio

    defect = await crud.get_defect(defect_id)
    if defect is None:
        return fail(404, '缺陷不存在')

    async def _enrich_logs():
        logs = await crud.get_defect_logs(defect_id)
        enriched_logs = []
        for log in logs:
            op_name = ''
            if log['operator_id']:
                try:
                    user = await crud.get_user_by_id(log['operator_id'])
                    if user:
                        op_name = user.get('nickname', '')
                except Exception:
                    pass
            enriched_logs.append({**log, 'operator_name': op_name})
        return enriched_logs

    enriched_defect, logs, attachments, comments = await asyncio.gather(
        _enrich_defect(defect),
        _enrich_logs(),
        crud.get_defect_attachments(defect_id),
        crud.get_defect_comments(defect_id),
    )
    return ok({
        'defect': enriched_defect,
        'logs': logs,
        'attachments': attachments,
        'comments': comments,
    })


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

    # Process new attachments — move from temp to defect dir and create records
    if data.attachments:
        import shutil
        defect_dir = PROJECTS_DATA_DIR / 'defects' / str(defect_id)
        defect_dir.mkdir(parents=True, exist_ok=True)
        for att in data.attachments:
            src = att.get('filepath', '')
            filename = att.get('filename', '')
            if src and os.path.exists(src):
                dst = str(defect_dir / filename)
                shutil.move(src, dst)
                await crud.create_defect_attachment(
                    defect_id=defect_id,
                    filename=filename,
                    filepath=dst,
                    file_size=att.get('file_size', 0),
                    mime_type=att.get('mime_type', ''),
                    created_by=user['id'],
                )

    # Finalize pasted images inside steps HTML — move temp files to defect dir
    if data.steps:
        final_steps = await _finalize_steps_images(defect_id, data.steps, user['id'])
        if final_steps != data.steps:
            await crud.update_defect(defect_id, DefectUpdate(steps=final_steps))

    return ok(None, msg='缺陷更新成功')


@router.delete('/{defect_id}')
async def delete_defect(request: Request, defect_id: int):
    """删除缺陷（含附件、日志、评论）"""
    user = await get_current_user(request)

    success = await crud.delete_defect(defect_id)
    if not success:
        return fail(404, '缺陷不存在')

    # 清理缺陷附件磁盘目录
    import shutil
    defect_dir = PROJECTS_DATA_DIR / 'defects' / str(defect_id)
    if defect_dir.exists():
        shutil.rmtree(defect_dir, ignore_errors=True)

    return ok(None, msg='缺陷删除成功')


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
        if getattr(data, 'duplicate_defect_id', 0):
            kwargs['duplicate_defect_id'] = data.duplicate_defect_id

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


@router.post('/attachments/upload')
async def upload_temp_attachment(request: Request, file: UploadFile = File(...)):
    """上传附件到临时目录，返回文件路径信息。保存缺陷时传入路径即可绑定。"""
    user = await get_current_user(request)

    upload_dir = PROJECTS_DATA_DIR / 'defects' / 'temp'
    upload_dir.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    filename = file.filename or 'unnamed'
    filepath = str(upload_dir / filename)

    # Handle duplicate filenames
    counter = 1
    base, ext = os.path.splitext(filename)
    while os.path.exists(filepath):
        filename = f'{base}_{counter}{ext}'
        filepath = str(upload_dir / filename)
        counter += 1

    with open(filepath, 'wb') as f:
        f.write(content)

    file_size = len(content)
    mime_type = file.content_type or 'application/octet-stream'

    return ok({
        'filename': filename,
        'filepath': filepath,
        'file_size': file_size,
        'mime_type': mime_type,
    })


# ── Helper: finalize pasted images inside steps HTML ──


async def _finalize_steps_images(defect_id: int, steps_html: str, user_id: int) -> str:
    """将复现步骤 HTML 中粘贴的临时图片（/api/defects/attachments/temp/<file>）
    移到缺陷目录，并把 img src 替换为缺陷内嵌图片 URL。返回替换后的 HTML。
    内嵌图片不作为独立附件记录，因此不会出现在附件列表中。"""
    if not steps_html or 'attachments/temp' not in steps_html:
        return steps_html

    import re
    import shutil
    from urllib.parse import quote, unquote

    temp_dir = PROJECTS_DATA_DIR / 'defects' / 'temp'
    defect_dir = PROJECTS_DATA_DIR / 'defects' / str(defect_id)
    defect_dir.mkdir(parents=True, exist_ok=True)

    pattern = re.compile(r'/api/defects/attachments/temp/([^"\'\s<>]+)')
    # encoded filename -> 转正后的目标文件名（同一图片被多次引用时复用）
    finalized: dict[str, str] = {}

    def _repl(m: re.Match) -> str:
        encoded = m.group(1)
        if encoded in finalized:
            return f'/api/defects/{defect_id}/images/{quote(finalized[encoded])}'
        filename = unquote(encoded)
        if not filename or '/' in filename or '\\' in filename:
            return m.group(0)
        src = temp_dir / filename
        if not os.path.exists(src):
            return m.group(0)
        # 目标已存在（同名附件/重复保存）时追加序号，避免覆盖
        dst = defect_dir / filename
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(dst):
            dst = defect_dir / f'{base}_{counter}{ext}'
            counter += 1
        shutil.move(str(src), str(dst))
        final_name = dst.name
        finalized[encoded] = final_name
        return f'/api/defects/{defect_id}/images/{quote(final_name)}'

    result = []
    last = 0
    for m in pattern.finditer(steps_html):
        result.append(steps_html[last:m.start()])
        result.append(_repl(m))
        last = m.end()
    result.append(steps_html[last:])
    return ''.join(result)


@router.get('/attachments/temp/{filename}')
async def download_temp_image(filename: str):
    """临时目录图片访问（富文本编辑器粘贴图片的预览/编辑阶段使用）"""
    from fastapi.responses import FileResponse
    from urllib.parse import unquote

    name = unquote(filename)
    if not name or '/' in name or '\\' in name:
        return fail(400, '非法文件名')
    filepath = PROJECTS_DATA_DIR / 'defects' / 'temp' / name
    if not os.path.exists(filepath):
        return fail(404, '文件不存在')
    return FileResponse(filepath)


@router.get('/{defect_id}/images/{filename}')
async def download_defect_image(defect_id: int, filename: str):
    """缺陷内嵌图片访问（复现步骤中粘贴的图片，不属于附件列表）"""
    from fastapi.responses import FileResponse
    from urllib.parse import unquote

    name = unquote(filename)
    if not name or '/' in name or '\\' in name:
        return fail(400, '非法文件名')
    filepath = PROJECTS_DATA_DIR / 'defects' / str(defect_id) / name
    if not os.path.exists(filepath):
        return fail(404, '文件不存在')
    return FileResponse(filepath)


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


@router.get('/attachments/{attachment_id}/download')
async def download_attachment(attachment_id: int):
    """下载附件"""
    from fastapi.responses import FileResponse
    attachment = await crud.get_defect_attachment(attachment_id)
    if attachment is None:
        return fail(404, '附件不存在')
    filepath = attachment.get('filepath', '')
    if not filepath or not os.path.exists(filepath):
        return fail(404, '文件不存在')
    return FileResponse(
        filepath,
        filename=attachment.get('filename', 'download'),
        media_type=attachment.get('mime_type', 'application/octet-stream'),
    )


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