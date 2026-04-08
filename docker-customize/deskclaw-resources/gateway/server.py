"""DeskClaw Gateway Adapter - FastAPI + WebSocket server.

Architecture mirrors nanobot's gateway_bridge: three concurrent loops
(receive, send, bus_outbound) instead of a blocking async-generator.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from loguru import logger
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .agent import GatewayAgent
from .paths import resolve_allowlist_path
from .security import current_ws as _current_ws_var
from .models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SessionListResponse,
    SessionInfo,
    AbortResponse,
    CronJobInfo,
    CronJobListResponse,
    CronJobStateInfo,
    CronPayloadInfo,
    CronScheduleInfo,
    CronToggleRequest,
    CronToggleResponse,
    CronRunResponse,
    CronDeleteResponse,
    CronStatusResponse,
    CronRunListResponse,
    CronRunInfo,
)

agent = GatewayAgent()

from .asset_registry import AssetRegistry
_asset_registry = AssetRegistry(agent.workspace)

_gateway_port: int = 18790

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v", ".ogg"}
_MEDIA_EXTS = _IMAGE_EXTS | _VIDEO_EXTS
_LOCAL_IMG_RE = re.compile(
    r'(!\[[^\]]*\])\(((?!https?://)[^)\s]+?\.(?:png|jpe?g|gif|webp|bmp|svg|mp4|webm|mov|avi|mkv|m4v|ogg))\)',
    re.IGNORECASE,
)
_TOOL_HINT_RE = re.compile(r'(\w[\w.-]+)\("?')


def _workspace_path() -> str:
    return str(agent._agent.workspace) if agent._agent else ""


def _rewrite_local_images(text: str) -> str:
    """Rewrite markdown images with local/relative paths to gateway /files/ URLs."""
    if not text:
        return text

    def _replace(m):
        alt, fpath = m.group(1), m.group(2)
        if not os.path.isabs(fpath):
            ws = _workspace_path()
            if ws:
                fpath = str(Path(ws) / fpath)
            else:
                return m.group(0)
        if Path(fpath).is_file():
            return f"{alt}(http://127.0.0.1:{_gateway_port}/files/{quote(fpath).lstrip('/')})"
        return m.group(0)

    return _LOCAL_IMG_RE.sub(_replace, text)


def _file_paths_to_urls(paths: list[str]) -> list[str]:
    """Convert local file paths to gateway /files/ URLs."""
    urls = []
    for p in paths:
        fp = Path(p)
        if fp.is_file() and fp.suffix.lower() in _MEDIA_EXTS:
            urls.append(f"http://127.0.0.1:{_gateway_port}/files/{quote(str(fp)).lstrip('/')}")
        elif p.startswith("http"):
            urls.append(p)
    return urls


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from .mcp_server import get_session_manager
        sm = get_session_manager()
        async with sm.run():
            await agent.start()
            yield
            await agent.stop()
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("Built-in MCP init failed: %s", _e)
        await agent.start()
        yield
        await agent.stop()


app = FastAPI(title="DeskClaw Gateway Adapter", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from .mcp_server import _starlette_app as _mcp_app
    app.mount("/deskclaw", _mcp_app)
except Exception as _mcp_err:
    import logging as _log
    _log.getLogger(__name__).warning("Built-in MCP server failed to mount: %s", _mcp_err)


# ── HTTP endpoints ─────────────────────────────────────────────────

@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse()


@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    result = await agent.chat(
        message=request.message,
        session_id=request.session_id,
    )
    return ChatResponse(**result)


@app.get("/chat/{session_id}/history")
async def get_history(session_id: str):
    history = agent.get_history(session_id)
    for msg in history:
        content = msg.get("content")
        if isinstance(content, str):
            lines = [ln for ln in content.split("\n") if ln.strip() != "[image]"]
            msg["content"] = _rewrite_local_images("\n".join(lines))
        elif isinstance(content, list):
            texts = []
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "text":
                    continue
                t = item.get("text", "")
                if t == "[image]":
                    continue
                texts.append(_rewrite_local_images(t))
            msg["content"] = "\n".join(texts) if texts else ""
    return {"session_id": session_id, "messages": history}


@app.post("/chat/{session_id}/abort")
async def abort_chat(session_id: str) -> AbortResponse:
    success = agent.abort(session_id)
    return AbortResponse(success=success, session_id=session_id)


@app.get("/sessions")
async def list_sessions() -> SessionListResponse:
    sessions = agent.list_sessions()
    return SessionListResponse(
        sessions=[SessionInfo(**s) for s in sessions]
    )


@app.delete("/chat/{session_id}")
async def delete_session(session_id: str):
    agent.delete_session(session_id)
    return {"ok": True}


@app.get("/assets")
async def list_assets(session_id: str | None = None, source: str | None = None, kind: str | None = None):
    rows = await asyncio.get_running_loop().run_in_executor(
        None, _asset_registry.query, session_id, source, kind,
    )
    return {"ok": True, "assets": rows}


@app.get("/files/{file_path:path}")
async def serve_file(file_path: str):
    """Serve local files — confined to workspace and its cache directories.

    Symlinks *within* the workspace (e.g. linked material directories) are
    allowed: we check the logical path (before symlink resolution) in addition
    to the resolved path so that user-linked folders are accessible.
    """
    fp = Path("/") / file_path
    try:
        resolved = fp.resolve(strict=False)
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid path")
    ws = _workspace_path()
    if not ws:
        raise HTTPException(status_code=503, detail="Agent not ready")
    ws_resolved = Path(ws).resolve()
    cache_dir = Path.home() / ".deskclaw_cache"
    media_dir = Path.home() / ".deskclaw" / "media"
    downloads_dir = Path.home() / "Downloads"
    fp_logical = Path(os.path.normpath(str(fp)))
    allowed_prefixes = [
        str(ws_resolved) + os.sep,
        str(cache_dir.resolve()) + os.sep,
        str(media_dir.resolve()) + os.sep,
        str(downloads_dir.resolve()) + os.sep,
    ]
    if not (
        any(str(resolved).startswith(p) for p in allowed_prefixes)
        or str(fp_logical).startswith(str(ws_resolved) + os.sep)
        or resolved == ws_resolved
    ):
        raise HTTPException(status_code=403, detail="Access denied")
    if not fp.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    mime, _ = mimetypes.guess_type(str(fp))
    return FileResponse(fp, media_type=mime or "application/octet-stream")


# ── Cron endpoints ─────────────────────────────────────────────────

def _cron_job_to_info(job) -> CronJobInfo:
    """Convert a nanobot CronJob to the API response model."""
    return CronJobInfo(
        id=job.id,
        name=job.name,
        enabled=job.enabled,
        schedule=CronScheduleInfo(
            kind=job.schedule.kind,
            atMs=job.schedule.at_ms,
            everyMs=job.schedule.every_ms,
            expr=job.schedule.expr,
            tz=job.schedule.tz,
        ),
        payload=CronPayloadInfo(
            kind=job.payload.kind,
            message=job.payload.message,
            deliver=job.payload.deliver,
            channel=job.payload.channel,
            to=job.payload.to,
        ),
        state=CronJobStateInfo(
            nextRunAtMs=job.state.next_run_at_ms,
            lastRunAtMs=job.state.last_run_at_ms,
            lastStatus=job.state.last_status,
            lastError=job.state.last_error,
        ),
        createdAtMs=job.created_at_ms,
        updatedAtMs=job.updated_at_ms,
        deleteAfterRun=job.delete_after_run,
    )


def _get_cron():
    """Get the CronService or raise 503."""
    cron = agent._cron
    if cron is None:
        raise HTTPException(status_code=503, detail="Cron service not available")
    return cron


@app.get("/cron/jobs")
async def cron_list_jobs() -> CronJobListResponse:
    cron = _get_cron()
    jobs = cron.list_jobs(include_disabled=True)
    return CronJobListResponse(jobs=[_cron_job_to_info(j) for j in jobs])


@app.post("/cron/jobs/{job_id}/toggle")
async def cron_toggle_job(job_id: str, req: CronToggleRequest) -> CronToggleResponse:
    cron = _get_cron()
    result = cron.enable_job(job_id, req.enabled)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return CronToggleResponse(success=True, job=_cron_job_to_info(result))


@app.post("/cron/jobs/{job_id}/run")
async def cron_run_job(job_id: str) -> CronRunResponse:
    cron = _get_cron()
    ok = await cron.run_job(job_id, force=True)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found")
    return CronRunResponse(success=True)


@app.delete("/cron/jobs/{job_id}")
async def cron_delete_job(job_id: str) -> CronDeleteResponse:
    cron = _get_cron()
    removed = cron.remove_job(job_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Job not found")
    return CronDeleteResponse(success=True)


@app.get("/cron/jobs/{job_id}/runs")
async def cron_get_runs(job_id: str, limit: int = 50, offset: int = 0) -> CronRunListResponse:
    history = agent._cron_history
    if history is None:
        return CronRunListResponse()
    data = history.get_runs(job_id, limit=limit, offset=offset)
    return CronRunListResponse(
        runs=[CronRunInfo(**r) for r in data["runs"]],
        total=data["total"],
        hasMore=data["hasMore"],
    )


@app.get("/cron/status")
async def cron_status() -> CronStatusResponse:
    cron = _get_cron()
    st = cron.status()
    return CronStatusResponse(
        enabled=st["enabled"],
        jobs=st["jobs"],
        nextWakeAtMs=st.get("next_wake_at_ms"),
    )


@app.get("/cron/migration")
async def cron_migration_status():
    return agent.get_cron_migration_status()


# ── Sandbox / Security endpoints ──────────────────────────────────

@app.get("/security/sandbox/status")
async def sandbox_status():
    from .security.sandbox.runtime import detect_runtime, get_status
    rt = detect_runtime()
    return get_status(rt)


@app.post("/security/sandbox/detect")
async def sandbox_detect():
    from .security.sandbox.runtime import detect_runtime_async, get_status
    rt = await detect_runtime_async()
    return get_status(rt)


@app.post("/security/sandbox/pull-image")
async def sandbox_pull_image(variant: str = "alpine"):
    from .security.sandbox.runtime import detect_runtime, download_and_load, image_exists
    rt = detect_runtime()
    if rt is None:
        raise HTTPException(400, "No container runtime detected")
    try:
        ok = await download_and_load(rt, variant=variant)
    except Exception as exc:
        raise HTTPException(500, f"Image pull error: {exc}") from exc
    if not ok:
        raise HTTPException(500, "Image download or load failed — check gateway logs")
    return {"ok": True, "image_ready": image_exists(rt)}


class _SandboxModeBody(BaseModel):
    mode: str = "transparent"


@app.post("/security/sandbox/mode")
async def sandbox_set_mode(body: _SandboxModeBody):
    mode = body.mode
    if mode not in ("transparent", "isolated"):
        raise HTTPException(400, f"Invalid mode: {mode}")
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"vars": {}, "rules": {}}
    data["sandbox"] = mode
    allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    allowlist_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "sandbox": mode}


@app.get("/security/sandbox/mode")
async def sandbox_get_mode():
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
        return {"sandbox": data.get("sandbox", "transparent")}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sandbox": "transparent"}


class _SandboxNetworkBody(BaseModel):
    network: str = "none"


@app.post("/security/sandbox/network")
async def sandbox_set_network(body: _SandboxNetworkBody):
    network = body.network.strip()
    if not network:
        raise HTTPException(400, "network must not be empty")
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"vars": {}, "rules": {}}
    data["sandbox_network"] = network
    allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    allowlist_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        from gateway.security.builtin_plugins.container_sandbox import reset_executor
        await reset_executor()
    except Exception:
        pass
    return {"ok": True, "sandbox_network": network}


@app.get("/security/sandbox/network")
async def sandbox_get_network():
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
        return {"sandbox_network": data.get("sandbox_network", "none")}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sandbox_network": "none"}


@app.get("/security/bot-control")
async def get_bot_control():
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
        return {"mcp_bot_control": data.get("mcp_bot_control", True)}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"mcp_bot_control": True}


class _BotControlBody(BaseModel):
    enabled: bool = True


@app.post("/security/bot-control")
async def set_bot_control(body: _BotControlBody):
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data["mcp_bot_control"] = body.enabled
    allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    allowlist_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "mcp_bot_control": body.enabled}


@app.get("/security/full-access")
async def get_full_access():
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
        return {"full_access": data.get("full_access", False)}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"full_access": False}


class _FullAccessBody(BaseModel):
    enabled: bool = False


@app.post("/security/full-access")
async def set_full_access(body: _FullAccessBody):
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data["full_access"] = body.enabled
    allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    allowlist_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "full_access": body.enabled}


@app.get("/security/allowlist")
async def get_allowlist():
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
        return {"rules": data.get("rules", {})}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"rules": {}}


class _AllowlistAddBody(BaseModel):
    key: str
    rule: dict = {}


@app.post("/security/allowlist/add")
async def add_allowlist_rule(body: _AllowlistAddBody):
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"vars": {}, "rules": {}}
    rules = data.setdefault("rules", {})
    existing = rules.get(body.key)
    if existing is None:
        rules[body.key] = body.rule
    else:
        for field in ("paths", "urls"):
            new_patterns = body.rule.get(field, [])
            if new_patterns:
                existing_patterns = existing.setdefault(field, [])
                for p in new_patterns:
                    if p not in existing_patterns:
                        existing_patterns.append(p)
    allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    allowlist_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "rules": data.get("rules", {})}


class _AllowlistDeleteBody(BaseModel):
    key: str


@app.post("/security/allowlist/delete")
async def delete_allowlist_rule(body: _AllowlistDeleteBody):
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"vars": {}, "rules": {}}
    rules = data.get("rules", {})
    rules.pop(body.key, None)
    allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    allowlist_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "rules": data.get("rules", {})}


class _AllowlistDeletePathBody(BaseModel):
    key: str
    field: str = "paths"
    pattern: str


@app.post("/security/allowlist/delete-path")
async def delete_allowlist_path(body: _AllowlistDeletePathBody):
    allowlist_path = resolve_allowlist_path()
    try:
        data = json.loads(allowlist_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"vars": {}, "rules": {}}
    rules = data.get("rules", {})
    rule = rules.get(body.key)
    if isinstance(rule, dict) and body.field in rule:
        patterns = rule[body.field]
        if body.pattern in patterns:
            patterns.remove(body.pattern)
        if not patterns:
            del rule[body.field]
    allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    allowlist_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "rules": data.get("rules", {})}


@app.post("/security/sandbox/restart")
async def sandbox_restart_container():
    try:
        from gateway.security.builtin_plugins.container_sandbox import restart_executor
        result = await restart_executor()
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


_EXTERNAL_CHANNELS = GatewayAgent._EXTERNAL_CHANNELS


def _parse_session(session_id: str) -> tuple[str, str]:
    """Split any session_id into (channel, chat_id) that round-trips as f'{ch}:{cid}'.

    Examples:
        "agent:main:desk-cd649817" → ("agent", "main:desk-cd649817")
        "feishu:ou_xxx"            → ("feishu", "ou_xxx")
        "cron:jobid"               → ("cron", "jobid")
        "bare-id"                  → ("gateway", "bare-id")
    """
    parts = session_id.split(":", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "gateway", session_id


# ── Outbound fan-out ───────────────────────────────────────────────
# The outbound bus is a single-consumer asyncio.Queue.  ChannelManager
# and WebSocket handlers both need outbound messages.  We monkey-patch
# publish_outbound once to fan-out a copy to each active WS connection.

_outbound_fanout_installed = False
_ws_outbound_queues: set[asyncio.Queue] = set()


def _refresh_message_tool_outbound() -> None:
    """Point MessageTool at the current bus.publish_outbound (includes WS fan-out).

    MessageTool keeps a callback captured at AgentLoop init (or refreshed to
    ChannelManager's _broadcast only). Those callables bypass _fanout, so
    message-tool QR/media never reaches ws_q. Re-bind after fan-out exists and
    again on each new WebSocket (agent stop/start leaves fan-out installed but
    replaces AgentLoop with a new MessageTool).
    """
    try:
        _loop_agent = agent._agent
        if _loop_agent is None:
            return
        from nanobot.agent.tools.message import MessageTool as _MessageTool

        _msg_tool = _loop_agent.tools.get("message")
        if _msg_tool is not None and isinstance(_msg_tool, _MessageTool):
            _msg_tool.set_send_callback(agent.bus.publish_outbound)
    except Exception:
        logger.debug(
            "Could not refresh MessageTool send_callback for outbound delivery",
            exc_info=True,
        )


def _ensure_outbound_fanout() -> None:
    global _outbound_fanout_installed
    if _outbound_fanout_installed:
        return
    _outbound_fanout_installed = True
    _orig = agent.bus.publish_outbound

    async def _fanout(msg):
        await _orig(msg)
        for q in list(_ws_outbound_queues):
            try:
                q.put_nowait(msg)
            except Exception:
                pass

    agent.bus.publish_outbound = _fanout
    _refresh_message_tool_outbound()


# ── WebSocket endpoint ─────────────────────────────────────────────
# Three concurrent loops: receive, send, bus_outbound.
# Mirrors nanobot gateway_bridge architecture.

@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    _current_ws_var.set(ws)

    send_q: asyncio.Queue[dict] = asyncio.Queue()
    active_tasks: dict[str, asyncio.Task] = {}
    active_tools: dict[str, list[str]] = {}

    checkers: dict = {}
    chat_to_session: dict[tuple[str, str], str] = {}

    def _enqueue(event: dict) -> None:
        try:
            send_q.put_nowait(event)
        except asyncio.QueueFull:
            pass

    async def _cancel_task(session_id: str) -> None:
        task = active_tasks.pop(session_id, None)
        checkers.pop(session_id, None)
        active_tools.pop(session_id, None)
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            from nanobot.bus.events import InboundMessage as _Inbound
            _ch, _cid = _parse_session(session_id)
            stop_msg = _Inbound(
                channel=_ch,
                sender_id="user",
                chat_id=_cid,
                content="/stop",
            )
            await agent._agent._handle_stop(stop_msg)
        except Exception:
            pass

    async def _run_chat(message: str, session_id: str, run_id: str, media: list[str] | None = None) -> None:
        from .security import current_session_id as _current_session_id
        _current_session_id.set(session_id)

        _tele_tokens: list = []
        _tele_notify = None
        try:
            from .telemetry.collector import (
                _telemetry_session_id as _t_sid,
                _telemetry_usage as _t_usage,
                _telemetry_message_id as _t_mid,
                _notify_message_end as _t_notify,
            )
            _tele_tokens.append(_t_sid.set(session_id))
            _tele_tokens.append(_t_usage.set({"prompt_tokens": 0, "completion_tokens": 0}))
            _tele_tokens.append(_t_mid.set(uuid.uuid4().hex))
            _tele_notify = _t_notify
        except Exception:
            pass

        logger.info("_run_chat: session={}, msg_len={}, media={}",
                     session_id, len(message), len(media) if media else 0)
        tools_active: list[str] = []
        active_tools[session_id] = tools_active

        try:
            from nanobot.agent.steering import InterruptionChecker, SteeringHook
            checker = InterruptionChecker()
            steering_hook = SteeringHook(checker)
        except ImportError:
            checker = None
            steering_hook = None
        checkers[session_id] = checker

        _ch, _cid = _parse_session(session_id)
        chat_to_session[(_ch, _cid)] = session_id

        streamed_parts: list[str] = []

        async def on_progress(content: str, **kwargs) -> None:
            if kwargs.get("tool_result"):
                tool_name = kwargs.get("tool_name", "")
                _enqueue({
                    "type": "tool", "name": tool_name,
                    "output": content, "status": "done",
                    "session_id": session_id,
                })
                try:
                    tools_active.remove(tool_name)
                except ValueError:
                    pass
            elif kwargs.get("tool_hint"):
                parts = [p.strip() for p in content.split(", ")]
                for part in parts:
                    m = _TOOL_HINT_RE.match(part)
                    if m:
                        name = m.group(1)
                        tools_active.append(name)
                        _enqueue({
                            "type": "tool", "name": name,
                            "input": part, "status": "calling",
                            "session_id": session_id,
                        })
            else:
                for name in tools_active:
                    _enqueue({
                        "type": "tool", "name": name,
                        "input": {}, "status": "done",
                        "session_id": session_id,
                    })
                tools_active.clear()
                streamed_parts.append(content)
                _enqueue({
                    "type": "delta",
                    "content": _rewrite_local_images(content),
                    "session_id": session_id,
                })

        _enqueue({
            "type": "lifecycle", "phase": "start",
            "session_id": session_id,
        })

        enriched = message
        orphans: list = []
        _pm_completed = False
        try:
            # Persist uploaded media into workspace (returns workspace-relative paths)
            rel_media: list[str] | None = None
            abs_media: list[str] = []
            if media:
                from .media import persist_media as _persist
                rel_media = await _persist(media, session_id, str(agent._agent.workspace),
                                           registry=_asset_registry)

            if rel_media:
                refs = "\n".join(f"![image]({p})" for p in rel_media)
                enriched = f"{refs}\n{message}" if message else refs
                ws = str(agent._agent.workspace)
                abs_media = [str(Path(ws) / p) for p in rel_media]

            from nanobot.bus.events import InboundMessage as _Inbound
            await agent._agent._connect_mcp()
            inbound = _Inbound(
                channel=_ch,
                sender_id="user",
                chat_id=_cid,
                content=enriched, media=abs_media or [],
            )
            _pm_kwargs: dict = dict(
                session_key=session_id, on_progress=on_progress,
            )
            if steering_hook is not None:
                _pm_kwargs["extra_hooks"] = [steering_hook]
            response = await agent._agent._process_message(inbound, **_pm_kwargs)
            _pm_completed = True
            result = response.content if response else ""

            if result and "maximum number of tool call iterations" in result:
                result = (
                    "本次任务步骤较多，已达到单轮工具调用上限，暂时无法继续。\n"
                    "你可以发送「继续」让我接着完成剩余工作。"
                )
                try:
                    from datetime import datetime, timezone as _tz
                    _sess = agent._agent.sessions.get_or_create(session_id)
                    _sess.messages.append({
                        "role": "assistant",
                        "content": result,
                        "timestamp": datetime.now(_tz.utc).isoformat(),
                    })
                    agent._agent.sessions.save(_sess)
                except Exception:
                    pass

            # Dual delivery: also push to external channel via bus
            if _ch in _EXTERNAL_CHANNELS and result:
                from nanobot.bus.events import OutboundMessage as _Outbound
                await agent.bus.publish_outbound(_Outbound(
                    channel=_ch, chat_id=_cid, content=result,
                ))
            orphans = checker.drain_all() if checker else []

            for name in tools_active:
                _enqueue({"type": "tool", "name": name, "input": {}, "status": "done", "session_id": session_id})
            tools_active.clear()

            _enqueue({
                "type": "final",
                "content": _rewrite_local_images(result or ""),
                "session_id": session_id,
                "tool_calls": [],
                **({"has_more": True} if orphans else {}),
            })
            if not orphans:
                _enqueue({
                    "type": "lifecycle", "phase": "end",
                    "session_id": session_id,
                })

        except asyncio.CancelledError:
            for name in tools_active:
                _enqueue({"type": "tool", "name": name, "input": {}, "status": "done", "session_id": session_id})
            tools_active.clear()

            if not _pm_completed:
                try:
                    session = agent._agent.sessions.get_or_create(session_id)
                    from datetime import datetime, timezone
                    ts = datetime.now(timezone.utc).isoformat()
                    session.messages.append({
                        "role": "user", "content": enriched, "timestamp": ts,
                    })
                    partial = "".join(streamed_parts)
                    if partial:
                        session.messages.append({
                            "role": "assistant", "content": partial, "timestamp": ts,
                        })
                    session.updated_at = datetime.now(timezone.utc)
                    agent._agent.sessions.save(session)
                except Exception:
                    import traceback
                    traceback.print_exc()
            _enqueue({
                "type": "lifecycle", "phase": "aborted",
                "session_id": session_id,
                "partial_content": "".join(streamed_parts) or None,
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            _enqueue({
                "type": "lifecycle", "phase": "error",
                "error": str(e),
                "session_id": session_id,
            })
        finally:
            if _tele_notify is not None:
                try:
                    _tele_notify()
                except Exception:
                    pass
            for tok in _tele_tokens:
                try:
                    tok.var.reset(tok)
                except Exception:
                    pass

            checkers.pop(session_id, None)
            active_tasks.pop(session_id, None)
            active_tools.pop(session_id, None)
            chat_to_session.pop((_ch, _cid), None)

            for orphan in orphans:
                new_run_id = str(uuid.uuid4())
                task = asyncio.create_task(
                    _run_chat(orphan.content, session_id, new_run_id)
                )
                active_tasks[session_id] = task

    # ── receive loop ──

    async def receive_loop():
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    _enqueue({"type": "error", "error": "Invalid JSON"})
                    continue
                msg_type = data.get("type", "message")
                session_id = data.get("session_id") or f"agent:main:gw-{uuid.uuid4().hex[:8]}"

                if msg_type == "abort":
                    await _cancel_task(session_id)
                    continue

                if msg_type == "tool_approval_response":
                    req_id = data.get("id", "")
                    action = data.get("action", "deny")
                    sec = getattr(agent, "_security", None)
                    if sec and req_id:
                        sec.resolve_approval(req_id, {"action": action})
                    continue

                message = data.get("message", "")
                media = data.get("media") or []
                logger.info("receive_loop: session={}, msg_len={}, media={}",
                            session_id, len(message), len(media))
                if not message and not media:
                    _enqueue({"type": "error", "error": "Empty message"})
                    continue

                if agent._agent:
                    try:
                        _sess = agent._agent.sessions.get_or_create(session_id)
                        agent._agent.sessions.save(_sess)
                    except Exception:
                        logger.warning("Failed to pre-register session {}", session_id)

                existing = active_tasks.get(session_id)
                if existing and not existing.done():
                    checker = checkers.get(session_id)
                    if checker:
                        from nanobot.bus.events import InboundMessage
                        _sch, _scid = _parse_session(session_id)
                        inbound = InboundMessage(
                            channel=_sch,
                            sender_id="user",
                            chat_id=_scid,
                            content=message,
                        )
                        await checker.signal(inbound)
                        continue

                run_id = str(uuid.uuid4())
                task = asyncio.create_task(
                    _run_chat(message, session_id, run_id, media=media or None)
                )
                active_tasks[session_id] = task

        except WebSocketDisconnect:
            pass
        except Exception:
            import traceback
            traceback.print_exc()

    # ── send loop ──

    async def send_loop():
        try:
            while True:
                event = await send_q.get()
                try:
                    await ws.send_json(event)
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    # ── bus outbound loop (captures message tool media) ──
    # Uses a fan-out subscription so we don't race ChannelManager for
    # outbound messages (fixes subagent "Unknown channel: gateway" bug).

    async def bus_outbound_loop():
        _ensure_outbound_fanout()
        # Fan-out may already be installed (e.g. after agent restart); new AgentLoop
        # still needs MessageTool bound to the current publish_outbound.
        _refresh_message_tool_outbound()
        ws_q: asyncio.Queue = asyncio.Queue()
        _ws_outbound_queues.add(ws_q)
        try:
            while True:
                msg = await ws_q.get()
                if msg.channel == "cron":
                    continue
                media = msg.media or []
                content = _rewrite_local_images(msg.content or "")
                image_urls = _file_paths_to_urls(media) if media else []
                session_key = chat_to_session.get(
                    (msg.channel, msg.chat_id),
                    f"{msg.channel}:{msg.chat_id}" if msg.channel else msg.chat_id,
                )
                if media:
                    from .media import persist_agent_outputs
                    asyncio.create_task(persist_agent_outputs(
                        media, session_key,
                        str(Path(agent.workspace)),
                        registry=_asset_registry,
                    ))

                if content or image_urls:
                    from loguru import logger as _bus_log
                    _bus_log.debug(
                        "bus_outbound_loop: delivering ({},{}) -> session={}",
                        msg.channel, msg.chat_id, session_key,
                    )
                    # Only emit `message` — do not wrap in lifecycle start/end here.
                    # A synthetic lifecycle end makes ipc-router send streaming/done and
                    # ChatPanel runs loadSession (full history replace) while the main
                    # turn is still running → jarring "page refresh" and wrong loading UX.
                    # deskclaw:chat:message alone appends the bubble; final + lifecycle end
                    # from _run_chat still refresh history when the turn actually completes.
                    _enqueue({
                        "type": "message",
                        "content": content,
                        "media": image_urls,
                        "session_id": session_key,
                    })
        except asyncio.CancelledError:
            pass
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            _ws_outbound_queues.discard(ws_q)

    recv = asyncio.create_task(receive_loop())
    send = asyncio.create_task(send_loop())
    bus_out = asyncio.create_task(bus_outbound_loop())

    try:
        done, _ = await asyncio.wait(
            [recv, send, bus_out], return_when=asyncio.FIRST_COMPLETED,
        )
    except Exception:
        pass
    finally:
        sec = getattr(agent, "_security", None)
        if sec:
            sec.approval_channel.cancel_all()
        pending: list[asyncio.Task] = []
        for task in active_tasks.values():
            if not task.done():
                task.cancel()
                pending.append(task)
        for t in [recv, send, bus_out]:
            if not t.done():
                t.cancel()
                pending.append(t)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


def _patch_proactor_accept():
    """Auto-fallback from IOCP AcceptEx to threaded accept on Windows.

    CPython's ProactorEventLoop uses the IOCP ``AcceptEx`` API for async
    accept.  On some Windows machines (typically due to third-party LSP /
    WFP drivers from VPN or antivirus software) ``AcceptEx`` consistently
    fails with WinError 10014 (WSAEFAULT), making the server unable to
    accept any connections.

    This patch starts with the normal IOCP path.  If ``AcceptEx`` fails
    ``_IOCP_FAIL_THRESHOLD`` times in a row, it transparently switches to
    a standard ``socket.accept()`` running in a thread-pool executor,
    bypassing ``AcceptEx`` entirely while keeping ``ProactorEventLoop``
    (needed by ``asyncio.create_subprocess_*`` / the exec tool).

    Ref: https://github.com/python/cpython/issues/93821
    """
    import logging as _logging
    import select as _select
    from asyncio import exceptions, trsock

    _log = _logging.getLogger("asyncio")
    _IOCP_FAIL_THRESHOLD = 3

    def _sync_accept(sock):
        """Block in a worker thread until a connection arrives."""
        while True:
            if sock.fileno() == -1:
                raise OSError(9, "Bad file descriptor")
            readable, _, _ = _select.select([sock], [], [], 1.0)
            if readable:
                try:
                    return sock.accept()
                except BlockingIOError:
                    continue

    def _patched_start_serving(
        self, protocol_factory, sock,
        sslcontext=None, server=None, backlog=100,
        ssl_handshake_timeout=None,
        ssl_shutdown_timeout=None,
    ):
        iocp_failures = 0
        use_threaded = False

        def loop(f=None):
            nonlocal iocp_failures, use_threaded
            try:
                if f is not None:
                    try:
                        conn, addr = f.result()
                    except OSError as exc:
                        if sock.fileno() != -1:
                            if not use_threaded:
                                iocp_failures += 1
                                if iocp_failures >= _IOCP_FAIL_THRESHOLD:
                                    use_threaded = True
                                    _log.warning(
                                        "AcceptEx failed %d times consecutively, "
                                        "switching to threaded accept (bypassing IOCP)",
                                        iocp_failures,
                                    )
                            self.call_exception_handler({
                                "message": "Accept failed on a socket (retrying)",
                                "exception": exc,
                                "socket": trsock.TransportSocket(sock),
                            })
                            self.call_soon(loop)
                        return
                    iocp_failures = 0
                    if self._debug:
                        _log.debug(
                            "%r got a new connection from %r: %r",
                            server, addr, conn,
                        )
                    protocol = protocol_factory()
                    if sslcontext is not None:
                        self._make_ssl_transport(
                            conn, protocol, sslcontext, server_side=True,
                            extra={"peername": addr}, server=server,
                            ssl_handshake_timeout=ssl_handshake_timeout,
                            ssl_shutdown_timeout=ssl_shutdown_timeout,
                        )
                    else:
                        self._make_socket_transport(
                            conn, protocol,
                            extra={"peername": addr}, server=server,
                        )
                if self.is_closed():
                    return
                if use_threaded:
                    f = self.run_in_executor(None, _sync_accept, sock)
                else:
                    f = self._proactor.accept(sock)
            except OSError as exc:
                if sock.fileno() != -1:
                    self.call_exception_handler({
                        "message": "Accept failed on a socket",
                        "exception": exc,
                        "socket": trsock.TransportSocket(sock),
                    })
                    sock.close()
                elif self._debug:
                    _log.debug(
                        "Accept failed on socket %r", sock, exc_info=True,
                    )
            except exceptions.CancelledError:
                sock.close()
            else:
                self._accept_futures[sock.fileno()] = f
                f.add_done_callback(loop)

        self.call_soon(loop)

    asyncio.ProactorEventLoop._start_serving = _patched_start_serving


def main():
    global _gateway_port
    import logging
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if sys.platform == "win32":
        _patch_proactor_accept()

    host = os.environ.get("DESKCLAW_ADAPTER_HOST", "127.0.0.1")
    port = int(os.environ.get("DESKCLAW_ADAPTER_PORT", "18790"))
    _gateway_port = port
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
