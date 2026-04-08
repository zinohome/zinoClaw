#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import shutil
import sys


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

    print(f"[patch] done, total={applied}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
