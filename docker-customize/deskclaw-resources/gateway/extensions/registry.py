"""Extension registry -- manages loaded instances and dispatches events."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from .base import DeskClawExtension, ExtensionContext
from .loader import DiscoveredExtension, discover_extensions


class ExtensionRegistry:
    """Central registry for all discovered DeskClaw extensions.

    Tracks both enabled and disabled extensions so MCP tools can list,
    toggle, and inspect any installed extension.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    # ── Lifecycle ────────────────────────────────────────────────────

    async def load_and_activate(
        self,
        workspace: Path,
        extensions_dir: Path | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Discover extensions, instantiate enabled ones, and call ``activate``."""
        ext_dir = extensions_dir or (Path.home() / ".deskclaw" / "extensions")
        global_config = config or {}

        discovered = discover_extensions(ext_dir)

        for d in discovered:
            ctx = ExtensionContext(
                workspace=workspace,
                extensions_dir=ext_dir,
                config={**global_config, **d.config},
            )
            entry = _Entry(
                discovered=d,
                enabled=d.enabled,
            )
            if d.instance and d.enabled:
                try:
                    await d.instance.activate(ctx)
                    entry.activated = True
                except Exception:
                    logger.exception(
                        "[Extensions] activate() failed for {}", d.name,
                    )
            self._entries[d.name] = entry

    async def deactivate_all(self) -> None:
        for entry in self._entries.values():
            if entry.activated and entry.enabled and entry.instance:
                try:
                    await entry.instance.deactivate()
                except Exception:
                    logger.exception(
                        "[Extensions] deactivate() failed for {}",
                        entry.discovered.name,
                    )
                entry.activated = False

    async def reload(
        self,
        workspace: Path,
        extensions_dir: Path | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Deactivate all, clear, and re-discover from disk."""
        await self.deactivate_all()
        self._entries.clear()
        await self.load_and_activate(workspace, extensions_dir, config)

    # ── Query ────────────────────────────────────────────────────────

    @property
    def extensions(self) -> list[DeskClawExtension]:
        """Return only enabled extension instances (for event dispatch)."""
        return [
            e.instance
            for e in self._entries.values()
            if e.enabled and e.instance
        ]

    def list_all(self) -> list[dict[str, Any]]:
        """List all discovered extensions (including disabled), sorted by priority."""
        results = []
        for e in self._entries.values():
            d = e.discovered
            inst = e.instance
            results.append({
                "name": d.name,
                "version": inst.version if inst else "",
                "description": inst.description if inst else self._readme_summary(d.readme),
                "enabled": e.enabled,
                "activated": e.activated,
                "priority": d.priority,
                "directory": str(d.directory),
                "has_readme": bool(d.readme),
            })
        results.sort(key=lambda r: r["priority"])
        return results

    def get_discovered(self, name: str) -> DiscoveredExtension | None:
        """Get the DiscoveredExtension by name (for MCP info/config tools)."""
        entry = self._entries.get(name)
        return entry.discovered if entry else None

    def toggle(self, name: str, enabled: bool) -> bool:
        """Enable or disable an extension by name (runtime only).  Returns True if found."""
        entry = self._entries.get(name)
        if entry is None:
            return False
        entry.enabled = enabled
        return True

    @staticmethod
    def _readme_summary(readme: str) -> str:
        """Extract first non-heading, non-empty line from README as description."""
        for line in readme.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped[:120]
        return ""

    # ── Event dispatch helpers ───────────────────────────────────────

    async def _fire(self, method: str, *args: Any, **kwargs: Any) -> None:
        for ext in self.extensions:
            try:
                await getattr(ext, method)(*args, **kwargs)
            except Exception:
                logger.exception(
                    "[Extensions] {}.{}() error", ext.name, method,
                )

    # -- Agent iteration shortcuts ------------------------------------

    async def fire_before_model(self, ctx: Any) -> None:
        await self._fire("on_before_model", ctx)

    async def fire_after_iteration(self, ctx: Any) -> None:
        await self._fire("on_after_iteration", ctx)

    async def fire_before_tools(self, ctx: Any) -> None:
        await self._fire("on_before_tools", ctx)

    async def fire_stream(self, ctx: Any, delta: str) -> None:
        await self._fire("on_stream", ctx, delta)

    async def fire_stream_end(self, ctx: Any, *, resuming: bool) -> None:
        await self._fire("on_stream_end", ctx, resuming=resuming)

    def fire_finalize_content(self, ctx: Any, content: str | None) -> str | None:
        for ext in self.extensions:
            try:
                content = ext.on_finalize_content(ctx, content)
            except Exception:
                logger.exception(
                    "[Extensions] {}.on_finalize_content() error", ext.name,
                )
        return content

    # -- Turn shortcuts -----------------------------------------------

    async def fire_turn_start(self, session_key: str, message: str) -> None:
        await self._fire("on_turn_start", session_key, message)

    async def fire_turn_end(self, session_key: str, response: str | None) -> None:
        await self._fire("on_turn_end", session_key, response)

    # -- Memory shortcuts ---------------------------------------------

    async def fire_memory_consolidate(self, session_key: str, summary: str) -> None:
        await self._fire("on_memory_consolidate", session_key, summary)

    async def fire_memory_archive(self, session_key: str, chunk: list[dict]) -> None:
        await self._fire("on_memory_archive", session_key, chunk)


# ── Internal ─────────────────────────────────────────────────────────

class _Entry:
    __slots__ = ("discovered", "enabled", "activated")

    def __init__(self, discovered: DiscoveredExtension, enabled: bool) -> None:
        self.discovered = discovered
        self.enabled = enabled
        self.activated = False

    @property
    def instance(self) -> DeskClawExtension | None:
        return self.discovered.instance
