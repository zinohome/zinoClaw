"""Turn-level telemetry collector.

Aggregates individual tool-call AuditRecords into turn-level events,
then pushes them to ReportQueue for batch HTTP upload.

Turn boundary: 30 s of idle time within the same session.
"""

from __future__ import annotations

import contextvars
import json
import os
import re
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import TelemetryConfig, load_config
from .reporter import ReportQueue

_DEBUG = bool(os.environ.get("DESKCLAW_TELEMETRY_DEBUG"))
_TURN_IDLE_TIMEOUT = 5.0 if _DEBUG else 30.0
_SWEEP_INTERVAL = 5.0 if _DEBUG else 30.0

_SKILL_PATH_RE = re.compile(r'[/\\]skills[/\\]([^/\\]+)[/\\]SKILL\.md$')


@dataclass
class _ToolCall:
    name: str
    duration_ms: float
    decision: str


@dataclass
class _TurnState:
    session_id: str
    channel: str
    start_ts: float
    tool_calls: list[_ToolCall] = field(default_factory=list)
    last_activity: float = 0.0
    skills_used: set[str] = field(default_factory=set)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    message_ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if not self.last_activity:
            self.last_activity = self.start_ts


def _read_client_id() -> str:
    """Read deviceId from the shared Electron store file."""
    settings = Path.home() / ".deskclaw" / "deskclaw-settings.json"
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
        return data.get("deviceId", "")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""


def _read_user_id() -> str:
    """Read userId from the shared Electron store file.

    The Store class uses dot-notation flat keys, so ``auth.userInfo`` is
    a top-level key in the JSON, not a nested ``auth.userInfo`` path.
    """
    settings = Path.home() / ".deskclaw" / "deskclaw-settings.json"
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
        info = data.get("auth.userInfo")
        if isinstance(info, dict):
            return str(info.get("userId", "") or "")
        return ""
    except Exception:
        return ""


def _extract_skill_name(params: dict) -> str | None:
    """Return skill name if *params* describe a read_file of a SKILL.md."""
    path = params.get("path") or ""
    m = _SKILL_PATH_RE.search(str(path))
    return m.group(1) if m else None


def _read_always_skills() -> list[str]:
    """Return names of skills marked ``always=true``."""
    try:
        from nanobot.config.loader import load_config as _load_nanobot_config
        cfg = _load_nanobot_config()
        workspace = cfg.workspace_path
        from nanobot.agent.skills import SkillsLoader
        return SkillsLoader(workspace).get_always_skills()
    except Exception:
        return []


_DESKCLAW_CHANNELS = frozenset({"agent", "gateway"})


def _normalize_channel(session_id: str) -> str:
    """Derive a normalised channel name from session_id.

    "agent:*" / "gateway" (no colon) → "deskclaw"  (DeskClaw client)
    "feishu:*" / "wecom:*" / …       → original prefix
    "cron:*"                          → "cron"
    """
    raw = session_id.split(":", 1)[0] if ":" in session_id else "gateway"
    return "deskclaw" if raw in _DESKCLAW_CHANNELS else raw


# ── Session-id propagation (class-level, idempotent) ──────────────
#
# We patch AgentLoop._dispatch (bus/external channels) and .process_direct
# (HTTP/cron/CLI) to set a ContextVar *owned by this module* with the
# session key.  We cannot patch _process_message because agent.py applies
# an instance-level override that shadows any class-level patch.
#
# Why a local ContextVar instead of the one in gateway.security.approval?
#   1. No cross-module import-path aliasing risk.
#   2. ContextVar automatically propagates to child Tasks created by
#      asyncio.gather (used by nanobot for parallel tool execution).
# WebSocket messages are covered by a fallback that reads the ContextVar
# set by server.py _run_chat.

_telemetry_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_telemetry_session_id", default="",
)
_telemetry_usage: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "_telemetry_usage", default=None,
)
_telemetry_message_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_telemetry_message_id", default="",
)
_session_propagation_installed = False

_collector_ref: TelemetryCollector | None = None


def _notify_message_end() -> None:
    """Called from _dispatch/_process_direct wrappers when a message finishes.

    Ensures a turn record exists even when no tools were called, and
    writes the final token usage snapshot (which may include tokens from
    the LLM's closing reply that never triggers on_after).
    """
    try:
        collector = _collector_ref
        if collector is None or not collector._config.enabled:
            return

        session_id = _current_session_key()
        now = time.time()

        turn = collector._turns.get(session_id)
        if turn is None:
            channel = _normalize_channel(session_id)
            turn = _TurnState(session_id=session_id, channel=channel, start_ts=now)
            collector._turns[session_id] = turn

        turn.last_activity = now

        acc = _telemetry_usage.get()
        if acc:
            turn.prompt_tokens = acc["prompt_tokens"]
            turn.completion_tokens = acc["completion_tokens"]

        mid = _telemetry_message_id.get()
        if mid:
            turn.message_ids.add(mid)
    except Exception:
        pass


def _install_usage_tracking() -> None:
    """Replace ``AgentLoop._last_usage`` with a property whose setter
    accumulates token counts into a per-Task ContextVar.

    The ContextVar is initialised in ``_dispatch`` / ``process_direct``
    wrappers, so each concurrent session gets its own accumulator.
    """
    try:
        from nanobot.agent.loop import AgentLoop

        _storage_attr = "_last_usage_val"

        @property  # type: ignore[misc]
        def _last_usage_prop(self) -> dict:
            return getattr(self, _storage_attr, {})

        @_last_usage_prop.setter
        def _last_usage_prop(self, value: dict) -> None:
            setattr(self, _storage_attr, value)
            try:
                acc = _telemetry_usage.get()
                if acc is not None:
                    acc["prompt_tokens"] += int(value.get("prompt_tokens", 0) or 0)
                    acc["completion_tokens"] += int(value.get("completion_tokens", 0) or 0)
            except Exception:
                pass

        AgentLoop._last_usage = _last_usage_prop  # type: ignore[assignment]
        print("[Telemetry] _last_usage property patch installed",
              file=sys.stderr, flush=True)
    except Exception:
        pass


def _install_session_propagation() -> None:
    """Patch AgentLoop._dispatch and .process_direct to set ContextVars
    for session id, token usage accumulator, and message id.

    NOTE: We cannot patch _process_message because agent.py applies an
    INSTANCE-level override (_patch_process_message_for_pending_restart)
    that shadows any CLASS-level patch.  _dispatch and process_direct have
    no instance override and together cover bus + HTTP/cron paths.
    WebSocket is handled by the ContextVar fallback (set by _run_chat).

    Fully defensive — original methods always called. Idempotent.
    """
    global _session_propagation_installed
    if _session_propagation_installed:
        return
    _session_propagation_installed = True

    _install_usage_tracking()

    try:
        import functools
        from nanobot.agent.loop import AgentLoop

        # ── _dispatch: bus / external channels (feishu, wecom, cron bus) ──
        _orig_dispatch = AgentLoop._dispatch

        @functools.wraps(_orig_dispatch)
        async def _dispatch_with_session(self, msg, *a, **kw):
            tok_sid = tok_usage = tok_mid = None
            try:
                tok_sid = _telemetry_session_id.set(
                    getattr(msg, "session_key", "") or ""
                )
            except Exception:
                pass
            try:
                tok_usage = _telemetry_usage.set({"prompt_tokens": 0, "completion_tokens": 0})
            except Exception:
                pass
            try:
                tok_mid = _telemetry_message_id.set(uuid.uuid4().hex)
            except Exception:
                pass
            try:
                return await _orig_dispatch(self, msg, *a, **kw)
            finally:
                try:
                    _notify_message_end()
                except Exception:
                    pass
                for tok in (tok_sid, tok_usage, tok_mid):
                    if tok is not None:
                        try:
                            tok.var.reset(tok)  # type: ignore[union-attr]
                        except Exception:
                            pass

        AgentLoop._dispatch = _dispatch_with_session

        # ── process_direct: HTTP /chat, cron, CLI ──
        _orig_pd = AgentLoop.process_direct

        @functools.wraps(_orig_pd)
        async def _pd_with_session(self, content, session_key="cli:direct", *a, **kw):
            tok_sid = tok_usage = tok_mid = None
            try:
                tok_sid = _telemetry_session_id.set(session_key)
            except Exception:
                pass
            try:
                tok_usage = _telemetry_usage.set({"prompt_tokens": 0, "completion_tokens": 0})
            except Exception:
                pass
            try:
                tok_mid = _telemetry_message_id.set(uuid.uuid4().hex)
            except Exception:
                pass
            try:
                return await _orig_pd(self, content, session_key, *a, **kw)
            finally:
                try:
                    _notify_message_end()
                except Exception:
                    pass
                for tok in (tok_sid, tok_usage, tok_mid):
                    if tok is not None:
                        try:
                            tok.var.reset(tok)  # type: ignore[union-attr]
                        except Exception:
                            pass

        AgentLoop.process_direct = _pd_with_session

        print("[Telemetry] _dispatch + process_direct patches installed",
              file=sys.stderr, flush=True)
    except Exception as exc:
        print(f"[Telemetry] session propagation patch failed: {exc}",
              file=sys.stderr, flush=True)


def _current_session_key() -> str:
    """Read session key for the current asyncio task.

    Primary: our own ContextVar set by _dispatch / process_direct patches.
             Propagates automatically to asyncio.gather child tasks.
    Fallback: the ContextVar in gateway.security.approval set by
              server.py _run_chat (covers the WebSocket path).
    """
    sid = _telemetry_session_id.get()
    if sid:
        return sid

    for mod_path in ("gateway.security.approval", "gateway.security"):
        try:
            mod = sys.modules.get(mod_path)
            if mod is not None:
                csid = getattr(mod, "current_session_id", None)
                if csid is not None:
                    val = csid.get()
                    if val:
                        return val
        except Exception:
            pass

    return "__unknown__"


_DEFAULT_LLM_HOST = "llm-gateway-api.nodesk.tech"


def _read_model_info() -> dict[str, str]:
    """Read model provider / name / host from the nanobot config file."""
    try:
        from urllib.parse import urlparse
        from nanobot.config.loader import load_config as _load_nanobot_config
        cfg = _load_nanobot_config()
        model = cfg.agents.defaults.model
        api_base = cfg.get_api_base(model) or ""
        host = (urlparse(api_base).hostname or "") if api_base else ""
        return {
            "provider": "default" if host == _DEFAULT_LLM_HOST else "custom",
            "name": model,
            "api_base_host": host,
        }
    except Exception:
        return {}


class TelemetryCollector:
    """Collects tool execution data and aggregates into turn-level events.

    Self-contained: reads all config from disk, no external dependencies.
    Loaded automatically via the security-plugin mechanism.
    """

    def __init__(self) -> None:
        global _collector_ref

        self._config: TelemetryConfig = load_config()
        self._client_id: str = _read_client_id()
        self._model_info: dict[str, str] = _read_model_info()
        self._turns: dict[str, _TurnState] = {}
        self._sweep_timer: threading.Timer | None = None

        try:
            self._user_id: str = _read_user_id()
        except Exception:
            self._user_id = ""

        try:
            self._always_skills: list[str] = _read_always_skills()
        except Exception:
            self._always_skills = []

        self._reporter = ReportQueue(
            self._config, self._client_id, self._user_id,
            user_id_fn=_read_user_id,
        )

        _collector_ref = self

        if self._config.enabled and self._config.endpoint:
            self._reporter.start()
            self._schedule_sweep()
            import atexit
            atexit.register(self.stop)
            cid_display = self._client_id[:8] if self._client_id else "<no-id>"
            uid_display = self._user_id[:8] if self._user_id else "<no-uid>"
            print(
                f"[Telemetry] Collector ready (client={cid_display}, user={uid_display})",
                file=sys.stderr, flush=True,
            )

    def stop(self) -> None:
        """Flush remaining turns and stop the reporter."""
        if self._sweep_timer:
            self._sweep_timer.cancel()
            self._sweep_timer = None
        for sid in list(self._turns):
            self._flush_turn(sid)
        self._reporter.stop()

    def on_after(self, record: Any) -> None:
        """Hook called by ToolSecurityLayer after each tool execution."""
        if not self._config.enabled:
            return

        session_id = self._get_session_id()
        now = time.time()

        self._sweep_idle_turns(now)

        turn = self._turns.get(session_id)
        if turn is None:
            channel = _normalize_channel(session_id)
            turn = _TurnState(session_id=session_id, channel=channel, start_ts=now)
            self._turns[session_id] = turn

        turn.tool_calls.append(_ToolCall(
            name=record.tool,
            duration_ms=record.duration_ms,
            decision=record.decision,
        ))
        turn.last_activity = now

        # ── skill detection ──
        try:
            if record.tool == "read_file" and record.decision != "denied":
                skill = _extract_skill_name(record.params)
                if skill:
                    turn.skills_used.add(skill)
        except Exception:
            pass

        # ── token usage snapshot ──
        try:
            acc = _telemetry_usage.get()
            if acc:
                turn.prompt_tokens = acc["prompt_tokens"]
                turn.completion_tokens = acc["completion_tokens"]
        except Exception:
            pass

        # ── message id collection ──
        try:
            mid = _telemetry_message_id.get()
            if mid:
                turn.message_ids.add(mid)
        except Exception:
            pass

    # ── internal ──

    def _schedule_sweep(self) -> None:
        self._sweep_timer = threading.Timer(_SWEEP_INTERVAL, self._sweep_and_reschedule)
        self._sweep_timer.daemon = True
        self._sweep_timer.start()

    def _sweep_and_reschedule(self) -> None:
        try:
            self._sweep_idle_turns(time.time())
        except Exception:
            pass
        if self._sweep_timer is not None:
            self._schedule_sweep()

    def _sweep_idle_turns(self, now: float) -> None:
        idle = [
            sid for sid, t in self._turns.items()
            if now - t.last_activity > _TURN_IDLE_TIMEOUT
        ]
        for sid in idle:
            self._flush_turn(sid)

    def _flush_turn(self, session_id: str) -> None:
        turn = self._turns.pop(session_id, None)
        if not turn:
            return

        tool_agg: dict[str, dict[str, Any]] = {}
        total_calls = 0
        total_denied = 0

        for tc in turn.tool_calls:
            total_calls += 1
            if tc.decision == "denied":
                total_denied += 1
            agg = tool_agg.setdefault(tc.name, {
                "name": tc.name, "count": 0, "total_ms": 0.0, "denied": 0,
            })
            agg["count"] += 1
            agg["total_ms"] = round(agg["total_ms"] + tc.duration_ms, 1)
            if tc.decision == "denied":
                agg["denied"] += 1

        duration_ms = (turn.last_activity - turn.start_ts) * 1000

        properties: dict[str, Any] = {
            "session_id": turn.session_id,
            "channel": turn.channel,
            "duration_ms": round(duration_ms, 1),
            "model_provider": self._model_info.get("provider", ""),
            "model_name": self._model_info.get("name", ""),
            "model_endpoint_host": self._model_info.get("api_base_host", ""),
            "tool_count": total_calls,
            "tool_denied_count": total_denied,
            "tools": list(tool_agg.values()),
        }

        try:
            if turn.skills_used:
                properties["skills_used"] = sorted(turn.skills_used)
        except Exception:
            pass
        try:
            if self._always_skills:
                properties["always_skills"] = list(self._always_skills)
        except Exception:
            pass
        try:
            if turn.prompt_tokens or turn.completion_tokens:
                properties["prompt_tokens"] = turn.prompt_tokens
                properties["completion_tokens"] = turn.completion_tokens
        except Exception:
            pass
        try:
            if turn.message_ids:
                properties["message_count"] = len(turn.message_ids)
        except Exception:
            pass

        self._reporter.enqueue({
            "name": "agent_turn",
            "id": uuid.uuid4().hex,
            "time": int(turn.start_ts * 1000),
            "properties": properties,
        })

    @staticmethod
    def _get_session_id() -> str:
        return _current_session_key()
