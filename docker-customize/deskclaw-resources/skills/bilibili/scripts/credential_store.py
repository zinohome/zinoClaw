#!/usr/bin/env python3
"""
B站凭证加密存储模块

使用 Fernet 对称加密（AES-128-CBC），密钥派生自机器指纹，
凭证保存在 data/credential.enc 中，不再写入 .zshrc。
"""

import base64
import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Dict, Optional

SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
DATA_DIR = SKILL_DIR / "data"
CREDENTIAL_ENC_FILE = DATA_DIR / "credential.enc"
CREDENTIAL_JSON_FILE = DATA_DIR / "credential.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def _derive_key() -> bytes:
    """
    从机器指纹派生加密密钥。
    组合 hostname + username + 固定 salt，经 SHA-256 后截取 32 字节作为 Fernet key。
    这样同一台机器同一用户始终得到相同密钥，换机器则无法解密。
    """
    fingerprint = f"{platform.node()}|{os.getlogin()}|bili_mcp_salt_2026"
    digest = hashlib.sha256(fingerprint.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet():
    from cryptography.fernet import Fernet
    return Fernet(_derive_key())


def save(data: Dict[str, str]) -> bool:
    """加密并保存凭证到文件"""
    try:
        fernet = _get_fernet()
        plaintext = json.dumps(data).encode()
        encrypted = fernet.encrypt(plaintext)
        CREDENTIAL_ENC_FILE.write_bytes(encrypted)
        return True
    except ImportError:
        return _save_fallback(data)
    except Exception as e:
        print(f"保存凭证失败: {e}", file=sys.stderr)
        return False


def load() -> Optional[Dict[str, str]]:
    """从加密文件加载凭证"""
    if CREDENTIAL_ENC_FILE.exists():
        try:
            fernet = _get_fernet()
            encrypted = CREDENTIAL_ENC_FILE.read_bytes()
            plaintext = fernet.decrypt(encrypted)
            return json.loads(plaintext.decode())
        except ImportError:
            pass
        except Exception:
            pass

    return _load_fallback()


def clear() -> bool:
    """删除凭证文件"""
    removed = False
    for f in (CREDENTIAL_ENC_FILE, CREDENTIAL_JSON_FILE):
        if f.exists():
            f.unlink()
            removed = True

    _clean_zshrc()
    return removed


def _save_fallback(data: Dict[str, str]) -> bool:
    """cryptography 不可用时回退到 JSON 文件（权限 600）"""
    try:
        CREDENTIAL_JSON_FILE.write_text(json.dumps(data, indent=2))
        CREDENTIAL_JSON_FILE.chmod(0o600)
        return True
    except Exception as e:
        print(f"保存凭证失败 (fallback): {e}", file=sys.stderr)
        return False


def _load_fallback() -> Optional[Dict[str, str]]:
    """依次尝试：JSON 文件 -> .zshrc 环境变量（兼容旧数据迁移）"""
    if CREDENTIAL_JSON_FILE.exists():
        try:
            data = json.loads(CREDENTIAL_JSON_FILE.read_text())
            _try_migrate_to_encrypted(data)
            return data
        except Exception:
            pass

    data = _parse_env_from_rc()
    if data.get("sessdata") and data.get("bili_jct"):
        _try_migrate_to_encrypted(data)
        return data

    return None


def _try_migrate_to_encrypted(data: Dict[str, str]):
    """尝试将旧格式数据迁移到加密存储"""
    try:
        _get_fernet()
        save(data)
    except ImportError:
        pass


def _parse_env_from_rc() -> Dict[str, str]:
    """从 .zshrc/.bashrc 读取 BILI_ 环境变量（仅用于一次性迁移）"""
    env_to_key = {
        "BILI_SESSDATA": "sessdata",
        "BILI_BILI_JCT": "bili_jct",
        "BILI_BUVID3": "buvid3",
        "BILI_DEDEUSERID": "dedeuserid",
        "BILI_AC_TIME_VALUE": "ac_time_value",
    }
    result: Dict[str, str] = {}
    shell = os.environ.get("SHELL", "/bin/zsh")
    rc_file = Path.home() / (".zshrc" if "zsh" in shell else ".bashrc")
    if not rc_file.exists():
        return result
    try:
        with open(rc_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("export BILI_") and "=" in line:
                    kv = line[len("export "):].split("=", 1)
                    if len(kv) == 2:
                        env_name = kv[0]
                        if env_name in env_to_key:
                            result[env_to_key[env_name]] = kv[1].strip('"').strip("'")
    except Exception:
        pass
    return result


def _clean_zshrc():
    """清理 .zshrc 中的旧 BILI_ 凭证行"""
    shell = os.environ.get("SHELL", "/bin/zsh")
    rc_file = Path.home() / (".zshrc" if "zsh" in shell else ".bashrc")
    if not rc_file.exists():
        return
    try:
        lines = rc_file.read_text().splitlines(keepends=True)
        new_lines = []
        skip_next = False
        for line in lines:
            if "# Bilibili MCP 凭据" in line:
                skip_next = True
                continue
            if skip_next and line.strip().startswith("export BILI_"):
                continue
            skip_next = False
            new_lines.append(line)
        rc_file.write_text("".join(new_lines))
    except Exception:
        pass
