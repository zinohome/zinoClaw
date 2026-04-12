"""ToolSecurityLayer — zero-invasion security for nanobot tool execution.

Architecture: Before (Policy Gate) -> Around (Execute) -> Result pipeline -> After (Audit)

After a tool returns, all results pass through a single ordered pipeline before the agent
sees them:

1. **Builtin max output** — optional cap; default is **10×** ``AgentLoop._TOOL_RESULT_MAX_CHARS``
   (only pathological sizes; see ``result_pipeline`` in ``tool-security-policy.json``).
   Implemented under ``tool_layer.result_pipeline``.
2. **Builtin DLP** — in ``enforce`` mode only; see ``tool_layer.dlp``.
3. **User plugins** — each ``~/.deskclaw/security-plugins/*.py`` may export
   ``transform_result(tool, params, result) -> Any`` (sync or async) and/or
   ``transform_results: list[Callable]`` (same signature). Plugins run **after** DLP so
   truncation cannot bypass scanning. ``on_after`` hooks remain audit-only and cannot
   change the return value.

Monkey-patches ToolRegistry.execute() at runtime; nanobot kernel is never modified.

Concrete helpers live in the ``tool_layer`` subpackage (policy, plugins, DLP, pipeline, registry patch).
"""

from __future__ import annotations

import asyncio
import inspect
import re
import sys
from typing import Any, Callable

from .approval import ApprovalChannel, HookContext
from .tool_layer.dlp import apply_dlp as apply_dlp_actions
from .tool_layer.dlp import scan_dlp as scan_dlp_text
from .tool_layer.paths import user_home
from .tool_layer.plugin_loader import default_plugin_dir, ensure_builtin_plugins, load_security_plugins
from .tool_layer.policy_ops import check_builtin_policy, init_default_policy, load_policy, reload_policy
from .tool_layer.registry_patch import install as install_registry_patch
from .tool_layer.registry_patch import uninstall as uninstall_registry_patch
from .tool_layer.result_pipeline import apply_result_pipeline, default_tool_result_max_chars
from .types import AuditRecord, DLPFinding, PolicyRule

# Backward-compatible alias for tests / callers
_default_tool_result_max_chars = default_tool_result_max_chars


class ToolSecurityLayer:
    """Zero-invasion security layer for nanobot tool execution.

    Extension points:
      - before_hooks: (gate) sync/async → {"allowed": False, ...} to deny.
      - around_hooks: (execute) async → return str to replace execution, None to pass.
      - after_hooks:  (audit)  sync   → receives AuditRecord.
      - result_transform_hooks: transform_result(tool, params, result) after builtin steps.
      - custom_dlp_patterns: dict[str, list[re.Pattern]]
      - Security plugins: ~/.deskclaw/security-plugins/*.py

    Policy JSON (``~/.deskclaw/tool-security-policy.json``) optional key ``result_pipeline``:
      - ``max_output_enabled`` (bool, default ``true``) — set ``false`` to disable the builtin
        size guard and handle output only in plugins.
      - ``max_output_chars`` (int, optional) — omit to use 10× ``AgentLoop._TOOL_RESULT_MAX_CHARS``.
    """

    def __init__(self, policy_path: str | None = None):
        self.mode: str = "monitor"  # enforce / monitor / disable
        self.policy: dict[str, PolicyRule] = {}
        self.audit_log: list[AuditRecord] = []
        self.before_hooks: list[Callable] = []
        self.around_hooks: list[Callable] = []
        self.after_hooks: list[Callable] = []
        self.result_transform_hooks: list[Callable] = []
        self.max_output_enabled: bool = True
        self.max_output_chars: int | None = None  # None → 10× kernel nominal (see result_pipeline)
        self.custom_dlp_patterns: dict[str, list[re.Pattern]] = {}
        self.dlp_enabled: bool = True
        self.dlp_on_critical: str = "block"
        self.dlp_on_high: str = "redact"
        self._original_execute = None
        self._plugin_dir = default_plugin_dir()
        self.approval_channel = ApprovalChannel()
        self._hook_context = HookContext(self.approval_channel)
        self._approval_lock = asyncio.Lock()

        if policy_path:
            load_policy(self, policy_path)
        else:
            default_path = user_home() / ".deskclaw" / "tool-security-policy.json"
            if default_path.exists():
                load_policy(self, str(default_path))
            else:
                init_default_policy(self)

        ensure_builtin_plugins(self)
        load_security_plugins(self)

    def _init_default_policy(self):
        init_default_policy(self)

    def _load_policy(self, path: str):
        load_policy(self, path)

    def reload_policy(self):
        reload_policy(self)

    def _ensure_builtin_plugins(self):
        ensure_builtin_plugins(self)

    def _load_security_plugins(self):
        load_security_plugins(self)

    def check_builtin_policy(self, tool_name: str, params: dict) -> tuple[bool, str]:
        return check_builtin_policy(self, tool_name, params)

    async def run_hooks(self, tool_name: str, params: dict) -> dict | None:
        """Run plugin before-hooks. Always authoritative — not controlled by mode.

        Plugin decisions override default policy because they represent explicit
        user-defined logic (e.g. interactive approval where user clicks Cancel).

        Returns None if all hooks pass, or the first denial dict:
          {"allowed": False, "reason": "...", "message": "..."}
        Plugins control the agent-facing message via the "message" field.
        """
        for hook in self.before_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    result = await hook(tool_name, params, ctx=self._hook_context)
                else:
                    result = hook(tool_name, params)
                if result and not result.get("allowed", True):
                    return result
            except Exception:
                print(
                    f"[Security] before-hook {getattr(hook, '__name__', hook)} "
                    f"raised for {tool_name}: {sys.exc_info()[1]}",
                    file=sys.stderr, flush=True,
                )
        return None

    async def run_around(self, tool_name: str, params: dict) -> str | None:
        """Run plugin around-hooks. First hook to return a non-None string wins.

        Around hooks replace normal tool execution (e.g. container sandbox).
        They run AFTER before-hooks (approval), so the approval gate is respected.
        Returns the result string, or None if no hook intercepted.
        """
        for hook in self.around_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    result = await hook(tool_name, params)
                else:
                    result = hook(tool_name, params)
                if result is not None:
                    return result
            except Exception:
                print(
                    f"[Security] around-hook {getattr(hook, '__name__', hook)} "
                    f"raised for {tool_name}: {sys.exc_info()[1]}",
                    file=sys.stderr, flush=True,
                )
        return None

    def resolve_approval(self, request_id: str, decision: dict) -> bool:
        """Resolve a pending approval request (called from WS inbound handler)."""
        return self.approval_channel.resolve(request_id, decision)

    def scan_dlp(self, result: str) -> list[DLPFinding]:
        return scan_dlp_text(
            result,
            dlp_enabled=self.dlp_enabled,
            custom_patterns=self.custom_dlp_patterns,
        )

    def apply_dlp(self, result: str, findings: list[DLPFinding]) -> tuple[str, str]:
        return apply_dlp_actions(
            result,
            findings,
            dlp_on_critical=self.dlp_on_critical,
            dlp_on_high=self.dlp_on_high,
        )

    async def _apply_result_pipeline(
        self, tool: str, params: dict, result: Any
    ) -> tuple[Any, list[DLPFinding], str]:
        return await apply_result_pipeline(self, tool, params, result)

    async def audit(self, record: AuditRecord):
        self.audit_log.append(record)
        if len(self.audit_log) > 5000:
            self.audit_log = self.audit_log[-2500:]

        for hook in self.after_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    await hook(record)
                else:
                    hook(record)
            except Exception:
                pass

    def install(self):
        install_registry_patch(self)

    def uninstall(self):
        uninstall_registry_patch(self)

    @staticmethod
    def normalize_tool_params(params: Any) -> dict:
        """Coerce LLM tool arguments to a dict.

        Some models emit a JSON array for a single tool call, e.g.
        ``write_file([{"path": "...", "content": "..."}])``, which would
        otherwise break security policy (expects ``dict`` with ``.items()``).
        """
        if params is None:
            return {}
        if isinstance(params, dict):
            return params
        if isinstance(params, list):
            if len(params) == 1 and isinstance(params[0], dict):
                return params[0]
            for el in params:
                if isinstance(el, dict):
                    return el
            return {}
        return {}

    @staticmethod
    def _brief_params(params: Any) -> str:
        if not params:
            return ""
        if isinstance(params, list):
            if len(params) == 1 and isinstance(params[0], dict):
                return ToolSecurityLayer._brief_params(params[0])
            return f"(list len={len(params)})"
        if not isinstance(params, dict):
            s = str(params)
            return s[:60] + ("\u2026" if len(s) > 60 else "")
        parts = []
        for k, v in list(params.items())[:2]:
            s = str(v)
            parts.append(f"{k}={s[:40]}{'\u2026' if len(s) > 40 else ''}")
        return ", ".join(parts)
