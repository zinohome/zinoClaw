#!/bin/bash
set -euo pipefail

CONFIG_TEMPLATE="/opt/nanobot/config.json.template"
CONFIG_DIR="/root/.nanobot"
CONFIG_FILE="${CONFIG_DIR}/config.json"

mkdir -p "${CONFIG_DIR}"

if [ -f "${CONFIG_TEMPLATE}" ] && [ ! -f "${CONFIG_FILE}" ]; then
  envsubst < "${CONFIG_TEMPLATE}" > "${CONFIG_FILE}"
fi

if [ -f /opt/nanobot/.nanobot-version ]; then
  echo "Nanobot image version: $(cat /opt/nanobot/.nanobot-version)"
fi

exec "$@"
