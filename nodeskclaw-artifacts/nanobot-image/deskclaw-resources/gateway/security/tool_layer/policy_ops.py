"""Built-in policy: defaults, JSON load, path checks."""

from __future__ import annotations

import json
import logging
import os
import re
from fnmatch import fnmatch
from typing import TYPE_CHECKING

from .paths import user_home
from ..types import PolicyRule

if TYPE_CHECKING:
    from ..layer import ToolSecurityLayer

logger = logging.getLogger("deskclaw.security")


def path_matches(path: str, pattern: str) -> bool:
    path = os.path.expanduser(path)
    pattern = os.path.expanduser(pattern)
    return fnmatch(path, pattern) or fnmatch(os.path.basename(path), pattern)


def init_default_policy(layer: ToolSecurityLayer) -> None:
    workspace = os.environ.get(
        "DESKCLAW_WORKSPACE",
        str(user_home() / ".deskclaw" / "nanobot" / "workspace"),
    )
    layer.policy = {
        "read_file": PolicyRule(
            action="allow",
            allowed_paths=[f"{workspace}/**"],
            denied_paths=["**/.env", "**/.env.*", "**/credentials*", "**/*.pem", "**/*.key", "~/.ssh/**"],
        ),
        "write_file": PolicyRule(
            action="allow",
            allowed_paths=[f"{workspace}/**"],
            denied_paths=["**/.git/**", "/etc/**", "/usr/**"],
        ),
        "edit_file": PolicyRule(action="allow"),
        "list_dir": PolicyRule(action="allow"),
        "exec": PolicyRule(
            action="allow",
            sandbox="restricted",
            denied_commands=[
                re.compile(r"^sudo\b"),
                re.compile(r"\brm\s+-rf\s+/"),
                re.compile(r"\bcurl\b.*\|\s*(bash|sh)"),
                re.compile(r"\bchmod\s+777\b"),
                re.compile(r"\bshutdown\b"),
                re.compile(r"\breboot\b"),
            ],
        ),
        "web_fetch": PolicyRule(action="allow"),
        "web_search": PolicyRule(action="allow"),
        "message": PolicyRule(action="allow"),
        "spawn": PolicyRule(action="allow"),
    }


def load_policy(layer: ToolSecurityLayer, path: str) -> None:
    try:
        with open(path) as f:
            data = json.load(f)
        layer.mode = data.get("mode", "monitor")
        layer.dlp_enabled = data.get("dlp", {}).get("enabled", True)
        layer.dlp_on_critical = data.get("dlp", {}).get("on_critical", "block")
        layer.dlp_on_high = data.get("dlp", {}).get("on_high", "redact")
        rp = data.get("result_pipeline") or {}
        layer.max_output_enabled = rp.get("max_output_enabled", True)
        if "max_output_chars" in rp:
            layer.max_output_chars = int(rp["max_output_chars"])
        else:
            layer.max_output_chars = None
        for tool_name, rule_data in data.get("tools", {}).items():
            denied_cmds = [re.compile(p) for p in rule_data.get("denied_commands", [])]
            layer.policy[tool_name] = PolicyRule(
                action=rule_data.get("action", "allow"),
                denied_paths=rule_data.get("denied_paths", []),
                allowed_paths=rule_data.get("allowed_paths", []),
                denied_commands=denied_cmds,
                allowed_domains=rule_data.get("allowed_domains", []),
                denied_domains=rule_data.get("denied_domains", []),
                sandbox=rule_data.get("sandbox", "transparent"),
                max_timeout=rule_data.get("max_timeout", 60),
            )
        logger.info(f"[Security] Loaded policy from {path} (mode={layer.mode})")
    except Exception as e:
        logger.warning(f"[Security] Failed to load policy: {e}, using defaults")
        init_default_policy(layer)


def reload_policy(layer: ToolSecurityLayer) -> None:
    """Hot-reload policy from disk."""
    import sys as _sys

    default_path = user_home() / ".deskclaw" / "tool-security-policy.json"
    if default_path.exists():
        load_policy(layer, str(default_path))
        print(f"[Security] Policy reloaded (mode={layer.mode})", file=_sys.stderr, flush=True)


def check_builtin_policy(layer: ToolSecurityLayer, tool_name: str, params: dict) -> tuple[bool, str]:
    """Check built-in policy rules only (paths, commands, deny list).

    Controlled by layer.mode — monitor mode logs but doesn't block.
    """
    rule = layer.policy.get(tool_name)
    if rule is None:
        rule = layer.policy.get("_default", PolicyRule(action="monitor"))

    if rule.action == "deny":
        return False, f"Tool '{tool_name}' is denied by policy"

    if tool_name == "exec":
        cmd = params.get("command", "") or params.get("cmd", "")
        for pattern in rule.denied_commands:
            if pattern.search(cmd):
                return False, f"Command matches denied pattern: {pattern.pattern}"

    if tool_name in ("read_file", "write_file", "edit_file", "list_dir"):
        path = params.get("path", "") or params.get("file_path", "")
        if path:
            for denied in rule.denied_paths:
                if path_matches(path, denied):
                    return False, f"Path '{path}' matches denied pattern: {denied}"
            if rule.allowed_paths:
                if not any(path_matches(path, ap) for ap in rule.allowed_paths):
                    return False, f"Path '{path}' not in allowed paths"

    return True, ""
