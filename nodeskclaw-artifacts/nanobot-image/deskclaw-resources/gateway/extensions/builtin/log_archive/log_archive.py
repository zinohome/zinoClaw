# version: 1
"""Log archive extension — saves conversation turns to local files."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.extensions.base import DeskClawExtension, ExtensionContext
from loguru import logger


class LogArchiveExtension(DeskClawExtension):
    name = "log_archive"
    version = "1.0"
    description = "自动将每轮对话归档到本地文件（支持 JSONL / Markdown）"

    def __init__(self) -> None:
        super().__init__()
        self._dir: Path | None = None
        self._format: str = "jsonl"
        self._last_turn_start: dict[str, str] = {}

    async def activate(self, ctx: ExtensionContext) -> None:
        raw = ctx.config.get("dir", "")
        if not raw:
            logger.warning("[log_archive] No output directory configured")
            return
        self._dir = Path(raw).expanduser().resolve()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._format = ctx.config.get("format", "jsonl").lower()
        if self._format not in ("jsonl", "markdown"):
            logger.warning("[log_archive] Unknown format '{}', falling back to jsonl", self._format)
            self._format = "jsonl"

    async def on_turn_start(self, session_key: str, message: str) -> None:
        self._last_turn_start[session_key] = message

    async def on_turn_end(self, session_key: str, response: str | None) -> None:
        if not self._dir:
            return

        now = datetime.now(timezone.utc)
        user_msg = self._last_turn_start.pop(session_key, "")

        if self._format == "jsonl":
            self._write_jsonl(now, session_key, user_msg, response)
        else:
            self._write_markdown(now, session_key, user_msg, response)

    async def on_tool_end(self, record: Any) -> None:
        if not self._dir or self._format != "jsonl":
            return

        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        path = self._dir / f"{date_str}.jsonl"
        entry = {
            "ts": now.isoformat(),
            "type": "tool_call",
            "tool": getattr(record, "tool", str(record)),
            "decision": getattr(record, "decision", ""),
            "duration_ms": getattr(record, "duration_ms", None),
        }
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("[log_archive] Write failed: {}", exc)

    def _write_jsonl(
        self, now: datetime, session_key: str,
        user_msg: str, response: str | None,
    ) -> None:
        date_str = now.strftime("%Y-%m-%d")
        path = self._dir / f"{date_str}.jsonl"
        entry = {
            "ts": now.isoformat(),
            "type": "turn",
            "session": session_key,
            "user": user_msg,
            "response": response or "",
        }
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("[log_archive] Write failed: {}", exc)

    def _write_markdown(
        self, now: datetime, session_key: str,
        user_msg: str, response: str | None,
    ) -> None:
        date_str = now.strftime("%Y-%m-%d")
        path = self._dir / f"{date_str}.md"
        time_str = now.strftime("%H:%M:%S")
        section = (
            f"\n## {time_str} — {session_key}\n\n"
            f"**User:** {user_msg}\n\n"
            f"**Assistant:** {response or '(empty)'}\n\n"
            f"---\n"
        )
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(section)
        except Exception as exc:
            logger.warning("[log_archive] Write failed: {}", exc)
