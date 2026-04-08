#!/bin/bash
# Query available image generation models from NodeStudio.
# Usage: models.sh
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

curl -sL --max-time 15 \
    -H "Authorization: Bearer $TOKEN" \
    "${API}/image-generation/models" 2>&1
