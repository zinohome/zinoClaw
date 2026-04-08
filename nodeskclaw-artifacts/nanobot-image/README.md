# Nanobot 镜像构建

Nanobot 是基于 Python 的超轻量 AI Agent 运行时，提供 OpenAI 兼容的 API 接口。

## 目录结构

```
nanobot-image/
├── Dockerfile             # Base 镜像: python:3.13-slim-bookworm + DeskClaw 定制接入
├── Dockerfile.security    # 安全层镜像: FROM base + pip install 安全层 + startup wrapper
├── deskclaw-resources/    # 复制的 DeskClaw 定制资源（gateway / skills / security-plugins 等）
├── patches/nanobot-webui/ # 复制的 webui patch 集合
├── scripts/               # 复制的 DeskClaw 启动与补丁脚本
├── config.json.template   # Nanobot 配置模板（JSON 格式，envsubst 替换环境变量）
├── docker-entrypoint.sh   # 容器入口脚本
├── check-update.sh        # 版本检测脚本（查询 PyPI 最新稳定版）
└── README.md              # 本文件
```

## 构建

所有构建通过上级目录的 `build.sh` 统一入口执行：

源码仓库: [HKUDS/nanobot](https://github.com/HKUDS/nanobot)，PyPI 包名: `nanobot-ai`

### Base 镜像（无安全层）

```bash
cd nodeskclaw-artifacts
./build.sh nanobot                               # 自动检测 PyPI 最新稳定版
./build.sh nanobot --version 0.1.4               # 指定版本
./build.sh nanobot --version 0.1.4 --build-only
./build.sh nanobot --version 0.1.4 --skip-verify
```

### 安全层镜像

```bash
cd nodeskclaw-artifacts
# 需要先有 base 镜像（v0.1.4）
./build.sh nanobot --with-security --base-tag v0.1.4 --build-only
```

安全层镜像 FROM base，`pip install nanobot-security-layer`，CMD 替换为 `startup.py` wrapper 在同一进程内 monkey-patch `ToolRegistry.execute` 后启动 nanobot CLI。

**注意**: 构建目标平台为 `linux/amd64`，在 Apple Silicon 设备上通过 QEMU 模拟运行。

## NoDeskClaw Tunnel Bridge

镜像内置 `nodeskclaw-tunnel-bridge` Python 包，提供 NanoBot 与 NoDeskClaw 后端的 WebSocket tunnel 连接。

通过 NanoBot 的 `entry_points("nanobot.channels")` 自动发现注册，在 `config.json` 中启用 `channels.nodeskclaw.enabled: true`。

支持 @mention 回复控制：收到 `no_reply` 标志时，消息仍注入 AgentLoop（保留上下文），但丢弃回复。

## 镜像说明

- 基础镜像: `python:3.13-slim-bookworm`
- 通过 `pip install nanobot-ai` + `pip install nodeskclaw-tunnel-bridge` 安装
- 默认监听端口: `18790`（Gateway），并预留 `18780`（webui）
- 配置文件: `/root/.nanobot/config.json`（首次启动时从 `/opt/nanobot/config.json.template` 生成）
- 默认启动命令: `python -m gateway.server`（DeskClaw 定制网关）
