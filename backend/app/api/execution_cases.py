"""Execution case resource endpoints — RESTful separate resource."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.db import crud
from app.api.common import ok

router = APIRouter(prefix='/api/execution-cases', tags=['execution-cases'])


@router.get('/{case_id}/log')
async def get_execution_case_log(case_id: int):
    """Get execution log for a single test case."""
    data = await crud.get_execution_case_log(case_id)
    if data is None:
        raise HTTPException(status_code=404, detail='执行用例不存在')
    return ok(data)
