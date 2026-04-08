"""Gateway management tools: restart, health, config read/write."""

from __future__ import annotations

import json
import os
import signal
import time

from . import NANOBOT_CONFIG_PATH, _read_allowlist, read_config_raw, write_config_raw

_start_time = time.time()

# ── Pending-action state (consumed by server.py after each turn) ─

_pending_action: str | None = None


def get_pending_action() -> str | None:
    return _pending_action


def consume_pending_action() -> str | None:
    global _pending_action
    action = _pending_action
    _pending_action = None
    return action


def _do_restart_gateway() -> None:
    os.kill(os.getpid(), signal.SIGTERM)


def _do_restart_deskclaw() -> None:
    os._exit(42)


# ── Channel helper ────────────────────────────────────────────────


def _ensure_channel_defaults(config: dict) -> None:
    """Auto-populate required fields for enabled channels to prevent crash loops."""
    channels = config.get("channels")
    if not isinstance(channels, dict):
        return
    for ch_cfg in channels.values():
        if not isinstance(ch_cfg, dict):
            continue
        enabled = ch_cfg.get("enabled")
        if enabled is True or (isinstance(enabled, str) and enabled.lower() == "true"):
            if "allowFrom" not in ch_cfg:
                ch_cfg["allowFrom"] = ["*"]


# ── Tool registration ─────────────────────────────────────────────


def register(mcp) -> None:
    @mcp.tool()
    async def restart_gateway() -> str:
        """重启网关进程以应用配置变更。

        调用后网关会等待当前轮次 ``_process_message`` 结束（含飞书/企微等外部通道与桌面 WebSocket），
        约 1 秒后向本进程发 SIGTERM。由 Electron/进程管理器拉起新网关；桌面端 WebSocket 会重连。

        适用场景：修改了 config.json 中的 provider/model/tools/channels 配置后需要生效。

        重要：调用此工具后，请直接回复用户告知即将重启，不要再调用任何其他工具。
        """
        from nanobot.config.schema import Config

        try:
            raw = json.loads(NANOBOT_CONFIG_PATH.read_text(encoding="utf-8"))
            Config.model_validate(raw)
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"Config validation failed, restart aborted: {e}",
                "hint": "Fix config.json and try again.",
            })

        global _pending_action
        _pending_action = "gateway"
        return (
            "Restart scheduled. The gateway will restart AFTER this response is fully sent. "
            "Do NOT call any more tools. Reply to the user and finish your turn."
        )

    @mcp.tool()
    async def get_health() -> str:
        """获取网关健康状态，包括运行时间、Agent 是否就绪等信息。"""
        from ..server import agent

        uptime = int(time.time() - _start_time)
        agent_ready = agent._agent is not None
        return json.dumps({
            "status": "ok",
            "uptime_seconds": uptime,
            "agent_ready": agent_ready,
        }, ensure_ascii=False)

    @mcp.tool()
    async def get_config(section: str = "") -> str:
        """读取当前 Gateway 配置。

        Args:
            section: 可选，指定返回的配置段落。可选值：agents, providers, tools, gateway, channels。
                     留空则返回完整配置。
        """
        config = read_config_raw()
        if not config:
            return json.dumps({"error": "Cannot read config"})

        if section and section in config:
            return json.dumps({section: config[section]}, indent=2, ensure_ascii=False)
        return json.dumps(config, indent=2, ensure_ascii=False)

    @mcp.tool()
    async def update_config(path: str, value: str) -> str:
        """更新 Gateway 配置的指定字段，修改后需要调用 restart_gateway 才能生效。

        Args:
            path: 配置路径，用点号分隔。例如：
                  - "agents.defaults.model" 修改默认模型
                  - "agents.defaults.temperature" 修改温度
                  - "providers.custom.api_key" 修改 API Key
                  - "providers.custom.api_base" 修改 API URL
                  - "channels.feishu.enabled" 启用飞书通道
            value: 新值（JSON 格式字符串）。例如 '"gpt-4o"' 或 '0.5' 或 'true'。
        """
        config = read_config_raw()

        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value

        keys = path.split(".")
        obj = config
        for k in keys[:-1]:
            if k not in obj or not isinstance(obj[k], dict):
                obj[k] = {}
            obj = obj[k]
        obj[keys[-1]] = parsed_value

        _ensure_channel_defaults(config)

        from nanobot.config.schema import Config

        try:
            Config.model_validate(config)
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"Config validation failed: {e}",
                "hint": "Fix the value and try again.",
            })

        write_config_raw(config)
        return json.dumps({"ok": True, "path": path, "hint": "Call restart_gateway to apply changes."})

    # ── Conditional: restart_deskclaw ──────────────────────────────
    allowlist = _read_allowlist()
    if allowlist.get("enable_restart_deskclaw", False):
        @mcp.tool()
        async def restart_deskclaw() -> str:
            """重启整个 DeskClaw 应用（包括 Electron 主进程和网关）。

            此操作会关闭当前所有窗口并重新启动应用。仅在必须重启整个应用时使用
            （例如插件更新、渲染器更新等）。普通配置变更请使用 restart_gateway。
            """
            global _pending_action
            _pending_action = "deskclaw"
            return (
                "App relaunch scheduled. DeskClaw will restart AFTER this response is fully sent. "
                "Do NOT call any more tools. Reply to the user and finish your turn."
            )
