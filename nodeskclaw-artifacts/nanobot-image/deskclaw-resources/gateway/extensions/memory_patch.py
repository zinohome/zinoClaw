"""Memory hook patch -- wraps Consolidator methods to fire
on_memory_consolidate / on_memory_archive on the extension registry.

Same monkey-patch pattern as ``perf/agent.py``'s
``patch_nonblocking_consolidation``.
"""

from __future__ import annotations

import asyncio
import types
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.agent.loop import AgentLoop
    from .registry import ExtensionRegistry


def install_memory_patch(
    registry: "ExtensionRegistry",
    agent_loop: "AgentLoop",
) -> None:
    consolidator = getattr(agent_loop, "consolidator", None)
    if consolidator is None:
        logger.warning("[Extensions] No consolidator found, memory hooks skipped")
        return

    _orig_archive = consolidator.archive

    async def _hooked_archive(self_con, messages: list[dict]) -> bool:
        result = await _orig_archive(messages)
        if result:
            summary = ""
            try:
                last_entry = self_con.store.read_history_tail(1)
                if last_entry:
                    summary = last_entry[-1] if isinstance(last_entry, list) else str(last_entry)
            except Exception:
                pass
            try:
                await registry.fire_memory_consolidate("", summary)
            except Exception:
                logger.exception("[Extensions] fire_memory_consolidate error")
        return result

    consolidator.archive = types.MethodType(_hooked_archive, consolidator)

    _orig_archive_trimmed = consolidator.archive_trimmed_chunk

    async def _hooked_archive_trimmed(self_con, session_key: str, chunk: list[dict]) -> None:
        await _orig_archive_trimmed(session_key, chunk)
        try:
            await registry.fire_memory_archive(session_key, chunk)
        except Exception:
            logger.exception("[Extensions] fire_memory_archive error")

    consolidator.archive_trimmed_chunk = types.MethodType(
        _hooked_archive_trimmed, consolidator,
    )

    logger.info("[Extensions] Memory hook patch installed")
