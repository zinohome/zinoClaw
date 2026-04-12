#!/bin/bash
# Download image(s) from URL(s) to a local directory.
# Usage: download.sh '<image_url>' [filename] [output_dir]
#   image_url can be a single URL or a JSON array '["url1","url2"]'.
# Env: NODESTUDIO_URL, NODESTUDIO_TOKEN (used for auth download attempt)
#      NANOBOT_SESSION_KEY or OPENCLAW_SESSION_KEY — auto output dir under $WORKSPACE/outputs/

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python3)

IMAGE_INPUT="$1"
FILENAME="${2:-}"
OUTPUT_DIR="${3:-}"

if [ -z "$IMAGE_INPUT" ]; then
    echo '{"error": "Usage: download.sh <image_url_or_json_array> [filename] [output_dir]"}'
    exit 1
fi

BASE_URL="${NODESTUDIO_URL:-https://nostudio-api.deskclaw.me}"
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

URLS=$("$PYTHON" -c "
import sys,json
raw = sys.argv[1]
try:
    arr = json.loads(raw)
    if isinstance(arr, list):
        for u in arr: print(u)
    else:
        print(str(arr))
except:
    print(raw)
" "$IMAGE_INPUT" 2>/dev/null || echo "$IMAGE_INPUT")

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DOWNLOADED_PATHS=""
IDX=0
TOTAL_OK=0
TOTAL_FAIL=0

is_valid_image() {
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
    [ "${size:-0}" -lt 500 ] && return 1
    return 0
}

try_download() {
    local url="$1"; shift
    local out="$1"; shift
    local EXTRA_ARGS=("$@")
    local TMP_OUT="${out}.tmp"
    local CODE
    CODE=$(curl -sL --max-time 120 -o "$TMP_OUT" -w "%{http_code}" "${EXTRA_ARGS[@]}" "$url" 2>&1)
    if [ "$CODE" -ge 200 ] && [ "$CODE" -lt 300 ] && is_valid_image "$TMP_OUT"; then
        mv "$TMP_OUT" "$out"
        return 0
    fi
    rm -f "$TMP_OUT" 2>/dev/null
    return 1
}

while IFS= read -r URL; do
    [ -z "$URL" ] && continue
    URL=$(printf '%s' "$URL" | sed 's/\\u0026/\&/g; s/\\u003d/=/g; s/\\u003f/?/g')

    EXT="png"
    case "$URL" in
        *.jpg|*.jpeg) EXT="jpg" ;;
        *.webp) EXT="webp" ;;
        *.gif) EXT="gif" ;;
    esac

    if [ -n "$FILENAME" ]; then
        SAFE_NAME=$(printf '%s' "$FILENAME" | sed 's/[[:space:]\/\\:*?"<>|]/_/g')
        if [ "$IDX" -eq 0 ]; then
            OUTFILE="${OUTPUT_DIR}/${SAFE_NAME}_${TIMESTAMP}.${EXT}"
        else
            OUTFILE="${OUTPUT_DIR}/${SAFE_NAME}_${TIMESTAMP}_${IDX}.${EXT}"
        fi
    else
        if [ "$IDX" -eq 0 ]; then
            OUTFILE="${OUTPUT_DIR}/image_${TIMESTAMP}.${EXT}"
        else
            OUTFILE="${OUTPUT_DIR}/image_${TIMESTAMP}_${IDX}.${EXT}"
        fi
    fi

    DL_OK=""
    if [ -n "$TOKEN" ]; then
        try_download "$URL" "$OUTFILE" -H "Authorization: Bearer $TOKEN" && DL_OK=true
    fi
    if [ -z "$DL_OK" ]; then
        try_download "$URL" "$OUTFILE" && DL_OK=true
    fi
    if [ -z "$DL_OK" ]; then
        try_download "$URL" "$OUTFILE" \
            -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
            -H "Referer: ${BASE_URL}/" \
            && DL_OK=true
    fi

    if [ -n "$DL_OK" ] && [ -f "$OUTFILE" ]; then
        FILE_SIZE=$(stat -f%z "$OUTFILE" 2>/dev/null || stat -c%s "$OUTFILE" 2>/dev/null || wc -c < "$OUTFILE" 2>/dev/null | tr -d ' ')
        SIZE_KB=$(awk "BEGIN{printf \"%.1f\", ${FILE_SIZE:-0}/1024}" 2>/dev/null || echo "unknown")
        DOWNLOADED_PATHS="${DOWNLOADED_PATHS}${DOWNLOADED_PATHS:+,}\"${OUTFILE}\""
        TOTAL_OK=$((TOTAL_OK + 1))
    else
        rm -f "$OUTFILE" "${OUTFILE}.tmp" 2>/dev/null
        TOTAL_FAIL=$((TOTAL_FAIL + 1))
    fi
    IDX=$((IDX + 1))
done <<< "$URLS"

if [ "$TOTAL_OK" -gt 0 ]; then
    echo "{\"status\":\"ok\",\"paths\":[${DOWNLOADED_PATHS}],\"downloaded\":${TOTAL_OK},\"failed\":${TOTAL_FAIL}}"
else
    echo "{\"status\":\"download_failed\",\"message\":\"All download methods failed.\",\"failed\":${TOTAL_FAIL}}"
    exit 1
fi
