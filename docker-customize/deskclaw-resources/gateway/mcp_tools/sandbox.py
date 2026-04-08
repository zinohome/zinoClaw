"""Sandbox management tools."""

from __future__ import annotations

import json

from . import _read_allowlist, _write_allowlist, _bot_control_allowed


def register(mcp) -> None:
    @mcp.tool()
    async def sandbox_status() -> str:
        """获取沙箱状态：容器运行时是否可用、镜像是否就绪、当前模式和网络配置。"""
        from ..security.sandbox.runtime import detect_runtime, get_status

        rt = detect_runtime()
        status = get_status(rt)
        allowlist = _read_allowlist()
        status["sandbox_mode"] = allowlist.get("sandbox", "transparent")
        status["sandbox_network"] = allowlist.get("sandbox_network", "none")
        return json.dumps(status, ensure_ascii=False, default=str)

    @mcp.tool()
    async def sandbox_set_mode(mode: str) -> str:
        """设置沙箱执行模式。

        Args:
            mode: "transparent"（直接在宿主机执行）或 "isolated"（在 Docker 容器内执行）。
        """
        if not _bot_control_allowed():
            return json.dumps({"error": "Bot control is disabled by user. Enable it in Settings → Security."})
        if mode not in ("transparent", "isolated"):
            return json.dumps({"error": f"Invalid mode: {mode}. Use 'transparent' or 'isolated'."})
        data = _read_allowlist()
        data["sandbox"] = mode
        _write_allowlist(data)
        return json.dumps({"ok": True, "sandbox": mode})

    @mcp.tool()
    async def sandbox_set_network(network: str) -> str:
        """设置沙箱容器的网络模式，修改后需调用 sandbox_restart 生效。

        Args:
            network: 网络模式。常用值：
                     - "none" — 禁用网络（最安全）
                     - "host" — 共享宿主机网络
                     - 其他值对应 docker run --network 参数
        """
        if not _bot_control_allowed():
            return json.dumps({"error": "Bot control is disabled by user. Enable it in Settings → Security."})
        network = network.strip()
        if not network:
            return json.dumps({"error": "network must not be empty"})
        data = _read_allowlist()
        data["sandbox_network"] = network
        _write_allowlist(data)
        return json.dumps({"ok": True, "sandbox_network": network, "hint": "Call sandbox_restart to apply."})

    @mcp.tool()
    async def sandbox_restart() -> str:
        """重启沙箱容器，应用最新的网络和模式配置。返回容器实际状态。"""
        if not _bot_control_allowed():
            return json.dumps({"error": "Bot control is disabled by user. Enable it in Settings → Security."})
        try:
            from ..security.builtin_plugins.container_sandbox import restart_executor
            result = await restart_executor()
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)})
