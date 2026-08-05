"""WebSocket endpoint for real-time test execution updates."""
from __future__ import annotations
import asyncio
try:
    import redis.asyncio as redis
except ModuleNotFoundError:  # local validation fallback
    redis = None
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.config import REDIS_URL
from app.websocket.events import channel
from app.services.executor import execution_manager

router = APIRouter()


@router.websocket('/ws/run/{run_id}')
async def run_websocket(ws: WebSocket, run_id: str):
    """Stream real-time test execution progress."""
    await ws.accept()
    if redis is None:
        state = execution_manager.get_run(run_id)
        if not state:
            await ws.close(code=4004, reason='Run not found')
            return
        queue: asyncio.Queue = asyncio.Queue()
        state.subscribers.append(queue)
        try:
            while True:
                try:
                    await ws.send_text(await asyncio.wait_for(queue.get(), timeout=30))
                except asyncio.TimeoutError:
                    await ws.send_text('{"type":"heartbeat"}')
        except WebSocketDisconnect:
            return
        finally:
            if queue in state.subscribers:
                state.subscribers.remove(queue)
        return
    client = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel(run_id))

    try:
        while True:
            try:
                message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True, timeout=25), timeout=30)
                if message and message['type'] == 'message':
                    await ws.send_text(message['data'])
                else:
                    await ws.send_text('{"type":"heartbeat"}')
            except asyncio.TimeoutError:
                # Send heartbeat
                await ws.send_text('{"type":"heartbeat"}')
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel(run_id))
        await pubsub.aclose()
        await client.aclose()


@router.websocket('/ws/execution/{execution_id}')
async def execution_websocket(ws: WebSocket, execution_id: str):
    """Plan-compatible alias for the execution progress stream."""
    await run_websocket(ws, execution_id)
