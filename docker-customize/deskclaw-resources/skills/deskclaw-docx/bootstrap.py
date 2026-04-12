#!/usr/bin/env python3
"""DeskClaw DOCX bootstrap — Node.js docx-js、Python 工具链与运行时探测"""
import json, os, subprocess, sys, shutil
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = SKILL_DIR / "runtime"
VERSION_FILE = RUNTIME_DIR / "version.txt"
MANIFEST = SKILL_DIR / "manifest.json"
MIRROR_NPM = "https://registry.npmmirror.com"
MIRROR_PIP = "https://pypi.tuna.tsinghua.edu.cn/simple"
IS_WIN = sys.platform == "win32"

required_version = json.loads(MANIFEST.read_text())["version"]

# 总体幂等检查：版本匹配则跳过全部
if VERSION_FILE.exists() and VERSION_FILE.read_text().strip() == required_version:
    print(f"[bootstrap] v{required_version} already installed.")
    sys.exit(0)

RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

# === 1. Node.js 检测 ===
NODE = None
DESKCLAW_HOME = Path(os.environ.get("DESKCLAW_HOME", "")) if os.environ.get("DESKCLAW_HOME") else (
    Path(os.environ.get("USERPROFILE", "")) / ".deskclaw" if IS_WIN else Path.home() / ".deskclaw"
)
candidates = [
    DESKCLAW_HOME / "node" / "node.exe",
    DESKCLAW_HOME / "node" / "bin" / "node",
    shutil.which("node") or "",
]
for candidate in candidates:
    p = Path(str(candidate))
    if p.exists() and p.is_file():
        NODE = str(p)
        break

if not NODE:
    import platform, urllib.request
    print("[bootstrap] Node.js not found, downloading...")
    arch = "arm64" if platform.machine() in ("arm64", "aarch64") else "x64"
    node_ver = "v22.16.0"
    node_dir = RUNTIME_DIR / "node"
    if IS_WIN:
        import zipfile
        url = f"https://npmmirror.com/mirrors/node/{node_ver}/node-{node_ver}-win-{arch}.zip"
        dl_path = RUNTIME_DIR / "node.zip"
        try:
            urllib.request.urlretrieve(url, dl_path)
            with zipfile.ZipFile(dl_path) as zf:
                zf.extractall(RUNTIME_DIR)
            list(RUNTIME_DIR.glob("node-*"))[0].rename(node_dir)
            dl_path.unlink()
            NODE = str(node_dir / "node.exe")
        except Exception as e:
            print(f"ERROR: Failed to download Node.js: {e}"); sys.exit(1)
    else:
        import tarfile
        system = "darwin" if sys.platform == "darwin" else "linux"
        url = f"https://npmmirror.com/mirrors/node/{node_ver}/node-{node_ver}-{system}-{arch}.tar.gz"
        dl_path = RUNTIME_DIR / "node.tar.gz"
        try:
            urllib.request.urlretrieve(url, dl_path)
            with tarfile.open(dl_path) as tf:
                tf.extractall(RUNTIME_DIR)
            list(RUNTIME_DIR.glob("node-*"))[0].rename(node_dir)
            dl_path.unlink()
            NODE = str(node_dir / "bin" / "node")
        except Exception as e:
            print(f"ERROR: Failed to download Node.js: {e}"); sys.exit(1)
    print(f"[bootstrap] Node.js installed to {NODE}")

node_root = Path(NODE).parent if IS_WIN else Path(NODE).parent.parent
NPM_CLI = node_root / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js"
if IS_WIN and not NPM_CLI.exists():
    NPM_CLI = node_root / "node_modules" / "npm" / "bin" / "npm-cli.js"
if not NPM_CLI.exists():
    npm_path = shutil.which("npm")
    NPM_CLI = Path(npm_path) if npm_path else None
if not NPM_CLI or not NPM_CLI.exists():
    print("ERROR: npm not found"); sys.exit(1)

print(f"[bootstrap] Node: {NODE}")

# === 2. npm docx（跳过已安装） ===
node_modules = RUNTIME_DIR / "node_modules" / "docx"
if node_modules.exists():
    print("[bootstrap] npm docx already installed, skipping")
else:
    npm_cmd = [NODE, str(NPM_CLI)]
    try:
        subprocess.check_call(npm_cmd + ["install", "docx", "--prefix", str(RUNTIME_DIR), "--registry", MIRROR_NPM, "--silent"])
    except subprocess.CalledProcessError:
        subprocess.check_call(npm_cmd + ["install", "docx", "--prefix", str(RUNTIME_DIR), "--silent"])
    print("[bootstrap] npm docx installed")

# === 3. python-docx（跳过已安装） ===
try:
    import docx
    print("[bootstrap] python-docx already installed, skipping")
except ImportError:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx", "-i", MIRROR_PIP, "--quiet"])
    except subprocess.CalledProcessError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx", "--quiet"])
    print("[bootstrap] python-docx installed")

# === 4. lxml（跳过已安装） ===
try:
    import lxml
    print("[bootstrap] lxml already installed, skipping")
except ImportError:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "lxml", "-i", MIRROR_PIP, "--quiet"])
    except subprocess.CalledProcessError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "lxml", "--quiet"])
    print("[bootstrap] lxml installed")

# === 5. 解压 schemas（跳过已解压） ===
schemas_tar = SKILL_DIR / "scripts" / "office" / "schemas.tar.gz"
schemas_dir = SKILL_DIR / "scripts" / "office" / "schemas"
if schemas_dir.exists():
    print("[bootstrap] schemas already extracted, skipping")
elif schemas_tar.exists():
    import tarfile
    with tarfile.open(schemas_tar) as tf:
        tf.extractall(SKILL_DIR / "scripts" / "office")
    print("[bootstrap] schemas extracted")

# === 6. 写 env.json ===
env_data = {
    "node": NODE,
    "npm_cli": str(NPM_CLI),
    "python": sys.executable,
    "node_modules": str(RUNTIME_DIR / "node_modules"),
    "skill_dir": str(SKILL_DIR),
}
(RUNTIME_DIR / "env.json").write_text(json.dumps(env_data, indent=2))

# === 7. 写版本标记（最后写，确保前面全部成功） ===
VERSION_FILE.write_text(required_version)
print(f"[bootstrap] v{required_version} ready.")
