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


# ── 需求文档在线协作：同一需求的连接间广播文档内容变更（last-write-wins）──
_doc_ws_clients: dict[int, set] = {}


@router.websocket('/ws/doc/{req_id}')
async def doc_collab_ws(ws: WebSocket, req_id: int):
    """需求文档多人在线编辑：客户端发 {content}，转发给同需求其它连接。

    持久化由调用方（PUT /api/req/{id}）负责，本通道仅负责实时同步。
    """
    req_id = int(req_id)
    await ws.accept()
    _doc_ws_clients.setdefault(req_id, set()).add(ws)
    try:
        while True:
            msg = await ws.receive_json()
            content = (msg or {}).get('content')
            if content is None:
                continue
            for other in list(_doc_ws_clients.get(req_id, set())):
                if other is not ws:
                    try:
                        await other.send_json({'type': 'doc', 'content': content, 'by': msg.get('by', '')})
                    except Exception:
                        pass
    except WebSocketDisconnect:
        pass
    finally:
        _doc_ws_clients.get(req_id, set()).discard(ws)
