# version: 4
"""Webhook notification extension — sends HTTP POST on agent events."""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any

from gateway.extensions.base import DeskClawExtension, ExtensionContext
from loguru import logger

_EVENT_LABELS = {
    "turn_end": "对话完成",
    "turn_start": "对话开始",
    "tool_call": "工具调用",
}


def _render(template: Any, variables: dict[str, str]) -> Any:
    """Recursively replace {key} placeholders in a JSON-compatible structure."""
    if isinstance(template, str):
        for k, v in variables.items():
            template = template.replace(f"{{{k}}}", v)
        return template
    if isinstance(template, dict):
        return {k: _render(v, variables) for k, v in template.items()}
    if isinstance(template, list):
        return [_render(item, variables) for item in template]
    return template


class WebhookNotifierExtension(DeskClawExtension):
    name = "webhook_notifier"
    version = "1.2"
    description = "对话完成或工具调用时发送 HTTP 通知到指定 URL"

    def __init__(self) -> None:
        super().__init__()
        self._url: str = ""
        self._events: set[str] = set()
        self._secret: str = ""
        self._timeout: float = 5.0
        self._template: dict[str, Any] | None = None

    async def activate(self, ctx: ExtensionContext) -> None:
        self._url = ctx.config.get("url", "")
        self._events = set(ctx.config.get("events", ["turn_end"]))
        self._secret = ctx.config.get("secret", "")
        self._timeout = ctx.config.get("timeout", 5.0)
        self._template = ctx.config.get("template")

        if not self._url:
            logger.warning("[webhook_notifier] No URL configured — notifications disabled")

    def _build_payload(self, raw: dict[str, Any]) -> dict[str, Any]:
        if self._template is None:
            return raw

        event = raw.get("event", "unknown")
        label = _EVENT_LABELS.get(event, event)
        ts = datetime.fromtimestamp(
            raw.get("timestamp", time.time()), tz=timezone.utc,
        ).strftime("%Y-%m-%d %H:%M:%S")

        if event == "turn_end":
            summary = f"{label}: {raw.get('response', '')[:300]}"
        elif event == "turn_start":
            summary = f"{label}: {raw.get('message', '')[:300]}"
        elif event == "tool_call":
            dur = raw.get("duration_ms")
            dur_str = f" ({dur}ms)" if dur else ""
            summary = f"{label}: {raw.get('tool', '')} [{raw.get('decision', '')}]{dur_str}"
        else:
            summary = f"{label}"

        variables = {
            "event": event,
            "event_label": label,
            "timestamp": ts,
            "session": str(raw.get("session", "")),
            "response": str(raw.get("response", "")),
            "message": str(raw.get("message", "")),
            "tool": str(raw.get("tool", "")),
            "decision": str(raw.get("decision", "")),
            "duration_ms": str(raw.get("duration_ms", "")),
            "summary": summary,
        }

        return _render(copy.deepcopy(self._template), variables)

    async def on_turn_end(self, session_key: str, response: str | None) -> None:
        if "turn_end" not in self._events or not self._url:
            return
        await self._post({
            "event": "turn_end",
            "timestamp": time.time(),
            "session": session_key,
            "response": (response or "")[:2000],
        })

    async def on_tool_end(self, record: Any) -> None:
        if "tool_call" not in self._events or not self._url:
            return
        await self._post({
            "event": "tool_call",
            "timestamp": time.time(),
            "tool": getattr(record, "tool", str(record)),
            "decision": getattr(record, "decision", ""),
            "duration_ms": getattr(record, "duration_ms", None),
        })

    async def on_turn_start(self, session_key: str, message: str) -> None:
        if "turn_start" not in self._events or not self._url:
            return
        await self._post({
            "event": "turn_start",
            "timestamp": time.time(),
            "session": session_key,
            "message": message[:2000],
        })

    async def _post(self, raw: dict[str, Any]) -> None:
        import asyncio

        payload = self._build_payload(raw)

        try:
            import aiohttp
        except ImportError:
            await asyncio.get_running_loop().run_in_executor(
                None, self._post_sync, payload,
            )
            return

        body = json.dumps(payload, ensure_ascii=False)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._secret:
            sig = hmac.new(
                self._secret.encode(), body.encode(), hashlib.sha256,
            ).hexdigest()
            headers["X-DeskClaw-Signature"] = sig

        try:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self._url, data=body, headers=headers) as resp:
                    resp_body = await resp.text()
                    if resp.status >= 400:
                        logger.warning(
                            "[webhook_notifier] POST {} returned {} body={}",
                            self._url, resp.status, resp_body[:200],
                        )
                    else:
                        logger.debug(
                            "[webhook_notifier] POST {} => {} body={}",
                            self._url, resp.status, resp_body[:200],
                        )
        except Exception as exc:
            logger.warning("[webhook_notifier] POST failed: {}", exc)

    def _post_sync(self, payload: dict[str, Any]) -> None:
        """Fallback when aiohttp is not available."""
        import urllib.request

        body = json.dumps(payload, ensure_ascii=False).encode()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._secret:
            sig = hmac.new(
                self._secret.encode(), body, hashlib.sha256,
            ).hexdigest()
            headers["X-DeskClaw-Signature"] = sig

        req = urllib.request.Request(self._url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout):
                pass
        except Exception as exc:
            logger.warning("[webhook_notifier] POST failed: {}", exc)
