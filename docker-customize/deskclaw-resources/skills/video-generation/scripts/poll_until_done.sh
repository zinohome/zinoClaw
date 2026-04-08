#!/bin/bash
# Poll until task reaches completed or failed (single exec — avoids gateway duplicate-command blocks).
# Nanobot exec max is 600s; keep default below that so the shell is not killed mid-loop.
# Usage: poll_until_done.sh <task_id> [max_seconds]
# Default max_seconds: 540 (~9 min). Interval: 15s between polls. If still processing, re-run same task_id with a different max_seconds (do not re-submit).

set -uo pipefail

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)

DIR="$(cd "$(dirname "$0")" && pwd)"
TASK_ID="${1:-}"
MAX_SEC="${2:-540}"

if [ -z "$TASK_ID" ]; then
    echo '{"error":"Usage: poll_until_done.sh <task_id> [max_seconds]"}'
    exit 1
fi

elapsed=0
interval=15

while [ "$elapsed" -lt "$MAX_SEC" ]; do
    OUT=$("$DIR/poll.sh" "$TASK_ID" 2>&1) || true
    STATUS=$(printf '%s' "$OUT" | "$PYTHON" -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print(d.get('status') or '')
except Exception:
    print('')
" 2>/dev/null)

    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
        printf '%s\n' "$OUT"
        [ "$STATUS" = "completed" ] && exit 0
        exit 1
    fi

    sleep "$interval"
    elapsed=$((elapsed + interval))
done

OUT=$("$DIR/poll.sh" "$TASK_ID" 2>&1) || true
printf '%s\n' "$OUT"
printf '%s\n' "$OUT" | "$PYTHON" -c "import sys,json; s=sys.stdin.read().strip(); print(json.dumps({'error':'poll_until_done_timeout','max_seconds':int('$MAX_SEC'),'last_poll':json.loads(s) if s.startswith('{') else s}))" 2>/dev/null || echo "{\"error\":\"poll_until_done timeout after ${MAX_SEC}s\"}"
exit 1
