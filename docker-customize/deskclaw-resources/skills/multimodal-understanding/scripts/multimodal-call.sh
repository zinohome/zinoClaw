#!/bin/bash
# Multimodal image analysis via NoDesk AI Gateway.
#
# Mode 1 — raw messages JSON (advanced):
#   multimodal-call.sh '<messages_json>' [max_tokens] [model]
#
# Mode 2 — local file shortcut:
#   multimodal-call.sh --file <image_path> '<prompt>' [max_tokens] [model]
#   Auto-compresses large images, base64-encodes, and sends via temp file.
#   Default model: kimi-k2.5 (base64 supported).
#
# Mode 3 — image URL shortcut:
#   multimodal-call.sh --url '<image_url>' '<prompt>' [max_tokens] [model]
#   Sends public URL directly. Forces glm-5v-turbo (kimi-k2.5 does not support URL).

GATEWAY_BASE="https://llm-gateway-api.nodesk.tech"

CONFIG="$HOME/.deskclaw/nanobot/config.json"

eval $(python3 -c "
import json,sys
c=json.load(open(sys.argv[1]))
p=c.get('providers',{})
key=''
for k in ['custom','anthropic','openai']:
    v=p.get(k,{})
    key=v.get('apiKey','') or v.get('api_key','')
    if key: break
ep=''
if not key:
    base=p.get('custom',{}).get('api_base','') or p.get('custom',{}).get('baseUrl','')
    if '/ep/' in base:
        ep=base.split('/ep/')[1].split('/')[0]
print(f'API_KEY={chr(34)}{key}{chr(34)}')
print(f'EP_TOKEN={chr(34)}{ep}{chr(34)}')
" "$CONFIG" 2>/dev/null)

if [ -z "$API_KEY" ] && [ -z "$EP_TOKEN" ]; then
    echo '{"error": "Auth not found in ~/.deskclaw/nanobot/config.json. Need providers.custom.apiKey or providers.custom.api_base with /ep/ token."}'
    exit 1
fi

if [ -n "$API_KEY" ]; then
    MULTIMODAL_URL="${GATEWAY_BASE}/deskclaw/v1/multimodal/"
    AUTH_ARGS=(-H "Authorization: Bearer $API_KEY")
else
    MULTIMODAL_URL="${GATEWAY_BASE}/deskclaw/v1/ep/${EP_TOKEN}/multimodal/"
    AUTH_ARGS=()
fi

send_request() {
    curl -sL --max-time 120 \
        -X POST \
        -H "Content-Type: application/json" \
        "${AUTH_ARGS[@]}" \
        "$MULTIMODAL_URL" \
        -d @"$1" 2>&1
}

# --- Mode 2: --file <path> '<prompt>' [max_tokens] [model] ---
if [ "$1" = "--file" ]; then
    IMAGE_PATH="$2"
    PROMPT="${3:-Describe this image in detail.}"
    MAX_TOKENS="${4:-1500}"
    MODEL="${5:-kimi-k2.5}"

    if [ -z "$IMAGE_PATH" ] || [ ! -f "$IMAGE_PATH" ]; then
        echo "{\"error\": \"File not found: $IMAGE_PATH\"}"
        exit 1
    fi

    TMPDIR_WORK=$(mktemp -d)
    trap "rm -rf '$TMPDIR_WORK'" EXIT

    FILE_SIZE=$(stat -f%z "$IMAGE_PATH" 2>/dev/null || stat -c%s "$IMAGE_PATH" 2>/dev/null)
    EXT_LOWER=$(echo "${IMAGE_PATH##*.}" | tr '[:upper:]' '[:lower:]')

    WORK_FILE="$IMAGE_PATH"

    if [ "$FILE_SIZE" -gt 500000 ] 2>/dev/null; then
        RESIZED="$TMPDIR_WORK/resized.jpg"
        if sips --resampleHeightWidthMax 1536 --setProperty format jpeg --setProperty formatOptions 80 "$IMAGE_PATH" --out "$RESIZED" >/dev/null 2>&1; then
            WORK_FILE="$RESIZED"
            EXT_LOWER="jpg"
        fi
    fi

    case "$EXT_LOWER" in
        jpg|jpeg) MIME="jpeg" ;;
        png)      MIME="png" ;;
        gif)      MIME="gif" ;;
        webp)     MIME="webp" ;;
        *)        MIME="jpeg" ;;
    esac

    B64_FILE="$TMPDIR_WORK/b64.txt"
    base64 -i "$WORK_FILE" | tr -d '\n' > "$B64_FILE"

    PROMPT_FILE="$TMPDIR_WORK/prompt.txt"
    printf '%s' "$PROMPT" > "$PROMPT_FILE"

    BODY_FILE="$TMPDIR_WORK/body.json"
    python3 - "$B64_FILE" "$PROMPT_FILE" "$MIME" "$MODEL" "$MAX_TOKENS" "$BODY_FILE" << 'PYEOF'
import json, sys

b64_path, prompt_path, mime, model, max_tokens, out_path = sys.argv[1:7]

with open(b64_path) as f:
    b64 = f.read()
with open(prompt_path) as f:
    prompt = f.read()

data_uri = f"data:image/{mime};base64,{b64}"
body = {
    "model": model,
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": data_uri}}
    ]}],
    "max_tokens": int(max_tokens)
}
with open(out_path, "w") as f:
    json.dump(body, f)
PYEOF

    if [ ! -f "$BODY_FILE" ]; then
        echo '{"error": "Failed to build request body"}'
        exit 1
    fi

    send_request "$BODY_FILE"
    exit $?
fi

# --- Mode 3: --url <image_url> '<prompt>' [max_tokens] [model] ---
if [ "$1" = "--url" ]; then
    IMAGE_URL="$2"
    PROMPT="${3:-Describe this image in detail.}"
    MAX_TOKENS="${4:-1500}"
    MODEL="glm-5v-turbo"

    if [ -z "$IMAGE_URL" ]; then
        echo '{"error": "Usage: multimodal-call.sh --url <image_url> <prompt>"}'
        exit 1
    fi

    TMPDIR_WORK=$(mktemp -d)
    trap "rm -rf '$TMPDIR_WORK'" EXIT
    BODY_FILE="$TMPDIR_WORK/body.json"

    python3 - "$IMAGE_URL" "$PROMPT" "$MODEL" "$MAX_TOKENS" "$BODY_FILE" << 'PYEOF'
import json, sys
image_url, prompt, model, max_tokens, out_path = sys.argv[1:6]
body = {
    "model": model,
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_url}}
    ]}],
    "max_tokens": int(max_tokens)
}
with open(out_path, "w") as f:
    json.dump(body, f)
PYEOF

    if [ ! -f "$BODY_FILE" ]; then
        echo '{"error": "Failed to build request body"}'
        exit 1
    fi

    RESPONSE=$(send_request "$BODY_FILE")

    if echo "$RESPONSE" | grep -q '"1210"'; then
        DL_FILE="$TMPDIR_WORK/downloaded_img"
        curl -sL --max-time 30 -o "$DL_FILE" "$IMAGE_URL"

        if [ ! -f "$DL_FILE" ] || [ ! -s "$DL_FILE" ]; then
            echo "$RESPONSE"
            exit 1
        fi

        FILE_SIZE=$(stat -f%z "$DL_FILE" 2>/dev/null || stat -c%s "$DL_FILE" 2>/dev/null)
        WORK_FILE="$DL_FILE"

        DETECTED_MIME=$(file --mime-type -b "$DL_FILE" 2>/dev/null)
        case "$DETECTED_MIME" in
            image/jpeg) MIME="jpeg" ;;
            image/png)  MIME="png" ;;
            image/gif)  MIME="gif" ;;
            image/webp) MIME="webp" ;;
            *)          MIME="jpeg" ;;
        esac

        if [ "$FILE_SIZE" -gt 500000 ] 2>/dev/null; then
            RESIZED="$TMPDIR_WORK/resized.jpg"
            if sips --resampleHeightWidthMax 1536 --setProperty format jpeg --setProperty formatOptions 80 "$DL_FILE" --out "$RESIZED" >/dev/null 2>&1; then
                WORK_FILE="$RESIZED"
                MIME="jpeg"
            fi
        fi

        B64_FILE="$TMPDIR_WORK/b64.txt"
        base64 -i "$WORK_FILE" | tr -d '\n' > "$B64_FILE"

        PROMPT_FILE="$TMPDIR_WORK/prompt.txt"
        printf '%s' "$PROMPT" > "$PROMPT_FILE"

        FALLBACK_MODEL="kimi-k2.5"
        BODY_FILE="$TMPDIR_WORK/fallback_body.json"

        python3 - "$B64_FILE" "$PROMPT_FILE" "$MIME" "$FALLBACK_MODEL" "$MAX_TOKENS" "$BODY_FILE" << 'PYEOF'
import json, sys
b64_path, prompt_path, mime, model, max_tokens, out_path = sys.argv[1:7]
with open(b64_path) as f:
    b64 = f.read()
with open(prompt_path) as f:
    prompt = f.read()
data_uri = f"data:image/{mime};base64,{b64}"
body = {
    "model": model,
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": data_uri}}
    ]}],
    "max_tokens": int(max_tokens)
}
with open(out_path, "w") as f:
    json.dump(body, f)
PYEOF

        if [ ! -f "$BODY_FILE" ]; then
            echo '{"error": "Fallback failed: could not build base64 request body"}'
            exit 1
        fi

        send_request "$BODY_FILE"
        exit $?
    fi

    echo "$RESPONSE"
    exit 0
fi

# --- Mode 1: raw messages JSON ---
MESSAGES="$1"
MAX_TOKENS="${2:-1500}"
MODEL="${3:-kimi-k2.5}"

if [ -z "$MESSAGES" ]; then
    echo '{"error": "Usage: multimodal-call.sh --file <path> <prompt> | multimodal-call.sh --url <url> <prompt> | multimodal-call.sh <messages_json>"}'
    exit 1
fi

TMPDIR_WORK=$(mktemp -d)
trap "rm -rf '$TMPDIR_WORK'" EXIT
BODY_FILE="$TMPDIR_WORK/body.json"

python3 - "$MESSAGES" "$MODEL" "$MAX_TOKENS" "$BODY_FILE" << 'PYEOF'
import json, sys
messages_raw, model, max_tokens, out_path = sys.argv[1:5]
body = {
    "model": model,
    "messages": json.loads(messages_raw),
    "max_tokens": int(max_tokens)
}
with open(out_path, "w") as f:
    json.dump(body, f)
PYEOF

if [ -f "$BODY_FILE" ]; then
    send_request "$BODY_FILE"
else
    echo '{"error": "Failed to parse messages JSON"}'
    exit 1
fi
