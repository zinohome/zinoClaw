#!/usr/bin/with-contenv bash
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
GATEWAY_PYTHONPATH="/opt/deskclaw/resources"
SKILLS_SRC="/opt/deskclaw/resources/skills"
SKILLS_DST="${DESKCLAW_NANOBOT_HOME}/workspace/skills"
mkdir -p "$DESKCLAW_HOME" "$DESKCLAW_NANOBOT_HOME" "$(dirname "$NANOBOT_CONFIG_PATH")"
chown -R abc:abc "$DESKCLAW_HOME" || true

cleanup_listen_port() {
  local port="$1"
  local name="$2"
  local pids
  pids="$( (lsof -tiTCP:"$port" -sTCP:LISTEN || true) 2>/dev/null )"
  if [ -z "${pids}" ]; then
    return 0
  fi

  echo "[deskclaw] ${name} port :${port} is already in use by PID(s): ${pids}. Stopping stale process(es)..."
  # shellcheck disable=SC2086
  kill -TERM ${pids} 2>/dev/null || true

  for _ in $(seq 1 20); do
    pids="$( (lsof -tiTCP:"$port" -sTCP:LISTEN || true) 2>/dev/null )"
    if [ -z "${pids}" ]; then
      echo "[deskclaw] ${name} port :${port} released."
      return 0
    fi
    sleep 0.2
  done

  echo "[deskclaw] ${name} port :${port} still busy after TERM. Sending KILL to PID(s): ${pids}."
  # shellcheck disable=SC2086
  kill -KILL ${pids} 2>/dev/null || true
  sleep 0.2
}

# 幂等同步内置 skills：只补缺失，不覆盖用户已有修改
if [ -d "$SKILLS_SRC" ]; then
  mkdir -p "$SKILLS_DST"
  cp -rn "$SKILLS_SRC"/. "$SKILLS_DST"/ 2>/dev/null || true
  chown -R abc:abc "$SKILLS_DST" || true
fi

if [ ! -x "${GATEWAY_VENV}/bin/python" ]; then
  echo "gateway python 运行时缺失于 ${GATEWAY_VENV}，请重新构建镜像。" >&2
  exit 1
fi

if [ ! -x "${WEBUI_VENV}/bin/nanobot" ]; then
  echo "nanobot-webui 未预安装到 ${WEBUI_VENV}，请重新构建镜像。" >&2
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

# 幂等补齐 DeskClaw MCP server 配置（不覆盖用户其他配置）。
# 某些历史 config.json 没有这段，会导致 DeskClaw 工具不可用。
"${WEBUI_VENV}/bin/python" - <<PY
import json
from pathlib import Path

cfg_path = Path("${NANOBOT_CONFIG_PATH}")
cfg = {}
if cfg_path.exists():
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}

tools = cfg.setdefault("tools", {})

# 兼容两种字段风格，避免同时写出 mcpServers + mcp_servers
snake = tools.get("mcp_servers")
camel = tools.get("mcpServers")

if isinstance(camel, dict):
    mcp_map = camel
    map_style = "camel"
elif isinstance(snake, dict):
    mcp_map = snake
    map_style = "snake"
else:
    mcp_map = tools.setdefault("mcp_servers", {})
    map_style = "snake"

deskclaw = mcp_map.get("deskclaw")

desired = {
    "type": "streamableHttp",
    "url": "http://${GATEWAY_HOST}:${GATEWAY_PORT}/deskclaw/mcp",
    "tool_timeout": 30,
    "enabled_tools": ["*"],
}

if not isinstance(deskclaw, dict):
    mcp_map["deskclaw"] = desired
else:
    deskclaw.setdefault("type", "streamableHttp")
    deskclaw["url"] = desired["url"]
    deskclaw.setdefault("tool_timeout", 30)
    deskclaw.setdefault("enabled_tools", ["*"])

# 若历史上两套键都存在，清理另一套，避免重复
if map_style == "camel":
    tools.pop("mcp_servers", None)
else:
    tools.pop("mcpServers", None)

cfg_path.parent.mkdir(parents=True, exist_ok=True)
cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
PY

echo "[deskclaw] gateway: http://${GATEWAY_HOST}:${GATEWAY_PORT}"
echo "[deskclaw] webui:   http://${WEBUI_HOST}:${WEBUI_PORT}"

export DESKCLAW_HOME
export DESKCLAW_NANOBOT_HOME
export NANOBOT_CONFIG_PATH
export DESKCLAW_ADAPTER_HOST="$GATEWAY_HOST"
export DESKCLAW_ADAPTER_PORT="$GATEWAY_PORT"
export WEBUI_USE_DESKCLAW_GATEWAY="true"
export DESKCLAW_GATEWAY_BASE="http://${GATEWAY_HOST}:${GATEWAY_PORT}"

# restart 流程中可能出现旧实例残留，先清理端口避免重复拉起时冲突
cleanup_listen_port "$GATEWAY_PORT" "gateway"
cleanup_listen_port "$WEBUI_PORT" "webui"

# webtop/linuxserver 使用 abc 用户运行应用进程；用 s6-setuidgid 降权。
s6-setuidgid abc env \
  PYTHONPATH="${GATEWAY_PYTHONPATH}" \
  DESKCLAW_HOME="${DESKCLAW_HOME}" \
  DESKCLAW_NANOBOT_HOME="${DESKCLAW_NANOBOT_HOME}" \
  NANOBOT_CONFIG_PATH="${NANOBOT_CONFIG_PATH}" \
  DESKCLAW_ADAPTER_HOST="${GATEWAY_HOST}" \
  DESKCLAW_ADAPTER_PORT="${GATEWAY_PORT}" \
  "${GATEWAY_VENV}/bin/python" -m gateway.server &
GATEWAY_PID=$!

# 等待 gateway 健康，再启动 webui，避免 MCP 初始化抢跑
for _ in $(seq 1 60); do
  if curl -fsS "http://${GATEWAY_HOST}:${GATEWAY_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://${GATEWAY_HOST}:${GATEWAY_PORT}/health" >/dev/null 2>&1; then
  echo "[deskclaw] gateway health check failed: http://${GATEWAY_HOST}:${GATEWAY_PORT}/health" >&2
  kill -TERM "$GATEWAY_PID" 2>/dev/null || true
  wait "$GATEWAY_PID" 2>/dev/null || true
  exit 1
fi

s6-setuidgid abc "${WEBUI_VENV}/bin/nanobot" webui start --webui-only --host "$WEBUI_HOST" --port "$WEBUI_PORT" --config "$NANOBOT_CONFIG_PATH" &
WEBUI_PID=$!

wait -n "$GATEWAY_PID" "$WEBUI_PID"
EXIT_CODE=$?

kill -TERM "$GATEWAY_PID" "$WEBUI_PID" 2>/dev/null || true
wait "$GATEWAY_PID" "$WEBUI_PID" 2>/dev/null || true
exit "$EXIT_CODE"
