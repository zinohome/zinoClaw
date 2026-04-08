#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeskClaw gateway-venv + default-Python litellm presence check.

Primary intent: **gateway-venv** (DeskClaw 运行时环境). **default** 为遍历 PATH
各目录中的 python3/python（去重后逐一检查），避免「PATH 首部被临时注入」只命中一个解释器。

Stdlib only (Python 3.10+). Cross-platform (macOS, Linux, Windows).

When litellm is present, reads its version and flags known alert releases
(currently 1.82.7, 1.82.8 per product notice). Other versions are reported as
outside that set so users can contextualize risk.

Exit codes:
  0  No litellm detected in checked scope(s), or scope skipped (e.g. no venv)
  1  litellm detected in at least one checked scope
  2  Fatal error (e.g. cannot run subprocess)
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# 当前通报需重点关注的 litellm 版本（与上游/安全公告对齐后可在此扩展）
KNOWN_ALERT_VERSIONS: frozenset[str] = frozenset({"1.82.7", "1.82.8"})


def home() -> Path:
    return Path(os.path.expanduser("~"))


def default_venv_root() -> Path:
    raw = os.environ.get("DESKCLAW_GATEWAY_VENV", "").strip()
    if raw:
        return Path(os.path.expanduser(raw))
    return home() / ".deskclaw" / "gateway-venv"


def find_venv_python(venv: Path) -> Path | None:
    if sys.platform == "win32":
        for name in ("python.exe", "python3.exe"):
            cand = venv / "Scripts" / name
            if cand.is_file():
                return cand
    else:
        for name in ("python3", "python"):
            cand = venv / "bin" / name
            if cand.is_file() and os.access(cand, os.X_OK):
                return cand
    return None


def pip_show(py: Path, pkg: str) -> bool:
    try:
        r = subprocess.run(
            [str(py), "-m", "pip", "show", pkg],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def can_import(py: Path, mod: str) -> bool:
    code = (
        "import importlib.util,sys;"
        f"sys.exit(0 if importlib.util.find_spec({mod!r}) else 1)"
    )
    try:
        r = subprocess.run(
            [str(py), "-c", code],
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def fs_litellm_in_venv(venv: Path) -> bool:
    if sys.platform == "win32":
        sp = venv / "Lib" / "site-packages"
        if not sp.is_dir():
            return False
        for p in sp.iterdir():
            if p.name.lower().startswith("litellm"):
                return True
        return False
    lib = venv / "lib"
    if not lib.is_dir():
        return False
    for sub in lib.glob("python*"):
        sp = sub / "site-packages"
        if not sp.is_dir():
            continue
        for p in sp.iterdir():
            if p.name.startswith("litellm"):
                return True
    return False


def normalize_release_base(version: str) -> str:
    """Map '1.82.8.post0', '1.82.7+foo' -> '1.82.8' / '1.82.7' for comparison."""
    v = version.strip().split("+", 1)[0].strip()
    m = re.match(r"^(\d+\.\d+\.\d+)", v)
    return m.group(1) if m else v.split("-", 1)[0].strip()


def litellm_version_from_py(py: Path) -> str | None:
    code = (
        "try:\n"
        " import importlib.metadata as m\n"
        " print(m.version('litellm'))\n"
        "except Exception:\n"
        " import sys\n"
        " sys.exit(1)\n"
    )
    try:
        r = subprocess.run(
            [str(py), "-c", code],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        r = subprocess.run(
            [str(py), "-m", "pip", "show", "litellm"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if r.returncode != 0:
            return None
        for line in r.stdout.splitlines():
            if line.lower().startswith("version:"):
                return line.split(":", 1)[1].strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def is_alert_version(version: str | None) -> bool:
    if not version:
        return False
    return normalize_release_base(version) in KNOWN_ALERT_VERSIONS


def inspect_scope(
    label: str,
    py: Path,
    venv_for_fs: Path | None,
) -> tuple[bool, str | None, bool]:
    """
    Returns (detected, raw_version_or_none, hits_known_alert_version).
    """
    det = False
    if pip_show(py, "litellm"):
        print(f"[{label}] [pip] 检测到 litellm")
        det = True
    if can_import(py, "litellm"):
        print(f"[{label}] [import] 可加载 litellm")
        det = True
    if venv_for_fs is not None and fs_litellm_in_venv(venv_for_fs):
        print(f"[{label}] [fs] site-packages 下存在 litellm*")
        det = True

    ver: str | None = litellm_version_from_py(py) if det else None
    alert = is_alert_version(ver)

    if det:
        if ver:
            base = normalize_release_base(ver)
            alert_list = ", ".join(sorted(KNOWN_ALERT_VERSIONS))
            if alert:
                print(f"[{label}] 版本: {ver}（release≈{base}，属于当前通报需重点关注: {alert_list}）")
            else:
                print(
                    f"[{label}] 版本: {ver}（release≈{base}，不在当前通报版本 {alert_list}；"
                    f"相对更远版本可稍放心，若产品已不再依赖 litellm 仍建议择机移除）"
                )
        else:
            print(f"[{label}] 无法解析版本号，请人工核对；仍建议评估是否保留 litellm")
        print(f"→ {label}: 检测到 litellm")
    else:
        print(f"→ {label}: 未检测到 litellm")

    return det, ver, alert


def check_gateway(venv: Path) -> tuple[str, bool, bool]:
    if not venv.is_dir():
        print(f"[gateway] 未找到 venv 目录: {venv}")
        return "SKIP", False, False
    py = find_venv_python(venv)
    if not py:
        print(f"[gateway] 未找到可执行解释器 (Scripts|bin): {venv}")
        return "SKIP", False, False
    print(f"[gateway] 解释器: {py}")
    det, _ver, alert = inspect_scope("gateway", py, venv)
    return ("DETECT" if det else "NONE"), det, alert


def _is_path_executable(p: Path) -> bool:
    if not p.is_file():
        return False
    if sys.platform == "win32":
        return True
    return os.access(p, os.X_OK)


def iter_distinct_path_pythons() -> list[Path]:
    """
    Walk PATH in order; in each directory look for python3 / python (or .exe on Windows).
    Deduplicate by resolved path so the same binary reached via different PATH entries is checked once.
    """
    if sys.platform == "win32":
        names = ("python3.exe", "python.exe")
    else:
        names = ("python3", "python")
    seen_resolved: set[Path] = set()
    ordered: list[Path] = []
    for raw in os.environ.get("PATH", "").split(os.pathsep):
        piece = raw.strip()
        if not piece:
            continue
        try:
            d = Path(piece).expanduser()
        except (OSError, ValueError):
            continue
        if not d.is_dir():
            continue
        for name in names:
            cand = d / name
            if not _is_path_executable(cand):
                continue
            try:
                key = cand.resolve()
            except OSError:
                key = cand
            if key in seen_resolved:
                continue
            seen_resolved.add(key)
            ordered.append(cand)
    return ordered


def python_from_py_launcher() -> Path | None:
    """Windows fallback when no python*.exe found under PATH directories."""
    py_launcher = shutil.which("py")
    if not py_launcher:
        return None
    try:
        r = subprocess.run(
            [py_launcher, "-3", "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def check_default(py_override: Path | None) -> tuple[str, bool, bool, int]:
    """
    Returns (status, any_detected, any_alert, path_interpreters_checked).
    path_interpreters_checked is 0 when skipped, else number of interpreters scanned.
    """
    if py_override is not None:
        py = py_override.expanduser().resolve()
        if not py.is_file():
            print(f"[default] --default-python 不是可执行文件: {py}")
            return "SKIP", False, False, 0
        print(f"[default] 解释器（--default-python，仅此一项）: {py}")
        det, _ver, alert = inspect_scope("default", py, None)
        return ("DETECT" if det else "NONE"), det, alert, 1

    pythons = iter_distinct_path_pythons()
    if not pythons and sys.platform == "win32":
        py = python_from_py_launcher()
        if py:
            pythons = [py]
    if not pythons:
        print("[default] PATH 各目录下未发现 python3/python（Windows 已尝试 py -3）")
        return "SKIP", False, False, 0

    n = len(pythons)
    print(
        f"[default] PATH 上去重后共 {n} 个解释器待查（按 PATH 目录顺序；"
        f"解析到同一文件只查一次）"
    )
    any_det = False
    any_alert = False
    for i, py in enumerate(pythons, 1):
        print()
        print(f"[default #{i}/{n}] 解释器: {py}")
        det, _ver, alert = inspect_scope(f"default#{i}", py, None)
        any_det |= det
        any_alert |= det and alert
    return ("DETECT" if any_det else "NONE"), any_det, any_alert, n


def main() -> int:
    p = argparse.ArgumentParser(description="Check litellm in DeskClaw gateway-venv and/or default Python.")
    p.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=("all", "gateway", "default"),
        help="all: gateway then default; gateway|default: one scope only",
    )
    p.add_argument(
        "--venv",
        type=Path,
        default=None,
        metavar="PATH",
        help="gateway venv root (default: ~/.deskclaw/gateway-venv or DESKCLAW_GATEWAY_VENV)",
    )
    p.add_argument(
        "--default-python",
        type=Path,
        default=None,
        metavar="EXE",
        help="force interpreter for default scope (skip PATH discovery)",
    )
    args = p.parse_args()
    venv = args.venv if args.venv is not None else default_venv_root()

    any_detect = False
    any_alert = False
    path_checked = 0
    if args.command in ("all", "gateway"):
        _, d, a = check_gateway(venv)
        any_detect = any_detect or d
        any_alert = any_alert or (d and a)
        if args.command == "all":
            print()
    if args.command in ("all", "default"):
        _, d, a, path_checked = check_default(args.default_python)
        any_detect = any_detect or d
        any_alert = any_alert or (d and a)

    print()
    summary_bits = [
        f"litellm_detected={'yes' if any_detect else 'no'}",
        f"high_risk_version={'yes' if any_alert else 'no'}",
    ]
    if path_checked > 0:
        summary_bits.append(f"path_interpreters_checked={path_checked}")
    print("SUMMARY " + " ".join(summary_bits))
    return 1 if any_detect else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n中断", file=sys.stderr)
        raise SystemExit(130)
