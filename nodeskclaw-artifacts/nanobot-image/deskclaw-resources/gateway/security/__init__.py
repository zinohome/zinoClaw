"""Gateway security package — tool execution security layer.

Public API:
  ToolSecurityLayer  — main coordinator (policy, DLP, audit, monkey-patch)
  current_ws         — contextvars.ContextVar for WebSocket injection
  ApprovalChannel    — async approval request/resolve mechanism
  HookContext        — passed to async plugin hooks
"""

from .types import DLP_PATTERNS, AuditRecord, DLPFinding, PolicyRule
from .approval import ApprovalChannel, HookContext, current_ws, current_session_id
from .layer import ToolSecurityLayer

__all__ = [
    "DLP_PATTERNS",
    "AuditRecord",
    "DLPFinding",
    "PolicyRule",
    "ApprovalChannel",
    "HookContext",
    "current_ws",
    "current_session_id",
    "ToolSecurityLayer",
]
