#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import re
import shutil
import sys


def _replace_text(path: pathlib.Path, old: str, new: str) -> int:
    if not path.exists():
        return 0
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return 0
    count = text.count(old)
    if count <= 0:
        return 0
    path.write_text(text.replace(old, new), encoding="utf-8")
    return count


def _replace_regex(path: pathlib.Path, pattern: str, repl: str) -> int:
    if not path.exists():
        return 0
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return 0
    new_text, count = re.subn(pattern, repl, text, flags=re.MULTILINE)
    if count <= 0:
        return 0
    path.write_text(new_text, encoding="utf-8")
    return count


def main() -> int:
    patch_root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("/opt/patches/nanobot-webui")
    spec = importlib.util.find_spec("webui")
    if not spec or not spec.submodule_search_locations:
        print("[patch] webui not installed, skip")
        return 0
    target_root = pathlib.Path(spec.submodule_search_locations[0])
    if not patch_root.exists():
        print(f"[patch] patch root missing: {patch_root}")
        return 0

    applied = 0
    for src in patch_root.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(patch_root)
        dst = target_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        applied += 1
        print(f"[patch] applied {rel}")

    text_rewrites = 0

    # 1) Fix misleading config path shown in System Config page.
    #    Frontend bundle is hashed, so rewrite every asset file that contains this literal.
    target_old = "~/.nanobot/config.json"
    target_new = "~/.deskclaw/nanobot/config.json"
    for asset in (target_root / "web" / "dist" / "assets").glob("*"):
        if not asset.is_file():
            continue
        text_rewrites += _replace_text(
            asset,
            target_old,
            target_new,
        )

    # 2) Remove dangerous fallback for custom provider api_base.
    #    Empty api_base should fail fast via provider validation logic, not silently
    #    fall back to localhost:8000/v1.
    provider_file = target_root / "patches" / "provider.py"
    text_rewrites += _replace_text(
        provider_file,
        'api_base=config.get_api_base(model) or "http://localhost:8000/v1",',
        "api_base=config.get_api_base(model),",
    )
    text_rewrites += _replace_regex(
        provider_file,
        r'api_base\s*=\s*config\.get_api_base\(model\)\s*or\s*["\']http://localhost:8000/v1["\']\s*,',
        "api_base=config.get_api_base(model),",
    )

    # Validate the fallback was actually removed.
    if provider_file.exists():
        provider_text = provider_file.read_text(encoding="utf-8", errors="ignore")
        if 'http://localhost:8000/v1' in provider_text:
            print(
                "[patch][warn] provider localhost fallback still present: "
                f"{provider_file}"
            )
        else:
            print(f"[patch] provider localhost fallback removed: {provider_file}")

    # 3) Hot-reload provider/model after saving raw config.json in WebUI.
    #    This avoids needing container restart for provider switch.
    config_route_file = target_root / "api" / "routes" / "config.py"
    text_rewrites += _replace_text(
        config_route_file,
        "    svc.config.__dict__.update(new_config.__dict__)\n\n    return {\"ok\": True, \"content\": content}",
        "    svc.config.__dict__.update(new_config.__dict__)\n    svc.reload_provider()\n\n    return {\"ok\": True, \"content\": content}",
    )
    text_rewrites += _replace_regex(
        config_route_file,
        r"(svc\.config\.__dict__\.update\(new_config\.__dict__\)\n)(\s*return\s+\{\"ok\":\s*True,\s*\"content\":\s*content\})",
        r"\1    svc.reload_provider()\n\n\2",
    )

    if text_rewrites == 0:
        print(
            "[patch][warn] no text rewrites applied; "
            "check whether upstream bundle/layout changed"
        )
    else:
        print(
            f"[patch] rewrote config title literal: "
            f"'{target_old}' -> '{target_new}'"
        )

    print(f"[patch] done, total={applied}, rewrites={text_rewrites}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
