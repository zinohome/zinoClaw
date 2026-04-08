"""Central user home resolution (test-friendly monkeypatch target)."""

from __future__ import annotations

from pathlib import Path


def user_home() -> Path:
    return Path.home()
