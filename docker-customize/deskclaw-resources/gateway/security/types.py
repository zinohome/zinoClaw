"""Shared data types and constants for the security layer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ─── DLP Patterns ───

DLP_PATTERNS: dict[str, list[re.Pattern]] = {
    "CREDENTIAL": [
        re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*\S+"),
        re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"sk-[A-Za-z0-9]{32,}"),
        re.compile(r"ghp_[A-Za-z0-9]{36}"),
    ],
    "PII": [
        re.compile(r"\b\d{17}[\dXx]\b"),
        re.compile(r"\b1[3-9]\d{9}\b"),
    ],
    "FINANCIAL": [
        re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    ],
}


@dataclass
class DLPFinding:
    category: str
    level: str  # CRITICAL / HIGH / LOW
    match: str


@dataclass
class AuditRecord:
    ts: float
    tool: str
    params: dict[str, Any]
    decision: str  # allowed / denied / monitored
    reason: str = ""
    duration_ms: float = 0
    dlp_findings: list[DLPFinding] = field(default_factory=list)
    dlp_action: str = ""
    result_size: int = 0
    result_snippet: str = ""


@dataclass
class PolicyRule:
    action: str = "allow"  # allow / deny / monitor
    denied_paths: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    denied_commands: list[re.Pattern] = field(default_factory=list)
    allowed_domains: list[str] = field(default_factory=list)
    denied_domains: list[str] = field(default_factory=list)
    sandbox: str = "transparent"  # transparent / isolated
    max_timeout: int = 60
