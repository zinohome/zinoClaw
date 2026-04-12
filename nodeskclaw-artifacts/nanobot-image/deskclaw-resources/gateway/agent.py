"""Thin wrapper around nanobot's AgentLoop for the gateway adapter.

Shell ``exec`` PATH: ``exec_tool_patch.install()`` runs before AgentLoop import so
gateway-venv is prepended per subprocess only (nanobot package unchanged).
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import json as _json
import uuid
from pathlib import Path
from typing import Any, Callable

import os

fallback_notify_var: contextvars.ContextVar[Callable[[str, str], None] | None] = contextvars.ContextVar(
    "fallback_notify", default=None,
)

from nanobot.config.loader import load_config, set_config_path
from nanobot.config.schema import Config

from .exec_tool_patch import install as _install_deskclaw_exec_tool
from .text_file_patch import install as _install_text_file_patch
from .paths import resolve_allowlist_path, resolve_nanobot_config_path

_install_deskclaw_exec_tool()
_install_text_file_patch()

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.session.manager import SessionManager


def _resolve_provider_backend(spec: Any, provider_name: str | None, model: str) -> str:
    """``ProviderSpec.backend`` exists on newer nanobot-ai; older wheels omit it.

    Prefer bootstrap keeping venv in sync; this avoids hard failure if venv lags.
    """
    if spec is not None:
        b = getattr(spec, "backend", None)
        if isinstance(b, str) and b:
            return b
    pn = (provider_name or "").strip().lower()
    if pn == "azure_openai":
        return "azure_openai"
    if pn == "anthropic":
        return "anthropic"
    if pn == "openai_codex" or model.lower().startswith("openai-codex"):
        return "openai_codex"
    return "openai_compat"


def _detect_system_timezone() -> str | None:
    """Detect the system's IANA timezone name (e.g. 'Asia/Shanghai').

    Returns None if detection fails, so callers can fall back to UTC.
    """
    tz_env = os.environ.get("TZ", "").strip()
    if tz_env:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(tz_env)
            return tz_env
        except Exception:
            pass
    try:
        target = os.path.realpath("/etc/localtime")
        idx = target.find("/zoneinfo/")
        if idx != -1:
            candidate = target[idx + len("/zoneinfo/"):]
            from zoneinfo import ZoneInfo
            ZoneInfo(candidate)
            return candidate
    except Exception:
        pass
    return None


def _spec_exempt_from_api_key(spec: Any) -> bool:
    if spec is None:
        return False
    return bool(
        getattr(spec, "is_oauth", False)
        or getattr(spec, "is_local", False)
        or getattr(spec, "is_direct", False)
    )


def _merge_deskclaw_version_header(extra: dict[str, str] | None) -> dict[str, str] | None:
    """Attach X-DeskClaw-Version for upstream LLM gateways (set by Electron via DESKCLAW_APP_VERSION)."""
    ver = os.environ.get("DESKCLAW_APP_VERSION", "").strip()
    if not ver:
        return extra
    merged = dict(extra) if extra else {}
    merged.setdefault("X-DeskClaw-Version", ver)
    return merged


_LLM_HTTP_TIMEOUT = float(os.environ.get("DESKCLAW_LLM_TIMEOUT", "120"))


def _apply_llm_timeout(provider: Any) -> None:
    """Set HTTP-level timeout on the provider's SDK client (openai / anthropic)."""
    client = getattr(provider, "_client", None)
    if client is None:
        return
    try:
        import httpx
        client.timeout = httpx.Timeout(_LLM_HTTP_TIMEOUT, connect=10.0)
    except Exception:
        pass


def _make_provider_for_model(config: Config, model: str) -> Any:
    """Create an LLM provider for an arbitrary model string.

    Re-uses the same resolution logic as ``_make_provider`` but accepts any
    model name so that fallback models get their own provider instances.
    """
    import sys

    from nanobot.providers.base import GenerationSettings
    from nanobot.providers.registry import find_by_name

    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)
    spec = find_by_name(provider_name) if provider_name else None
    backend = _resolve_provider_backend(spec, provider_name, model)
    api_base = config.get_api_base(model)

    if p is None:
        from nanobot.providers.registry import PROVIDERS
        for _spec in PROVIDERS:
            candidate = getattr(config.providers, _spec.name, None)
            if candidate and candidate.api_base:
                p = candidate
                api_base = candidate.api_base
                provider_name = _spec.name
                spec = _spec
                backend = _resolve_provider_backend(spec, provider_name, model)
                break

    if backend == "openai_codex":
        from nanobot.providers.openai_codex_provider import OpenAICodexProvider
        provider = OpenAICodexProvider(default_model=model)
    elif backend == "github_copilot":
        from nanobot.providers.github_copilot_provider import GitHubCopilotProvider
        provider = GitHubCopilotProvider(default_model=model)
    elif backend == "azure_openai":
        from nanobot.providers.azure_openai_provider import AzureOpenAIProvider
        provider = AzureOpenAIProvider(
            api_key=p.api_key if p else None,
            api_base=p.api_base if p else None,
            default_model=model,
        )
    elif backend == "anthropic":
        from nanobot.providers.anthropic_provider import AnthropicProvider
        provider = AnthropicProvider(
            api_key=p.api_key if p else None,
            api_base=api_base,
            default_model=model,
            extra_headers=_merge_deskclaw_version_header(
                getattr(p, "extra_headers", None) if p else None
            ),
        )
    else:
        from nanobot.providers.openai_compat_provider import OpenAICompatProvider
        provider = OpenAICompatProvider(
            api_key=p.api_key if p else None,
            api_base=api_base,
            default_model=model,
            extra_headers=_merge_deskclaw_version_header(
                getattr(p, "extra_headers", None) if p else None
            ),
            spec=spec,
        )

    defaults = config.agents.defaults
    provider.generation = GenerationSettings(
        temperature=defaults.temperature,
        max_tokens=defaults.max_tokens,
        reasoning_effort=defaults.reasoning_effort,
    )
    _apply_llm_timeout(provider)
    return provider


def _make_provider_from_entry(entry: dict, config: Config) -> Any:
    """Create an LLM provider from an explicit fallback entry with its own API credentials."""
    from nanobot.providers.base import GenerationSettings

    model = entry.get("model", "")
    api_format = entry.get("apiFormat", entry.get("api_format", "openai"))
    api_key = entry.get("apiKey", entry.get("api_key", ""))
    api_url = entry.get("apiUrl", entry.get("api_url", ""))

    if api_format == "anthropic":
        from nanobot.providers.anthropic_provider import AnthropicProvider
        provider = AnthropicProvider(
            api_key=api_key or None,
            api_base=api_url or None,
            default_model=model,
            extra_headers=_merge_deskclaw_version_header(None),
        )
    else:
        from nanobot.providers.openai_compat_provider import OpenAICompatProvider
        provider = OpenAICompatProvider(
            api_key=api_key or None,
            api_base=api_url or "https://api.openai.com/v1",
            default_model=model,
            extra_headers=_merge_deskclaw_version_header(None),
        )

    defaults = config.agents.defaults
    provider.generation = GenerationSettings(
        temperature=defaults.temperature,
        max_tokens=defaults.max_tokens,
        reasoning_effort=defaults.reasoning_effort,
    )
    _apply_llm_timeout(provider)
    return provider


def _load_fallback_entries() -> dict[str, dict]:
    """Load per-model API configs from ``fallback_entries.json`` (written by DeskClaw IPC)."""
    import json as _json
    from .paths import resolve_nanobot_home

    p = resolve_nanobot_home() / "fallback_entries.json"
    try:
        raw = _json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return {e["model"]: e for e in raw if isinstance(e, dict) and e.get("model")}
    except Exception:
        pass
    return {}


class _FallbackNotifyProxy:
    """Thin proxy around an LLM provider that emits a UI notification via
    ``fallback_notify_var`` each time the provider is actually used for
    inference.  The nanobot ``AgentRunner`` caches fallback providers, so
    placing the notification inside the factory function only fires once.
    By wrapping the provider, the notification fires on every request."""

    __slots__ = ("_provider", "_primary", "_fallback")

    def __init__(self, provider: Any, primary_model: str, fallback_model: str) -> None:
        self._provider = provider
        self._primary = primary_model
        self._fallback = fallback_model

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)

    def _emit(self) -> None:
        notify = fallback_notify_var.get(None)
        if notify:
            notify(self._primary, self._fallback)

    async def chat_with_retry(self, **kwargs: Any) -> Any:
        self._emit()
        return await self._provider.chat_with_retry(**kwargs)

    async def chat_stream_with_retry(self, **kwargs: Any) -> Any:
        self._emit()
        return await self._provider.chat_stream_with_retry(**kwargs)


def _make_gateway_provider_factory(config: Config):
    """Build a cached factory for fallback model providers (gateway side).

    Prefers explicit entries from ``fallback_entries.json`` (each with its own
    API credentials) when present; falls back to config-based resolution.

    Returns a ``_FallbackNotifyProxy`` so the frontend receives a transient
    notice every time a fallback model is used — without touching nanobot core.
    """
    cache: dict[str, Any] = {}
    entry_map = _load_fallback_entries()
    primary_model = config.agents.defaults.model

    def factory(model: str):
        if model not in cache:
            entry = entry_map.get(model)
            if entry:
                cache[model] = _make_provider_from_entry(entry, config)
            else:
                cache[model] = _make_provider_for_model(config, model)
        return _FallbackNotifyProxy(cache[model], primary_model, model)

    return factory


def _make_provider(config: Config) -> tuple:
    """Create LLM provider from config — mirrors ``nanobot.cli.commands._make_provider``.

    Returns (provider, model) for AgentLoop. Uses OpenAI-compatible or Anthropic
    native SDKs (no LiteLLM).
    """
    import sys

    from nanobot.providers.base import GenerationSettings
    from nanobot.providers.registry import find_by_name

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)
    spec = find_by_name(provider_name) if provider_name else None
    backend = _resolve_provider_backend(spec, provider_name, model)
    api_base = config.get_api_base(model)

    # Dynamic gateway fallback: nanobot core only matches providers with
    # api_key set.  When a dynamic gateway supplies only api_base (no key),
    # the core returns (None, None).  Search for any provider that has
    # api_base configured and use it.
    if p is None:
        from nanobot.providers.registry import PROVIDERS
        for _spec in PROVIDERS:
            candidate = getattr(config.providers, _spec.name, None)
            if candidate and candidate.api_base:
                p = candidate
                api_base = candidate.api_base
                provider_name = _spec.name
                spec = _spec
                backend = _resolve_provider_backend(spec, provider_name, model)
                break

    print(f"[Gateway] Provider={provider_name}, backend={backend}, model={model}, api_base={api_base or '(default)'}",
          file=sys.stderr, flush=True)

    if backend == "azure_openai":
        if not p or not p.api_key or not p.api_base:
            raise RuntimeError(
                "Azure OpenAI requires api_key and api_base in config (providers.azure_openai)."
            )
    elif backend == "openai_compat" and not model.startswith("bedrock/"):
        needs_key = not (p and p.api_key)
        has_base = bool(p and p.api_base) or bool(api_base)
        exempt = _spec_exempt_from_api_key(spec) or has_base
        if needs_key and not exempt:
            raise RuntimeError("No API key configured for the active provider in config.json")

    if backend == "openai_codex":
        from nanobot.providers.openai_codex_provider import OpenAICodexProvider

        provider = OpenAICodexProvider(default_model=model)
    elif backend == "github_copilot":
        from nanobot.providers.github_copilot_provider import GitHubCopilotProvider

        provider = GitHubCopilotProvider(default_model=model)
    elif backend == "azure_openai":
        from nanobot.providers.azure_openai_provider import AzureOpenAIProvider

        provider = AzureOpenAIProvider(
            api_key=p.api_key,
            api_base=p.api_base,
            default_model=model,
        )
    elif backend == "anthropic":
        from nanobot.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(
            api_key=p.api_key if p else None,
            api_base=api_base,
            default_model=model,
            extra_headers=_merge_deskclaw_version_header(
                getattr(p, "extra_headers", None) if p else None
            ),
        )
    else:
        from nanobot.providers.openai_compat_provider import OpenAICompatProvider

        provider = OpenAICompatProvider(
            api_key=p.api_key if p else None,
            api_base=api_base,
            default_model=model,
            extra_headers=_merge_deskclaw_version_header(
                getattr(p, "extra_headers", None) if p else None
            ),
            spec=spec,
        )

    defaults = config.agents.defaults
    provider.generation = GenerationSettings(
        temperature=defaults.temperature,
        max_tokens=defaults.max_tokens,
        reasoning_effort=defaults.reasoning_effort,
    )
    _apply_llm_timeout(provider)
    return provider, model



_STEERING_PREFIX = (
    "[The user just sent a new message while you were working. "
    "Read it and decide: continue current work, switch to the "
    "new request, or address both.]\n\n"
)


def _schedule_pending_tool_restart() -> None:
    """Run after each ``AgentLoop._process_message`` completes (all entry paths).

    ``restart_gateway`` / ``restart_deskclaw`` MCP tools set a module-level pending
    flag. WebSocket chat used to consume it in ``server._run_chat`` finally, but
    external channels (飞书 / WeCom / QQ / …) only go through ``AgentLoop.run`` →
    ``_dispatch`` → ``_process_message``, so the consumer must attach here.
    """
    try:
        from .mcp_server import consume_pending_action, _do_restart_gateway, _do_restart_deskclaw

        action = consume_pending_action()
        if not action:
            return
        loop = asyncio.get_running_loop()
        if action == "gateway":
            loop.call_later(1.0, _do_restart_gateway)
        elif action == "deskclaw":
            loop.call_later(1.0, _do_restart_deskclaw)
    except RuntimeError:
        pass
    except Exception:
        pass


def _patch_process_message_for_pending_restart(agent: AgentLoop) -> None:
    _orig = agent._process_message

    @functools.wraps(_orig)
    async def _wrapped(*args, **kwargs):
        try:
            return await _orig(*args, **kwargs)
        finally:
            _schedule_pending_tool_restart()

    agent._process_message = _wrapped  # type: ignore[method-assign]


class GatewayAgent:
    """Wraps nanobot AgentLoop. Exposes _agent for server's direct use."""

    def __init__(self) -> None:
        config_path_str = os.environ.get("NANOBOT_CONFIG_PATH")
        if config_path_str:
            set_config_path(Path(config_path_str))
        self.config = load_config()
        self.workspace = self.config.workspace_path
        os.environ.setdefault("DESKCLAW_WORKSPACE", str(Path(self.workspace).expanduser()))
        self.bus = MessageBus()
        self.session_manager = SessionManager(self.workspace)
        self._agent: AgentLoop | None = None
        self._cron = None  # CronService if available
        self._cron_history = None  # CronRunHistory if cron available
        self._channel_manager = None
        self._bus_task = None
        self._mcp_warmup_task: asyncio.Task | None = None
        self._image_cache = Path(self.workspace) / ".deskclaw_cache" / "images"
        self._cron_store_path: Path | None = None
        self._cron_migration_status: str = "idle"  # idle | running | done | failed
        self._cron_migration_count: int = 0
        self._cron_migration_task: asyncio.Task | None = None
        self._extension_registry = None  # ExtensionRegistry if loaded

    def _verify_cron_store(self) -> None:
        """After CronService.start(), compare loaded jobs against the backup.

        Three outcomes:
        - Jobs loaded OK → delete .bak (no longer needed), done.
        - Jobs lost + backup has data → kick off background LLM migration.
        - No backup → nothing to do.
        """
        import json as _json
        p = self._cron_store_path
        if not p or not self._cron:
            return
        bak = p.with_suffix(".json.bak")
        if not bak.exists():
            return
        try:
            loaded_jobs = self._cron.list_jobs(include_disabled=True)
            if loaded_jobs:
                bak.unlink(missing_ok=True)
                return
            bak_data = _json.loads(bak.read_text(encoding="utf-8"))
            bak_jobs = bak_data.get("jobs")
            if not bak_jobs:
                bak.unlink(missing_ok=True)
                return
            self._cron_migration_status = "running"
            self._cron_migration_count = len(bak_jobs)
            print(f"[Gateway] Starting background cron migration: {len(bak_jobs)} job(s)",
                  file=__import__('sys').stderr, flush=True)
            self._cron_migration_task = asyncio.create_task(self._run_cron_migration())
        except Exception as exc:
            print(f"[Gateway] Cron store verification error: {exc}",
                  file=__import__('sys').stderr, flush=True)

    def get_cron_migration_status(self) -> dict:
        """Return migration progress for the UI."""
        status = self._cron_migration_status
        if status == "idle":
            return {"pending": False}
        return {
            "pending": status == "running",
            "status": status,
            "count": self._cron_migration_count,
        }

    async def _run_cron_migration(self) -> None:
        """Background task: use the agent (LLM) to re-create cron jobs."""
        import json as _json
        bak = self._cron_store_path.with_suffix(".json.bak")
        try:
            raw = bak.read_text(encoding="utf-8")
            prompt = (
                "You are migrating scheduled tasks (cron jobs) from a previous version. "
                "Below is the raw JSON from the old jobs.json backup. "
                "For EACH job in the list, use the `cron` tool with action=\"add\" to re-create it. "
                "Preserve the original name, schedule, message, and enabled/disabled state. "
                "If a job was disabled (enabled=false), first add it, then use action=\"list\" "
                "to find it, and finally disable it with cron(action=\"toggle\", job_id=..., enabled=false).\n\n"
                "IMPORTANT: Re-create ALL jobs. Do not skip any.\n\n"
                f"```json\n{raw}\n```"
            )
            await self._agent.process_direct(
                content=prompt,
                session_key="system:cron-migration",
                channel="system",
                chat_id="cron-migration",
            )
            self._cron_migration_status = "done"
            bak.unlink(missing_ok=True)
            migrated = len(self._cron.list_jobs(include_disabled=True))
            print(f"[Gateway] Cron migration done: {migrated} job(s) restored",
                  file=__import__('sys').stderr, flush=True)
        except Exception as exc:
            self._cron_migration_status = "failed"
            print(f"[Gateway] Cron migration failed: {exc}",
                  file=__import__('sys').stderr, flush=True)

    def _patch_sandbox_prompt(self) -> None:
        """When sandbox is isolated, monkey-patch the ContextBuilder so the
        system prompt shows /workspace instead of the real host path.
        Only affects prompt text; actual file I/O still uses the real path."""
        import json
        try:
            data = json.loads(resolve_allowlist_path().read_text(encoding="utf-8"))
            if data.get("sandbox") != "isolated":
                return
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return

        ctx = self._agent.context
        real_path = str(Path(self.workspace).expanduser().resolve())
        _original = ctx._get_identity

        def _patched() -> str:
            return _original().replace(real_path, "/workspace")

        ctx._get_identity = _patched

    async def start(self) -> None:
        provider, resolved_model = _make_provider(self.config)
        defaults = self.config.agents.defaults

        kwargs: dict[str, Any] = dict(
            bus=self.bus,
            provider=provider,
            workspace=self.workspace,
            model=resolved_model,
            max_iterations=defaults.max_tool_iterations,
            session_manager=self.session_manager,
        )

        for attr in (
            "context_window_tokens", "context_block_limit",
            "max_tool_result_chars", "provider_retry_mode",
            "reasoning_effort", "timezone", "unified_session",
        ):
            val = getattr(defaults, attr, None)
            if val is not None:
                kwargs[attr] = val

        if kwargs.get("timezone", "UTC") == "UTC":
            detected = _detect_system_timezone()
            if detected:
                kwargs["timezone"] = detected

        if defaults.fallback_models:
            kwargs["fallback_models"] = defaults.fallback_models
            kwargs["provider_factory"] = _make_gateway_provider_factory(self.config)

        if hasattr(self.config.tools, "exec"):
            kwargs["exec_config"] = self.config.tools.exec
        if hasattr(self.config.tools, "mcp_servers"):
            kwargs["mcp_servers"] = self.config.tools.mcp_servers
        if hasattr(self.config.tools, "web") and self.config.tools.web:
            kwargs["web_config"] = self.config.tools.web
        if hasattr(self.config.tools, "restrict_to_workspace"):
            kwargs["restrict_to_workspace"] = self.config.tools.restrict_to_workspace
        if hasattr(self.config, "channels"):
            kwargs["channels_config"] = self.config.channels

        try:
            from nanobot.cron.service import CronService

            from .cron_setup import cron_jobs_path, migrate_legacy_cron_store

            migrate_legacy_cron_store(self.config)
            cron_store = cron_jobs_path(self.config)
            cron_store.parent.mkdir(parents=True, exist_ok=True)
            self._cron_store_path = cron_store
            self._cron = CronService(store_path=cron_store)
            kwargs["cron_service"] = self._cron
        except Exception as exc:
            print(f"[Gateway] Cron service init failed: {exc}", file=__import__('sys').stderr, flush=True)

        # Filter out any kwargs the current nanobot AgentLoop doesn't accept
        import inspect
        _accepted = set(inspect.signature(AgentLoop.__init__).parameters.keys())
        kwargs = {k: v for k, v in kwargs.items() if k in _accepted}
        self._agent = AgentLoop(**kwargs)

        _ws = getattr(getattr(self.config.tools, "web", None), "search", None)
        _provider = getattr(_ws, "provider", "") or ""
        _keep_search = _ws and (
            _provider.strip().lower() == "duckduckgo"
            or (_provider.strip().lower() == "searxng" and getattr(_ws, "base_url", None))
            or getattr(_ws, "api_key", None)
        )
        if not _keep_search:
            self._agent.tools.unregister("web_search")

        # Exclude kernel built-in skills that DeskClaw doesn't ship
        _EXCLUDED_BUILTIN_SKILLS = {"weather"}
        _skills = getattr(getattr(self._agent, "context", None), "skills", None)
        if _skills and hasattr(_skills, "list_skills"):
            _orig_list = _skills.list_skills
            def _filtered_list(*a, **kw):
                return [s for s in _orig_list(*a, **kw)
                        if not (s.get("source") == "builtin" and s["name"] in _EXCLUDED_BUILTIN_SKILLS)]
            _skills.list_skills = _filtered_list

        self._patch_sandbox_prompt()

        if self._cron and self._agent:
            from .cron_history import CronRunHistory
            from .cron_setup import cron_jobs_path

            self._cron_history = CronRunHistory(cron_jobs_path(self.config).parent)

            from nanobot.cron.types import CronJob as _CJ
            history = self._cron_history

            async def _on_cron_job(job: _CJ) -> str | None:
                import time as _time
                from nanobot.agent.tools.cron import CronTool as _CT
                from nanobot.agent.tools.message import MessageTool as _MT
                from nanobot.utils.evaluator import evaluate_response as _evaluate
                from nanobot.bus.events import OutboundMessage as _Outbound
                start_ms = int(_time.time() * 1000)
                session_key = f"cron:{job.id}"
                job_channel = job.payload.channel or "cron"
                job_chat_id = job.payload.to or job.id
                error = None
                result = None

                reminder_note = (
                    "[Scheduled Task] Timer finished.\n\n"
                    f"Task '{job.name}' has been triggered.\n"
                    f"Scheduled instruction: {job.payload.message}"
                )

                cron_tool = self._agent.tools.get("cron")
                cron_token = None
                if isinstance(cron_tool, _CT):
                    cron_token = cron_tool.set_cron_context(True)
                try:
                    result = await self._agent.process_direct(
                        content=reminder_note,
                        session_key=session_key,
                        channel=job_channel,
                        chat_id=job_chat_id,
                    )
                except Exception as exc:
                    error = str(exc)
                finally:
                    if isinstance(cron_tool, _CT) and cron_token is not None:
                        cron_tool.reset_cron_context(cron_token)

                response = result.content if result else ""

                if not error:
                    message_tool = self._agent.tools.get("message")
                    already_sent = isinstance(message_tool, _MT) and message_tool._sent_in_turn

                    if not already_sent and job.payload.to and response:
                        try:
                            should_notify = await _evaluate(
                                response, job.payload.message,
                                self._agent.provider, self._agent.model,
                            )
                            if should_notify:
                                await self._agent.bus.publish_outbound(_Outbound(
                                    channel=job_channel,
                                    chat_id=job.payload.to,
                                    content=response,
                                ))
                        except Exception:
                            pass

                duration_ms = int(_time.time() * 1000) - start_ms
                history.record(job.id, {
                    "runAtMs": start_ms,
                    "status": "error" if error else "ok",
                    "durationMs": duration_ms,
                    "error": error,
                    "summary": response[:500] if not error else None,
                    "sessionKey": session_key,
                })
                if error:
                    raise RuntimeError(error)
                return response

            self._cron.on_job = _on_cron_job
            await self._cron.start()
            self._verify_cron_store()

        # Install performance patches (zero-invasion monkey-patch)
        from .perf import install_perf_patches
        install_perf_patches(self._agent)

        # Pre-warm MCP connections in a separate task so anyio cancel-scope
        # leaks (e.g. self-referencing deskclaw MCP that isn't listening yet)
        # don't crash the lifespan context.
        if self._agent._mcp_servers:
            async def _prewarm_mcp() -> None:
                try:
                    await self._agent._connect_mcp()
                except BaseException as exc:
                    print(f"[Gateway] MCP pre-warm failed (will retry on first request): {exc}",
                          file=__import__('sys').stderr, flush=True)
            self._mcp_warmup_task = asyncio.create_task(_prewarm_mcp())

        # Install tool execution security layer (zero-invasion monkey-patch)
        from .security import ToolSecurityLayer
        self._security = ToolSecurityLayer()
        self._security.install()

        # Load and activate user extensions (~/.deskclaw/extensions/)
        await self._install_extensions()

        # restart_gateway / restart_deskclaw: consume pending action after every turn
        # (WS desktop chat, Feishu, cron process_direct, etc. all use _process_message).
        _patch_process_message_for_pending_restart(self._agent)

        # Start ChannelManager for external channels (Feishu, WeCom, QQ, etc.)
        # cm.bus IS self.bus (same Python object reference), so we cannot patch
        # cm.bus.consume_outbound directly — that would also change self.bus.
        # Instead, replace cm.bus with a proxy that reads from its own queue.
        try:
            from nanobot.channels.manager import ChannelManager
            cm = ChannelManager(self.config, self.bus)
            if cm.enabled_channels:
                _channel_outbound: asyncio.Queue = asyncio.Queue()
                _original_publish = self.bus.publish_outbound

                async def _broadcast_outbound(msg):
                    await _original_publish(msg)
                    await _channel_outbound.put(msg)

                self.bus.publish_outbound = _broadcast_outbound

                # MessageTool captured the original publish_outbound at
                # __init__ time; refresh it so media messages also reach
                # the channel outbound queue.
                from nanobot.agent.tools.message import MessageTool as _MT
                _mt = self._agent.tools.get("message")
                if _mt and isinstance(_mt, _MT):
                    _mt.set_send_callback(self.bus.publish_outbound)

                class _ChannelBusProxy:
                    """Proxy so ChannelManager reads from its own queue
                    while server.py reads from the original bus queue."""
                    def __init__(self, real_bus, queue):
                        self._real = real_bus
                        self._queue = queue
                        self.outbound = queue
                    async def consume_outbound(self):
                        return await self._queue.get()
                    def __getattr__(self, name):
                        return getattr(self._real, name)

                cm.bus = _ChannelBusProxy(self.bus, _channel_outbound)

                # Patch _dispatch to set current_channel_name for approval routing
                from .security.approval import current_channel_name
                _original_dispatch = self._agent._dispatch

                async def _channel_aware_dispatch(msg):
                    current_channel_name.set(msg.channel)
                    await _original_dispatch(msg)

                self._agent._dispatch = _channel_aware_dispatch

                self._channel_manager = cm
                asyncio.create_task(cm.start_all())
                self._bus_task = asyncio.create_task(self._agent.run())
                from loguru import logger
                logger.info(
                    "ChannelManager started: {}",
                    ", ".join(cm.enabled_channels),
                )
        except (Exception, SystemExit) as e:
            from loguru import logger
            logger.warning("ChannelManager not available: {}", e)

        import shutil
        _cfg = resolve_nanobot_config_path()
        if _cfg.exists():
            shutil.copy2(_cfg, _cfg.with_suffix(".last-good"))

    async def _install_extensions(self) -> None:
        """Discover and activate user extensions, wire enabled ones into the agent loop."""
        try:
            from .extensions.registry import ExtensionRegistry
            from .extensions.agent_hook import AgentHookAdapter

            registry = ExtensionRegistry()
            await registry.load_and_activate(
                workspace=Path(self.workspace),
                config={"model": self._agent.model if self._agent else None},
            )

            # Always store the registry so MCP tools can list/toggle
            # even when no extensions are currently enabled.
            self._extension_registry = registry

            # Always install patches so that extensions enabled later
            # (via MCP tools + extension_reload) have working hooks.
            adapter = AgentHookAdapter(registry)
            self._agent._extra_hooks.append(adapter)

            from .extensions.security_bridge import install_security_bridge
            install_security_bridge(registry, self._security)

            from .extensions.turn_patch import install_turn_patch
            install_turn_patch(registry)

            from .extensions.memory_patch import install_memory_patch
            install_memory_patch(registry, self._agent)

            import sys as _sys
            all_count = len(registry.list_all())
            active_count = len(registry.extensions)
            print(
                f"[Extensions] {all_count} installed, {active_count} active",
                file=_sys.stderr, flush=True,
            )
        except Exception as exc:
            import sys as _sys
            print(
                f"[Extensions] Failed to load extensions: {exc}",
                file=_sys.stderr, flush=True,
            )

    async def stop(self) -> None:
        if self._cron_migration_task and not self._cron_migration_task.done():
            self._cron_migration_task.cancel()
            try:
                await self._cron_migration_task
            except BaseException:
                pass
            self._cron_migration_task = None
        if self._mcp_warmup_task and not self._mcp_warmup_task.done():
            self._mcp_warmup_task.cancel()
            try:
                await self._mcp_warmup_task
            except BaseException:
                pass
            self._mcp_warmup_task = None
        if self._channel_manager:
            try:
                await self._channel_manager.stop_all()
            except BaseException:
                pass
        if self._bus_task and not self._bus_task.done():
            self._bus_task.cancel()
            try:
                await self._bus_task
            except BaseException:
                pass
        if self._cron:
            try:
                self._cron.stop()
            except BaseException:
                pass
        if self._extension_registry:
            try:
                await self._extension_registry.deactivate_all()
            except BaseException:
                pass
        if self._agent:
            try:
                await self._agent.close_mcp()
            except BaseException:
                pass
            try:
                self._agent.stop()
            except BaseException:
                pass
        self._agent = None

    async def chat(self, message: str, session_id: str | None = None) -> dict[str, Any]:
        sid = session_id or f"gateway:{uuid.uuid4().hex[:8]}"
        if not self._agent:
            raise RuntimeError("Agent not started")

        parts = sid.split(":", 1)
        ch, cid = (parts[0], parts[1]) if len(parts) == 2 else ("gateway", sid)
        response = await self._agent.process_direct(
            content=message,
            session_key=sid,
            channel=ch,
            chat_id=cid,
        )
        return {
            "run_id": uuid.uuid4().hex,
            "content": response.content if response else "",
            "session_id": sid,
            "tool_calls": [],
        }

    def get_history(self, session_id: str) -> list[dict]:
        """Return full session history for UI display.

        Mirrors gateway_bridge's get_history: builds tool-card entries and
        extracts message-tool content as standalone assistant bubbles.
        The frontend paginates via visibleMsgCount, so no server-side
        truncation is applied — all messages are returned.
        """
        if not self._agent:
            return []
        session = self._agent.sessions.get_or_create(session_id)
        msgs = session.messages

        out: list[dict] = []
        pending_tools: dict[str, dict[str, Any]] = {}

        for msg in msgs:
            role = msg.get("role", "")
            content = msg.get("content", "")
            ts = msg.get("timestamp")
            if not isinstance(content, str):
                content = self._normalize_content(content)

            if role == "user":
                if content.startswith(_STEERING_PREFIX):
                    content = content[len(_STEERING_PREFIX):]
                if content:
                    entry: dict[str, Any] = {"role": role, "content": content}
                    if ts:
                        entry["timestamp"] = ts
                    out.append(entry)
                continue

            if role == "assistant":
                tool_calls = msg.get("tool_calls") or []
                if content:
                    entry = {"role": role, "content": content}
                    if ts:
                        entry["timestamp"] = ts
                    out.append(entry)

                for tc in tool_calls:
                    tool_entry = self._build_tool_entry(tc)
                    out.append(tool_entry)
                    if tool_entry.get("toolCallId"):
                        pending_tools[tool_entry["toolCallId"]] = tool_entry

                    msg_content = self._extract_message_tool_content(tc)
                    if msg_content:
                        a_entry: dict[str, Any] = {"role": "assistant", "content": msg_content}
                        if ts:
                            a_entry["timestamp"] = ts
                        out.append(a_entry)
                continue

            if role == "tool":
                tool_call_id = msg.get("tool_call_id")
                tool_entry = pending_tools.get(tool_call_id)  # type: ignore[arg-type]
                if tool_entry is None:
                    tool_entry = {
                        "role": "tool",
                        "name": msg.get("name") or "tool",
                        "toolCallId": tool_call_id,
                        "phase": "end",
                    }
                    out.append(tool_entry)
                    if tool_call_id:
                        pending_tools[tool_call_id] = tool_entry

                tool_entry["name"] = msg.get("name") or tool_entry.get("name") or "tool"
                tool_entry["phase"] = "end"
                raw_content = msg.get("content", "")
                if raw_content and isinstance(raw_content, str):
                    tool_entry["result"] = raw_content
                continue

        return out

    def _normalize_content(self, content: Any) -> str:
        """Convert list-of-blocks content to plain string."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    t = block.get("type", "")
                    if t == "text":
                        parts.append(block.get("text", ""))
                    elif t in ("image_url", "image"):
                        url = block.get("image_url", {}).get("url", "") if t == "image_url" else block.get("url", "")
                        if url and not url.startswith("data:"):
                            parts.append(f"![image]({url})")
            return "\n".join(filter(None, parts))
        return str(content) if content else ""

    @staticmethod
    def _build_tool_entry(tool_call: dict) -> dict[str, Any]:
        fn = tool_call.get("function", {})
        return {
            "role": "tool",
            "name": fn.get("name") or "tool",
            "toolCallId": tool_call.get("id"),
            "args": fn.get("arguments", ""),
            "phase": "end",
        }

    @staticmethod
    def _extract_message_tool_content(tool_call: dict) -> str:
        """Build standalone assistant bubble from a message tool call."""
        fn = tool_call.get("function", {})
        if fn.get("name") != "message":
            return ""
        try:
            args = _json.loads(fn.get("arguments", "{}"))
        except (ValueError, TypeError):
            return ""

        text = args.get("content", "") or ""
        media_parts = [f"\n![image]({path})" for path in args.get("media", []) if path]
        media_md = "".join(media_parts)
        if text and media_md:
            return f"{text}{media_md}"
        return text or media_md.lstrip("\n")

    def abort(self, session_id: str) -> bool:
        if not self._agent:
            return False
        tasks = getattr(self._agent, "_active_tasks", {}).pop(session_id, [])
        cancelled = sum(t.cancel() for t in tasks if not t.done())
        return cancelled > 0

    _EXTERNAL_CHANNELS = frozenset({
        "feishu", "dingtalk", "qq", "wecom",
        "telegram", "discord", "slack", "whatsapp",
        "matrix", "email", "mochat",
    })

    @staticmethod
    def _parse_channel(session_key: str) -> str:
        """Extract channel name from session_key (format: ``channel:chat_id``)."""
        prefix = session_key.split(":", 1)[0] if session_key else ""
        if prefix in GatewayAgent._EXTERNAL_CHANNELS:
            return prefix
        return "internal"

    def list_sessions(self) -> list[dict]:
        from datetime import datetime, timezone

        sessions = self.session_manager.list_sessions()
        result = []
        for s in sessions:
            if isinstance(s, str):
                sid = s
            elif isinstance(s, dict):
                sid = s.get("key", str(s))
            else:
                sid = str(s)

            entry: dict = {"session_id": sid, "channel": self._parse_channel(sid)}
            try:
                path = self.session_manager._get_session_path(sid)
                if path.exists():
                    stat = path.stat()
                    entry["created_at"] = datetime.fromtimestamp(
                        stat.st_ctime, tz=timezone.utc
                    ).isoformat()
                    entry["last_active"] = datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat()
            except Exception:
                pass
            result.append(entry)
        return result

    def delete_session(self, session_id: str) -> None:
        # SessionManager has no delete() method, so we do it at the gateway layer:
        # 1. Clear the in-memory cache
        self.session_manager.invalidate(session_id)
        # 2. Delete the session file from disk
        session_path = self.session_manager._get_session_path(session_id)
        if session_path.exists():
            session_path.unlink()
