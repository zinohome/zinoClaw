"""Tool result post-processing: size guard, DLP, user transform_result hooks."""

from __future__ import annotations

import inspect
import logging
from typing import TYPE_CHECKING, Any

from .dlp import apply_dlp as apply_dlp_actions
from .dlp import scan_dlp as scan_dlp_text
from ..types import DLPFinding

if TYPE_CHECKING:
    from ..layer import ToolSecurityLayer

logger = logging.getLogger("deskclaw.security")

# Nanobot kernel nominal budget (when AgentLoop cannot be read)
_KERNEL_TOOL_RESULT_NOMINAL_FALLBACK = 16_000
# Gateway size guard: only replace pathologically large returns, not “normal large” vs kernel trim
_DEFAULT_SIZE_GUARD_MULTIPLIER = 10


def kernel_tool_result_nominal_chars() -> int:
    """Return the nominal per-result character budget used by the agent loop."""
    try:
        from nanobot.config.schema import AgentDefaults

        return int(AgentDefaults().max_tool_result_chars)
    except Exception:
        logger.warning(
            "[Security] Cannot read AgentDefaults.max_tool_result_chars; using nominal fallback %s",
            _KERNEL_TOOL_RESULT_NOMINAL_FALLBACK,
        )
        return _KERNEL_TOOL_RESULT_NOMINAL_FALLBACK


def default_tool_result_max_chars() -> int:
    """Kernel nominal limit — for diagnostics/tests; not the gateway guard ceiling."""
    return kernel_tool_result_nominal_chars()


def default_security_max_output_chars() -> int:
    """Default gateway size-guard ceiling: nominal × :data:`_DEFAULT_SIZE_GUARD_MULTIPLIER`."""
    return kernel_tool_result_nominal_chars() * _DEFAULT_SIZE_GUARD_MULTIPLIER


def tool_result_max_limit(max_output_chars: int | None) -> int:
    if max_output_chars is not None:
        return max_output_chars
    return default_security_max_output_chars()


def estimate_tool_result_text_size(result: Any) -> int | None:
    """Estimated text size for guard, or None to skip (e.g. list with no text blocks).

    For ``list`` results (multimodal), v1 sums ``len(text)`` for items with
    ``type`` in ``text`` / ``input_text`` / ``output_text``, plus raw ``str`` items.
    Pure-image lists (no such text) skip the guard so structure is preserved.
    Other types use ``len(str(result))``.
    """
    if isinstance(result, str):
        return len(result)
    if isinstance(result, list):
        total = 0
        saw_text = False
        for item in result:
            if isinstance(item, str):
                saw_text = True
                total += len(item)
            elif isinstance(item, dict):
                t = item.get("type")
                if t not in ("text", "input_text", "output_text"):
                    continue
                text = item.get("text")
                if isinstance(text, str):
                    saw_text = True
                    total += len(text)
        return total if saw_text else None
    return len(str(result))


def oversized_tool_result_message(approx_chars: int, limit: int, tool: str) -> str:
    return (
        f"[SECURITY] Tool output exceeded the configured size limit "
        f"(approx {approx_chars} chars, limit {limit}; tool={tool}). "
        "The full result was not passed to the agent. "
        "Try a smaller read_file `limit`, a higher `offset`, or a new session.\n"
        f"[安全] 工具输出超过大小限制（约 {approx_chars} 字符，上限 {limit}；工具={tool}）。"
        "完整结果未返回给智能体。请缩小 read_file 的 limit、提高 offset，或新开会话。"
    )


def builtin_size_step(
    *,
    max_output_enabled: bool,
    max_output_chars: int | None,
    tool: str,
    result: Any,
) -> Any:
    if not max_output_enabled:
        return result
    est = estimate_tool_result_text_size(result)
    if est is None:
        return result
    limit = tool_result_max_limit(max_output_chars)
    if est <= limit:
        return result
    return oversized_tool_result_message(est, limit, tool)


def builtin_dlp_transform(
    *,
    mode: str,
    dlp_enabled: bool,
    dlp_on_critical: str,
    dlp_on_high: str,
    custom_dlp_patterns: dict,
    result: Any,
) -> tuple[Any, list[DLPFinding], str]:
    if mode != "enforce" or not dlp_enabled:
        return result, [], ""
    result_str = str(result) if result is not None else ""
    findings = scan_dlp_text(
        result_str,
        dlp_enabled=dlp_enabled,
        custom_patterns=custom_dlp_patterns,
    )
    if not findings:
        return result, [], ""
    processed, action = apply_dlp_actions(
        result_str,
        findings,
        dlp_on_critical=dlp_on_critical,
        dlp_on_high=dlp_on_high,
    )
    if action in ("blocked", "redacted"):
        return processed, findings, action
    return result, findings, action


async def apply_result_pipeline(
    layer: ToolSecurityLayer,
    tool: str,
    params: dict,
    result: Any,
) -> tuple[Any, list[DLPFinding], str]:
    result = builtin_size_step(
        max_output_enabled=layer.max_output_enabled,
        max_output_chars=layer.max_output_chars,
        tool=tool,
        result=result,
    )
    result, dlp_findings, dlp_action = builtin_dlp_transform(
        mode=layer.mode,
        dlp_enabled=layer.dlp_enabled,
        dlp_on_critical=layer.dlp_on_critical,
        dlp_on_high=layer.dlp_on_high,
        custom_dlp_patterns=layer.custom_dlp_patterns,
        result=result,
    )
    for hook in layer.result_transform_hooks:
        prev = result
        try:
            if inspect.iscoroutinefunction(hook):
                result = await hook(tool, params, result)
            else:
                result = hook(tool, params, result)
        except Exception as e:
            logger.warning(
                "[Security] transform_result hook %r failed: %s",
                getattr(hook, "__name__", hook),
                e,
            )
            result = prev
    return result, dlp_findings, dlp_action
