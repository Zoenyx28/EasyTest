"""Redis pub/sub transport used between Celery workers and API WebSockets."""
from __future__ import annotations

import json

try:
    import redis.asyncio as redis
except ModuleNotFoundError:  # local validation before optional dependency install
    redis = None

from app.config import REDIS_URL


def channel(execution_id: str) -> str:
    return f'test-platform:execution:{execution_id}'


async def publish(execution_id: str, payload: dict) -> None:
    if redis is None:
        return
    client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await client.publish(channel(execution_id), json.dumps(payload, ensure_ascii=False))
    finally:
        await client.aclose()
