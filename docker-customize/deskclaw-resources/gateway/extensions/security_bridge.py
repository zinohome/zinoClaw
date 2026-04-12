"""SecurityBridge -- wires extension tool hooks into ToolSecurityLayer.

Extension methods ``on_tool_start``, ``on_tool_end``, ``on_tool_intercept``,
and ``on_tool_result_transform`` are registered as standard security-layer
hooks so they participate in the existing approval / audit pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from ..security.layer import ToolSecurityLayer
    from .registry import ExtensionRegistry


def install_security_bridge(
    registry: ExtensionRegistry,
    security: "ToolSecurityLayer",
) -> None:
    """Append extension-backed hooks to the security layer's hook lists."""

    async def _ext_on_before(tool: str, params: dict[str, Any], **_kw: Any) -> dict[str, Any] | None:
        for ext in registry.extensions:
            try:
                result = await ext.on_tool_start(tool, params)
                if result is not None:
                    return result
            except Exception:
                logger.exception("[Extensions] {}.on_tool_start() error", ext.name)
        return None

    async def _ext_on_around(tool: str, params: dict[str, Any]) -> str | None:
        for ext in registry.extensions:
            try:
                result = await ext.on_tool_intercept(tool, params)
                if result is not None:
                    return result
            except Exception:
                logger.exception("[Extensions] {}.on_tool_intercept() error", ext.name)
        return None

    async def _ext_on_after(record: Any) -> None:
        for ext in registry.extensions:
            try:
                await ext.on_tool_end(record)
            except Exception:
                logger.exception("[Extensions] {}.on_tool_end() error", ext.name)

    def _ext_transform_result(tool: str, params: dict[str, Any], result: str) -> str:
        for ext in registry.extensions:
            try:
                result = ext.on_tool_result_transform(tool, params, result)
            except Exception:
                logger.exception("[Extensions] {}.on_tool_result_transform() error", ext.name)
        return result

    security.before_hooks.append(_ext_on_before)
    security.around_hooks.append(_ext_on_around)
    security.after_hooks.append(_ext_on_after)
    security.result_transform_hooks.append(_ext_transform_result)

    logger.info("[Extensions] Security bridge installed")
