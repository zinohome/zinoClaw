"""Approval channel — reusable async mechanism for interactive tool approval.

Core provides the mechanism; actual "when to ask" policy lives in external
security plugins (see examples/security-plugin-interactive/).

Approval resolution order (three-level fallback):
  1. DeskClaw UI WebSocket dialog  (current_ws is set)
  2. Channel-specific transport     (e.g. Feishu interactive card)
  3. Auto allow_once                (cron, channels without transport)
"""

from __future__ import annotations

import asyncio
import contextvars
import uuid as _uuid
from typing import Any, Protocol, runtime_checkable

# WebSocket reference injected per-request via server.py
current_ws: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "current_ws", default=None,
)

# Channel name of the message currently being processed (set by _dispatch patch)
current_channel_name: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_channel_name", default=None,
)

# Session ID of the chat currently being processed (set by server._run_chat)
current_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_session_id", default=None,
)


@runtime_checkable
class ApprovalTransport(Protocol):
    """Channel-specific approval UI (e.g. Feishu interactive card).

    Implement ``send_approval`` to present the approval request to the user.
    When the user responds, call ``ApprovalChannel.resolve(request_id, decision)``.
    """

    async def send_approval(
        self,
        request_id: str,
        tool_name: str,
        params: dict,
        summary: str,
    ) -> None: ...


class ApprovalChannel:
    """Manages pending approval requests.

    Usage:
        channel = ApprovalChannel()
        decision = await channel.request("exec", {"command": "rm -rf /"})
        # decision == {"action": "allow_once" | "allowlist" | "deny"}
    """

    def __init__(self):
        self._pending: dict[str, asyncio.Future] = {}
        self._transports: dict[str, ApprovalTransport] = {}

    # ── transport registry ──

    def register_transport(self, channel: str, transport: ApprovalTransport) -> None:
        """Register a channel-specific approval transport."""
        self._transports[channel] = transport

    def unregister_transport(self, channel: str) -> None:
        self._transports.pop(channel, None)

    # ── core request / resolve ──

    async def request(
        self,
        tool_name: str,
        params: dict,
        summary: str = "",
    ) -> dict:
        """Send an approval request through the best available transport.

        Resolution order:
          1. DeskClaw UI WebSocket (current_ws is set by server.py)
          2. Channel transport     (current_channel_name + registered transport)
          3. Auto allow_once       (no interactive UI available)
        """
        # 1. DeskClaw UI WebSocket
        ws = current_ws.get()
        if ws is not None:
            return await self._request_via_ws(ws, tool_name, params, summary)

        # 2. Channel-specific transport
        ch = current_channel_name.get()
        transport = self._transports.get(ch) if ch else None
        if transport is not None:
            return await self._request_via_transport(
                transport, tool_name, params, summary,
            )

        # 3. No interactive UI — auto approve
        return {"action": "allow_once"}

    async def _request_via_ws(
        self, ws: Any, tool_name: str, params: dict, summary: str,
    ) -> dict:
        request_id = str(_uuid.uuid4())
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await ws.send_json({
                "type": "tool_approval",
                "id": request_id,
                "tool": tool_name,
                "params": params,
                "summary": summary or "",
                "session_id": current_session_id.get() or "",
            })
            return await future
        except asyncio.CancelledError:
            return {"action": "deny", "reason": "Connection lost"}
        finally:
            self._pending.pop(request_id, None)

    async def _request_via_transport(
        self,
        transport: ApprovalTransport,
        tool_name: str,
        params: dict,
        summary: str,
    ) -> dict:
        request_id = str(_uuid.uuid4())
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await transport.send_approval(request_id, tool_name, params, summary)
            return await future
        except asyncio.CancelledError:
            return {"action": "deny", "reason": "Transport disconnected"}
        finally:
            self._pending.pop(request_id, None)

    def resolve(self, request_id: str, decision: dict) -> bool:
        """Resolve a pending approval (called by WS handler or channel callback)."""
        future = self._pending.get(request_id)
        if future is None or future.done():
            return False
        future.set_result(decision)
        return True

    def cancel_all(self):
        """Deny all pending approvals — called on WebSocket disconnect."""
        for rid, future in list(self._pending.items()):
            if not future.done():
                future.cancel()
        self._pending.clear()


class HookContext:
    """Passed to async security plugin hooks, exposing the approval channel."""

    def __init__(self, approval_channel: ApprovalChannel):
        self._channel = approval_channel

    async def request_approval(
        self,
        tool_name: str,
        params: dict,
        summary: str = "",
    ) -> dict:
        return await self._channel.request(tool_name, params, summary)
