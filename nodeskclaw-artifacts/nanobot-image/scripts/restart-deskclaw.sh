#!/usr/bin/with-contenv bash
set -euo pipefail

SVC_DIR="/run/s6-rc/servicedirs/svc-deskclaw"
WEBUI_PORT="${WEBUI_PORT:-18780}"
GATEWAY_PORT="${DESKCLAW_ADAPTER_PORT:-18790}"
RESTART_MODE="${DESKCLAW_RESTART_MODE:-term}"

wait_port_closed() {
  local port="$1"
  for _ in $(seq 1 60); do
    if ! (lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1); then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

if [ ! -d "$SVC_DIR" ]; then
  echo "[restart-deskclaw] service dir not found: $SVC_DIR" >&2
  exit 1
fi

if [ "$RESTART_MODE" = "term" ]; then
  echo "[restart-deskclaw] TERM svc-deskclaw and let s6 auto-restart..."
  # TERM the supervised process without setting "down"; s6 should relaunch it.
  s6-svc -t "$SVC_DIR"
elif [ "$RESTART_MODE" = "cycle" ]; then
  echo "[restart-deskclaw] stopping svc-deskclaw..."
  s6-svc -d "$SVC_DIR" || true

  if ! wait_port_closed "$GATEWAY_PORT"; then
    echo "[restart-deskclaw] warning: gateway port :${GATEWAY_PORT} still in use after stop." >&2
  fi
  if ! wait_port_closed "$WEBUI_PORT"; then
    echo "[restart-deskclaw] warning: webui port :${WEBUI_PORT} still in use after stop." >&2
  fi

  echo "[restart-deskclaw] starting svc-deskclaw..."
  s6-svc -u "$SVC_DIR"
else
  echo "[restart-deskclaw] invalid DESKCLAW_RESTART_MODE=${RESTART_MODE}, expected: term|cycle" >&2
  exit 2
fi

echo "[restart-deskclaw] waiting for gateway health..."
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${GATEWAY_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://127.0.0.1:${GATEWAY_PORT}/health" >/dev/null 2>&1; then
  echo "[restart-deskclaw] gateway health check failed on :${GATEWAY_PORT}" >&2
  exit 1
fi

echo "[restart-deskclaw] checking webui port :${WEBUI_PORT}..."
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${WEBUI_PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "http://127.0.0.1:${WEBUI_PORT}/" >/dev/null 2>&1; then
  echo "[restart-deskclaw] webui check failed on :${WEBUI_PORT}" >&2
  exit 1
fi

echo "[restart-deskclaw] ok: gateway=:${GATEWAY_PORT}, webui=:${WEBUI_PORT}"
