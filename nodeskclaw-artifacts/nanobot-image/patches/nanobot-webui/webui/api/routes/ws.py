"""WebSocket /ws/chat endpoint (DeskClaw gateway compatible patch)."""

from __future__ import annotations

import asyncio
import os
import uuid

import httpx
import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()

_GATEWAY_BASE = os.environ.get("DESKCLAW_GATEWAY_BASE", "http://127.0.0.1:18790").rstrip("/")
_USE_DESKCLAW_GATEWAY = os.environ.get("WEBUI_USE_DESKCLAW_GATEWAY", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


async def _auth_websocket(websocket: WebSocket) -> dict | None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return None

    from webui.api.auth import decode_access_token

    user_store = websocket.app.state.user_store
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return None

    user = user_store.get_by_id(payload["sub"])
    if not user:
        await websocket.close(code=4001, reason="User not found")
        return None
    return user


async def _deskclaw_chat(content: str, session_key: str) -> str:
    payload = {"message": content, "session_id": session_key}
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(f"{_GATEWAY_BASE}/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return str(data.get("content") or "")
        return ""


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    user = await _auth_websocket(websocket)
    if user is None:
        return

    await websocket.accept()

    is_admin = user.get("role") == "admin"

    def _is_allowed_session(key: str) -> bool:
        if key.startswith(f"web:{user['id']}"):
            return True
        return is_admin

    requested_key = websocket.query_params.get("session")
    session_key = (
        requested_key
        if requested_key and _is_allowed_session(requested_key)
        else f"web:{user['id']}:{uuid.uuid4().hex[:8]}"
    )
    await websocket.send_json({"type": "session_info", "session_key": session_key})

    session_tasks: dict[str, asyncio.Task] = {}

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type")

            if msg_type == "cancel":
                cancel_key = raw.get("session_key") or session_key
                task = session_tasks.get(cancel_key)
                if task and not task.done():
                    task.cancel()
                    await websocket.send_json(
                        {"type": "error", "content": "cancelled", "session_key": cancel_key}
                    )
                continue

            if msg_type == "new_session":
                session_key = f"web:{user['id']}:{uuid.uuid4().hex[:8]}"
                await websocket.send_json({"type": "session_info", "session_key": session_key})
                continue

            if msg_type != "message":
                continue

            content = raw.get("content", "")
            msg_session_key = raw.get("session_key")
            if msg_session_key and _is_allowed_session(msg_session_key):
                if msg_session_key != session_key:
                    session_key = msg_session_key
                    await websocket.send_json({"type": "session_info", "session_key": session_key})

            if not content:
                continue

            effective_key = msg_session_key or session_key

            existing_task = session_tasks.get(effective_key)
            if existing_task and not existing_task.done():
                await websocket.send_json(
                    {
                        "type": "error",
                        "content": "Previous message still processing in this session",
                        "session_key": effective_key,
                    }
                )
                continue

            async def _run_agent(msg: str, sess: str) -> None:
                try:
                    if _USE_DESKCLAW_GATEWAY:
                        reply = await _deskclaw_chat(msg, sess)
                    else:
                        container = websocket.app.state.services
                        result = await container.agent.process_direct(
                            msg,
                            session_key=sess,
                            channel="web",
                            chat_id=user["id"],
                        )
                        reply = getattr(result, "content", result) if result else ""

                    await websocket.send_json(
                        {"type": "done", "content": reply or "", "session_key": sess}
                    )
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.error("WebSocket agent error: {}", exc)
                    try:
                        await websocket.send_json(
                            {"type": "error", "content": str(exc), "session_key": sess}
                        )
                    except Exception:
                        pass
                finally:
                    session_tasks.pop(sess, None)

            task = asyncio.create_task(_run_agent(content, effective_key))
            session_tasks[effective_key] = task

    except WebSocketDisconnect:
        for task in session_tasks.values():
            if not task.done():
                task.cancel()
    except Exception as exc:
        logger.error("WebSocket error: {}", exc)
        try:
            await websocket.send_json({"type": "error", "content": str(exc)})
        except Exception:
            pass
