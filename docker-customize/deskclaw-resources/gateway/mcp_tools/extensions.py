"""MCP tools for managing DeskClaw extensions.

Tools: extension_list, extension_info, extension_toggle,
       extension_config_set, extension_reload, extension_create.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from . import DESKCLAW_HOME

_EXTENSIONS_DIR = DESKCLAW_HOME / "extensions"


def _get_agent():
    try:
        from ..server import agent
        return agent
    except Exception:
        return None


def _get_registry():
    ag = _get_agent()
    return getattr(ag, "_extension_registry", None) if ag else None


def register(mcp) -> None:

    @mcp.tool()
    async def extension_list() -> str:
        """List all installed extensions and their status (including disabled ones)."""
        registry = _get_registry()
        if registry is None:
            return "Extension system not active."
        entries = registry.list_all()
        if not entries:
            return (
                "No extensions installed.\n\n"
                f"Extensions live in `{_EXTENSIONS_DIR}/<name>/` directories.\n"
                "Use `extension_create` to scaffold a new one."
            )
        lines = []
        for e in entries:
            status = "enabled" if e["enabled"] else "disabled"
            desc = e["description"] or ""
            readme_hint = " (has README)" if e.get("has_readme") else ""
            pri = e.get("priority", 100)
            lines.append(
                f"- **{e['name']}** [{status}, priority={pri}]{readme_hint}"
                + (f"  {desc}" if desc else "")
            )
        lines.append("")
        lines.append("Use `extension_info(name)` to read an extension's README and config.")
        return "\n".join(lines)

    @mcp.tool()
    async def extension_info(name: str) -> str:
        """Read an extension's README and current config.

        Use this to learn what an extension does and how to configure it
        before enabling or modifying its settings.

        Args:
            name: Extension name (directory name under ~/.deskclaw/extensions/).
        """
        registry = _get_registry()
        if registry is None:
            return "Extension system not active."
        discovered = registry.get_discovered(name)

        if discovered is None:
            ext_dir = _EXTENSIONS_DIR / name
            if not ext_dir.is_dir():
                return f"Extension '{name}' not found."
            readme = _read_file(ext_dir / "README.md")
            config = _read_file(ext_dir / "config.json")
        else:
            readme = discovered.readme
            config = json.dumps(discovered.config, indent=2, ensure_ascii=False) if discovered.config else ""

        parts = []
        if readme:
            parts.append(readme)
        else:
            parts.append(f"# {name}\n\nNo README available.")
        if config:
            parts.append(f"## Current config.json\n\n```json\n{config}\n```")
        return "\n\n".join(parts)

    @mcp.tool()
    async def extension_toggle(name: str, enabled: bool) -> str:
        """Enable or disable an extension.

        Updates config.json on disk and toggles the runtime state.
        A reload may be required for newly-enabled extensions to take full effect.

        Args:
            name: Extension name (directory name).
            enabled: True to enable, False to disable.
        """
        config_path = _EXTENSIONS_DIR / name / "config.json"
        if not config_path.parent.is_dir():
            return f"Extension '{name}' not found."

        config = _load_json(config_path)
        config["enabled"] = enabled
        _save_json(config_path, config)

        registry = _get_registry()
        if registry is not None:
            registry.toggle(name, enabled)

        state = "enabled" if enabled else "disabled"
        hint = " Run `extension_reload` to activate it." if enabled else ""
        return f"Extension '{name}' is now {state}.{hint}"

    @mcp.tool()
    async def extension_config_set(name: str, key: str, value: str) -> str:
        """Set a configuration value for an extension.

        Updates the extension's config.json on disk. Use `extension_info`
        first to see available config keys.

        Args:
            name: Extension name (directory name).
            key: Config key to set (e.g. "url", "events", "dir").
            value: New value (JSON-encoded for non-string types, e.g. '["turn_end"]').
        """
        config_path = _EXTENSIONS_DIR / name / "config.json"
        if not config_path.parent.is_dir():
            return f"Extension '{name}' not found."

        config = _load_json(config_path)

        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            parsed = value

        config[key] = parsed
        _save_json(config_path, config)
        return f"Set `{name}`.`{key}` = {json.dumps(parsed, ensure_ascii=False)}"

    @mcp.tool()
    async def extension_reload() -> str:
        """Hot-reload all extensions from disk.

        Deactivates current extensions, re-discovers directories in
        ~/.deskclaw/extensions/, and activates enabled ones.
        """
        registry = _get_registry()
        if registry is None:
            return "Extension system not active."
        try:
            ag = _get_agent()
            if not ag:
                return "Gateway agent not available."
            await registry.reload(
                workspace=Path(ag.workspace),
                config={"model": ag._agent.model if ag._agent else None},
            )
            all_count = len(registry.list_all())
            active = len(registry.extensions)
            return f"Reloaded: {all_count} installed, {active} active."
        except Exception as exc:
            return f"Reload failed: {exc}"

    @mcp.tool()
    async def extension_create(
        name: str,
        description: str = "",
        hooks: str = "on_turn_end",
    ) -> str:
        """Create a new extension directory with boilerplate code.

        Scaffolds a ready-to-use extension with config.json (enabled)
        and a README.  Call ``extension_reload`` afterwards to activate.

        Args:
            name: Extension name (used as directory name, e.g. "my_notifier").
            description: One-line description of what this extension does.
            hooks: Comma-separated hook names to stub (e.g. "on_turn_end,on_tool_end").
        """
        dirname = name.replace("-", "_").replace(" ", "_")
        ext_dir = _EXTENSIONS_DIR / dirname
        if ext_dir.exists():
            return f"Directory already exists: {ext_dir}"

        ext_dir.mkdir(parents=True, exist_ok=True)

        hook_list = [h.strip() for h in hooks.split(",") if h.strip()]
        class_name = "".join(w.capitalize() for w in dirname.split("_")) + "Extension"

        _HOOK_SIGNATURES = {
            "on_before_model": ("async def on_before_model(self, ctx: AgentHookContext) -> None:", True),
            "on_after_iteration": ("async def on_after_iteration(self, ctx: AgentHookContext) -> None:", True),
            "on_before_tools": ("async def on_before_tools(self, ctx: AgentHookContext) -> None:", True),
            "on_stream": ("async def on_stream(self, ctx: AgentHookContext, delta: str) -> None:", True),
            "on_finalize_content": ("def on_finalize_content(self, ctx: AgentHookContext, content: str | None) -> str | None:", True),
            "on_turn_start": ("async def on_turn_start(self, session_key: str, message: str) -> None:", False),
            "on_turn_end": ("async def on_turn_end(self, session_key: str, response: str | None) -> None:", False),
            "on_tool_start": ("async def on_tool_start(self, tool: str, params: dict) -> dict | None:", False),
            "on_tool_end": ("async def on_tool_end(self, record) -> None:", False),
            "on_tool_intercept": ("async def on_tool_intercept(self, tool: str, params: dict) -> str | None:", False),
            "on_tool_result_transform": ("def on_tool_result_transform(self, tool: str, params: dict, result: str) -> str:", False),
            "on_memory_consolidate": ("async def on_memory_consolidate(self, session_key: str, summary: str) -> None:", False),
            "on_memory_archive": ("async def on_memory_archive(self, session_key: str, chunk: list[dict]) -> None:", False),
        }

        hook_methods = []
        needs_hook_ctx = False
        for h in hook_list:
            entry = _HOOK_SIGNATURES.get(h)
            if entry is None:
                continue
            sig, uses_ctx = entry
            if uses_ctx:
                needs_hook_ctx = True
            if "-> str" in sig and "| None" not in sig:
                body = "        return result"
            elif "-> str | None" in sig:
                body = "        return content"
            elif "-> dict" in sig:
                body = "        return None"
            else:
                body = "        pass  # TODO"
            hook_methods.append(f"    {sig}\n{body}")

        imports = "from gateway.extensions.base import DeskClawExtension, ExtensionContext"
        if needs_hook_ctx:
            imports += "\nfrom nanobot.agent.hook import AgentHookContext"

        methods_block = "\n\n".join(hook_methods) if hook_methods else "    pass"

        code = textwrap.dedent(f"""\
            # version: 1
            \"""{description or f'{class_name} extension.'}\"""

            {imports}


            class {class_name}(DeskClawExtension):
                name = "{name}"
                version = "1.0"
                description = "{description}"

                async def activate(self, ctx: ExtensionContext) -> None:
                    self.workspace = ctx.workspace

            {methods_block}
        """)

        py_path = ext_dir / f"{dirname}.py"
        py_path.write_text(code, encoding="utf-8")

        config = {"enabled": True, "priority": 100}
        _save_json(ext_dir / "config.json", config)

        readme = f"# {name}\n\n{description or 'Custom extension.'}\n"
        (ext_dir / "README.md").write_text(readme, encoding="utf-8")

        return (
            f"Created: {ext_dir}/\n"
            f"  {dirname}.py  — extension code\n"
            f"  config.json   — enabled by default\n"
            f"  README.md     — edit to document your extension\n\n"
            f"Call `extension_reload` to activate."
        )


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
