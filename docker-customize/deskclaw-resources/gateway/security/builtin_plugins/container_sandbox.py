# version: 4
# author: DeskClaw
"""Container sandbox security plugin — routes tool calls to an isolated
container when the user has enabled sandbox mode.

Registers as an **on_around** hook so it runs AFTER on_before (approval).
This guarantees the interactive approval plugin is always respected.

Behavior:
  - In isolated mode, sandboxed tools (exec, list_dir, read_file, write_file,
    edit_file, web_fetch, web_search) execute inside the container.
  - web_fetch / web_search are routed through a tool-proxy script that lives
    in the shared workspace, so the container's network policy controls access.
  - External MCP tools (mcp_*) are blocked when sandbox network is "none";
    built-in DeskClaw MCP tools (mcp_deskclaw_*) always pass through.
  - When container is unavailable: gracefully degrades to transparent mode.
  - All sandbox results are prefixed with [Sandbox] so the agent knows
    it's operating in an isolated environment.
"""

from __future__ import annotations

import json
import logging
import shlex
import sys

from ...paths import resolve_allowlist_path, resolve_workspace_path
logger = logging.getLogger("deskclaw.security.sandbox_plugin")

ALLOWLIST_FILE = resolve_allowlist_path()

_WORKSPACE = str(resolve_workspace_path())

_SANDBOXED_TOOLS = {"exec", "list_dir", "read_file", "write_file", "edit_file",
                    "web_fetch", "web_search"}

_BUILTIN_MCP_PREFIX = "mcp_deskclaw_"

_executor = None
_runtime = None
_initialised = False


def _load_allowlist() -> dict:
    try:
        return json.loads(ALLOWLIST_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {}


def _load_sandbox_mode() -> str:
    return _load_allowlist().get("sandbox", "transparent")


def _host_to_container(host_path: str) -> str:
    """Remap a host absolute path to /workspace inside the container."""
    if not host_path or not os.path.isabs(host_path):
        return host_path
    try:
        rel = os.path.relpath(host_path, _WORKSPACE)
        if rel.startswith(".."):
            return host_path
        return f"/workspace/{rel}"
    except ValueError:
        return host_path


def _ensure_executor():
    global _executor, _runtime, _initialised

    if _initialised:
        return _executor

    _initialised = True

    try:
        from gateway.security.sandbox.runtime import detect_runtime, image_exists
        from gateway.security.sandbox.executor import ContainerExecutor
    except ImportError as e:
        print(f"[Sandbox] Cannot import sandbox modules: {e}", file=sys.stderr, flush=True)
        return None

    rt = detect_runtime()
    if rt is None:
        print("[Sandbox] No container runtime detected", file=sys.stderr, flush=True)
        return None

    if not image_exists(rt):
        print("[Sandbox] Sandbox image not found", file=sys.stderr, flush=True)
        return None

    _runtime = rt
    network = _load_allowlist().get("sandbox_network", "none")
    from gateway.security.sandbox.executor import SandboxConfig
    config = SandboxConfig(network=network)
    _executor = ContainerExecutor(runtime=rt, config=config)

    try:
        from gateway.security.sandbox.tool_proxy import ensure_tool_proxy
        ensure_tool_proxy(_WORKSPACE)
    except Exception as exc:
        print(f"[Sandbox] tool-proxy deploy warning: {exc}", file=sys.stderr, flush=True)

    print(f"[Sandbox] Executor ready: {rt.name} {rt.version} (network={network})", file=sys.stderr, flush=True)
    return _executor


async def reset_executor() -> None:
    """Tear down the running sandbox container so the next call re-creates it with fresh config."""
    global _executor, _initialised
    if _executor is not None:
        try:
            await _executor.cleanup()
        except Exception:
            pass
    _executor = None
    _initialised = False


async def restart_executor() -> dict:
    """Destroy current container and start a new one with fresh config."""
    await reset_executor()
    executor = _ensure_executor()
    if executor is None:
        return {"ok": False, "error": "executor_unavailable"}
    started = await executor.start()
    if not started:
        return {"ok": False, "error": "container_start_failed", "network": executor.config.network}
    actual_network = await executor.inspect_network()
    return {
        "ok": True,
        "network": executor.config.network,
        "actual_network": actual_network or executor.config.network,
        "running": await executor.is_running(),
    }


# ── Tool handlers (each returns a result string) ──


async def _handle_exec(executor, params: dict) -> str:
    command = params.get("command", "") or params.get("cmd", "")
    if not command:
        return "[Sandbox] Empty command"

    timeout = params.get("timeout", 60)
    if isinstance(timeout, str):
        try:
            timeout = int(timeout)
        except ValueError:
            timeout = 60

    if _WORKSPACE and _WORKSPACE in command:
        command = command.replace(_WORKSPACE, "/workspace")

    print(f"[Sandbox] exec: {command[:80]}", file=sys.stderr, flush=True)
    result = await executor.exec(command, timeout=timeout)
    output = result.to_output() or f"(exit code {result.exit_code})"
    return f"[Sandbox] {output}"


async def _handle_list_dir(executor, params: dict) -> str:
    path = params.get("path", ".") or "."
    cpath = _host_to_container(path)
    print(f"[Sandbox] list_dir: {path} -> {cpath}", file=sys.stderr, flush=True)
    result = await executor.exec(f"ls -la {shlex.quote(cpath)}", timeout=10)
    if result.exit_code != 0:
        return f"[Sandbox] Error listing {path}: {result.stderr.strip()}"
    return f"[Sandbox] {result.stdout}"


async def _handle_read_file(executor, params: dict) -> str:
    path = params.get("path", "") or params.get("file_path", "")
    if not path:
        return "[Sandbox] Error: no path provided"
    cpath = _host_to_container(path)
    print(f"[Sandbox] read_file: {path} -> {cpath}", file=sys.stderr, flush=True)
    result = await executor.exec(f"cat {shlex.quote(cpath)}", timeout=30)
    if result.exit_code != 0:
        return f"[Sandbox] Error reading {path}: {result.stderr.strip()}"
    return result.stdout


async def _handle_write_file(executor, params: dict) -> str:
    path = params.get("path", "") or params.get("file_path", "")
    content = params.get("content", "")
    if not path:
        return "[Sandbox] Error: no path provided"
    cpath = _host_to_container(path)
    print(f"[Sandbox] write_file: {path} -> {cpath}", file=sys.stderr, flush=True)

    await executor.exec(f"mkdir -p $(dirname {shlex.quote(cpath)})", timeout=5)
    result = await executor.exec_with_stdin(
        f"cat > {shlex.quote(cpath)}", content, timeout=30,
    )
    if result.exit_code != 0:
        return f"[Sandbox] Error writing {path}: {result.stderr.strip()}"
    return f"[Sandbox] Written to {path}"


async def _handle_edit_file(executor, params: dict) -> str:
    path = params.get("path", "") or params.get("file_path", "")
    old_string = params.get("old_string", "")
    new_string = params.get("new_string", "")
    if not path:
        return "[Sandbox] Error: no path provided"
    cpath = _host_to_container(path)
    print(f"[Sandbox] edit_file: {path} -> {cpath}", file=sys.stderr, flush=True)

    read_result = await executor.exec(f"cat {shlex.quote(cpath)}", timeout=30)
    if read_result.exit_code != 0:
        return f"[Sandbox] Error reading {path}: {read_result.stderr.strip()}"

    content = read_result.stdout
    if old_string not in content:
        return f"[Sandbox] Error: old_string not found in {path}"

    new_content = content.replace(old_string, new_string, 1)
    write_result = await executor.exec_with_stdin(
        f"cat > {shlex.quote(cpath)}", new_content, timeout=30,
    )
    if write_result.exit_code != 0:
        return f"[Sandbox] Error writing {path}: {write_result.stderr.strip()}"
    return f"[Sandbox] Edited {path}"


async def _handle_web_tool(executor, tool_name: str, params: dict) -> str:
    """Route web_fetch / web_search through the in-container tool proxy."""
    from gateway.security.sandbox.tool_proxy import CONTAINER_PROXY_PATH

    payload = json.dumps({"tool": tool_name, "params": params}, ensure_ascii=False)
    print(f"[Sandbox] {tool_name} → tool-proxy", file=sys.stderr, flush=True)
    result = await executor.exec_with_stdin(
        f"python3 {CONTAINER_PROXY_PATH}", payload, timeout=45,
    )
    if result.exit_code != 0:
        error = result.stderr.strip() or result.stdout.strip() or "unknown error"
        return f"[Sandbox] tool-proxy error: {error}"
    return result.stdout


_HANDLERS = {
    "exec": _handle_exec,
    "list_dir": _handle_list_dir,
    "read_file": _handle_read_file,
    "write_file": _handle_write_file,
    "edit_file": _handle_edit_file,
}


# ── Hook entry points ──


async def on_around(tool_name: str, params: dict) -> str | None:
    """Around hook: replace tool execution with container execution.

    Runs AFTER on_before (approval) has passed.
    Returns result string when handled, None to fall through to host execution.

    Routing:
      1. Non-isolated mode → pass through
      2. Built-in DeskClaw MCP tools → always pass through
      3. External MCP tools + network=none → block
      4. web_fetch / web_search → tool-proxy inside container
      5. Other sandboxed tools → existing shell handlers
      6. Everything else (message, spawn) → pass through
    """
    mode = _load_sandbox_mode()
    if mode != "isolated":
        return None

    # Built-in DeskClaw MCP tools always pass through (local, no network)
    if tool_name.startswith(_BUILTIN_MCP_PREFIX):
        return None

    # External MCP tools: block when network is disabled
    if tool_name.startswith("mcp_"):
        network = _load_allowlist().get("sandbox_network", "none")
        if network == "none":
            print(f"[Sandbox] Blocked MCP tool {tool_name} (network=none)", file=sys.stderr, flush=True)
            return f"[Sandbox] Tool '{tool_name}' blocked: sandbox network is set to 'none'. " \
                   f"External MCP tools cannot run without network access."
        return None

    if tool_name not in _SANDBOXED_TOOLS:
        return None

    executor = _ensure_executor()
    if executor is None:
        print("[Sandbox] Degrading to transparent — executor unavailable", file=sys.stderr, flush=True)
        return None

    # Web tools → tool-proxy inside container
    if tool_name in ("web_fetch", "web_search"):
        try:
            return await _handle_web_tool(executor, tool_name, params)
        except Exception as exc:
            print(f"[Sandbox] {tool_name} tool-proxy error, degrading: {exc}", file=sys.stderr, flush=True)
            return None

    handler = _HANDLERS.get(tool_name)
    if handler is None:
        return None

    try:
        return await handler(executor, params)
    except Exception as exc:
        print(f"[Sandbox] {tool_name} error, degrading: {exc}", file=sys.stderr, flush=True)
        return None


def on_after(record) -> None:
    """Annotate audit records with sandbox metadata."""
    if record.tool not in _SANDBOXED_TOOLS:
        return

    mode = _load_sandbox_mode()
    actual = "isolated" if (record.reason == "sandbox-executed") else "transparent"

    if not hasattr(record, "extra"):
        return
    record.extra = {"sandbox_mode": mode, "sandbox_actual": actual}
