#!/usr/bin/env python3
"""DeskClaw XLSX bootstrap — openpyxl、pandas 与工具脚本依赖检测"""
import json, subprocess, sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = SKILL_DIR / "runtime"
VERSION_FILE = RUNTIME_DIR / "version.txt"
MANIFEST = SKILL_DIR / "manifest.json"
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

required_version = json.loads(MANIFEST.read_text())["version"]

if VERSION_FILE.exists() and VERSION_FILE.read_text().strip() == required_version:
    print(f"[bootstrap] v{required_version} already installed.")
    sys.exit(0)

RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

def pip_install(pkg, import_name=None):
    import_name = import_name or pkg.replace("-", "_")
    try:
        __import__(import_name)
        print(f"[bootstrap] {pkg} already installed, skipping")
        return
    except ImportError:
        pass
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-i", MIRROR, "--quiet"])
    except subprocess.CalledProcessError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])
    print(f"[bootstrap] {pkg} installed")

pip_install("openpyxl")
pip_install("pandas")

VERSION_FILE.write_text(required_version)
print(f"[bootstrap] v{required_version} ready.")
