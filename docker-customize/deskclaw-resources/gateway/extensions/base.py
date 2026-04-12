"""Base class and context types for DeskClaw extensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nanobot.agent.hook import AgentHookContext


@dataclass
class ExtensionContext:
    """Read-only context provided to extensions on activation."""

    workspace: Path
    extensions_dir: Path
    config: dict[str, Any] = field(default_factory=dict)


class DeskClawExtension:
    """Base class for DeskClaw Agent extensions.

    Users subclass this and override only the hooks they need.
    Drop the file into ``~/.deskclaw/extensions/`` and it takes effect
    on the next gateway start (or after ``extension_reload``).

    Hook domains
    ------------
    * **Agent Iteration** -- fires during each LLM request/tool cycle
    * **Turn** -- fires once per user message (wrapping all iterations)
    * **Tool Execution** -- fires around individual tool calls
    * **Memory** -- fires when the consolidator archives or trims history
    """

    name: str = ""
    version: str = "1.0"
    description: str = ""

    # ── Lifecycle ────────────────────────────────────────────────────

    async def activate(self, ctx: ExtensionContext) -> None:
        """Called once when the extension is loaded.  Use for initialisation."""

    async def deactivate(self) -> None:
        """Called when the extension is unloaded.  Use for cleanup."""

    # ── Agent Iteration (bridged via AgentHookAdapter → AgentHook) ──

    async def on_before_model(self, ctx: AgentHookContext) -> None:
        """Before each LLM request.  ``ctx.messages`` is mutable."""

    async def on_after_iteration(self, ctx: AgentHookContext) -> None:
        """After each iteration (tools executed or final response).

        ``ctx.tool_results``, ``ctx.tool_events``, ``ctx.final_content``
        are populated depending on the iteration outcome.
        """

    async def on_before_tools(self, ctx: AgentHookContext) -> None:
        """Before the tool-call batch is executed."""

    async def on_stream(self, ctx: AgentHookContext, delta: str) -> None:
        """Each streaming content chunk from the LLM."""

    async def on_stream_end(self, ctx: AgentHookContext, *, resuming: bool) -> None:
        """End of a streaming segment.

        *resuming=True* means tool calls follow; *False* means final.
        """

    def on_finalize_content(
        self, ctx: AgentHookContext, content: str | None,
    ) -> str | None:
        """Post-process assistant text before it is persisted.

        Return the (possibly modified) content.
        """
        return content

    # ── Turn (轮次) ─────────────────────────────────────────────────

    async def on_turn_start(self, session_key: str, message: str) -> None:
        """A new user turn begins (before any LLM iteration)."""

    async def on_turn_end(self, session_key: str, response: str | None) -> None:
        """The turn is complete and the final response has been produced."""

    # ── Tool Execution (bridged via SecurityBridge → ToolSecurityLayer)

    async def on_tool_start(
        self, tool: str, params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Before a single tool call.

        Return ``None`` to allow, or a dict ``{"allowed": False,
        "reason": "...", "message": "..."}`` to deny.
        """
        return None

    async def on_tool_end(self, record: Any) -> None:
        """After a tool call, with the ``AuditRecord``."""

    async def on_tool_intercept(
        self, tool: str, params: dict[str, Any],
    ) -> str | None:
        """Replace tool execution entirely.

        Return a result string to short-circuit, or ``None`` to proceed.
        """
        return None

    def on_tool_result_transform(
        self, tool: str, params: dict[str, Any], result: str,
    ) -> str:
        """Post-process a tool's return value before the agent sees it."""
        return result

    # ── Memory ──────────────────────────────────────────────────────

    async def on_memory_consolidate(
        self, session_key: str, summary: str,
    ) -> None:
        """After history messages are consolidated into a summary."""

    async def on_memory_archive(
        self, session_key: str, chunk: list[dict[str, Any]],
    ) -> None:
        """When a trimmed message chunk is archived to long-term storage."""
