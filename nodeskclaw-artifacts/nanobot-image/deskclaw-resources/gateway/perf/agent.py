"""Agent loop performance patches — tool progress, caching, non-blocking consolidation."""

from __future__ import annotations

import contextvars
import sys
import time
from typing import Any, Callable

from loguru import logger

_current_on_progress: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "_current_on_progress", default=None,
)


async def _safe_on_progress(on_progress, content, **kwargs):
    """Call on_progress with best-effort kwargs, falling back for older kernels.

    For tool_result calls, if the callback doesn't support the kwarg we skip
    silently — raw tool output should NOT leak to channels that don't expect it.
    """
    try:
        await on_progress(content, **kwargs)
    except TypeError:
        if kwargs.get("tool_result"):
            return
        try:
            await on_progress(content)
        except TypeError:
            pass


# ── 1. Per-tool result progress ─────────────────────────────────────


def patch_tool_result_progress(agent_loop) -> None:
    """Emit tool_result progress after each tool execution.

    Upstream's _run_agent_loop handles parallel execution and the main loop.
    This patch adds the gateway-specific feature of sending individual tool
    completion events to the UI — upstream only sends tool_hint (start) but
    not per-tool results.

    Implementation:
    1. Wrap _process_message to capture on_progress onto the instance.
    2. Wrap tools.execute to emit tool_result after each execution.
    """
    from nanobot.agent.loop import AgentLoop

    _orig_pm = AgentLoop._process_message

    async def _capturing_process_message(
        self, msg, session_key=None, on_progress=None,
        on_stream=None, on_stream_end=None, **kwargs,
    ):
        try:
            from gateway.security.approval import current_session_id
            current_session_id.set(session_key)
        except Exception:
            pass
        try:
            import sys as _sys
            _lg = _sys.modules.get("security_plugin.loop_guard")
            if _lg and hasattr(_lg, "reset_turn"):
                _lg.reset_turn(session_key)
        except Exception:
            pass

        token = _current_on_progress.set(on_progress)
        try:
            return await _orig_pm(
                self, msg, session_key=session_key, on_progress=on_progress,
                on_stream=on_stream, on_stream_end=on_stream_end, **kwargs,
            )
        finally:
            _current_on_progress.reset(token)

    AgentLoop._process_message = _capturing_process_message

    registry = agent_loop.tools

    async def _progress_execute(name, args):
        cls_execute = type(registry).execute
        try:
            result = await cls_execute(registry, name, args)
        except Exception as exc:
            progress = _current_on_progress.get(None)
            if progress:
                await _safe_on_progress(
                    progress, f"Error: {exc}", tool_result=True, tool_name=name,
                )
            raise
        progress = _current_on_progress.get(None)
        if progress:
            await _safe_on_progress(progress, result, tool_result=True, tool_name=name)
        return result

    registry.execute = _progress_execute
    print("[Perf] Tool result progress patch installed", file=sys.stderr, flush=True)


# ── 2. Session history hard cap ─────────────────────────────────────

_HISTORY_HARD_CAP = 200


def patch_history_cap() -> None:
    """Cap Session.get_history(max_messages=0) to avoid flooding the context.

    In Python ``list[-0:]`` equals ``list[0:]`` (all items), so callers
    passing ``max_messages=0`` to mean "no limit" accidentally get the
    full unconsolidated history — potentially hundreds of tool-call
    messages from a previous turn that hit the iteration cap.
    """
    from nanobot.session.manager import Session

    _orig_get_history = Session.get_history

    def _capped_get_history(self, max_messages: int = 500) -> list[dict]:
        if max_messages <= 0:
            max_messages = _HISTORY_HARD_CAP
        return _orig_get_history(self, max_messages=max_messages)

    Session.get_history = _capped_get_history
    print("[Perf] Session history hard-cap patch installed", file=sys.stderr, flush=True)


# ── 3. Cached ToolRegistry.get_definitions() ───────────────────────


def patch_tool_definitions_cache() -> None:
    """Cache get_definitions() — invalidated on register/unregister."""
    from nanobot.agent.tools.registry import ToolRegistry

    _orig_get = ToolRegistry.get_definitions
    _orig_register = ToolRegistry.register
    _orig_unregister = ToolRegistry.unregister

    def _cached_get_definitions(self) -> list[dict[str, Any]]:
        cache = getattr(self, "_perf_defs_cache", None)
        if cache is not None:
            return cache
        result = _orig_get(self)
        self._perf_defs_cache = result
        return result

    def _invalidating_register(self, tool) -> None:
        self._perf_defs_cache = None
        return _orig_register(self, tool)

    def _invalidating_unregister(self, name: str) -> None:
        self._perf_defs_cache = None
        return _orig_unregister(self, name)

    ToolRegistry.get_definitions = _cached_get_definitions
    ToolRegistry.register = _invalidating_register
    ToolRegistry.unregister = _invalidating_unregister
    print("[Perf] Tool definitions cache patch installed", file=sys.stderr, flush=True)


# ── 4. Cached ContextBuilder.build_system_prompt() ─────────────────

_SP_CACHE_TTL = 30.0  # seconds


def patch_system_prompt_cache() -> None:
    """Cache build_system_prompt() with a short TTL to avoid repeated disk I/O."""
    from nanobot.agent.context import ContextBuilder

    _orig_build = ContextBuilder.build_system_prompt

    def _cached_build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        key = tuple(skill_names) if skill_names else ()
        now = time.monotonic()
        prev = getattr(self, "_perf_sp_cache", None)
        if prev is not None:
            cached_key, cached_ts, cached_val = prev
            if cached_key == key and (now - cached_ts) < _SP_CACHE_TTL:
                return cached_val
        result = _orig_build(self, skill_names)
        self._perf_sp_cache = (key, now, result)
        return result

    ContextBuilder.build_system_prompt = _cached_build_system_prompt
    print("[Perf] System prompt cache patch installed", file=sys.stderr, flush=True)


# ── 5. Non-blocking memory consolidation ───────────────────────────


def patch_nonblocking_consolidation(agent_loop) -> None:
    """Replace blocking pre-request memory consolidation with background scheduling.

    The original _process_message awaits maybe_consolidate_by_tokens before
    running the agent loop, which can trigger an LLM call (5-10s+).
    We patch the consolidator so it always schedules consolidation in the
    background and returns immediately.
    """
    mc = getattr(agent_loop, "memory_consolidator", None)
    if mc is None:
        logger.warning("AgentLoop has no memory_consolidator — skipping non-blocking consolidation patch")
        return
    _original = mc.maybe_consolidate_by_tokens.__func__

    async def _nonblocking_maybe_consolidate(self, session) -> None:
        if not session.messages or self.context_window_tokens <= 0:
            return

        lock = self.get_lock(session.key)
        if lock.locked():
            return

        async with lock:
            budget = self.context_window_tokens - self.max_completion_tokens - self._SAFETY_BUFFER
            estimated, source = self.estimate_session_prompt_tokens(session)
            if estimated <= 0 or estimated < budget:
                return

        agent_loop._schedule_background(_original(self, session))
        logger.debug(
            "Memory consolidation deferred to background for {}",
            session.key,
        )

    import types
    mc.maybe_consolidate_by_tokens = types.MethodType(
        _nonblocking_maybe_consolidate, mc
    )
    print("[Perf] Non-blocking memory consolidation patch installed", file=sys.stderr, flush=True)
