"""PATH segments prepended only for nanobot ``exec`` subprocesses (not process-wide)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def deskclaw_home() -> Path:
    return Path(os.environ.get("DESKCLAW_HOME", Path.home() / ".deskclaw"))


def deskclaw_exec_path_prepend() -> str:
    """Directories to prepend to PATH for each ``exec`` invocation.

    Order: ``~/.deskclaw/gateway-venv/{bin|Scripts}``, then current interpreter
    ``{sys.prefix}/{bin|Scripts}`` if different, then ``~/.deskclaw/uv`` when ``uv`` exists.
    """
    parts: list[str] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        if not p.is_dir():
            return
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key not in seen:
            seen.add(key)
            parts.append(key)

    dc = deskclaw_home()
    if sys.platform == "win32":
        add(dc / "gateway-venv" / "Scripts")
    else:
        add(dc / "gateway-venv" / "bin")

    interp = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
    add(interp)

    uv_bin = dc / "uv" / ("uv.exe" if sys.platform == "win32" else "uv")
    if uv_bin.is_file():
        add(uv_bin.parent)

    return os.pathsep.join(parts)
