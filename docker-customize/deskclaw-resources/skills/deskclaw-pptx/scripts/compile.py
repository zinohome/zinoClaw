#!/usr/bin/env python3
"""
Run compile.js to assemble slide modules into a single PPTX file.

Usage:
    python scripts/compile.py slides/ output.pptx

Reads env.json for node path and node_modules, sets NODE_PATH,
then runs slides/compile.js.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ENV_JSON = SKILL_DIR / "runtime" / "env.json"


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/compile.py <slides_dir> <output.pptx>")
        sys.exit(1)

    slides_dir = Path(sys.argv[1]).resolve()
    output_path = Path(sys.argv[2]).resolve()

    compile_js = slides_dir / "compile.js"
    if not compile_js.exists():
        print(f"[compile] Error: {compile_js} not found")
        sys.exit(1)

    # Read env.json
    if not ENV_JSON.exists():
        print("[compile] Error: runtime/env.json not found. Run bootstrap.py first.")
        sys.exit(1)

    env_data = json.loads(ENV_JSON.read_text())
    node_path = env_data["node"]
    node_modules = env_data["node_modules"]

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Set NODE_PATH + PATH + output path
    env = os.environ.copy()
    env["NODE_PATH"] = node_modules
    env["PATH"] = str(Path(node_path).parent) + os.pathsep + env.get("PATH", "")
    env["PPTX_OUTPUT"] = str(output_path)

    print(f"[compile] slides: {slides_dir}")
    print(f"[compile] output: {output_path}")
    print(f"[compile] node: {node_path}")

    result = subprocess.run(
        [node_path, str(compile_js)],
        cwd=str(slides_dir),
        env=env,
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"[compile] Failed with exit code {result.returncode}")
        sys.exit(result.returncode)

    if output_path.exists():
        size_kb = output_path.stat().st_size / 1024
        print(f"[compile] Success: {output_path} ({size_kb:.0f} KB)")
    else:
        print(f"[compile] Warning: node exited 0 but {output_path} not found")
        sys.exit(1)


if __name__ == "__main__":
    main()
