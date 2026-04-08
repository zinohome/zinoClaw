"""DLP scan and apply — pure helpers parameterized by layer state."""

from __future__ import annotations

import re

from ..types import DLP_PATTERNS, DLPFinding


def scan_dlp(
    result: str,
    *,
    dlp_enabled: bool,
    custom_patterns: dict[str, list[re.Pattern]],
) -> list[DLPFinding]:
    if not dlp_enabled or not result:
        return []
    findings: list[DLPFinding] = []
    for category, patterns in DLP_PATTERNS.items():
        level = "CRITICAL" if category == "CREDENTIAL" else "HIGH"
        for pattern in patterns:
            matches = pattern.findall(result)
            for m in matches[:3]:
                findings.append(
                    DLPFinding(
                        category=category,
                        level=level,
                        match=m[:50] + "..." if len(m) > 50 else m,
                    )
                )
    for category, patterns in custom_patterns.items():
        level = "HIGH"
        for pattern in patterns:
            matches = pattern.findall(result)
            for m in matches[:3]:
                findings.append(
                    DLPFinding(
                        category=category,
                        level=level,
                        match=m[:50] + "..." if len(m) > 50 else m,
                    )
                )
    return findings


def apply_dlp(
    result: str,
    findings: list[DLPFinding],
    *,
    dlp_on_critical: str,
    dlp_on_high: str,
) -> tuple[str, str]:
    """Returns (processed_result, action_taken)."""
    if not findings:
        return result, ""
    max_level = max(f.level for f in findings) if findings else ""
    if max_level == "CRITICAL" and dlp_on_critical == "block":
        return "[SECURITY] Result blocked: contained sensitive data (credentials/keys)", "blocked"
    if max_level in ("HIGH", "CRITICAL") and dlp_on_high == "redact":
        redacted = result
        for f in findings:
            if f.match and len(f.match) > 3:
                redacted = redacted.replace(f.match.rstrip("..."), "***REDACTED***")
        return redacted, "redacted"
    return result, "alert"
