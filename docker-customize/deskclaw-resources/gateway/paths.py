from __future__ import annotations

import os
from pathlib import Path


def resolve_deskclaw_home() -> Path:
    return Path(os.environ.get("DESKCLAW_HOME", str(Path.home() / ".deskclaw"))).expanduser()


def resolve_nanobot_home() -> Path:
    config_path = os.environ.get("NANOBOT_CONFIG_PATH", "").strip()
    if config_path:
        return Path(config_path).expanduser().parent
    nanobot_home = os.environ.get("DESKCLAW_NANOBOT_HOME", "").strip()
    if nanobot_home:
        return Path(nanobot_home).expanduser()
    return resolve_deskclaw_home() / "nanobot"


def resolve_nanobot_config_path() -> Path:
    return Path(
        os.environ.get("NANOBOT_CONFIG_PATH", str(resolve_nanobot_home() / "config.json"))
    ).expanduser()


def resolve_workspace_path() -> Path:
    workspace = os.environ.get("DESKCLAW_WORKSPACE", "").strip()
    if workspace:
        return Path(workspace).expanduser()
    return resolve_nanobot_home() / "workspace"


def resolve_allowlist_path() -> Path:
    return resolve_deskclaw_home() / "tool-allowlist.json"
