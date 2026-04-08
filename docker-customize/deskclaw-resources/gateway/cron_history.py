"""Simple JSONL-based run history for cron jobs.

Each job gets its own file: <cron_dir>/runs/<job_id>.jsonl
Newest runs are appended at the end; reads return reverse-chronological order.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class CronRunHistory:
    def __init__(self, cron_dir: Path) -> None:
        self._dir = cron_dir / "runs"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _job_file(self, job_id: str) -> Path:
        safe = job_id.replace("/", "_").replace("..", "_")
        return self._dir / f"{safe}.jsonl"

    def record(self, job_id: str, run: dict[str, Any]) -> None:
        run.setdefault("ts", int(time.time() * 1000))
        fp = self._job_file(job_id)
        with fp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(run, ensure_ascii=False) + "\n")

    def get_runs(
        self, job_id: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        fp = self._job_file(job_id)
        if not fp.exists():
            return {"runs": [], "total": 0, "hasMore": False}

        lines = fp.read_text(encoding="utf-8").strip().splitlines()
        total = len(lines)
        # Reverse so newest first
        lines.reverse()
        page = lines[offset : offset + limit]
        runs = []
        for line in page:
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return {
            "runs": runs,
            "total": total,
            "hasMore": offset + limit < total,
        }
