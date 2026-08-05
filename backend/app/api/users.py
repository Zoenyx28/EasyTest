"""User search and batch query API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.common import ok
from app.db import crud

router = APIRouter(prefix='/api/users', tags=['users'])


@router.get('/search')
async def search_users(q: str = Query('', description='Search keyword for username or nickname')):
    """Search users by username or nickname."""
    if not q or not q.strip():
        return ok([])
    results = await crud.search_users(q.strip())
    return ok(results)


@router.get('/batch')
async def get_users_batch(ids: str = Query('', description='Comma-separated user IDs')):
    """Get multiple users by comma-separated IDs."""
    if not ids:
        return ok([])
    try:
        id_list = [int(x.strip()) for x in ids.split(',') if x.strip()]
    except ValueError:
        return ok([])
    results = await crud.get_users_batch(id_list)
    return ok(results)