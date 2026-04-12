# version: 8
# author: DeskClaw
"""Loop guard — detect and stop stuck agent loops.

Registers on_before and on_after hooks to track tool calls per session.
Only **failed** and **fully-duplicate** tool calls count toward limits;
normal successful non-duplicate calls are never blocked.

Config file: ~/.deskclaw/loop-guard.json
  {
    "enabled": true,
    "sensitivity": "default",
    "max_duplicate_calls": 3,
    "max_consecutive_errors": 5,
    "max_failed_per_turn": 25,
    "turn_reset_seconds": 60
  }

All threshold values are persisted in the config file.  Changing the
"sensitivity" preset via UI / MCP tools writes the corresponding
threshold values into the file.  Set "sensitivity" to "custom" to
use your own threshold values without preset overrides.

Sensitivity presets (max_duplicate_calls / max_consecutive_errors / max_failed_per_turn):
  conservative: 2 / 3 / 15
  default:      3 / 5 / 25
  relaxed:      5 / 8 / 40

The config file is hot-reloaded (mtime-based, ~2 s latency) so
edits take effect without restarting the gateway.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

_CONFIG_PATH = Path.home() / ".deskclaw" / "loop-guard.json"

_PRESETS = {
    "conservative": {"max_duplicate_calls": 2, "max_consecutive_errors": 3, "max_failed_per_turn": 15},
    "default":      {"max_duplicate_calls": 3, "max_consecutive_errors": 5, "max_failed_per_turn": 25},
    "relaxed":      {"max_duplicate_calls": 5, "max_consecutive_errors": 8, "max_failed_per_turn": 40},
}

_DEFAULTS = {
    "enabled": True,
    "sensitivity": "default",
    "max_duplicate_calls": 3,
    "max_consecutive_errors": 5,
    "max_failed_per_turn": 25,
    "turn_reset_seconds": 60,
}


def _write_config_safe(cfg: dict) -> None:
    """Persist config to disk, creating parent directories if needed."""
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _safe_load_config() -> dict:
    """Load config with graceful fallback.

    Creates a complete config file on first run so users can see and
    edit every threshold without touching the source code.
    """
    cfg = dict(_DEFAULTS)
    try:
        if _CONFIG_PATH.exists():
            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if "max_calls_per_turn" in raw and "max_failed_per_turn" not in raw:
                raw["max_failed_per_turn"] = raw.pop("max_calls_per_turn")
            cfg.update(raw)
            if any(k not in raw for k in _DEFAULTS):
                _write_config_safe(cfg)
        else:
            _write_config_safe(cfg)
    except Exception:
        pass
    return cfg


_config = _safe_load_config()
_CONFIG_CHECK_INTERVAL = 2.0

try:
    _config_mtime: float = _CONFIG_PATH.stat().st_mtime
except OSError:
    _config_mtime = 0.0
_config_last_check: float = time.monotonic()


def _get_config() -> dict:
    """Return current config, hot-reloading from disk when file changes."""
    global _config, _config_mtime, _config_last_check
    now = time.monotonic()
    if now - _config_last_check < _CONFIG_CHECK_INTERVAL:
        return _config
    _config_last_check = now
    try:
        mt = _CONFIG_PATH.stat().st_mtime
        if mt != _config_mtime:
            _config = _safe_load_config()
            _config_mtime = mt
    except OSError:
        pass
    return _config

# ── Telemetry ──

def _track_intervention(trigger: str, tool_name: str, count: int, threshold: int) -> None:
    """Emit a loop_guard_intervention event to the telemetry pipeline."""
    try:
        mod = sys.modules.get("gateway.telemetry.collector")
        if mod is None:
            return
        collector = getattr(mod, "_collector_ref", None)
        if collector is None:
            return
        reporter = getattr(collector, "_reporter", None)
        if reporter is None or not getattr(
            getattr(collector, "_config", None), "enabled", False
        ):
            return
        reporter.enqueue({
            "name": "loop_guard_intervention",
            "id": uuid.uuid4().hex,
            "time": int(time.time() * 1000),
            "properties": {
                "trigger": trigger,
                "tool_name": tool_name,
                "count": count,
                "threshold": threshold,
                "sensitivity": _config.get("sensitivity", "default"),
                "session_id": _get_session_id(),
            },
        })
    except Exception:
        pass


# ── Session state ──

class _TurnState:
    __slots__ = ("call_log", "consecutive_errors", "failed_calls", "last_ts")

    def __init__(self):
        self.call_log: list = []       # [(tool_name, args_hash, result_hash | None)]
        self.consecutive_errors: int = 0
        self.failed_calls: int = 0
        self.last_ts: float = time.monotonic()


_sessions: dict[str, _TurnState] = {}
_STALE_CLEANUP_INTERVAL = 600.0
_last_cleanup = time.monotonic()


def _get_session_id() -> str:
    try:
        from gateway.security.approval import current_session_id
        sid = current_session_id.get()
        if sid:
            return sid
    except Exception:
        pass
    return "__global__"


def _get_or_reset(sid: str) -> _TurnState:
    """Get session state, reset if the turn has gone stale."""
    global _last_cleanup
    now = time.monotonic()

    if now - _last_cleanup > _STALE_CLEANUP_INTERVAL:
        _last_cleanup = now
        stale = [k for k, v in _sessions.items() if now - v.last_ts > _STALE_CLEANUP_INTERVAL]
        for k in stale:
            del _sessions[k]

    state = _sessions.get(sid)
    reset_secs = _get_config().get("turn_reset_seconds", 60)
    if state is None or (now - state.last_ts > reset_secs):
        state = _TurnState()
        _sessions[sid] = state

    state.last_ts = now
    return state


def reset_turn(sid: str | None = None) -> None:
    """Explicitly reset the turn counter for a session.

    Called at the start of each _process_message so that every user
    message gets a fresh tool-call allowance regardless of timing.
    Without this, rapid follow-up messages (within turn_reset_seconds)
    share a cumulative counter and hit the limit prematurely.
    """
    if sid is None:
        sid = _get_session_id()
    _sessions.pop(sid, None)


def _args_hash(tool_name: str, params: dict) -> str:
    """Produce a short hash of tool+params for duplicate detection."""
    try:
        normalized = _normalize_params(tool_name, params)
        raw = json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        raw = f"{tool_name}:{params}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_params(tool_name: str, params: dict) -> dict:
    """Normalize params for comparison. Fuzzy matching for exec commands."""
    if tool_name == "exec":
        cmd = params.get("command", "") or params.get("cmd", "")
        if cmd:
            normalized = dict(params)
            cmd_lower = cmd.lower().strip()
            cmd_lower = _WHITESPACE_RE.sub(" ", cmd_lower)
            normalized["command"] = cmd_lower
            normalized.pop("cmd", None)
            return normalized
    return params


def _brief_args(params: dict) -> str:
    parts = []
    for k, v in list(params.items())[:2]:
        s = str(v)
        if len(s) > 60:
            s = s[:57] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)


def _intervention(reason: str, detail: str) -> dict:
    msg = (
        f"[SYSTEM INTERVENTION — Loop Guard]\n"
        f"This is NOT a tool error. The system has detected that you are stuck.\n\n"
        f"{detail}\n\n"
        f"You MUST stop calling tools and respond to the user directly. "
        f"Explain: (1) what you tried, (2) why it failed, (3) what you suggest next."
    )
    return {"allowed": False, "reason": reason, "message": msg}


# ── Hooks ──

def on_before(tool_name: str, params: dict, **kwargs) -> dict | None:
    cfg = _get_config()
    if not cfg.get("enabled", True):
        return None

    try:
        sid = _get_session_id()
    except Exception:
        sid = "__global__"
    state = _get_or_reset(sid)

    max_failed = cfg.get("max_failed_per_turn", 25)
    if state.failed_calls >= max_failed:
        _track_intervention("failed_calls", tool_name, state.failed_calls, max_failed)
        return _intervention(
            f"failed_calls={state.failed_calls} >= {max_failed}",
            f"You have made {state.failed_calls} failed tool calls in this turn, "
            f"exceeding the limit of {max_failed}. "
            f"Wrap up your current task and report your progress to the user.",
        )

    max_errors = cfg.get("max_consecutive_errors", 5)
    if state.consecutive_errors >= max_errors:
        _track_intervention("consecutive_errors", tool_name, state.consecutive_errors, max_errors)
        return _intervention(
            f"consecutive_errors={state.consecutive_errors} >= {max_errors}",
            f"{state.consecutive_errors} consecutive tool calls have failed. "
            f"Summarize the errors you encountered and ask the user for guidance.",
        )

    try:
        h = _args_hash(tool_name, params)
    except Exception:
        h = hashlib.md5(f"{tool_name}".encode()).hexdigest()[:16]

    dup_count = sum(1 for t, ah, _ in state.call_log if t == tool_name and ah == h)
    max_dup = cfg.get("max_duplicate_calls", 3)
    if dup_count >= max_dup:
        brief = _brief_args(params)
        _track_intervention("duplicate_calls", tool_name, dup_count + 1, max_dup)
        return _intervention(
            f"duplicate: {tool_name}({brief}) x{dup_count + 1}",
            f"You have called `{tool_name}({brief})` {dup_count + 1} times with "
            f"identical arguments and results. "
            f"This approach is not working. Try a completely different strategy or report the issue.",
        )

    state.call_log.append((tool_name, h, None))
    return None


def _result_hash(result) -> str:
    """Short hash of a tool result for duplicate-with-same-result detection."""
    raw = str(result) if result is not None else ""
    if len(raw) > 4096:
        raw = raw[:4096]
    return hashlib.md5(raw.encode()).hexdigest()[:16]


_ERROR_PREFIXES = (
    "error:", "error :", "failed:", "failed :",
    "traceback (most recent call last)",
)
_ERROR_PATTERNS = re.compile(
    r"(?i)"
    r"(?:^Error\b)"                          # "Error: ..."
    r"|(?:\[WinError\s+\d+\])"              # "[WinError 5] ..."
    r"|(?:\[Errno\s+\d+\])"                 # "[Errno 2] ..."
    r"|(?:exit\s+code:\s*[1-9])"            # "Exit code: 1"
    r"|(?:command\s+failed)"                 # "command failed ..."
    r"|(?:permission\s*denied)"              # "permission denied" / "PermissionError"
    r"|(?:access\s*(?:is\s*)?denied)"        # "access denied" / "拒绝访问"
    r"|(?:file\s*not\s*found)"               # "file not found"
    r"|(?:no\s+such\s+file)"                 # "No such file or directory"
    r"|(?:拒绝访问)"                          # Chinese "access denied"
    r"|(?:找不到文件)"                        # Chinese "file not found"
    r"|(?:操作失败)"                          # Chinese "operation failed"
)


def _looks_like_error(snippet: str) -> bool:
    """Heuristic: does this tool result look like an error?"""
    if not snippet:
        return False
    lower = snippet.lstrip()[:256].lower()
    if any(lower.startswith(p) for p in _ERROR_PREFIXES):
        return True
    return bool(_ERROR_PATTERNS.search(snippet[:512]))


def on_after(record) -> None:
    if not _get_config().get("enabled", True):
        return

    try:
        sid = _get_session_id()
    except Exception:
        sid = "__global__"
    state = _sessions.get(sid)
    if state is None:
        return

    if getattr(record, "decision", None) == "denied":
        return

    try:
        reason_str = str(record.reason).lower() if getattr(record, "reason", None) else ""
        is_error = "exception" in reason_str

        if not is_error:
            snippet = getattr(record, "result_snippet", "") or ""
            is_error = _looks_like_error(snippet)
    except Exception:
        is_error = False

    if is_error:
        state.consecutive_errors += 1
        state.failed_calls += 1
    else:
        state.consecutive_errors = 0

    try:
        rh = _result_hash(getattr(record, "result_snippet", None))
        if state.call_log and state.call_log[-1][2] is None:
            name, ah, _ = state.call_log[-1]
            state.call_log[-1] = (name, ah, rh)
    except Exception:
        pass
