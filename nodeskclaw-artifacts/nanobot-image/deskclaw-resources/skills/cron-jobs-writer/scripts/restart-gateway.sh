#!/usr/bin/env bash
# 修改 jobs.json 后重启 Gateway，彻底 kill 后 start，避免双实例
# Usage: restart-gateway.sh
# 端口: 18789

set -e

# 1. 用 pkill 杀掉 Gateway 进程（匹配 gateway --port 18789，避免误杀 openclaw gateway start）
pkill -f "gateway --port 18789" 2>/dev/null || true

# 2. 若 pkill 未命中，用端口兜底（某些环境下进程名可能不同）
pid=$(lsof -t -i :18789 2>/dev/null)
if [[ -n "$pid" ]]; then
  kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
fi

# 3. 等待进程完全退出
sleep 3

# 4. 启动 Gateway（launchd 管理，单实例）
openclaw gateway start
