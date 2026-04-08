"""MCP server configuration tools: list, add/update, remove."""

from __future__ import annotations

import json

from . import NANOBOT_CONFIG_PATH, BUILTIN_MCP_SERVERS, read_config_raw, write_config_raw


def register(mcp) -> None:
    @mcp.tool()
    async def mcp_server_list() -> str:
        """列出所有已配置的 MCP 服务器，包括名称、连接类型和连接信息。

        返回 JSON 数组，每个元素包含 name（名称）、type（连接类型）、以及连接详情。
        内置服务器（如 deskclaw）会标记 builtin: true。
        """
        config = read_config_raw()
        servers = config.get("tools", {}).get("mcp_servers", {})

        result = []
        for name, cfg in servers.items():
            entry = {"name": name, "builtin": name in BUILTIN_MCP_SERVERS}
            if isinstance(cfg, dict):
                entry.update(cfg)
            result.append(entry)

        return json.dumps(result, indent=2, ensure_ascii=False)

    @mcp.tool()
    async def mcp_server_add(
        name: str,
        type: str = "",
        command: str = "",
        args: str = "",
        url: str = "",
        headers: str = "",
        env: str = "",
        tool_timeout: int = 30,
        enabled_tools: str = '["*"]',
    ) -> str:
        """添加或更新一个 MCP 服务器配置。修改后需调用 restart_gateway 才能生效。

        支持三种连接类型：
        - stdio: 本地命令启动的 MCP 服务器（需提供 command 和 args）
        - sse: 通过 SSE 协议连接的远程服务器（需提供 url）
        - streamableHttp: 通过 HTTP 流连接的远程服务器（需提供 url）

        type 留空时会自动推断：有 command → stdio，有 url 且以 /sse 结尾 → sse，否则 → streamableHttp。

        使用示例：
        - 添加 GitHub MCP: name="github", command="npx", args="-y @modelcontextprotocol/server-github",
          env='{"GITHUB_TOKEN":"ghp_xxx"}'
        - 添加远程 MCP: name="remote", url="https://api.example.com/mcp",
          headers='{"Authorization":"Bearer xxx"}'

        Args:
            name: 服务器名称（唯一标识），如 "github"、"filesystem"。不可与内置服务器同名。
            type: 连接类型。可选值："stdio"、"sse"、"streamableHttp"。留空自动推断。
            command: stdio 模式的启动命令，如 "npx"、"uvx"、"node"。
            args: stdio 模式的命令参数，空格分隔。如 "-y @modelcontextprotocol/server-github"。
            url: HTTP/SSE 模式的服务器端点 URL。如 "http://localhost:3000/mcp"。
            headers: HTTP 请求头，JSON 对象格式。如 '{"Authorization": "Bearer xxx"}'。
            env: 环境变量，JSON 对象格式。如 '{"GITHUB_TOKEN": "ghp_xxx"}'。
            tool_timeout: 单个工具调用的超时秒数，默认 30。
            enabled_tools: 启用的工具白名单，JSON 数组格式。默认 '["*"]' 表示全部启用。
        """
        if name in BUILTIN_MCP_SERVERS:
            return json.dumps({"ok": False, "error": f"Cannot modify built-in server '{name}'."})

        name = name.strip()
        if not name:
            return json.dumps({"ok": False, "error": "Server name must not be empty."})

        # Build server config dict
        server_cfg: dict = {}

        if type:
            if type not in ("stdio", "sse", "streamableHttp"):
                return json.dumps({
                    "ok": False,
                    "error": f"Invalid type '{type}'. Use 'stdio', 'sse', or 'streamableHttp'.",
                })
            server_cfg["type"] = type

        if command:
            server_cfg["command"] = command
        if args:
            server_cfg["args"] = args.strip().split()
        if url:
            server_cfg["url"] = url

        if headers:
            try:
                parsed = json.loads(headers)
                if not isinstance(parsed, dict):
                    return json.dumps({"ok": False, "error": "headers must be a JSON object."})
                server_cfg["headers"] = parsed
            except json.JSONDecodeError:
                return json.dumps({"ok": False, "error": "Invalid headers JSON."})

        if env:
            try:
                parsed = json.loads(env)
                if not isinstance(parsed, dict):
                    return json.dumps({"ok": False, "error": "env must be a JSON object."})
                server_cfg["env"] = parsed
            except json.JSONDecodeError:
                return json.dumps({"ok": False, "error": "Invalid env JSON."})

        if tool_timeout > 0:
            server_cfg["tool_timeout"] = tool_timeout

        if enabled_tools:
            try:
                parsed = json.loads(enabled_tools)
                if not isinstance(parsed, list):
                    return json.dumps({"ok": False, "error": "enabled_tools must be a JSON array."})
                server_cfg["enabled_tools"] = parsed
            except json.JSONDecodeError:
                return json.dumps({"ok": False, "error": "Invalid enabled_tools JSON."})

        # Validate the individual server entry
        from nanobot.config.schema import MCPServerConfig
        try:
            MCPServerConfig.model_validate(server_cfg)
        except Exception as e:
            return json.dumps({"ok": False, "error": f"Server config validation failed: {e}"})

        # Read full config, merge, validate, write
        config = read_config_raw()
        tools = config.setdefault("tools", {})
        servers = tools.setdefault("mcp_servers", {})
        is_update = name in servers
        servers[name] = server_cfg

        from nanobot.config.schema import Config
        try:
            Config.model_validate(config)
        except Exception as e:
            return json.dumps({"ok": False, "error": f"Full config validation failed: {e}"})

        write_config_raw(config)

        action = "updated" if is_update else "added"
        return json.dumps({
            "ok": True,
            "action": action,
            "name": name,
            "config": server_cfg,
            "hint": "Call restart_gateway to apply changes.",
        }, ensure_ascii=False)

    @mcp.tool()
    async def mcp_server_remove(name: str) -> str:
        """删除一个已配置的 MCP 服务器。删除后需调用 restart_gateway 生效。

        注意：内置服务器（如 deskclaw）不可删除。

        Args:
            name: 要删除的服务器名称。
        """
        if name in BUILTIN_MCP_SERVERS:
            return json.dumps({"ok": False, "error": f"Cannot remove built-in server '{name}'."})

        config = read_config_raw()
        servers = config.get("tools", {}).get("mcp_servers", {})

        if name not in servers:
            available = [n for n in servers if n not in BUILTIN_MCP_SERVERS]
            return json.dumps({
                "ok": False,
                "error": f"Server '{name}' not found.",
                "available": available,
            })

        del servers[name]
        write_config_raw(config)

        return json.dumps({
            "ok": True,
            "name": name,
            "hint": "Call restart_gateway to apply changes.",
        })
