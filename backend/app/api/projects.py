"""Project management API endpoints."""
from __future__ import annotations
import asyncio
import logging
import shutil
import sys
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Request
from app.models.schemas import ProjectCreate, ProjectInfo, ProjectSyncResult
from app.config import PROJECTS_DATA_DIR, PROJECTS_SOURCE_DIR, PROJECTS_REPORT_DIR, PROJECTS_VENV_DIR
from app.db import crud
from app.services import discoverer
from app.services.executor import set_discovery_cache, _create_venv
from app.api.discovery import _build_discovery_response
from app.api.common import ok, fail
from app.api.auth import get_current_user

router = APIRouter(prefix='/api/projects', tags=['projects'])

# Path to the default pytest.ini template shipped with the backend
_DEFAULT_PYTEST_INI = Path(__file__).resolve().parent.parent / 'templates' / 'default_pytest.ini'


def _ensure_pytest_config(project_dir: Path) -> None:
    """If the project directory lacks a pytest config file, place the default one."""
    config_files = ['pytest.ini', 'pyproject.toml', 'setup.cfg']
    has_config = any((project_dir / f).exists() for f in config_files)
    if not has_config and _DEFAULT_PYTEST_INI.exists():
        shutil.copy2(str(_DEFAULT_PYTEST_INI), str(project_dir / 'pytest.ini'))


def _contains_cjk(text: str) -> bool:
    """Whether the text contains CJK (Chinese) characters."""
    return any('\u4e00' <= ch <= '\u9fff' for ch in text)


async def _bg_ai_title_update(project_id: int, discovery_path: str) -> None:
    """Background task: re-discover with AI enabled and update Chinese titles.

    Only writes the description when the DB value is empty or contains no
    Chinese characters, so user-edited descriptions are never overwritten.
    """
    try:
        data = await discoverer.discover_tests_at_path(
            discovery_path, project_id=project_id, run_ai=True
        )
        flat_items = []
        for mod in data.modules:
            for cls in mod.classes:
                for item in cls.items:
                    flat_items.append(item.model_dump())

        existing, _ = await crud.load_discovery_cache(project_id=project_id)
        old_desc: dict[str, str] = {c['uid']: (c.get('description') or '') for c in existing}

        updated = 0
        for item in flat_items:
            uid = item['uid']
            new_desc = (item.get('description') or '').strip()
            if not new_desc:
                continue
            cur = old_desc.get(uid, '')
            if cur and _contains_cjk(cur):
                # Already has a Chinese description (possibly user-edited); keep it.
                continue
            await crud.update_test_case(
                uid=uid,
                project_id=project_id,
                branch_id=0,
                description=new_desc,
            )
            updated += 1
        logger.info('background AI title update done: project=%s updated=%s', project_id, updated)
    except Exception:
        logger.exception('background AI title update failed: project=%s', project_id)


async def _bg_after_sync(project_id: int, discovery_path: str) -> None:
    """Background: generate AI Chinese titles first, then rebuild the venv.

    Run serially because rebuilding deletes the venv directory and would
    break a concurrently running pytest collection.
    """
    try:
        await _bg_ai_title_update(project_id, discovery_path)
    finally:
        await _rebuild_venv(project_id)


async def _rebuild_venv(project_id: int) -> None:
    """Rebuild the project's virtualenv asynchronously after sync.

    Deletes the existing venv (if any) and creates a fresh one, installing
    dependencies from requirements.txt. Fails silently — the sync response
    is not affected by venv rebuild failures.
    """
    try:
        venv_dir = PROJECTS_VENV_DIR / f'project_{project_id}'

        # Remove old venv if exists
        if venv_dir.exists():
            shutil.rmtree(venv_dir)

        # Create fresh venv using shared helper
        await _create_venv(venv_dir, project_id)
    except Exception:
        # Venv rebuild failure must not break the sync response
        pass


@router.get('')
async def get_projects(request: Request):
    """List all projects (filtered by current user's membership)."""
    user = await get_current_user(request)
    projects = await crud.get_all_projects(user_id=user['id'])
    for p in projects:
        pid = p['id']
        p['source_path'] = str(PROJECTS_SOURCE_DIR / f'project_{pid}')
        p['report_path'] = str(PROJECTS_REPORT_DIR / f'project_{pid}')
    return ok(projects)


@router.get('/server-directories')
async def list_server_directories():
    """List first-level directories under the server projects base directory.

    These are the directories a user may pick when creating a "server sync"
    project. Managed subdirectories (source / venvs / reports) are excluded,
    as are hidden entries.
    """
    managed = {PROJECTS_SOURCE_DIR.name, PROJECTS_REPORT_DIR.name, PROJECTS_VENV_DIR.name}
    try:
        if not PROJECTS_DATA_DIR.is_dir():
            return ok([])
        dirs = sorted(
            str(entry)
            for entry in PROJECTS_DATA_DIR.iterdir()
            if entry.is_dir() and not entry.name.startswith('.') and entry.name not in managed
        )
    except OSError:
        dirs = []
    return ok(dirs)


@router.get('/active')
async def get_active_project(request: Request):
    """Get the active project for the current user."""
    user = await get_current_user(request)
    project = await crud.get_active_project(user_id=user['id'])
    if project is None:
        return ok(None)
    return ok(project)


@router.get('/{project_id}')
async def get_project(project_id: int):
    """Get project detail by ID."""
    project = await crud.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail='项目不存在')
    return ok(project)


@router.get('/{project_id}/detail')
async def get_project_detail(project_id: int):
    """Get project detail summary with members, recent defects, and recent tasks."""
    project = await crud.get_project(project_id)
    if project is None:
        return fail(404, '项目不存在')

    members = await crud.get_project_members(project_id)

    # Get recent defects (last 5, using the default branch)
    branch = await crud.get_default_branch(project_id)
    branch_id = branch['id'] if branch else 0
    recent_defects = await crud.get_recent_defects(project_id, branch_id, limit=5)

    # Enrich defects with creator_name / assignee_name / recent operation logs
    enriched_defects = []
    for d in recent_defects:
        creator_name = ''
        if d.get('creator_id'):
            user = await crud.get_user_by_id(d['creator_id'])
            if user:
                creator_name = user.get('nickname', '') or user.get('username', '')
        assignee_name = ''
        if d.get('assignee_id'):
            user = await crud.get_user_by_id(d['assignee_id'])
            if user:
                assignee_name = user.get('nickname', '') or user.get('username', '')
        recent_logs = await crud.get_recent_defect_logs(d['id'], limit=3)
        enriched_logs = []
        for log in recent_logs:
            operator_name = ''
            if log.get('operator_id'):
                user = await crud.get_user_by_id(log['operator_id'])
                if user:
                    operator_name = user.get('nickname', '') or user.get('username', '')
            enriched_logs.append({**log, 'operator_name': operator_name})
        enriched_defects.append({
            **d,
            'creator_name': creator_name,
            'assignee_name': assignee_name,
            'recent_logs': enriched_logs,
        })

    recent_tasks = await crud.get_recent_executions(project_id, limit=5)

    # Expose the server-side storage paths (same as the project list endpoint)
    project['source_path'] = str(PROJECTS_SOURCE_DIR / f'project_{project_id}')
    project['report_path'] = str(PROJECTS_REPORT_DIR / f'project_{project_id}')

    return ok({
        'project': project,
        'members': members,
        'recent_defects': enriched_defects,
        'recent_tasks': recent_tasks,
    })


@router.post('')
async def create_project(request: Request, data: ProjectCreate):
    """Create a new project."""
    user = await get_current_user(request)
    if data.source_type == 'server' and not data.server_path:
        raise HTTPException(status_code=400, detail='服务器同步项目必须提供服务器路径')
    if data.source_type not in ('upload', 'server'):
        raise HTTPException(status_code=400, detail='来源类型必须为 upload 或 server')

    project_id = await crud.create_project(
        name=data.name,
        source_type=data.source_type,
        server_path=data.server_path,
        test_path=data.test_path,
        report_output=data.report_output,
        creator_id=user['id'],
    )

    # Auto-create main branch for this project
    await crud.ensure_main_branch(
        project_id=project_id,
        source_path=data.server_path,
        test_path=data.test_path,
    )

    # For server-sync type, copy source immediately
    if data.source_type == 'server':
        project_dir = PROJECTS_SOURCE_DIR / f'project_{project_id}'
        project_dir.mkdir(parents=True, exist_ok=True)
        src_path = Path(data.server_path)
        if not src_path.exists():
            raise HTTPException(status_code=400, detail=f'服务器路径不存在: {data.server_path}')
        if project_dir.exists():
            shutil.rmtree(project_dir)
        shutil.copytree(str(src_path), str(project_dir), dirs_exist_ok=True)

    project = await crud.get_project(project_id)
    return ok(project, msg='项目创建成功')


@router.put('/{project_id}')
async def update_project(project_id: int, data: ProjectCreate):
    """Update project configuration."""
    success = await crud.update_project(
        project_id,
        name=data.name,
        source_type=data.source_type,
        server_path=data.server_path,
        test_path=data.test_path,
        report_output=data.report_output,
    )
    if not success:
        raise HTTPException(status_code=404, detail='项目不存在')
    project = await crud.get_project(project_id)
    return ok(project, msg='项目更新成功')


@router.delete('/{project_id}')
async def delete_project(project_id: int):
    """Delete a project."""
    project = await crud.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail='项目不存在')
    if project.get('is_active'):
        raise HTTPException(status_code=400, detail='不能删除当前活跃项目，请先切换到其他项目')
    success = await crud.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail='项目不存在')
    # Clean up project source directory
    project_dir = PROJECTS_SOURCE_DIR / f'project_{project_id}'
    if project_dir.exists():
        shutil.rmtree(project_dir)
    return ok(None, msg='项目删除成功')


@router.post('/{project_id}/activate')
async def activate_project(project_id: int, request: Request):
    """Set a project as active for the current user."""
    user = await get_current_user(request)
    success = await crud.set_project_active(user_id=user['id'], project_id=project_id)
    if not success:
        raise HTTPException(status_code=404, detail='项目不存在')

    project = await crud.get_project(project_id)

    items, _ = await crud.load_discovery_cache(project_id=project_id)
    if items:
        data = _build_discovery_response(items)
        set_discovery_cache(data)

    return ok(project, msg='项目切换成功')


@router.post('/{project_id}/sync')
async def sync_project(project_id: int):
    """Sync test cases for a project by re-discovering tests."""
    project = await crud.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail='项目不存在')

    source_type = project['source_type']

    # Unified source directory for this project
    project_dir = PROJECTS_SOURCE_DIR / f'project_{project_id}'
    project_dir.mkdir(parents=True, exist_ok=True)

    if source_type == 'server':
        # A directory that only contains files placed automatically by the
        # system (e.g. the default pytest.ini) counts as "not yet synced";
        # otherwise the copy below would be skipped forever once the default
        # pytest config has been added.
        auto_placed = {'pytest.ini'}
        needs_copy = not project_dir.exists() or not any(
            entry for entry in project_dir.iterdir() if entry.name not in auto_placed
        )
        # If project source directory doesn't exist, try to copy from server_path
        if needs_copy:
            server_path = project.get('server_path', '')
            if server_path:
                src_path = Path(server_path)
                if src_path.exists():
                    project_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(str(src_path), str(project_dir), dirs_exist_ok=True)

    # Ensure the project has a pytest config file; place default if missing
    _ensure_pytest_config(project_dir)

    # Ensure the project's virtualenv exists and has dependencies installed.
    # This is needed so that discovery (which uses the venv Python) can resolve
    # project-specific imports (e.g. conftest.py -> fixtures -> requests).
    await _create_venv(PROJECTS_VENV_DIR / f'project_{project_id}', project_id)

    discovery_path = str(project_dir)
    test_path = project.get('test_path', '')
    if test_path:
        discovery_path = str(Path(discovery_path) / test_path)

    # Step 1: discover without AI so English info is available immediately
    data = await discoverer.discover_tests_at_path(
        discovery_path, project_id=project_id, run_ai=False
    )

    flat_items = []
    for mod in data.modules:
        for cls in mod.classes:
            for item in cls.items:
                flat_items.append(item.model_dump())

    added_count, deleted_count = await crud.sync_project_cases(project_id, [item['uid'] for item in flat_items])
    current_uids = [item['uid'] for item in flat_items if item['status'] != 'deleted']
    new_count = sum(1 for item in flat_items if item.get('isNew', False))
    await crud.update_project_case_count(project_id, len(current_uids), new_count)
    # Also populate TestCaseDefinition table so GET /api/tests returns data
    await crud.replace_discovery_cache(flat_items, project_id=project_id)
    set_discovery_cache(data)

    # Step 2: in background, re-discover with AI enabled to generate Chinese
    # titles, then rebuild the virtualenv afterwards.
    asyncio.ensure_future(_bg_after_sync(project_id, discovery_path))

    return ok({
        'project_id': project_id,
        'case_count': len(current_uids),
        'added_count': added_count,
        'deleted_count': deleted_count,
    }, msg='同步成功')


@router.post('/{project_id}/upload')
async def upload_project_zip(project_id: int, file: UploadFile = File(...)):
    """Upload a zip file containing project source code and extract it."""
    project = await crud.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail='项目不存在')

    project_dir = PROJECTS_SOURCE_DIR / f'project_{project_id}'
    project_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded zip to temp file
    zip_path = project_dir / 'upload.zip'
    content = await file.read()
    zip_path.write_bytes(content)

    # Extract zip
    try:
        with zipfile.ZipFile(str(zip_path), 'r') as zf:
            # Check if zip has a single root directory
            members = zf.namelist()
            if members:
                first = members[0]
                # If all files are under a single root dir, strip it
                root_dirs = {m.split('/')[0] for m in members if '/' in m}
                common_root = first.split('/')[0] if '/' in first else ''
                if common_root and len(root_dirs) == 1 and all(m.startswith(common_root + '/') or m == common_root for m in members):
                    # Extract stripping the common root
                    for member in members:
                        parts = member.split('/', 1)
                        if len(parts) == 2 and parts[1]:
                            zf.extract(member, str(project_dir))
                            # Move to correct location
                            src = project_dir / member
                            dst = project_dir / parts[1]
                            if src != dst:
                                dst.parent.mkdir(parents=True, exist_ok=True)
                                if src.is_file():
                                    shutil.move(str(src), str(dst))
                    # Clean up extracted root dir
                    for member in members:
                        parts = member.split('/', 1)
                        if len(parts) == 2:
                            extracted = project_dir / parts[0]
                            if extracted.exists() and extracted.is_dir():
                                shutil.rmtree(str(extracted))
                                break
                else:
                    zf.extractall(str(project_dir))
    except zipfile.BadZipFile:
        zip_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail='上传文件不是有效的ZIP格式')

    # Clean up zip file
    zip_path.unlink(missing_ok=True)

    return ok({'project_id': project_id}, msg='上传成功')


@router.post('/{project_id}/confirm-all-cases')
async def confirm_all_cases(project_id: int):
    """Confirm all new cases for a project."""
    count = await crud.confirm_all_project_cases(project_id)
    new_count = await crud.get_project_new_case_count(project_id)
    total_uids = await crud.get_project_case_uids(project_id)
    total_count = len(total_uids) if total_uids else 0
    await crud.update_project_case_count(project_id, total_count, new_count)
    return ok({'confirmed_count': count}, msg=f'已确认 {count} 个新用例')


@router.post('/{project_id}/cases/{uid}/confirm')
async def confirm_case(project_id: int, uid: str):
    """Confirm a single new case."""
    success = await crud.confirm_project_case(project_id, uid)
    if not success:
        raise HTTPException(status_code=404, detail='用例不存在')
    new_count = await crud.get_project_new_case_count(project_id)
    total_uids = await crud.get_project_case_uids(project_id)
    total_count = len(total_uids) if total_uids else 0
    await crud.update_project_case_count(project_id, total_count, new_count)
    return ok({'uid': uid}, msg='用例确认成功')


@router.get('/{project_id}/cases')
async def get_project_cases_paginated(
    project_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    search: str = Query(default=''),
    test_type: str = Query(default=''),
    status: str = Query(default=''),
    module: str = Query(default=''),
):
    """Return paginated test cases for a project, with server-side filtering."""
    result = await crud.get_cases_by_project_paginated(
        project_id=project_id,
        page=page,
        size=size,
        search=search,
        test_type=test_type,
        status=status,
        module=module,
    )
    return ok(result)


@router.get('/{project_id}/cases/modules')
async def get_project_case_modules(project_id: int):
    """Return module metadata for a project (module tree + counts)."""
    result = await crud.get_case_module_stats(project_id)
    return ok(result)