#!/bin/bash
# 复制默认工作区文件到配置文件目录
if [ ! -d "/config/.openclaw/workspace" ]; then
    echo "初始化 openclaw 默认 workspace..."
    mkdir -p "/config/.openclaw/workspace"
    cp -r /defaults/openclaw-workspace/* "/config/.openclaw/workspace/"
    # 确保权限正确
    # chown -R abc:abc "/config/.openclaw/workspace"
fi
