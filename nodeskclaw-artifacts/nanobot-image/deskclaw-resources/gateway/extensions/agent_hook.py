"""AgentHookAdapter -- bridges DeskClawExtension hooks into nanobot's AgentHook.

This adapter is passed to ``AgentLoop(hooks=[adapter])`` so that
extension iteration callbacks are invoked by nanobot's runner via
``CompositeHook._for_each_hook_safe``, which provides per-hook error
isolation automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nanobot.agent.hook import AgentHook, AgentHookContext

if TYPE_CHECKING:
    from .registry import ExtensionRegistry


class AgentHookAdapter(AgentHook):
    """Translates nanobot AgentHook lifecycle into ExtensionRegistry events."""

    def __init__(self, registry: ExtensionRegistry) -> None:
        super().__init__(reraise=False)
        self._registry = registry

    def wants_streaming(self) -> bool:
        for ext in self._registry.extensions:
            if ext.on_stream is not type(ext).__mro__[1].on_stream:
                return True
        return False

    async def before_iteration(self, context: AgentHookContext) -> None:
        await self._registry.fire_before_model(context)

    async def on_stream(self, context: AgentHookContext, delta: str) -> None:
        await self._registry.fire_stream(context, delta)

    async def on_stream_end(
        self, context: AgentHookContext, *, resuming: bool,
    ) -> None:
        await self._registry.fire_stream_end(context, resuming=resuming)

    async def before_execute_tools(self, context: AgentHookContext) -> None:
        await self._registry.fire_before_tools(context)

    async def after_iteration(self, context: AgentHookContext) -> None:
        await self._registry.fire_after_iteration(context)

    def finalize_content(
        self, context: AgentHookContext, content: str | None,
    ) -> str | None:
        return self._registry.fire_finalize_content(context, content)
