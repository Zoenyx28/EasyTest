"""Report API endpoints — database-backed."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from app.db import crud
from app.services import reporter
from app.api.common import ok

router = APIRouter(prefix='/api/reports', tags=['reports'])


@router.get('')
async def list_reports(project_id: int = Query(default=None),
                       page: int = Query(default=1, ge=1),
                       size: int = Query(default=20, ge=1, le=100),
                       version: int = Query(default=0)):
    """Return paginated list of historical report summaries, filtered by project and branch."""
    if project_id:
        branch_id = await crud.resolve_branch_id(project_id, version)
        data = await crud.get_reports_by_project(project_id, page=page, size=size, branch_id=branch_id)
    else:
        data = {'items': [], 'total': 0, 'page': page, 'size': size, 'pages': 0}
    return ok(data)


@router.get('/latest')
async def latest_report():
    """Return the most recent test report data from allure results."""
    data = reporter.get_latest_report()
    if data is None:
        raise HTTPException(status_code=404, detail='暂无报告数据，请先执行测试')
    return ok(data)


@router.get('/history')
async def report_history():
    """Return historical run records (legacy file-based)."""
    data = reporter.get_history()
    return ok(data)


@router.get('/execution/{execution_id}')
async def report_by_execution(execution_id: str):
    """Get report data by execution ID from database."""
    data = await crud.get_report_by_execution(execution_id)
    if data is None:
        data = await reporter.get_report_by_execution(execution_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f'Execution {execution_id} not found.')
    return ok(data)


@router.get('/{report_id}')
async def report_by_id(report_id: int):
    """Return a specific historical report by database ID."""
    data = await crud.get_report_by_id(report_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f'报告 {report_id} 不存在')
    return ok(data)


@router.delete('/{report_id}')
async def delete_report(report_id: int):
    """Delete a historical report by database ID."""
    success = await crud.delete_report(report_id)
    if not success:
        raise HTTPException(status_code=404, detail='报告不存在')
    return ok(None, msg='报告已删除')