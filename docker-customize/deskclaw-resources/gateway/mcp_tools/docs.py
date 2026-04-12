"""Documentation tools: read_docs and user_faq."""

from __future__ import annotations


def register(mcp) -> None:
    from ..docs_internal import DOCS
    from ..docs_faq import FAQ

    @mcp.tool()
    async def read_docs(topic: str) -> str:
        """读取 DeskClaw 内部系统文档（架构与实现细节）。当你需要了解自身架构、配置机制或内部工作原理时使用此工具。
        如果用户询问的是使用方法或遇到问题，优先使用 user_faq 工具。

        可用主题：
        - system — 系统架构概览（组件关系、核心能力、工作目录、重启机制）
        - configuration — LLM 配置指南（config.json 结构、修改流程、Provider 说明、配置安全）
        - security — 安全与审批管理（审批机制、完全访问模式、白名单、Bot 控制）
        - sandbox — 沙箱管理指南（执行模式、网络模式、Docker/Podman 支持）
        - loop_guard — 循环守卫（死循环检测、灵敏度配置、MCP 工具说明）
        - cron — 定时任务管理（创建、查看、删除、调度类型）
        - diagnostics — 故障诊断与升级处理（日志位置、自诊断工具、处理原则、反馈引导）
        - extensions — 扩展管理（目录结构、内置扩展、工具流程、创建新扩展）
        - channels — 外部消息通道配置（飞书、QQ、钉钉、企业微信、微信个人 weixin）

        Args:
            topic: 文档主题名。可选值：system, configuration, security, sandbox, loop_guard, cron, diagnostics, extensions, channels。
        """
        doc = DOCS.get(topic)
        if doc:
            return doc
        return (
            f"Unknown topic: '{topic}'. "
            f"Available topics: {', '.join(sorted(DOCS.keys()))}"
        )

    @mcp.tool()
    async def user_faq(topic: str) -> str:
        """查询用户使用帮助。当用户询问 DeskClaw 的使用方法、功能说明或遇到问题时，使用此工具获取解答。

        可用主题：
        - getting_started — 新手入门（首次启动、登录激活、API 配置、快捷操作）
        - chat — 聊天功能（多会话、图片、审批、上下文用量、执行中追加指令）
        - skills — 技能管理（查看、安装、配置、更新、内置技能说明）
        - settings — 设置说明（API、MCP、安全、主题语言）
        - cron — 定时任务（查看、创建、管理、执行历史）
        - channels — 外部通道（飞书/QQ/钉钉/企业微信/微信个人配置与排障）
        - troubleshooting — 常见问题排查（连接问题、配置错误、安装失败等）
        - pet — 桌面宠物（操作、菜单）
        - personalization — 个性化设置（配置项、保存方式）

        Args:
            topic: 帮助主题。可选值：getting_started, chat, skills, settings, cron, channels, troubleshooting, pet, personalization。
        """
        doc = FAQ.get(topic)
        if doc:
            return doc
        return (
            f"没有找到主题 '{topic}'。\n"
            f"可用主题：{', '.join(sorted(FAQ.keys()))}"
        )
