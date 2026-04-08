#!/bin/bash
# Download a video from URL to a local directory.
# Usage: download.sh '<video_url>' [filename] [output_dir]
# Env: NODESTUDIO_URL, NODESTUDIO_TOKEN (used for auth download attempt)
#      NANOBOT_SESSION_KEY or OPENCLAW_SESSION_KEY — 若未传 output_dir，且设置了此项（如 agent:main:desk-xxx），
#      则保存到 $WORKSPACE/outputs/<与 sessions/*.jsonl 同名的目录>/，与 media/ 下 agent_main_* 目录规则一致。

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)

VIDEO_URL="$1"
FILENAME="$2"
OUTPUT_DIR="$3"

VIDEO_URL=$(printf '%s' "$VIDEO_URL" | sed 's/\\u0026/\&/g; s/\\u003d/=/g; s/\\u003f/?/g')

if [ -z "$VIDEO_URL" ]; then
    echo '{"error": "Usage: download.sh <video_url> [filename] [output_dir]"}'
    exit 1
fi

BASE_URL="${NODESTUDIO_URL:-https://nostudio-api.deskclaw.me}"
TOKEN="${NODESTUDIO_TOKEN:-}"

if [ -z "$TOKEN" ]; then
    SETTINGS="$HOME/.deskclaw/deskclaw-settings.json"
    [ -f "$SETTINGS" ] && TOKEN=$("$PYTHON" -c "
import json,sys
c=json.load(open(sys.argv[1]))
print(c.get('auth.token','') or c.get('authToken',''))
" "$SETTINGS" 2>/dev/null)
fi

if [ -z "$OUTPUT_DIR" ]; then
    CONFIG="$HOME/.deskclaw/nanobot/config.json"
    WORKSPACE=$("$PYTHON" -c "
import json,sys,os
c=json.load(open(sys.argv[1]))
ws=c.get('agents',{}).get('defaults',{}).get('workspace','~/.deskclaw/nanobot/workspace')
print(os.path.expanduser(ws))
" "$CONFIG" 2>/dev/null)
    WORKSPACE="${WORKSPACE:-$HOME/.deskclaw/nanobot/workspace}"
    SESSION_KEY="${NANOBOT_SESSION_KEY:-${OPENCLAW_SESSION_KEY:-}}"
    if [ -n "$SESSION_KEY" ]; then
        SESSION_SAFE=$(printf '%s' "$SESSION_KEY" | "$PYTHON" -c 'import sys,re; k=sys.stdin.read().strip().replace(":","_"); print(re.sub(r"[<>:\"/\\\\|?*]", "_", k).strip())')
        OUTPUT_DIR="$WORKSPACE/outputs/$SESSION_SAFE"
    else
        OUTPUT_DIR="$WORKSPACE/outputs"
    fi
fi
mkdir -p "$OUTPUT_DIR"

SAVE_DIR="$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

if [ -z "$FILENAME" ]; then
    FILENAME="video_${TIMESTAMP}.mp4"
else
    FILENAME=$(printf '%s' "$FILENAME" | sed 's/[[:space:]\/\\:*?"<>|]/_/g')
    FILENAME="${FILENAME}_${TIMESTAMP}.mp4"
fi

OUTPUT="$SAVE_DIR/$FILENAME"

is_valid_video() {
    local f="$1"
    [ ! -f "$f" ] && return 1
    [ ! -s "$f" ] && return 1
    local head4
    head4=$(head -c 4 "$f" 2>/dev/null | od -A n -t x1 2>/dev/null | tr -d ' ' || "$PYTHON" -c "import sys;sys.stdout.write(open(sys.argv[1],'rb').read(4).hex())" "$f" 2>/dev/null)
    case "$head4" in
        3c3f786d|3c457272|3c68746d|3c214f43) return 1 ;;
    esac
    local size
    size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || wc -c < "$f" 2>/dev/null | tr -d ' ')
    [ "${size:-0}" -lt 10000 ] && return 1
    return 0
}

try_download() {
    local EXTRA_ARGS=("$@")
    local TMP_OUT="${OUTPUT}.tmp"
    local CODE
    CODE=$(curl -sL --max-time 180 -o "$TMP_OUT" -w "%{http_code}" "${EXTRA_ARGS[@]}" "$VIDEO_URL" 2>&1)
    if [ "$CODE" -ge 200 ] && [ "$CODE" -lt 300 ] && is_valid_video "$TMP_OUT"; then
        mv "$TMP_OUT" "$OUTPUT"
        return 0
    fi
    rm -f "$TMP_OUT" 2>/dev/null
    return 1
}

if [ -n "$TOKEN" ]; then
    try_download -H "Authorization: Bearer $TOKEN" && DOWNLOADED=true
fi

if [ -z "$DOWNLOADED" ]; then
    try_download && DOWNLOADED=true
fi

if [ -z "$DOWNLOADED" ]; then
    try_download \
        -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
        -H "Referer: ${BASE_URL}/" \
        && DOWNLOADED=true
fi

if [ -n "$DOWNLOADED" ] && [ -f "$OUTPUT" ] && [ -s "$OUTPUT" ]; then
    FILE_SIZE=$(stat -f%z "$OUTPUT" 2>/dev/null || stat -c%s "$OUTPUT" 2>/dev/null || wc -c < "$OUTPUT" 2>/dev/null | tr -d ' ')
    SIZE_MB=$(awk "BEGIN{printf \"%.1f\", ${FILE_SIZE:-0}/1048576}" 2>/dev/null || echo "unknown")
    echo "{\"status\": \"ok\", \"path\": \"$OUTPUT\", \"url\": \"$VIDEO_URL\", \"size_mb\": \"${SIZE_MB}MB\"}"
else
    rm -f "$OUTPUT" "${OUTPUT}.tmp" 2>/dev/null
    echo "{\"status\": \"download_failed\", \"url\": \"$VIDEO_URL\", \"message\": \"All download methods failed. The video URL may require proxy or has expired.\"}"
    exit 1
fi
