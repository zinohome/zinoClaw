#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"missing source: {src}")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    src_root = repo / "projects" / "DeskClaw.app" / "Contents" / "Resources"
    out_root = repo / "docker-customize" / "deskclaw-resources"

    gateway_src = src_root / "gateway"
    nanobot_src = src_root / "nanobot"
    gateway_dst = out_root / "gateway"
    nanobot_dst = out_root / "nanobot"

    out_root.mkdir(parents=True, exist_ok=True)
    copy_tree(gateway_src, gateway_dst)
    copy_tree(nanobot_src, nanobot_dst)

    print(f"prepared: {gateway_dst}")
    print(f"prepared: {nanobot_dst}")
    print("done. now you can build image without projects/ dependency.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
