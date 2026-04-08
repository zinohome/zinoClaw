"""Sessions routes (DeskClaw gateway compatible patch)."""

from __future__ import annotations

import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from webui.api.deps import get_current_user, get_services
from webui.api.gateway import ServiceContainer
from webui.api.models import MessageInfo, SessionInfo

router = APIRouter()

_GATEWAY_BASE = os.environ.get("DESKCLAW_GATEWAY_BASE", "http://127.0.0.1:18790").rstrip("/")
_USE_DESKCLAW_GATEWAY = os.environ.get("WEBUI_USE_DESKCLAW_GATEWAY", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _is_own_session(key: str, user: dict) -> bool:
    if user.get("role") == "admin":
        return True
    return key.startswith(f"web:{user['id']}")


@router.get("", response_model=list[SessionInfo])
async def list_sessions(
    current_user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[ServiceContainer, Depends(get_services)],
) -> list[SessionInfo]:
    if not _USE_DESKCLAW_GATEWAY:
        sessions = svc.session_manager.list_sessions()
        visible = [s for s in sessions if _is_own_session(s.get("key", ""), current_user)]
        return [
            SessionInfo(
                key=s["key"],
                created_at=s.get("created_at"),
                updated_at=s.get("updated_at"),
                last_message=s.get("last_message"),
            )
            for s in visible
        ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{_GATEWAY_BASE}/sessions")
        resp.raise_for_status()
        payload = resp.json()
    rows = payload.get("sessions", []) if isinstance(payload, dict) else []
    visible = [s for s in rows if _is_own_session(str(s.get("session_id", "")), current_user)]
    return [
        SessionInfo(
            key=str(s.get("session_id", "")),
            created_at=s.get("created_at"),
            updated_at=s.get("last_active") or s.get("updated_at"),
            last_message=s.get("last_message"),
        )
        for s in visible
    ]


@router.get("/{key:path}/messages", response_model=list[MessageInfo])
async def get_session_messages(
    key: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[ServiceContainer, Depends(get_services)],
) -> list[MessageInfo]:
    if not _is_own_session(key, current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")

    if not _USE_DESKCLAW_GATEWAY:
        session = svc.session_manager.get_or_create(key)
        return [
            MessageInfo(
                role=m.get("role", "unknown"),
                content=m.get("content"),
                timestamp=m.get("timestamp"),
                tool_calls=m.get("tool_calls"),
                tool_call_id=m.get("tool_call_id"),
                name=m.get("name"),
            )
            for m in session.messages
        ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{_GATEWAY_BASE}/chat/{key}/history")
        resp.raise_for_status()
        payload = resp.json()
    rows = payload.get("messages", []) if isinstance(payload, dict) else []
    return [
        MessageInfo(
            role=m.get("role", "unknown"),
            content=m.get("content"),
            timestamp=m.get("timestamp"),
            tool_calls=m.get("tool_calls"),
            tool_call_id=m.get("tool_call_id"),
            name=m.get("name"),
        )
        for m in rows
    ]


@router.get("/{key:path}/memory", response_model=dict)
async def get_session_memory(
    key: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[ServiceContainer, Depends(get_services)],
) -> dict:
    if not _is_own_session(key, current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    workspace = svc.config.workspace_path
    memory_file = workspace / "MEMORY.md"
    history_file = workspace / "HISTORY.md"
    return {
        "memory": memory_file.read_text(encoding="utf-8") if memory_file.exists() else "",
        "history": history_file.read_text(encoding="utf-8") if history_file.exists() else "",
    }


@router.delete("/{key:path}/messages/{index}", status_code=200)
async def revoke_message(
    key: str,
    index: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[ServiceContainer, Depends(get_services)],
) -> dict:
    if not _is_own_session(key, current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    if _USE_DESKCLAW_GATEWAY:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Revoke not supported in DeskClaw mode yet")
    session = svc.session_manager.get_or_create(key)
    if index < 0 or index >= len(session.messages):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid message index")
    removed = session.messages[index]
    if removed.get("role") == "user":
        end = index + 1
        while end < len(session.messages) and session.messages[end].get("role") != "user":
            end += 1
        count = end - index
        del session.messages[index:end]
    else:
        count = 1
        del session.messages[index]
    from datetime import datetime

    session.updated_at = datetime.now()
    svc.session_manager.save(session)
    return {"removed": count}


@router.delete("/{key:path}", status_code=204)
async def delete_session(
    key: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    svc: Annotated[ServiceContainer, Depends(get_services)],
) -> None:
    if not _is_own_session(key, current_user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")
    if _USE_DESKCLAW_GATEWAY:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(f"{_GATEWAY_BASE}/chat/{key}")
            if resp.status_code not in (200, 204):
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Gateway delete failed: {resp.status_code}")
        return
    svc.session_manager.delete(key)
