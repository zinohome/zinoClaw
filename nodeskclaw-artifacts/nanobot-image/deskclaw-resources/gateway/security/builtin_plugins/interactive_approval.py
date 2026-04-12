# version: 10
# author: DeskClaw
"""Interactive tool approval plugin — Cursor-style Run/Allowlist/Cancel.

Drop this file into ~/.deskclaw/security-plugins/ to enable interactive
approval for tool executions.

Behavior:
  - Tools listed in the allowlist are auto-approved (subject to path rules).
  - Unlisted tools or path mismatches trigger an approval dialog.
  - "Allowlist" button = run + add a derived rule for future auto-approval.

Allowlist file: defaults to ~/.deskclaw/tool-allowlist.json and follows DESKCLAW_HOME when set.
Format (v2 — per-tool path rules):
  {
    "vars": {
      "WORKSPACE": "$env:DESKCLAW_WORKSPACE ?? ($env:DESKCLAW_NANOBOT_HOME ?? ~/.deskclaw/nanobot) + /workspace"
    },
    "rules": {
      "read_file":    { "paths": ["$WORKSPACE/**", "/tmp/**"] },
      "list_dir":     { "paths": ["$WORKSPACE/**"] },
      "write_file":   { "paths": ["$WORKSPACE/**"] },
      "edit_file":    { "paths": ["$WORKSPACE/**"] },
      "web_search":   {},
      "web_fetch":    { "urls": ["https://*"] },
      "message":      {},
      "exec:git *":   {},
      "exec:bash *":  { "paths": ["$WORKSPACE/**"] },
      "exec:ls *":    {}
    }
  }

Rule value semantics (all values are objects):
  {}                              — auto-approve, no restrictions
  { "paths": ["pattern", ...] }  — auto-approve when path matches
  { "urls":  ["pattern", ...] }  — auto-approve when URL matches
  { "paths": [] }                — same as absent, always ask
  (absent from rules)            — always ask

This is a reference implementation. Users can freely modify the logic,
swap in enterprise approval systems, or delete the file entirely.
"""

from __future__ import annotations

import json
import os
from fnmatch import fnmatch
from urllib.parse import urlparse

try:
    from gateway.paths import resolve_allowlist_path
except ImportError:
    from ...paths import resolve_allowlist_path

ALLOWLIST_FILE = resolve_allowlist_path()

PATH_FIELDS: dict[str, str] = {
    "read_file": "path",
    "write_file": "path",
    "edit_file": "path",
    "list_dir": "path",
    "web_fetch": "url",
}

RULE_FIELD_MAP: dict[str, str] = {
    "path": "paths",
    "url": "urls",
}


# ─── Allowlist I/O (with mtime cache) ───

_allowlist_cache: dict | None = None
_allowlist_mtime: float = 0.0


def _load_allowlist() -> dict:
    global _allowlist_cache, _allowlist_mtime
    try:
        st = ALLOWLIST_FILE.stat()
        if _allowlist_cache is not None and st.st_mtime == _allowlist_mtime:
            return _allowlist_cache
        data = json.loads(ALLOWLIST_FILE.read_text(encoding="utf-8"))
        _allowlist_cache = data
        _allowlist_mtime = st.st_mtime
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        _allowlist_cache = None
        _allowlist_mtime = 0.0
        return {"vars": {}, "rules": {}}


def _save_allowlist(al: dict) -> None:
    global _allowlist_cache, _allowlist_mtime
    ALLOWLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALLOWLIST_FILE.write_text(
        json.dumps(al, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _allowlist_cache = al
    try:
        _allowlist_mtime = ALLOWLIST_FILE.stat().st_mtime
    except OSError:
        _allowlist_mtime = 0.0


# ─── Variable resolution ───


def _resolve_vars(pattern: str, vars_dict: dict[str, str]) -> str:
    """Resolve $VAR references in a pattern using the vars dict.

    Variable declarations in vars dict support:
      "$env:ENV_NAME ?? fallback" — read env var, use fallback if unset
      literal string              — used as-is
    """
    for var_name, var_def in vars_dict.items():
        placeholder = f"${var_name}"
        if placeholder not in pattern:
            continue
        resolved = _resolve_var_def(var_def)
        pattern = pattern.replace(placeholder, resolved)
    pattern = pattern.replace("$HOME", str(Path.home()))
    return os.path.expanduser(pattern)


def _resolve_var_def(var_def: str) -> str:
    """Resolve a single variable definition like '$env:NAME ?? fallback'."""
    if var_def.startswith("$env:"):
        rest = var_def[5:]
        if "??" in rest:
            env_name, fallback = rest.split("??", 1)
            env_name = env_name.strip()
            fallback = fallback.strip()
            value = os.environ.get(env_name)
            if value:
                return value
            return os.path.expanduser(fallback)
        else:
            return os.environ.get(rest.strip(), "")
    return var_def


# ─── Rule matching ───


def _find_rule(tool_name: str, params: dict, rules: dict) -> dict | None:
    """Find the matching rule for a tool call.

    Returns the rule object if found, None if no rule matches.
    For exec tools, iterates all 'exec:pattern' keys with fnmatch.
    For MCP tools (containing ':'), iterates MCP pattern keys with fnmatch.
    For built-in tools, does exact lookup.
    """
    if tool_name == "exec":
        cmd = params.get("command", "") or params.get("cmd", "")
        for key, rule in rules.items():
            if not key.startswith("exec:"):
                continue
            if fnmatch(cmd, key[5:]) and isinstance(rule, dict):
                return rule
        return None

    rule = rules.get(tool_name)
    if isinstance(rule, dict):
        return rule

    for key, rule in rules.items():
        if ":" not in key or key.startswith("exec:"):
            continue
        if fnmatch(tool_name, key) and isinstance(rule, dict):
            return rule

    return None


def _check_paths(
    tool_name: str, params: dict, rule: dict, vars_dict: dict[str, str]
) -> bool:
    """Check if the tool call's path/url matches the rule's patterns.

    - Empty rule {} (unrestricted): always pass.
    - exec with paths: extract path-like tokens from command, match against patterns.
    - Built-in tools with path dimension: match param value against patterns.
    - Tools without a path dimension: always pass (rule existence is enough).
    - Explicit empty pattern list: no match -> ask.
    """
    if not rule:
        return True

    # exec: check path-like tokens in the command against rule's paths
    if tool_name == "exec":
        patterns = rule.get("paths", [])
        if not patterns:
            return True  # no path restriction on this exec rule
        cmd = params.get("command", "") or params.get("cmd", "")
        path_tokens = [t for t in cmd.split() if t.startswith(("/", "~", "./"))]
        if not path_tokens:
            return True  # command has no path tokens, can't check
        for token in path_tokens:
            token = os.path.abspath(os.path.expanduser(token))
            for pattern in patterns:
                resolved = _resolve_vars(pattern, vars_dict)
                if fnmatch(token, resolved):
                    return True
        return False

    param_field = PATH_FIELDS.get(tool_name)
    if not param_field:
        return True

    rule_field = RULE_FIELD_MAP.get(param_field, "paths")
    patterns = rule.get(rule_field, [])
    if not patterns:
        return False

    value = params.get(param_field, "")
    if not value:
        return True

    value = os.path.expanduser(value)
    for pattern in patterns:
        resolved = _resolve_vars(pattern, vars_dict)
        if fnmatch(value, resolved):
            return True
    return False


# ─── Derive entries for Allowlist button ───


def _derive_entry(tool_name: str, params: dict) -> tuple[str, dict]:
    """Generate an allowlist entry when user clicks Allowlist.

    Returns (key, rule_object) to merge into the allowlist.

    Derivation strategy:
      exec — key is "exec:<binary> *", path-like args go into {"paths": [...]}
      path tools — file: parent dir/**, directory: dir itself/**
      web_fetch  — scheme://host/*
      other      — {}
    """
    if tool_name == "exec":
        cmd = params.get("command", "") or params.get("cmd", "")
        tokens = cmd.split()
        binary = tokens[0] if tokens else cmd
        key = f"exec:{binary} *"
        path_tokens = [t for t in tokens[1:] if t.startswith(("/", "~", "./"))]
        if path_tokens:
            patterns = [os.path.dirname(os.path.abspath(os.path.expanduser(t))) + "/**"
                        for t in path_tokens]
            return (key, {"paths": patterns})
        return (key, {})

    param_field = PATH_FIELDS.get(tool_name)
    if not param_field:
        return (tool_name, {})

    value = params.get(param_field, "")
    if not value:
        return (tool_name, {})

    rule_field = RULE_FIELD_MAP.get(param_field, "paths")

    if param_field == "url":
        try:
            parsed = urlparse(value)
            pattern = f"{parsed.scheme}://{parsed.netloc}/*"
        except Exception:
            pattern = value
    elif tool_name == "list_dir":
        pattern = value.rstrip("/") + "/**"
    else:
        pattern = os.path.dirname(value) + "/**"

    return (tool_name, {rule_field: [pattern]})


def _merge_to_allowlist(key: str, new_rule: dict) -> None:
    """Merge a derived entry into the allowlist file."""
    al = _load_allowlist()
    rules = al.setdefault("rules", {})
    existing = rules.get(key)

    if existing is None:
        rules[key] = new_rule
    elif not new_rule:
        rules[key] = {}  # upgrade to unrestricted
    elif not existing:
        pass  # already {} (unrestricted)
    else:
        for field in ("paths", "urls"):
            new_patterns = new_rule.get(field, [])
            if new_patterns:
                existing_patterns = existing.setdefault(field, [])
                for p in new_patterns:
                    if p not in existing_patterns:
                        existing_patterns.append(p)

    _save_allowlist(al)


# ─── Summary for approval card ───


def _build_summary(tool_name: str, params: dict) -> str:
    if tool_name == "exec":
        return params.get("command", "") or params.get("cmd", "")
    field = PATH_FIELDS.get(tool_name)
    if field:
        return params.get(field, "")
    brief = json.dumps(params, ensure_ascii=False)
    return brief[:200] + ("..." if len(brief) > 200 else "")


# ─── Hook entry point ───


async def on_before(tool_name: str, params: dict, ctx=None) -> dict | None:
    """Security hook: ask user before every non-allowlisted tool call."""
    al = _load_allowlist()

    if al.get("full_access", False):
        return None

    vars_dict = al.get("vars", {})
    rules = al.get("rules", {})

    rule = _find_rule(tool_name, params, rules)
    if rule is not None and _check_paths(tool_name, params, rule, vars_dict):
        return None  # allowlisted

    if ctx is None:
        return None

    decision = await ctx.request_approval(
        tool_name, params,
        summary=_build_summary(tool_name, params),
    )

    action = decision.get("action", "deny")

    if action == "deny":
        return {
            "allowed": False,
            "reason": "User denied",
            "message": (
                f"User declined to run tool '{tool_name}'. "
                "Do NOT retry this tool call — ask the user what they would "
                "like to do instead."
            ),
        }

    if action == "allowlist":
        key, new_rule = _derive_entry(tool_name, params)
        _merge_to_allowlist(key, new_rule)

    return None  # allow_once or allowlist both mean: execute
