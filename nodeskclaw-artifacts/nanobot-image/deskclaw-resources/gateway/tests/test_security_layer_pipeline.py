"""Tests for ToolSecurityLayer result pipeline (size guard, DLP, transform_result hooks)."""

from __future__ import annotations

import json

import pytest

from gateway.security.layer import ToolSecurityLayer, _default_tool_result_max_chars


@pytest.fixture
def isolated_home(monkeypatch, tmp_path):
    monkeypatch.setattr("gateway.security.tool_layer.paths.user_home", lambda: tmp_path)
    return tmp_path


def test_default_max_chars_matches_agent_loop():
    from nanobot.agent.loop import AgentLoop

    assert _default_tool_result_max_chars() == AgentLoop._TOOL_RESULT_MAX_CHARS


@pytest.mark.asyncio
async def test_default_size_guard_uses_ten_times_kernel_nominal(isolated_home, tmp_path):
    from gateway.security.tool_layer import result_pipeline as rp

    policy = tmp_path / "p.json"
    policy.write_text(json.dumps({"mode": "monitor", "tools": {}}), encoding="utf-8")
    layer = ToolSecurityLayer(str(policy))
    limit = rp.default_security_max_output_chars()
    assert limit == _default_tool_result_max_chars() * rp._DEFAULT_SIZE_GUARD_MULTIPLIER

    at_limit = "a" * limit
    out, _, _ = await layer._apply_result_pipeline("read_file", {}, at_limit)
    assert out == at_limit

    over = "b" * (limit + 1)
    out2, _, _ = await layer._apply_result_pipeline("read_file", {}, over)
    assert "[SECURITY]" in out2
    assert out2 != over


@pytest.mark.asyncio
async def test_pipeline_truncates_long_str(isolated_home, tmp_path):
    policy = tmp_path / "p.json"
    policy.write_text(
        json.dumps(
            {
                "mode": "monitor",
                "tools": {},
                "result_pipeline": {"max_output_chars": 50, "max_output_enabled": True},
            }
        ),
        encoding="utf-8",
    )
    layer = ToolSecurityLayer(str(policy))
    big = "x" * 200
    out, findings, action = await layer._apply_result_pipeline("read_file", {}, big)
    assert "[SECURITY]" in out
    assert "limit 50" in out
    assert out != big
    assert findings == []
    assert action == ""


@pytest.mark.asyncio
async def test_pipeline_list_text_sum_exceeds_limit(isolated_home, tmp_path):
    policy = tmp_path / "p.json"
    policy.write_text(
        json.dumps(
            {
                "mode": "monitor",
                "tools": {},
                "result_pipeline": {"max_output_chars": 20, "max_output_enabled": True},
            }
        ),
        encoding="utf-8",
    )
    layer = ToolSecurityLayer(str(policy))
    chunks = [{"type": "text", "text": "a" * 15}, {"type": "text", "text": "b" * 15}]
    out, _, _ = await layer._apply_result_pipeline("message", {}, chunks)
    assert isinstance(out, str)
    assert "limit" in out.lower()


@pytest.mark.asyncio
async def test_pipeline_pure_image_list_skips_size_guard(isolated_home, tmp_path):
    policy = tmp_path / "p.json"
    policy.write_text(
        json.dumps(
            {
                "mode": "monitor",
                "tools": {},
                "result_pipeline": {"max_output_chars": 10, "max_output_enabled": True},
            }
        ),
        encoding="utf-8",
    )
    layer = ToolSecurityLayer(str(policy))
    payload = [{"type": "image", "url": "http://example.com/"}]
    out, _, _ = await layer._apply_result_pipeline("x", {}, payload)
    assert out == payload


@pytest.mark.asyncio
async def test_max_output_disabled_passes_huge_str(isolated_home, tmp_path):
    policy = tmp_path / "p.json"
    policy.write_text(
        json.dumps(
            {
                "mode": "monitor",
                "tools": {},
                "result_pipeline": {"max_output_chars": 10, "max_output_enabled": False},
            }
        ),
        encoding="utf-8",
    )
    layer = ToolSecurityLayer(str(policy))
    big = "y" * 500
    out, _, _ = await layer._apply_result_pipeline("read_file", {}, big)
    assert out == big


@pytest.mark.asyncio
async def test_pipeline_dlp_enforce_blocks_credential(isolated_home, tmp_path):
    policy = tmp_path / "p.json"
    policy.write_text(json.dumps({"mode": "enforce", "tools": {}}), encoding="utf-8")
    layer = ToolSecurityLayer(str(policy))
    bad = "password: supersecret_value_here"
    out, findings, action = await layer._apply_result_pipeline("read_file", {}, bad)
    assert action == "blocked"
    assert findings
    assert "blocked" in out.lower()


@pytest.mark.asyncio
async def test_transform_result_hook_runs_after_builtin(isolated_home, tmp_path):
    policy = tmp_path / "p.json"
    policy.write_text(json.dumps({"mode": "monitor", "tools": {}}), encoding="utf-8")
    layer = ToolSecurityLayer(str(policy))

    def transform_result(tool, params, result):
        return "patched"

    layer.result_transform_hooks.append(transform_result)
    out, _, _ = await layer._apply_result_pipeline("t", {}, "orig")
    assert out == "patched"


@pytest.mark.asyncio
async def test_transform_result_async_hook(isolated_home, tmp_path):
    policy = tmp_path / "p.json"
    policy.write_text(json.dumps({"mode": "monitor", "tools": {}}), encoding="utf-8")
    layer = ToolSecurityLayer(str(policy))

    async def transform_result(tool, params, result):
        return "async-patched"

    layer.result_transform_hooks.append(transform_result)
    out, _, _ = await layer._apply_result_pipeline("t", {}, "orig")
    assert out == "async-patched"


@pytest.mark.asyncio
async def test_transform_hook_failure_keeps_previous(isolated_home, tmp_path):
    policy = tmp_path / "p.json"
    policy.write_text(json.dumps({"mode": "monitor", "tools": {}}), encoding="utf-8")
    layer = ToolSecurityLayer(str(policy))
    calls: list[str] = []

    def bad_hook(tool, params, result):
        calls.append("bad")
        raise ValueError("boom")

    def ok_hook(tool, params, result):
        calls.append("ok")
        return "recovered"

    layer.result_transform_hooks.extend([bad_hook, ok_hook])
    out, _, _ = await layer._apply_result_pipeline("t", {}, "start")
    assert out == "recovered"
    assert calls == ["bad", "ok"]


@pytest.mark.asyncio
async def test_dlp_then_user_transform_order(isolated_home, tmp_path):
    policy = tmp_path / "p.json"
    policy.write_text(json.dumps({"mode": "enforce", "tools": {}}), encoding="utf-8")
    layer = ToolSecurityLayer(str(policy))

    def transform_result(tool, params, result):
        if result == "[SECURITY] Result blocked: contained sensitive data (credentials/keys)":
            return "saw-block-message"
        return result

    layer.result_transform_hooks.append(transform_result)
    bad = "password: x"
    out, findings, action = await layer._apply_result_pipeline("read_file", {}, bad)
    assert action == "blocked"
    assert out == "saw-block-message"
    assert findings


def test_normalize_tool_params_unwraps_single_dict_in_list():
    raw = [{"path": "/tmp/x", "content": "hi"}]
    out = ToolSecurityLayer.normalize_tool_params(raw)
    assert out == {"path": "/tmp/x", "content": "hi"}


def test_normalize_tool_params_dict_unchanged():
    d = {"command": "echo ok"}
    assert ToolSecurityLayer.normalize_tool_params(d) is d


def test_brief_params_list_of_dict_does_not_call_items_on_list():
    raw = [{"content": "<html>", "path": "p"}]
    brief = ToolSecurityLayer._brief_params(raw)
    assert "content=" in brief or "path=" in brief
