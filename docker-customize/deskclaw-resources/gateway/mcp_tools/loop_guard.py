"""Loop guard management tools."""

from __future__ import annotations

import json
from pathlib import Path

from . import _bot_control_allowed, DESKCLAW_HOME, read_config_raw, write_config_raw

_CONFIG_PATH = DESKCLAW_HOME / "loop-guard.json"

_VALID_SENSITIVITIES = ("conservative", "default", "relaxed", "custom")

_PRESETS = {
    "conservative": {"max_duplicate_calls": 2, "max_consecutive_errors": 3, "max_failed_per_turn": 15},
    "default":      {"max_duplicate_calls": 3, "max_consecutive_errors": 5, "max_failed_per_turn": 25},
    "relaxed":      {"max_duplicate_calls": 5, "max_consecutive_errors": 8, "max_failed_per_turn": 40},
}

_DEFAULTS = {
    "enabled": True,
    "sensitivity": "default",
    "max_duplicate_calls": 3,
    "max_consecutive_errors": 5,
    "max_failed_per_turn": 25,
    "turn_reset_seconds": 60,
}


def _read_config() -> dict:
    cfg = dict(_DEFAULTS)
    try:
        if _CONFIG_PATH.exists():
            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if "max_calls_per_turn" in raw and "max_failed_per_turn" not in raw:
                raw["max_failed_per_turn"] = raw.pop("max_calls_per_turn")
            cfg.update(raw)
    except (json.JSONDecodeError, OSError):
        pass
    return cfg


def _write_config(cfg: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _reload_runtime() -> None:
    """Hot-reload the running loop guard plugin if it's loaded in sys.modules."""
    import sys
    mod = sys.modules.get("security_plugin.loop_guard")
    if mod and hasattr(mod, "_safe_load_config"):
        try:
            mod._config = mod._safe_load_config()
        except Exception:
            pass


def register(mcp) -> None:
    @mcp.tool()
    async def loop_guard_status() -> str:
        """获取循环守卫当前配置：是否启用、灵敏度、各项阈值。"""
        cfg = _read_config()
        return json.dumps(cfg, ensure_ascii=False)

    @mcp.tool()
    async def loop_guard_set_enabled(enabled: bool) -> str:
        """启用或禁用循环守卫。

        Args:
            enabled: true 启用，false 禁用。
        """
        if not _bot_control_allowed():
            return json.dumps({"error": "Bot control is disabled by user. Enable it in Settings → Security."})
        cfg = _read_config()
        cfg["enabled"] = enabled
        _write_config(cfg)
        _reload_runtime()
        return json.dumps({"ok": True, "enabled": enabled})

    @mcp.tool()
    async def loop_guard_set_sensitivity(sensitivity: str) -> str:
        """设置循环守卫灵敏度预设，会覆盖对应的阈值参数。

        Args:
            sensitivity: 灵敏度预设。可选值：
                         - "conservative" — 保守（更早介入）
                         - "default" — 默认（平衡）
                         - "relaxed" — 宽松（更高容忍度，适合复杂任务）
                         - "custom" — 自定义（使用配置文件中的阈值）
        """
        if not _bot_control_allowed():
            return json.dumps({"error": "Bot control is disabled by user. Enable it in Settings → Security."})
        sensitivity = sensitivity.strip().lower()
        if sensitivity not in _VALID_SENSITIVITIES:
            return json.dumps({
                "error": f"Invalid sensitivity: {sensitivity}. Use one of: {', '.join(_VALID_SENSITIVITIES)}",
            })
        cfg = _read_config()
        cfg["sensitivity"] = sensitivity
        preset = _PRESETS.get(sensitivity)
        if preset:
            cfg.update(preset)
        _write_config(cfg)
        _reload_runtime()
        return json.dumps({"ok": True, **cfg})

    @mcp.tool()
    async def get_max_tool_iterations() -> str:
        """查看当前单轮对话最大工具调用次数（maxToolIterations）。"""
        nanobot_cfg = read_config_raw()
        defaults = nanobot_cfg.get("agents", {}).get("defaults", {})
        current = defaults.get("maxToolIterations", 40)
        return json.dumps({"maxToolIterations": current, "source": "config.json"})

    @mcp.tool()
    async def set_max_tool_iterations(value: int) -> str:
        """设置单轮对话最大工具调用次数。修改后需 restart_gateway 生效。

        Args:
            value: 新的上限值，建议范围 10~200。
        """
        if not _bot_control_allowed():
            return json.dumps({"error": "Bot control is disabled by user. Enable it in Settings → Security."})
        if value < 1 or value > 500:
            return json.dumps({"error": f"Invalid value: {value}. Must be between 1 and 500."})
        nanobot_cfg = read_config_raw()
        nanobot_cfg.setdefault("agents", {}).setdefault("defaults", {})["maxToolIterations"] = value
        write_config_raw(nanobot_cfg)
        return json.dumps({"ok": True, "maxToolIterations": value, "note": "restart_gateway to apply"})
