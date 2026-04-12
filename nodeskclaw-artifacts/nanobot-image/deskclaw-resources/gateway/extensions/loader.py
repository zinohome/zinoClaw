"""Discovery and loading of user extensions from ~/.deskclaw/extensions/.

Each extension lives in its own directory::

    ~/.deskclaw/extensions/
    ├── my_extension/
    │   ├── my_extension.py   # Extension code (required)
    │   ├── config.json       # Configuration (required: {"enabled": true/false})
    │   └── README.md         # Documentation (recommended)
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from .base import DeskClawExtension

_VIRTUAL_PKG = "deskclaw_extension"
BUILTIN_DIR = Path(__file__).resolve().parent / "builtin"


DEFAULT_PRIORITY = 100


@dataclass
class DiscoveredExtension:
    """Represents a discovered extension directory (may or may not be enabled)."""

    name: str
    directory: Path
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = False
    priority: int = DEFAULT_PRIORITY
    instance: DeskClawExtension | None = None
    readme: str = ""


def _default_extensions_dir() -> Path:
    return Path.home() / ".deskclaw" / "extensions"


def _ensure_virtual_package() -> None:
    if _VIRTUAL_PKG not in sys.modules:
        pkg = types.ModuleType(_VIRTUAL_PKG)
        pkg.__path__ = []
        pkg.__package__ = _VIRTUAL_PKG
        sys.modules[_VIRTUAL_PKG] = pkg


def _read_config(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def extract_version(filepath: Path) -> int:
    """Read ``# version: N`` from the first line.  Returns 0 if absent."""
    try:
        first_line = filepath.read_text(encoding="utf-8").split("\n", 1)[0]
        if first_line.startswith("# version:"):
            return int(first_line.split(":", 1)[1].strip())
    except (FileNotFoundError, ValueError):
        pass
    return 0


def ensure_builtin_extensions(extensions_dir: Path) -> None:
    """Copy / upgrade bundled extension directories into the user directory.

    On upgrade, ``config.json`` is never overwritten so user settings are
    preserved.  Only the ``.py`` and ``README.md`` are refreshed.
    """
    if not BUILTIN_DIR.is_dir():
        return
    extensions_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = extensions_dir / ".installed.json"
    try:
        installed: list[str] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        installed = []

    changed = False
    for src_dir in sorted(BUILTIN_DIR.iterdir()):
        if not src_dir.is_dir() or src_dir.name.startswith(("__", ".")):
            continue

        src_py = src_dir / f"{src_dir.name}.py"
        if not src_py.exists():
            continue

        dest_dir = extensions_dir / src_dir.name
        dest_py = dest_dir / f"{src_dir.name}.py"
        src_ver = extract_version(src_py)

        if src_dir.name in installed and dest_dir.exists():
            if dest_py.exists() and src_ver > extract_version(dest_py):
                try:
                    for src_file in src_dir.iterdir():
                        if src_file.name.startswith("__") or src_file.name == "config.json":
                            continue
                        dest_file = dest_dir / src_file.name
                        dest_file.write_text(
                            src_file.read_text(encoding="utf-8"), encoding="utf-8",
                        )
                    logger.info("[Extensions] Upgraded: {} (v{})", src_dir.name, src_ver)
                    changed = True
                except Exception as exc:
                    logger.warning("[Extensions] Upgrade failed {}: {}", src_dir.name, exc)
            continue

        if src_dir.name in installed:
            continue

        try:
            if not dest_dir.exists():
                dest_dir.mkdir(parents=True, exist_ok=True)
                for src_file in src_dir.iterdir():
                    if src_file.name.startswith("__"):
                        continue
                    dest_file = dest_dir / src_file.name
                    dest_file.write_text(
                        src_file.read_text(encoding="utf-8"), encoding="utf-8",
                    )
                logger.info("[Extensions] Installed builtin: {}", src_dir.name)
            installed.append(src_dir.name)
            changed = True
        except Exception as exc:
            logger.warning("[Extensions] Install failed {}: {}", src_dir.name, exc)

    if changed:
        try:
            manifest_path.write_text(json.dumps(installed, indent=2), encoding="utf-8")
        except Exception:
            pass


def _find_extension_class(mod: types.ModuleType) -> type[DeskClawExtension] | None:
    explicit = getattr(mod, "extension", None)
    if isinstance(explicit, DeskClawExtension):
        return type(explicit)
    if isinstance(explicit, type) and issubclass(explicit, DeskClawExtension):
        return explicit

    for _name, obj in inspect.getmembers(mod, inspect.isclass):
        if obj is not DeskClawExtension and issubclass(obj, DeskClawExtension):
            return obj
    return None


def _load_module(py_file: Path) -> DeskClawExtension | None:
    """Load a single .py file and return a DeskClawExtension instance."""
    dotted = f"{_VIRTUAL_PKG}.{py_file.parent.name}"
    try:
        spec = importlib.util.spec_from_file_location(dotted, str(py_file))
        if not spec or not spec.loader:
            return None
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = _VIRTUAL_PKG
        spec.loader.exec_module(mod)
        sys.modules[dotted] = mod

        ext_cls = _find_extension_class(mod)
        if ext_cls is None:
            logger.debug("[Extensions] No DeskClawExtension subclass in {}", py_file)
            return None
        return ext_cls()
    except Exception as exc:
        logger.warning("[Extensions] Failed to load {}: {}", py_file, exc)
        return None


def discover_extensions(
    extensions_dir: Path | None = None,
) -> list[DiscoveredExtension]:
    """Scan extension directories and return ALL discovered extensions.

    Both enabled and disabled extensions are returned so MCP tools can
    list and manage them.  Only enabled extensions will have ``instance``
    populated.
    """
    ext_dir = extensions_dir or _default_extensions_dir()
    ensure_builtin_extensions(ext_dir)

    if not ext_dir.exists():
        return []

    _ensure_virtual_package()

    results: list[DiscoveredExtension] = []
    for sub in sorted(ext_dir.iterdir()):
        if not sub.is_dir() or sub.name.startswith((".", "_")):
            continue

        py_file = sub / f"{sub.name}.py"
        if not py_file.exists():
            continue

        config = _read_config(sub / "config.json")
        enabled = config.get("enabled", False)
        priority = config.get("priority", DEFAULT_PRIORITY)
        readme = _read_text(sub / "README.md")

        instance = None
        if enabled:
            instance = _load_module(py_file)
            if instance and not instance.name:
                instance.name = sub.name

        entry = DiscoveredExtension(
            name=sub.name,
            directory=sub,
            config=config,
            enabled=enabled,
            priority=priority,
            instance=instance,
            readme=readme,
        )
        results.append(entry)

        if enabled and instance:
            logger.info("[Extensions] Loaded: {} (priority={})", sub.name, priority)
        else:
            logger.debug("[Extensions] Discovered: {} (disabled)", sub.name)

    results.sort(key=lambda d: d.priority)

    loaded = sum(1 for r in results if r.instance)
    if results:
        logger.info(
            "[Extensions] {} discovered, {} enabled from {}",
            len(results), loaded, ext_dir,
        )
    return results
