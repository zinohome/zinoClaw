#!/bin/bash
# Poll image generation task status from NodeStudio.
# Usage: poll.sh <task_id>
# Env: NODESTUDIO_URL (default https://nostudio-api.deskclaw.me), NODESTUDIO_TOKEN (auto from deskclaw-settings.json)

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)

BASE_URL="${NODESTUDIO_URL:-https://nostudio-api.deskclaw.me}"
API="${BASE_URL}/api/v1"
TOKEN="${NODESTUDIO_TOKEN:-}"

if [ -z "$TOKEN" ]; then
    SETTINGS="$HOME/.deskclaw/deskclaw-settings.json"
    [ -f "$SETTINGS" ] && TOKEN=$("$PYTHON" -c "
import json,sys
c=json.load(open(sys.argv[1]))
a=c.get('auth')
t=a.get('token','') if isinstance(a,dict) else ''
print(t or c.get('auth.token','') or c.get('authToken',''))
" "$SETTINGS" 2>/dev/null)
fi

if [ -z "$TOKEN" ]; then
    echo '{"error":"No token. User access_token not found in ~/.deskclaw/deskclaw-settings.json (authToken). Ensure user is logged in to DeskClaw."}'
    exit 1
fi

TASK_ID="$1"
if [ -z "$TASK_ID" ]; then
    echo '{"error":"Usage: poll.sh <task_id>"}'
    exit 1
fi

RESP=$(curl -sL --max-time 15 \
    -H "Authorization: Bearer $TOKEN" \
    "${API}/image-generation/tasks/${TASK_ID}/status" 2>&1)

printf '%s' "$RESP" | "$PYTHON" -c "
import sys,json
try:
    r=json.load(sys.stdin)
    d=r.get('data',r)
    out={'task_id':d.get('task_id','$TASK_ID'),'status':d.get('status','unknown')}
    for k in ('progress','image_urls','error_message','provider_task_id','model_id','model_name','mode'):
        if d.get(k) is not None: out[k]=d[k]
    print(json.dumps(out))
except:
    print(sys.stdin.read() if hasattr(sys.stdin,'read') else '')
" 2>/dev/null || echo "$RESP"
