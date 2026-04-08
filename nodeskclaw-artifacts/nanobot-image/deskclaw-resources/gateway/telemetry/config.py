"""Telemetry configuration loader.

Config file: ~/.deskclaw/telemetry.json
Environment overrides: DESKCLAW_TELEMETRY_URL, DESKCLAW_TELEMETRY_TOKEN
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

_CONFIG_PATH = Path.home() / ".deskclaw" / "telemetry.json"


@dataclass
class TelemetryConfig:
    enabled: bool = True
    endpoint: str = ""
    api_key: str = ""
    flush_interval_sec: int = 60
    max_queue_size: int = 200


def load_config() -> TelemetryConfig:
    """Load telemetry config from disk, then apply env-var overrides."""
    cfg = TelemetryConfig()

    try:
        if _CONFIG_PATH.exists():
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data.get("enabled"), bool):
                cfg.enabled = data["enabled"]
            if data.get("endpoint"):
                cfg.endpoint = str(data["endpoint"]).rstrip("/")
            if data.get("api_key"):
                cfg.api_key = str(data["api_key"])
            if isinstance(data.get("flush_interval_sec"), (int, float)):
                cfg.flush_interval_sec = max(10, int(data["flush_interval_sec"]))
            if isinstance(data.get("max_queue_size"), (int, float)):
                cfg.max_queue_size = max(10, int(data["max_queue_size"]))
    except Exception:
        pass

    env_url = os.environ.get("DESKCLAW_TELEMETRY_URL")
    if env_url:
        cfg.endpoint = env_url.rstrip("/")
    env_key = os.environ.get("DESKCLAW_TELEMETRY_TOKEN")
    if env_key:
        cfg.api_key = env_key

    if os.environ.get("DESKCLAW_TELEMETRY_DEBUG"):
        cfg.flush_interval_sec = 5

    return cfg
