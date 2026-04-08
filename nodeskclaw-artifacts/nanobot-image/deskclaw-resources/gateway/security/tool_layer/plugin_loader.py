"""Bundled plugin install/upgrade and dynamic load of ~/.deskclaw/security-plugins."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .paths import user_home

if TYPE_CHECKING:
    from ..layer import ToolSecurityLayer

# security/builtin_plugins (parent of this package is security/)
BUILTIN_PLUGINS_DIR = Path(__file__).resolve().parent.parent / "builtin_plugins"


def extract_plugin_version(filepath: Path) -> int:
    """Extract version from first-line comment: '# version: N'. Returns 0 if absent."""
    try:
        first_line = filepath.read_text(encoding="utf-8").split("\n", 1)[0]
        if first_line.startswith("# version:"):
            return int(first_line.split(":", 1)[1].strip())
    except (FileNotFoundError, ValueError):
        pass
    return 0


def ensure_builtin_plugins(layer: ToolSecurityLayer) -> None:
    """Install or upgrade bundled default plugins.

    Convention: plugins declare '# version: N' on the first line.
    - New plugin (not installed): install and record in manifest.
    - Installed but outdated (bundled version > installed version): upgrade.
    - Installed and up-to-date or newer: skip.

    Uses a manifest (~/.deskclaw/security-plugins/.installed.json) to track
    which builtins have been released.
    """
    if not BUILTIN_PLUGINS_DIR.is_dir():
        return
    layer._plugin_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = layer._plugin_dir / ".installed.json"
    try:
        installed: list[str] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        installed = []

    import sys as _sys

    changed = False
    for src in BUILTIN_PLUGINS_DIR.glob("*.py"):
        dest = layer._plugin_dir / src.name
        src_ver = extract_plugin_version(src)

        if src.name in installed and dest.exists():
            dest_ver = extract_plugin_version(dest)
            if src_ver > dest_ver:
                try:
                    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                    print(
                        f"[Security] Upgraded plugin: {src.name} (v{dest_ver} → v{src_ver})",
                        file=_sys.stderr,
                        flush=True,
                    )
                    changed = True
                except Exception as e:
                    print(
                        f"[Security] Failed to upgrade plugin {src.name}: {e}",
                        file=_sys.stderr,
                        flush=True,
                    )
            continue

        if src.name in installed:
            continue

        try:
            if not dest.exists():
                dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"[Security] Installed default plugin: {src.name}", file=_sys.stderr, flush=True)
            installed.append(src.name)
            changed = True
        except Exception as e:
            print(f"[Security] Failed to install default plugin {src.name}: {e}", file=_sys.stderr, flush=True)

    if changed:
        try:
            manifest_path.write_text(json.dumps(installed, indent=2), encoding="utf-8")
        except Exception:
            pass


def load_security_plugins(layer: ToolSecurityLayer) -> None:
    """Load user-defined security plugins from ~/.deskclaw/security-plugins/.

    Each .py file can define:
      - on_before(tool, params[, ctx])  → gate hook (approval / deny)
      - on_around(tool, params)         → execution hook (sandbox / proxy)
      - on_after(record)                → audit hook
      - transform_result(tool, params, result) → post-process return value (after DLP)
      - transform_results: list[Callable]      → additional transforms, same signature
      - DLP_PATTERNS: dict[str, list[str]]
    """
    import sys as _sys

    if not layer._plugin_dir.exists():
        return
    loaded = 0
    for py_file in sorted(layer._plugin_dir.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(
                f"security_plugin.{py_file.stem}", str(py_file)
            )
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            import sys as _sys2
            _sys2.modules[f"security_plugin.{py_file.stem}"] = mod

            if hasattr(mod, "on_before") and callable(mod.on_before):
                layer.before_hooks.append(mod.on_before)
            if hasattr(mod, "on_around") and callable(mod.on_around):
                layer.around_hooks.append(mod.on_around)
            if hasattr(mod, "on_after") and callable(mod.on_after):
                layer.after_hooks.append(mod.on_after)
            if hasattr(mod, "transform_result") and callable(mod.transform_result):
                layer.result_transform_hooks.append(mod.transform_result)
            tr_list = getattr(mod, "transform_results", None)
            if isinstance(tr_list, (list, tuple)):
                for fn in tr_list:
                    if callable(fn):
                        layer.result_transform_hooks.append(fn)
            if hasattr(mod, "DLP_PATTERNS") and isinstance(mod.DLP_PATTERNS, dict):
                for cat, patterns in mod.DLP_PATTERNS.items():
                    compiled = [re.compile(p) if isinstance(p, str) else p for p in patterns]
                    layer.custom_dlp_patterns.setdefault(cat, []).extend(compiled)

            loaded += 1
            print(f"[Security] Loaded security plugin: {py_file.name}", file=_sys.stderr, flush=True)
        except Exception as e:
            print(f"[Security] Failed to load security plugin {py_file.name}: {e}", file=_sys.stderr, flush=True)

    if loaded:
        print(f"[Security] {loaded} security plugin(s) loaded from {layer._plugin_dir}", file=_sys.stderr, flush=True)


def default_plugin_dir() -> Path:
    return user_home() / ".deskclaw" / "security-plugins"
