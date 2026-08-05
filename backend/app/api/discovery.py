"""Test discovery API endpoints."""
from __future__ import annotations
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query
from app.models.schemas import DiscoverResponse, TestCaseInfo, TestClassInfo, TestModuleInfo, TestHistoryItem
from app.config import PROJECTS_SOURCE_DIR
from app.services import discoverer
from app.services.executor import set_discovery_cache
from app.db import crud
from app.api.common import ok

router = APIRouter(prefix='/api/tests', tags=['discovery'])


def _build_discovery_response(items: list[dict]) -> DiscoverResponse:
    """Build a tree-structured DiscoverResponse from flat test case dicts."""
    modules: dict[str, dict[str, list[dict]]] = {}
    for c in items:
        mod_name = c.get('module', '')
        cls_name = c.get('className', '')
        if mod_name not in modules:
            modules[mod_name] = {}
        if cls_name not in modules[mod_name]:
            modules[mod_name][cls_name] = []
        modules[mod_name][cls_name].append(c)

    module_list: list[TestModuleInfo] = []
    total = 0
    for mod_name in sorted(modules.keys()):
        classes: list[TestClassInfo] = []
        mod_total = 0
        for cls_name in sorted(modules[mod_name].keys()):
            items_list = modules[mod_name][cls_name]
            cls_total = len(items_list)
            mod_total += cls_total
            total += cls_total
            case_infos = [
                TestCaseInfo(
                    uid=c['uid'],
                    name=c.get('name', ''),
                    methodName=c.get('methodName', ''),
                    className=c.get('className', ''),
                    module=c.get('module', ''),
                    fullName=c.get('fullName', ''),
                    description=c.get('description', ''),
                    tags=c.get('tags', []),
                    filePath=c.get('filePath', ''),
                    testType=c.get('testType', 'api'),
                    isNew=c.get('isNew', False),
                    status=c.get('status', 'unknown'),
                )
                for c in items_list
            ]
            classes.append(TestClassInfo(
                name=cls_name,
                items=case_infos,
                total=cls_total,
            ))
        module_list.append(TestModuleInfo(
            module=mod_name,
            classes=classes,
            total=mod_total,
        ))
    return DiscoverResponse(modules=module_list, total=total)


@router.get('/count')
async def get_tests_count(project_id: int = Query(default=None), version: int = Query(default=0)):
    """Return how many test cases are stored in DB."""
    branch_id = 0
    if project_id:
        branch_id = await crud.resolve_branch_id(project_id, version)
        count = await crud.get_project_case_count(project_id, branch_id=branch_id)
    else:
        count = await crud.get_discovery_count()
    return ok({'count': count})


@router.get('')
async def get_tests(project_id: int = Query(default=None), version: int = Query(default=0)):
    """Return test cases from database cache only; no auto-collection."""
    target_project_id = project_id
    if not target_project_id:
        active_project = await crud.get_active_project()
        if active_project:
            target_project_id = active_project['id']
    
    branch_id = await crud.resolve_branch_id(target_project_id or 0, version)
    items, _ = await crud.load_discovery_cache(project_id=target_project_id or 0, branch_id=branch_id)
    
    uids = [item['uid'] for item in items]
    if uids:
        latest_status = await crud.get_latest_status_for_uids(uids)
        for item in items:
            if item['uid'] in latest_status:
                item['status'] = latest_status[item['uid']]['status']
    
    data = _build_discovery_response(items)
    return ok(data.model_dump())


@router.post('/refresh')
async def refresh_tests(project_id: int = Query(default=None), version: int = Query(default=0)):
    """Run pytest collection, persist to DB, then return results."""
    target_project_id = project_id
    if not target_project_id:
        active_project = await crud.get_active_project()
        if active_project:
            target_project_id = active_project['id']
    
    branch_id = await crud.resolve_branch_id(target_project_id or 0, version)
    
    # Determine discovery path from project's source directory
    discovery_path = str(PROJECTS_SOURCE_DIR / f'project_{target_project_id}') if target_project_id else None
    data = await discoverer.discover_tests_at_path(discovery_path) if discovery_path else await discoverer.discover_tests()
    flat_items = []
    for mod in data.modules:
        for cls in mod.classes:
            for item in cls.items:
                flat_items.append(item.model_dump())
    new_uids = await crud.replace_discovery_cache(flat_items, project_id=target_project_id or 0, branch_id=branch_id)
    
    if new_uids:
        for mod in data.modules:
            for cls in mod.classes:
                for item in cls.items:
                    if item.uid in new_uids:
                        item.isNew = True
    
    set_discovery_cache(data)
    return ok(data.model_dump())


@router.get('/history')
async def get_test_history_list(uids: str = Query(default='', description='Comma-separated uids'), limit: int = Query(default=5, ge=1, le=50)):
    """Get recent execution history for test cases. Supports ?uids=uid1,uid2 or returns all."""
    if uids:
        uid_list = [u.strip() for u in uids.split(',') if u.strip()]
        items = await crud.get_test_history_for_uids(uid_list, limit=limit)
    else:
        items = {}
    result: dict[str, list[dict]] = {}
    for uid, history in items.items():
        result[uid] = [TestHistoryItem(**item).model_dump() for item in history]
    return ok(result)


@router.post('/history')
async def get_test_history_batch(body: dict = Body(...)):
    """Get recent execution history for multiple test cases in batch.
    Accepts JSON body: {uids: string[]} with optional limit.
    """
    uids = body.get('uids', [])
    limit = body.get('limit', 5)
    items = await crud.get_test_history_for_uids(uids, limit=limit)
    result: dict[str, list[dict]] = {}
    for uid, history in items.items():
        result[uid] = [TestHistoryItem(**item).model_dump() for item in history]
    return ok(result)


@router.get('/{uid}/history')
async def get_test_history(uid: str, limit: int = 5):
    """Get recent execution history for a test case."""
    items = await crud.get_test_history(uid, limit=limit)
    data = [TestHistoryItem(**item).model_dump() for item in items]
    return ok(data)


@router.get('/{uid}')
async def get_test_detail(uid: str, project_id: int = Query(default=None)):
    """Return single test case detail by uid."""
    info = await discoverer.get_test_by_uid(uid, project_id=project_id or 0)
    if info is None:
        raise HTTPException(status_code=404, detail='未找到测试用例')
    return ok(info)
