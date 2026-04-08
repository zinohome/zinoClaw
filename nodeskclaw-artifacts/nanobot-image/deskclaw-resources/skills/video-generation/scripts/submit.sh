#!/bin/bash
# Submit a video generation task to NodeStudio (create → submit in one step).
# Usage: submit.sh '<json_body>'
# Local images: image_url / end_image_url / reference_images[] can be workspace paths or media/...
# Rewritten to http://HOST:PORT/files<abs_path> (DeskClaw gateway). Set DESKCLAW_GATEWAY_HOST to LAN IP for remote NodeStudio.

set -uo pipefail

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)

BASE_URL="${NODESTUDIO_URL:-https://nostudio-api.deskclaw.me}"
API="${BASE_URL}/api/v1"
TOKEN="${NODESTUDIO_TOKEN:-}"

if [ -z "$TOKEN" ]; then
    SETTINGS="$HOME/.deskclaw/deskclaw-settings.json"
    [ -f "$SETTINGS" ] && TOKEN=$("$PYTHON" -c "
import json,sys
c=json.load(open(sys.argv[1]))
print(c.get('auth.token','') or c.get('authToken',''))
" "$SETTINGS" 2>/dev/null)
fi

if [ -z "$TOKEN" ]; then
    echo '{"error":"No token. User access_token not found in ~/.deskclaw/deskclaw-settings.json (authToken). Ensure user is logged in to DeskClaw."}'
    exit 1
fi

INPUT="$1"
[ -z "$INPUT" ] && { echo '{"error":"Usage: submit.sh <json_body>"}'; exit 1; }

IDEM_KEY=$("$PYTHON" -c "import uuid;print(uuid.uuid4())" 2>/dev/null || echo "$(date +%s)-$$")

TMP_IN=$(mktemp)
TMP_CREATE=$(mktemp)
TMP_SUBMIT=$(mktemp)
trap 'rm -f "$TMP_IN" "$TMP_CREATE" "$TMP_SUBMIT"' EXIT

printf '%s' "$INPUT" > "$TMP_IN"

export _VG_SUBMIT_JSON_PATH="$TMP_IN"
"$PYTHON" <<'PYRESOLVE' || exit 1
import json, os, sys

def load_cfg():
    p = os.path.expanduser("~/.deskclaw/nanobot/config.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def resolve_media_urls(d):
    cfg = load_cfg()
    ws = cfg.get("agents", {}).get("defaults", {}).get("workspace", "~/.deskclaw/nanobot/workspace")
    ws = os.path.normpath(os.path.expanduser(ws))
    port = cfg.get("gateway", {}).get("port", 18790)
    host = os.environ.get("DESKCLAW_GATEWAY_HOST") or os.environ.get("DESKCLAW_FILES_HOST") or "127.0.0.1"
    base = os.environ.get("DESKCLAW_FILES_BASE_URL")
    if not base:
        base = f"http://{host}:{port}"
    base = base.rstrip("/")

    def one_url(v):
        if not v or not isinstance(v, str):
            return v
        s = v.strip()
        if s.startswith("http://") or s.startswith("https://"):
            return s
        if s.startswith("file://"):
            path = s[7:]
        elif os.path.isabs(s):
            path = s
        else:
            path = os.path.join(ws, s.lstrip("/"))
        path = os.path.normpath(os.path.expanduser(path))
        if os.name == "nt":
            if path.lower().replace("\\", "/")[:len(ws.replace("\\", "/"))] != ws.lower().replace("\\", "/"):
                raise ValueError("image path outside workspace: " + path)
        else:
            if not path.startswith(ws):
                raise ValueError("image path outside workspace: " + path)
        if not os.path.isfile(path):
            raise ValueError("not a file or missing: " + path)
        return base + "/files" + path.replace("\\", "/")

    for key in ("image_url", "end_image_url"):
        if key in d and d[key]:
            d[key] = one_url(d[key])
    if "reference_images" in d and isinstance(d["reference_images"], list):
        d["reference_images"] = [one_url(x) if x else x for x in d["reference_images"]]
    return d

path = os.environ.get("_VG_SUBMIT_JSON_PATH", "")
try:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data = resolve_media_urls(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
except Exception as e:
    print(json.dumps({"error": "resolve_media_urls: " + str(e)}, ensure_ascii=False))
    sys.exit(1)
PYRESOLVE
unset _VG_SUBMIT_JSON_PATH

"$PYTHON" - "$TMP_IN" "$TMP_CREATE" "$TMP_SUBMIT" <<'PYEOF'
import json, sys

d = json.load(open(sys.argv[1]))

create_body = {
    "task_type": "video_generate",
    "action": "generate",
    "title": d.get("title", d.get("prompt", "video")[:30]),
    "description": d.get("prompt", ""),
    "model_name": d.get("model", "fast"),
    "aspect_ratio": d.get("aspect_ratio", "16:9"),
    "duration": d.get("duration", 5),
    "input_materials": {},
    "parameters": {
        "prompt": d.get("prompt", ""),
        "resolution": d.get("resolution", "720p"),
        "generate_audio": d.get("generate_audio", True),
    },
}

submit_body = {
    "model_id": d.get("model", "fast"),
    "prompt": d.get("prompt", ""),
    "resolution": d.get("resolution", "720p"),
    "duration": d.get("duration", 5),
    "aspect_ratio": d.get("aspect_ratio", "16:9"),
    "generate_audio": d.get("generate_audio", True),
    "watermark": d.get("watermark", False),
}

for key in ("image_url", "end_image_url", "reference_images",
            "reference_videos", "reference_audios", "seed"):
    if key in d:
        submit_body[key] = d[key]
        if key in ("image_url", "end_image_url", "seed"):
            create_body["parameters"][key] = d[key]

json.dump(create_body, open(sys.argv[2], "w"), ensure_ascii=False)
json.dump(submit_body, open(sys.argv[3], "w"), ensure_ascii=False)
PYEOF

CREATE_RESP=$(curl -sL --max-time 30 \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-Idempotency-Key: $IDEM_KEY" \
    "${API}/tasks/generate" \
    -d @"$TMP_CREATE" 2>&1)

TASK_ID=$(printf '%s' "$CREATE_RESP" | "$PYTHON" -c "
import sys,json
try:
    r=json.load(sys.stdin)
    print(r.get('data',r).get('task_id',''))
except: print('')
" 2>/dev/null)

if [ -z "$TASK_ID" ]; then
    echo "$CREATE_RESP"
    exit 1
fi

SUBMIT_RESP=$(curl -sL --max-time 30 \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-Idempotency-Key: ${IDEM_KEY}-submit" \
    "${API}/generation/tasks/${TASK_ID}/submit" \
    -d @"$TMP_SUBMIT" 2>&1)

printf '%s' "$SUBMIT_RESP" | "$PYTHON" -c "
import sys,json
try:
    r=json.load(sys.stdin)
    d=r.get('data',r)
    d.setdefault('task_id','$TASK_ID')
    print(json.dumps(d))
except:
    print('{\"task_id\":\"$TASK_ID\",\"status\":\"submitted\"}')" 2>/dev/null
