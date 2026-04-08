FROM python:3.13-slim-bookworm

ARG NANOBOT_VERSION=0.1.5
ARG IMAGE_VERSION=v0.1.5
ARG PIP_INDEX_URL=""
ARG PIP_TRUSTED_HOST=""
ARG APT_MIRROR=""

ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gettext-base && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "nanobot-ai==${NANOBOT_VERSION}"

COPY nodeskclaw-tunnel-bridge/ /tmp/nodeskclaw-tunnel-bridge/
RUN pip install --no-cache-dir /tmp/nodeskclaw-tunnel-bridge/ && \
    rm -rf /tmp/nodeskclaw-tunnel-bridge/

# DeskClaw 定制版 nanobot 资源（复制接入，不依赖 projects 源码目录）
COPY deskclaw-resources/ /opt/deskclaw/resources/
COPY patches/nanobot-webui/ /opt/patches/nanobot-webui/
COPY scripts/apply_webui_patches.py /opt/patches/apply_webui_patches.py
COPY scripts/start-deskclaw-webui.sh /opt/deskclaw/scripts/start-deskclaw-webui.sh
COPY scripts/restart-deskclaw.sh /opt/deskclaw/scripts/restart-deskclaw.sh

RUN chmod +x /opt/patches/apply_webui_patches.py \
    /opt/deskclaw/scripts/start-deskclaw-webui.sh \
    /opt/deskclaw/scripts/restart-deskclaw.sh && \
    WHEEL_PATH="$(ls /opt/deskclaw/resources/nanobot/nanobot_ai-*.whl | sed -n '1p')" && \
    pip install --no-cache-dir "$WHEEL_PATH" && \
    pip install --no-cache-dir \
      "fastapi>=0.115.0" \
      "uvicorn>=0.34.0" \
      "websockets>=14.0" \
      "wecom-aibot-sdk-python>=0.1.5" \
      "qrcode[pil]>=8.0" \
      "pycryptodome>=3.20.0" \
      "nanobot-webui" && \
    python /opt/patches/apply_webui_patches.py /opt/patches/nanobot-webui

COPY config.json.template /opt/nanobot/config.json.template
COPY docker-entrypoint.sh /opt/nanobot/docker-entrypoint.sh
RUN chmod +x /opt/nanobot/docker-entrypoint.sh

RUN echo "${IMAGE_VERSION}" > /opt/nanobot/.nanobot-version

ENV PYTHONPATH="/opt/deskclaw/resources:${PYTHONPATH}" \
    DESKCLAW_ADAPTER_HOST=127.0.0.1 \
    DESKCLAW_ADAPTER_PORT=18790

EXPOSE 18790 18780
WORKDIR /opt/nanobot

ENTRYPOINT ["/opt/nanobot/docker-entrypoint.sh"]
CMD ["python", "-m", "gateway.server"]
