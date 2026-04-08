"""DeskClaw built-in MCP Server — modular tool package.

Exposes gateway management, sandbox control, MCP server configuration,
and documentation as MCP tools.  Mounted on the gateway FastAPI app at
``/mcp`` so the nanobot agent can connect via Streamable HTTP.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from ..paths import (
    resolve_allowlist_path,
    resolve_deskclaw_home,
    resolve_nanobot_config_path,
    resolve_nanobot_home,
)

# ── Shared constants ──────────────────────────────────────────────

DESKCLAW_HOME = resolve_deskclaw_home()
NANOBOT_HOME = resolve_nanobot_home()
NANOBOT_CONFIG_PATH = resolve_nanobot_config_path()

ALLOWLIST_PATH = resolve_allowlist_path()

BUILTIN_MCP_SERVERS = frozenset({"deskclaw"})

# ── Shared helpers ────────────────────────────────────────────────


def _read_allowlist() -> dict:
    try:
        return json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_allowlist(data: dict) -> None:
    ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALLOWLIST_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _bot_control_allowed() -> bool:
    return _read_allowlist().get("mcp_bot_control", True)


def read_config_raw() -> dict:
    """Read nanobot config.json as a plain dict."""
    try:
        return json.loads(NANOBOT_CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_config_raw(config: dict) -> None:
    """Write a plain dict back to nanobot config.json."""
    NANOBOT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    NANOBOT_CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8",
    )


# ── MCP instance ──────────────────────────────────────────────────

mcp = FastMCP(
    "deskclaw",
    instructions=(
        "DeskClaw 系统管理 MCP Server。提供网关重启、配置读写、沙箱管理、MCP 服务器管理等工具，"
        "以及系统文档（通过 read_docs 工具获取）。调用工具前请先阅读相关文档了解配置格式。"
    ),
)

# ── Register tools from sub-modules ──────────────────────────────
# NOTE: sub-modules may ``from . import NANOBOT_CONFIG_PATH, ...`` —
# all shared symbols above MUST be defined before these imports.

from . import gateway, sandbox, loop_guard, docs, mcp_config  # noqa: E402

gateway.register(mcp)
sandbox.register(mcp)
loop_guard.register(mcp)
docs.register(mcp)
mcp_config.register(mcp)

# ── Public API (re-exported by mcp_server.py for server.py) ──────

get_pending_action = gateway.get_pending_action
consume_pending_action = gateway.consume_pending_action
_do_restart_gateway = gateway._do_restart_gateway
_do_restart_deskclaw = gateway._do_restart_deskclaw

_starlette_app = mcp.streamable_http_app()


def get_session_manager():
    """Return the session manager (available after module import)."""
    return mcp.session_manager
