"""DeskClaw built-in MCP Server — backward-compatible entry point.

All tool implementations live in the ``mcp_tools`` sub-package.
This module re-exports the public API consumed by ``server.py``.
"""

from .mcp_tools import (  # noqa: F401
    mcp,
    _starlette_app,
    get_session_manager,
    get_pending_action,
    consume_pending_action,
    _do_restart_gateway,
    _do_restart_deskclaw,
)
