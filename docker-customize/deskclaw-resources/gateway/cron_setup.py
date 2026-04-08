"""Cron store path aligned with nanobot CLI / AgentLoop (workspace-scoped).

Upstream scopes ``jobs.json`` under ``<workspace>/cron/``; legacy installs used
``<config-dir>/cron/jobs.json`` (``get_cron_dir()``).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.config.schema import Config


def cron_jobs_path(config: "Config") -> Path:
    """Path to the cron JSON store (same as nanobot ``cli gateway`` / ``chat``)."""
    return config.workspace_path / "cron" / "jobs.json"


def migrate_legacy_cron_store(config: "Config") -> None:
    """Move legacy ``get_cron_dir()/jobs.json`` into workspace if present (idempotent)."""
    from nanobot.config.paths import get_cron_dir

    legacy_path = get_cron_dir() / "jobs.json"
    new_path = cron_jobs_path(config)
    if legacy_path.is_file() and not new_path.exists():
        new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy_path), str(new_path))
