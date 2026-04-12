#!/usr/bin/env python3
"""
DeskClaw PPTX Skill v4.0 — Bootstrap Script
Installs Python + Node.js dependencies for PptxGenJS creation and OOXML editing.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────
SKILL_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = SKILL_DIR / "runtime"
VERSION_FILE = RUNTIME_DIR / "version.txt"
MANIFEST = SKILL_DIR / "manifest.json"
ENV_JSON = RUNTIME_DIR / "env.json"

MIRROR_PIP = "https://pypi.tuna.tsinghua.edu.cn/simple"
MIRROR_NPM = "https://registry.npmmirror.com"

IS_WIN = sys.platform == "win32"
DESKCLAW_HOME = (
    Path(os.environ["DESKCLAW_HOME"])
    if os.environ.get("DESKCLAW_HOME")
    else (
        Path(os.environ.get("USERPROFILE", "")) / ".deskclaw"
        if IS_WIN
        else Path.home() / ".deskclaw"
    )
)

PIP_PACKAGES = [
    ("markitdown[pptx]", "markitdown"),
    ("Pillow", "PIL"),
    ("defusedxml", "defusedxml"),
    ("lxml", "lxml"),
]

NPM_PACKAGES = [
    "pptxgenjs",
    "react-icons",
    "react",
    "react-dom",
    "sharp",
]


# ── Helpers ──────────────────────────────────────────────────────────
def pip_install(pkg, import_name=None):
    """Install a pip package with mirror fallback. Skip if already importable."""
    check_name = import_name or pkg.split("[")[0].replace("-", "_").lower()
    try:
        __import__(check_name)
        print(f"[bootstrap] {pkg} already installed, skipping")
        return
    except ImportError:
        pass

    for args in (
        [sys.executable, "-m", "pip", "install", pkg, "-i", MIRROR_PIP, "--quiet"],
        [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
    ):
        try:
            subprocess.check_call(args)
            print(f"[bootstrap] {pkg} installed")
            return
        except subprocess.CalledProcessError:
            continue
    raise RuntimeError(f"Failed to install {pkg}")


def find_node():
    """Locate Node.js binary: DESKCLAW_HOME > system PATH."""
    candidates = [
        DESKCLAW_HOME / "node" / ("node.exe" if IS_WIN else "bin/node"),
    ]
    system_node = shutil.which("node")
    if system_node:
        candidates.append(Path(system_node))

    for p in candidates:
        if p.exists():
            return str(p)
    return None


def download_node() -> str:
    """Download Node.js binary from npmmirror CDN."""
    import platform
    import tarfile
    import urllib.request
    import zipfile

    arch = "arm64" if platform.machine() in ("arm64", "aarch64") else "x64"
    node_ver = "v22.16.0"
    node_dir = DESKCLAW_HOME / "node"
    node_dir.mkdir(parents=True, exist_ok=True)

    if IS_WIN:
        name = f"node-{node_ver}-win-{arch}"
        url = f"https://npmmirror.com/mirrors/node/{node_ver}/{name}.zip"
        archive = node_dir / f"{name}.zip"
        print(f"[bootstrap] Downloading Node.js from {url}")
        urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(node_dir)
        archive.unlink()
        extracted = node_dir / name
        for item in extracted.iterdir():
            shutil.move(str(item), str(node_dir / item.name))
        extracted.rmdir()
        return str(node_dir / "node.exe")
    else:
        system = "darwin" if sys.platform == "darwin" else "linux"
        name = f"node-{node_ver}-{system}-{arch}"
        url = f"https://npmmirror.com/mirrors/node/{node_ver}/{name}.tar.gz"
        archive = node_dir / f"{name}.tar.gz"
        print(f"[bootstrap] Downloading Node.js from {url}")
        urllib.request.urlretrieve(url, archive)
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(node_dir)
        archive.unlink()
        extracted = node_dir / name
        for item in extracted.iterdir():
            dest = node_dir / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))
        extracted.rmdir()
        bin_path = node_dir / "bin" / "node"
        bin_path.chmod(0o755)
        return str(bin_path)


def find_npm(node_path):
    """Locate npm-cli.js relative to node binary. Returns the JS file, not npm.cmd."""
    node_dir = Path(node_path).parent
    # Prefer npm-cli.js (works cross-platform via node, avoids Windows .cmd issues)
    candidates = [
        node_dir.parent / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js",  # macOS/Linux
        node_dir / "node_modules" / "npm" / "bin" / "npm-cli.js",  # Windows
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    # Fallback to npm in PATH
    system_npm = shutil.which("npm")
    if system_npm:
        return system_npm
    raise RuntimeError("npm not found")


def npm_install(npm_cli, node_path, packages):
    """Install npm packages into runtime/node_modules with mirror fallback."""
    # Always use node to run npm-cli.js (cross-platform, avoids .cmd issues on Windows)
    npm_cmd = [node_path, npm_cli]

    # Ensure node binary dir is in PATH for postinstall scripts (e.g. sharp)
    env = os.environ.copy()
    env["PATH"] = str(Path(node_path).parent) + os.pathsep + env.get("PATH", "")

    for args_extra in (
        ["--registry", MIRROR_NPM],
        [],
    ):
        try:
            subprocess.check_call(
                npm_cmd + ["install"] + packages
                + ["--prefix", str(RUNTIME_DIR)]
                + args_extra + ["--silent"],
                cwd=str(RUNTIME_DIR),
                env=env,
            )
            print(f"[bootstrap] npm packages installed: {', '.join(packages)}")
            return
        except subprocess.CalledProcessError:
            continue
    raise RuntimeError(f"Failed to install npm packages: {packages}")


def _print_ready_summary() -> None:
    """Print a READY block with all paths for the model to consume."""
    if ENV_JSON.exists():
        env = json.loads(ENV_JSON.read_text())
    else:
        env = {}
    print("\n[bootstrap] ══ READY ══")
    print(f"  node:        {env.get('node', 'N/A')}")
    print(f"  python:      {env.get('python', 'N/A')}")
    print(f"  node_modules:{env.get('node_modules', 'N/A')}")
    print(f"  skill_dir:   {env.get('skill_dir', 'N/A')}")


# ── Main ─────────────────────────────────────────────────────────────
def main() -> None:
    # 1. Read version from manifest
    if MANIFEST.exists():
        required_version = json.loads(MANIFEST.read_text()).get("required_version", "4.0.0")
    else:
        required_version = "4.0.0"

    # 2. Idempotent check — if already done, just print paths and exit
    if VERSION_FILE.exists() and VERSION_FILE.read_text().strip() == required_version:
        print(f"[bootstrap] v{required_version} already installed.")
        _print_ready_summary()
        sys.exit(0)

    print(f"[bootstrap] Installing PPTX skill v{required_version} dependencies...")

    # 3. Prepare runtime directory
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    # 4. Install Python dependencies
    print("[bootstrap] ── Python dependencies ──")
    for pkg, import_name in PIP_PACKAGES:
        pip_install(pkg, import_name)

    # 5. Locate or download Node.js
    print("[bootstrap] ── Node.js runtime ──")
    node_path = find_node()
    if not node_path:
        node_path = download_node()
    print(f"[bootstrap] Node.js: {node_path}")

    # 6. Install npm dependencies
    npm_cli = find_npm(node_path)
    print(f"[bootstrap] npm: {npm_cli}")

    node_modules = RUNTIME_DIR / "node_modules"
    pptxgenjs_check = node_modules / "pptxgenjs" / "package.json"
    if pptxgenjs_check.exists():
        print("[bootstrap] npm packages already installed, skipping")
    else:
        npm_install(npm_cli, node_path, NPM_PACKAGES)

    # 7. Generate env.json
    env_data = {
        "node": node_path,
        "npm": npm_cli,
        "python": sys.executable,
        "node_modules": str(RUNTIME_DIR / "node_modules"),
        "skill_dir": str(SKILL_DIR),
        "runtime_dir": str(RUNTIME_DIR),
    }
    (RUNTIME_DIR / "env.json").write_text(json.dumps(env_data, indent=2))

    # 8. Write version marker (LAST — ensures full success)
    VERSION_FILE.write_text(required_version)

    _print_ready_summary()


if __name__ == "__main__":
    main()
