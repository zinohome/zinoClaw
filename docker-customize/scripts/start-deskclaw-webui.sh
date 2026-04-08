#!/usr/bin/env bash
set -euo pipefail

DESKCLAW_HOME="${DESKCLAW_HOME:-/config/.deskclaw}"
DESKCLAW_NANOBOT_HOME="${DESKCLAW_NANOBOT_HOME:-$DESKCLAW_HOME/nanobot}"
NANOBOT_CONFIG_PATH="${NANOBOT_CONFIG_PATH:-$DESKCLAW_NANOBOT_HOME/config.json}"

GATEWAY_PORT="${DESKCLAW_ADAPTER_PORT:-18790}"
GATEWAY_HOST="${DESKCLAW_ADAPTER_HOST:-127.0.0.1}"
WEBUI_PORT="${WEBUI_PORT:-18780}"
WEBUI_HOST="${WEBUI_HOST:-0.0.0.0}"

DESKCLAW_MODEL="${DESKCLAW_MODEL:-qwen3.5-plus}"
DESKCLAW_API_BASE="${DESKCLAW_API_BASE:-}"
DESKCLAW_API_KEY="${DESKCLAW_API_KEY:-}"

GATEWAY_VENV="/opt/deskclaw/gateway-venv"
WEBUI_VENV="/opt/deskclaw/webui-venv"
GATEWAY_SRC="/opt/deskclaw/resources/gateway"
NANOBOT_WHEEL_GLOB="/opt/deskclaw/resources/nanobot/nanobot_ai-*.whl"
PATCH_ROOT="/opt/patches/nanobot-webui"
PATCH_APPLIER="/opt/patches/apply_webui_patches.py"

mkdir -p "$DESKCLAW_HOME" "$DESKCLAW_NANOBOT_HOME" "$(dirname "$NANOBOT_CONFIG_PATH")"

if [ ! -d "$GATEWAY_SRC" ] || [ ! -d "/opt/deskclaw/resources/nanobot" ]; then
  echo "DeskClaw 资源目录缺失: /opt/deskclaw/resources/{gateway,nanobot}" >&2
  echo "请先在仓库执行: python3 docker-customize/scripts/prepare-deskclaw-resources.py" >&2
  exit 1
fi

if [ ! -f "$NANOBOT_CONFIG_PATH" ]; then
  cat > "$NANOBOT_CONFIG_PATH" <<EOF
{
  "agents": {
    "defaults": {
      "workspace": "${DESKCLAW_NANOBOT_HOME}/workspace",
      "model": "${DESKCLAW_MODEL}",
      "provider": "custom"
    }
  },
  "providers": {
    "custom": {
      "api_key": "${DESKCLAW_API_KEY}",
      "api_base": "${DESKCLAW_API_BASE}"
    }
  },
  "tools": {
    "mcp_servers": {
      "deskclaw": {
        "type": "streamableHttp",
        "url": "http://${GATEWAY_HOST}:${GATEWAY_PORT}/deskclaw/mcp",
        "tool_timeout": 30,
        "enabled_tools": ["*"]
      }
    }
  }
}
EOF
fi

if [ ! -x "${GATEWAY_VENV}/bin/deskclaw-gateway" ]; then
  python3 -m venv "$GATEWAY_VENV"
  "${GATEWAY_VENV}/bin/pip" install -U pip setuptools wheel
  WHEEL_PATH="$(ls $NANOBOT_WHEEL_GLOB | head -n 1)"
  if [ -z "${WHEEL_PATH:-}" ]; then
    echo "未找到 DeskClaw nanobot wheel: $NANOBOT_WHEEL_GLOB" >&2
    exit 1
  fi
  "${GATEWAY_VENV}/bin/pip" install "$WHEEL_PATH"
  "${GATEWAY_VENV}/bin/pip" install "$GATEWAY_SRC"
fi

if [ ! -x "${WEBUI_VENV}/bin/nanobot" ]; then
  python3 -m venv "$WEBUI_VENV"
  "${WEBUI_VENV}/bin/pip" install -U pip setuptools wheel
  "${WEBUI_VENV}/bin/pip" install nanobot-webui
fi

if [ -d "$PATCH_ROOT" ] && [ -f "$PATCH_APPLIER" ]; then
  "${WEBUI_VENV}/bin/python" "$PATCH_APPLIER" "$PATCH_ROOT" || true
fi

echo "[deskclaw] gateway: http://${GATEWAY_HOST}:${GATEWAY_PORT}"
echo "[deskclaw] webui:   http://${WEBUI_HOST}:${WEBUI_PORT}"

export DESKCLAW_HOME
export DESKCLAW_NANOBOT_HOME
export NANOBOT_CONFIG_PATH
export DESKCLAW_ADAPTER_HOST="$GATEWAY_HOST"
export DESKCLAW_ADAPTER_PORT="$GATEWAY_PORT"
export WEBUI_USE_DESKCLAW_GATEWAY="true"
export DESKCLAW_GATEWAY_BASE="http://${GATEWAY_HOST}:${GATEWAY_PORT}"

"${GATEWAY_VENV}/bin/deskclaw-gateway" &
GATEWAY_PID=$!

cleanup() {
  kill -TERM "$GATEWAY_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec "${WEBUI_VENV}/bin/nanobot" webui start --webui-only --host "$WEBUI_HOST" --port "$WEBUI_PORT" --config "$NANOBOT_CONFIG_PATH"
