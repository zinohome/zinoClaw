#!/usr/bin/env bash
# Validate ~/.openclaw/cron/jobs.json before write.
# Usage: validate-jobs-json.sh [path]
# Exit 0 = valid, non-zero = invalid (stderr has error details)

set -e
PATH="${PATH:-/usr/bin:/bin}"

JOBS_PATH="${1:-$HOME/.openclaw/cron/jobs.json}"
if [[ ! -f "$JOBS_PATH" ]]; then
  echo "ERROR: File not found: $JOBS_PATH" >&2
  exit 1
fi

JOBS_PATH="$JOBS_PATH" python3 -c "
import json
import sys
import os

path = os.environ.get('JOBS_PATH', os.path.expanduser('~/.openclaw/cron/jobs.json'))
errors = []

try:
    with open(path, 'r') as f:
        data = json.load(f)
except json.JSONDecodeError as e:
    print(f'ERROR: JSON parse failed: {e}', file=sys.stderr)
    sys.exit(1)

if not isinstance(data, dict):
    errors.append('Root must be a JSON object')
if 'version' not in data:
    errors.append('Missing top-level \"version\"')
if 'jobs' not in data:
    errors.append('Missing top-level \"jobs\"')
elif not isinstance(data['jobs'], list):
    errors.append('\"jobs\" must be an array')

for i, job in enumerate(data.get('jobs', [])):
    if not isinstance(job, dict):
        errors.append(f'Job[{i}] must be an object')
        continue
    for key in ['id', 'agentId', 'name', 'schedule', 'sessionTarget', 'payload']:
        if key not in job:
            errors.append(f'Job[{i}] missing required field: {key}')
    if 'payload' in job and isinstance(job.get('payload'), dict):
        payload = job['payload']
        kind = payload.get('kind')
        target = job.get('sessionTarget')
        if target == 'isolated':
            if kind != 'agentTurn':
                errors.append(f'Job[{i}] sessionTarget=isolated requires payload.kind=agentTurn, got {kind!r}')
            if kind == 'agentTurn' and 'message' not in payload:
                errors.append(f'Job[{i}] agentTurn payload requires \"message\" field')
        elif target == 'main':
            if kind != 'systemEvent':
                errors.append(f'Job[{i}] sessionTarget=main requires payload.kind=systemEvent, got {kind!r}')
            if kind == 'systemEvent' and 'text' not in payload:
                errors.append(f'Job[{i}] systemEvent payload requires \"text\" field')

if errors:
    for e in errors:
        print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)

print('OK: jobs.json is valid')
sys.exit(0)
"
