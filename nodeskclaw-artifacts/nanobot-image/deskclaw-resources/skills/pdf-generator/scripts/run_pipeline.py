#!/usr/bin/env python3
"""
Cross-platform PDF pipeline runner (replaces 'bash make.sh run' on Windows).

Usage:
    python scripts/run_pipeline.py --title "Report" --type report \
        --author "Author" --content content.json --out report.pdf
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def find_python() -> str:
    for cmd in ("python3", "python"):
        path = shutil.which(cmd)
        if path:
            return path
    deskclaw_py = os.path.join(
        os.path.expanduser("~"), ".deskclaw", "python", "python.exe"
    )
    if os.path.isfile(deskclaw_py):
        return deskclaw_py
    print("Error: python not found", file=sys.stderr)
    sys.exit(2)


def find_node() -> str:
    path = shutil.which("node")
    if path:
        return path
    print("Error: node not found", file=sys.stderr)
    sys.exit(2)


def run(cmd: list[str], label: str) -> None:
    print(f"  [{label}] {' '.join(cmd[:3])}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAILED: {label}", file=sys.stderr)
        if result.stderr:
            for line in result.stderr.strip().splitlines()[-5:]:
                print(f"    {line}", file=sys.stderr)
        sys.exit(3)


def main() -> None:
    parser = argparse.ArgumentParser(description="minimax-pdf pipeline runner")
    parser.add_argument("--title", default="Untitled Document")
    parser.add_argument("--type", default="general", dest="doc_type")
    parser.add_argument("--author", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--abstract", default="")
    parser.add_argument("--cover-image", default="", dest="cover_image")
    parser.add_argument("--accent", default="")
    parser.add_argument("--cover-bg", default="", dest="cover_bg")
    parser.add_argument("--content", default="")
    parser.add_argument("--out", default="output.pdf")
    args = parser.parse_args()

    py = find_python()
    node = find_node()
    workdir = tempfile.mkdtemp(prefix="minimax-pdf-")

    print(f"Building: {args.title}")
    print(f"  Type  : {args.doc_type}")
    print(f"  Output: {args.out}")

    try:
        # Step 1: design tokens
        print("\nStep 1/4  Generating design tokens...")
        tokens_path = os.path.join(workdir, "tokens.json")
        cmd = [
            py, os.path.join(SCRIPTS_DIR, "palette.py"),
            "--title", args.title,
            "--type", args.doc_type,
            "--author", args.author,
            "--date", args.date,
            "--out", tokens_path,
        ]
        if args.accent:
            cmd += ["--accent", args.accent]
        if args.cover_bg:
            cmd += ["--cover-bg", args.cover_bg]
        run(cmd, "palette")

        if args.abstract or args.cover_image:
            with open(tokens_path) as f:
                tokens = json.load(f)
            if args.abstract:
                tokens["abstract"] = args.abstract
            if args.cover_image:
                tokens["cover_image"] = args.cover_image
            with open(tokens_path, "w") as f:
                json.dump(tokens, f, indent=2)

        # Step 2: cover
        print("\nStep 2/4  Rendering cover...")
        cover_html = os.path.join(workdir, "cover.html")
        cover_pdf = os.path.join(workdir, "cover.pdf")
        cmd = [
            py, os.path.join(SCRIPTS_DIR, "cover.py"),
            "--tokens", tokens_path,
            "--out", cover_html,
        ]
        if args.subtitle:
            cmd += ["--subtitle", args.subtitle]
        run(cmd, "cover.py")

        run([
            node, os.path.join(SCRIPTS_DIR, "render_cover.js"),
            "--input", cover_html,
            "--out", cover_pdf,
        ], "render_cover.js")
        print("  Done")

        # Step 3: body
        print("\nStep 3/4  Rendering body pages...")
        body_pdf = os.path.join(workdir, "body.pdf")
        content_file = args.content
        if not content_file:
            content_file = os.path.join(workdir, "content.json")
            with open(content_file, "w", encoding="utf-8") as f:
                json.dump([
                    {"type": "h1", "text": "Document Body"},
                    {"type": "body", "text": "No content file provided. Use --content path/to/content.json"},
                ], f, ensure_ascii=False, indent=2)
            print("  No content file — using placeholder.")

        run([
            py, os.path.join(SCRIPTS_DIR, "render_body.py"),
            "--tokens", tokens_path,
            "--content", content_file,
            "--out", body_pdf,
        ], "render_body.py")
        print("  Done")

        # Step 4: merge
        print("\nStep 4/4  Merging...")
        run([
            py, os.path.join(SCRIPTS_DIR, "merge.py"),
            "--cover", cover_pdf,
            "--body", body_pdf,
            "--out", args.out,
            "--title", args.title,
        ], "merge.py")

        size_kb = os.path.getsize(args.out) / 1024
        print(f"\nDone => {args.out} ({size_kb:.0f} KB)")

    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
