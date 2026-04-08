#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_DIR="${SCRIPT_DIR}/nanobot-image"

VERSION="${1:-0.1.5}"
IMAGE_TAG="${2:-local}"
IMAGE_NAME="${3:-nodeskclaw/nanobot}"

if [ ! -d "$IMAGE_DIR" ]; then
  echo "[build-nanobot] image dir not found: $IMAGE_DIR" >&2
  exit 1
fi

echo "[build-nanobot] building ${IMAGE_NAME}:${IMAGE_TAG}"
echo "[build-nanobot] NANOBOT_VERSION=${VERSION}"

docker build \
  --platform linux/amd64 \
  --build-arg "NANOBOT_VERSION=${VERSION}" \
  --build-arg "IMAGE_VERSION=${IMAGE_TAG}" \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  "$IMAGE_DIR"

echo "[build-nanobot] done: ${IMAGE_NAME}:${IMAGE_TAG}"
