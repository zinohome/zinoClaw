"""Turn-level hook patch -- wraps AgentLoop._process_message to fire
on_turn_start / on_turn_end events on the extension registry.

Installs *after* perf patches so the chain is:
  original → perf_patch → turn_patch
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .registry import ExtensionRegistry


def install_turn_patch(registry: "ExtensionRegistry") -> None:
    from nanobot.agent.loop import AgentLoop

    _prev = AgentLoop._process_message

    async def _with_turn_hooks(
        self,
        msg,
        session_key=None,
        on_progress=None,
        on_stream=None,
        on_stream_end=None,
        **kwargs,
    ):
        key = session_key or msg.session_key
        try:
            await registry.fire_turn_start(key, msg.content)
        except Exception:
            logger.exception("[Extensions] fire_turn_start error")

        result = None
        try:
            result = await _prev(
                self, msg,
                session_key=session_key,
                on_progress=on_progress,
                on_stream=on_stream,
                on_stream_end=on_stream_end,
                **kwargs,
            )
            return result
        finally:
            response = result.content if result else None
            try:
                await registry.fire_turn_end(key, response)
            except Exception:
                logger.exception("[Extensions] fire_turn_end error")

    AgentLoop._process_message = _with_turn_hooks
    logger.info("[Extensions] Turn hook patch installed")
