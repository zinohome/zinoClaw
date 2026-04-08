"""Gateway performance patches — zero nanobot kernel invasion.

All optimizations are applied via monkey-patch during GatewayAgent.start(),
following the same pattern as ToolSecurityLayer.install().

Patches:
  1. Per-tool result progress for UI                       (agent.py)
  2. Session history hard cap for get_history(0)            (agent.py)
  3. Cached ToolRegistry.get_definitions()                 (agent.py)
  4. Cached ContextBuilder.build_system_prompt()            (agent.py)
  5. Non-blocking memory consolidation                     (agent.py)
  6. Channel URL media pre-download                        (channels.py)
  7. Feishu reaction auto-cleanup                          (channels.py)
"""

from __future__ import annotations

import sys

from loguru import logger

from .agent import (
    patch_tool_result_progress,
    patch_history_cap,
    patch_tool_definitions_cache,
    patch_system_prompt_cache,
    patch_nonblocking_consolidation,
)
from .channels import (
    patch_channel_url_media,
    patch_feishu_reaction_cleanup,
)


def install_perf_patches(agent_loop) -> None:
    """Apply all performance patches to the given AgentLoop instance.

    Call this once after AgentLoop is constructed (in GatewayAgent.start).
    """
    _patches: list[tuple[str, ...]] = [
        ("tool_result_progress", lambda: patch_tool_result_progress(agent_loop)),
        ("history_cap",          patch_history_cap),
        ("tool_definitions_cache", patch_tool_definitions_cache),
        ("system_prompt_cache",  patch_system_prompt_cache),
        ("channel_url_media",    patch_channel_url_media),
        ("feishu_reaction",      patch_feishu_reaction_cleanup),
        ("nonblocking_consolidation", lambda: patch_nonblocking_consolidation(agent_loop)),
    ]
    for name, fn in _patches:
        try:
            fn()
        except Exception as exc:
            logger.warning("Perf patch [{}] skipped: {}", name, exc)
    print("[Perf] All performance patches installed", file=sys.stderr, flush=True)
