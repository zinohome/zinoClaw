"""HTTP reporter with in-memory queue and periodic batch flush.

Protocol: POST /v1/collect  (aligned with GA4 / Segment conventions)
Thread-safe: enqueue() from asyncio thread, _flush() from daemon Timer.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import threading
import urllib.error
import urllib.request
from collections import deque
from typing import Any

from .config import TelemetryConfig

_SDK_NAME = "deskclaw-gateway"
_SDK_VERSION = "0.1.0"


class ReportQueue:
    """In-memory event queue with periodic HTTP flush."""

    def __init__(self, config: TelemetryConfig, client_id: str, user_id: str = "",
                 user_id_fn: Any = None) -> None:
        self._config = config
        self._client_id = client_id
        self._user_id = user_id
        self._user_id_fn = user_id_fn
        self._context = self._build_context()
        self._queue: deque[dict[str, Any]] = deque(maxlen=config.max_queue_size)
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._running = False

    def start(self) -> None:
        if not self._config.endpoint or not self._config.enabled:
            return
        self._running = True
        self._schedule_flush()
        print(
            f"[Telemetry] Reporter started → {self._config.endpoint} "
            f"(interval={self._config.flush_interval_sec}s, queue_max={self._config.max_queue_size})",
            file=sys.stderr, flush=True,
        )

    def stop(self) -> None:
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._flush()

    def enqueue(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._queue.append(event)

    # ── internal ──

    @staticmethod
    def _build_context() -> dict[str, Any]:
        os_name = platform.system().lower()
        if os_name == "darwin":
            os_name = "macos"
        return {
            "app": {"version": os.environ.get("DESKCLAW_APP_VERSION", "")},
            "os": {"name": os_name, "version": platform.release()},
            "device": {"arch": platform.machine()},
            "sdk": {"name": _SDK_NAME, "version": _SDK_VERSION},
        }

    def _schedule_flush(self) -> None:
        if not self._running:
            return
        self._timer = threading.Timer(
            self._config.flush_interval_sec, self._flush_and_reschedule,
        )
        self._timer.daemon = True
        self._timer.start()

    def _flush_and_reschedule(self) -> None:
        try:
            self._flush()
        except Exception:
            pass
        if self._running:
            self._schedule_flush()

    def _flush(self) -> None:
        with self._lock:
            if not self._queue:
                return
            events = list(self._queue)
            self._queue.clear()

        if not self._config.endpoint:
            return

        user_id = self._user_id
        if self._user_id_fn is not None:
            try:
                user_id = self._user_id_fn() or user_id
            except Exception:
                pass

        payload: dict[str, Any] = {
            "client_id": self._client_id,
            "context": self._context,
            "events": events,
        }
        if user_id:
            payload["user_id"] = user_id

        if os.environ.get("DESKCLAW_TELEMETRY_DEBUG"):
            try:
                from pathlib import Path
                debug_file = Path.home() / ".deskclaw" / "telemetry-debug.jsonl"
                with debug_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            except Exception:
                pass

        try:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                self._config.endpoint,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            if self._config.api_key:
                req.add_header("X-Api-Key", self._config.api_key)

            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception:
            with self._lock:
                for evt in reversed(events):
                    if len(self._queue) < self._config.max_queue_size:
                        self._queue.appendleft(evt)
