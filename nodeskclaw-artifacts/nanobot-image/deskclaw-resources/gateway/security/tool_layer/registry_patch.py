"""Monkey-patch nanobot ToolRegistry to route all tool execution through
the security layer.

Upstream's ``AgentRunner`` introduced a fast-path: ``prepare_call()`` returns
the resolved ``Tool`` instance and the runner calls ``tool.execute()``
directly, bypassing ``ToolRegistry.execute()``.  We patch *both* methods so
the security pipeline (policy → approval hooks → around hooks → DLP → audit)
is always in the loop regardless of the caller's code-path.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import TYPE_CHECKING

from .result_pipeline import apply_result_pipeline
from ..types import AuditRecord

if TYPE_CHECKING:
    from ..layer import ToolSecurityLayer

logger = logging.getLogger("deskclaw.security")


def install(security: ToolSecurityLayer) -> None:
    """Monkey-patch ToolRegistry.execute() *and* prepare_call()."""
    try:
        from nanobot.agent.tools.registry import ToolRegistry
    except ImportError:
        logger.warning("[Security] Cannot import ToolRegistry — skipping install")
        return

    if security._original_execute is not None:
        logger.info("[Security] Already installed, skipping")
        return

    security._original_execute = ToolRegistry.execute
    _orig_prepare_call = ToolRegistry.prepare_call

    # ── Wrap prepare_call: strip the tool so runner falls back to execute() ──
    def _routing_prepare_call(self_reg, name, params):
        tool, cast_params, error = _orig_prepare_call(self_reg, name, params)
        return None, cast_params, error

    ToolRegistry.prepare_call = _routing_prepare_call

    # ── Secured execute: policy → hooks → run → DLP → audit ──
    async def secured_execute(self_reg, name: str, params: dict):
        if security.mode == "disable":
            tool = self_reg._tools.get(name)
            if tool is None:
                return f"Error: Tool '{name}' not found."
            return await tool.execute(**security.normalize_tool_params(params))

        params = security.normalize_tool_params(params)
        brief = security._brief_params(params)

        # ── Phase 1a: Built-in policy (controlled by mode) ──
        allowed, reason = security.check_builtin_policy(name, params)
        if not allowed and security.mode == "enforce":
            record = AuditRecord(
                ts=time.time(), tool=name, params=params,
                decision="denied", reason=reason,
            )
            print(f"[Security] \U0001f6ab {name}({brief}) denied: {reason}",
                  file=sys.stderr, flush=True)
            await security.audit(record)
            return f"Error: Blocked by security policy \u2014 {reason}"

        # ── Phase 1b: Plugin hooks (serialized — one approval dialog at a time) ──
        async with security._approval_lock:
            hook_result = await security.run_hooks(name, params)

        if hook_result is not None:
            hook_reason = hook_result.get("reason", "Denied by security hook")
            record = AuditRecord(
                ts=time.time(), tool=name, params=params,
                decision="denied", reason=hook_reason,
            )
            print(f"[Security] \U0001f6ab {name}({brief}) hook-denied: {hook_reason}",
                  file=sys.stderr, flush=True)
            await security.audit(record)
            return hook_result.get(
                "message", f"Error: Blocked by security plugin \u2014 {hook_reason}",
            )

        # ── Phase 2: Execute (around hooks or direct tool call) ──
        _HINT = "\n\n[Analyze the error above and try a different approach.]"
        t0 = time.time()
        try:
            result = await security.run_around(name, params)
            if result is None:
                tool = self_reg._tools.get(name)
                if tool is None:
                    return f"Error: Tool '{name}' not found." + _HINT
                result = await tool.execute(**params)
            duration_ms = (time.time() - t0) * 1000
        except Exception as e:
            duration_ms = (time.time() - t0) * 1000
            record = AuditRecord(
                ts=time.time(), tool=name, params=params,
                decision="allowed", reason=f"exception: {e}",
                duration_ms=duration_ms, result_snippet=str(e)[:512],
            )
            print(f"[Security] \u274c {name}({brief}) [{duration_ms:.0f}ms] exception",
                  file=sys.stderr, flush=True)
            await security.audit(record)
            raise

        # ── Phase 3: DLP + audit ──
        result, dlp_findings, dlp_action = await apply_result_pipeline(
            security, name, params, result,
        )
        result_str = str(result) if result is not None else ""
        record = AuditRecord(
            ts=time.time(), tool=name, params=params,
            decision="allowed", duration_ms=duration_ms,
            result_size=len(result_str), dlp_findings=dlp_findings,
            dlp_action=dlp_action, result_snippet=result_str[:512],
        )
        if dlp_findings and dlp_action in ("blocked", "redacted"):
            cats = {f.category for f in dlp_findings}
            print(
                f"[Security] \u26a0\ufe0f  {name}({brief}) [{duration_ms:.0f}ms] "
                f"DLP:{','.join(cats)}->{dlp_action}",
                file=sys.stderr, flush=True,
            )

        print(f"[Security] \u2705 {name}({brief}) [{duration_ms:.0f}ms] {len(result_str)}b",
              file=sys.stderr, flush=True)
        await security.audit(record)
        return result

    ToolRegistry.execute = secured_execute

    print(f"[Security] Installed tool execution security layer (mode={security.mode})",
          file=sys.stderr, flush=True)


def uninstall(security: ToolSecurityLayer) -> None:
    if security._original_execute is None:
        return
    try:
        from nanobot.agent.tools.registry import ToolRegistry

        ToolRegistry.execute = security._original_execute
        security._original_execute = None
        logger.info("[Security] Uninstalled tool execution security layer")
    except ImportError:
        pass
