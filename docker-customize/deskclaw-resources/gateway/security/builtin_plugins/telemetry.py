# version: 4
"""Telemetry bridge — loaded by ToolSecurityLayer as a builtin plugin.

Delegates to gateway.telemetry.TelemetryCollector which handles all
config, batching, and HTTP reporting internally.  If the telemetry
module is unavailable or fails to initialise, this plugin silently
becomes a no-op so the main security / agent flow is unaffected.
"""

from __future__ import annotations

_collector = None
_init_done = False


def _ensure_init() -> None:
    global _collector, _init_done
    if _init_done:
        return
    _init_done = True
    try:
        from gateway.telemetry import TelemetryCollector
        _collector = TelemetryCollector()
    except Exception:
        pass


# Eagerly install patches and create collector at plugin load time
# so that _notify_message_end() works even for zero-tool-call conversations.
try:
    from gateway.telemetry.collector import _install_session_propagation
    _install_session_propagation()
except Exception:
    pass

_ensure_init()


def on_after(record) -> None:
    _ensure_init()
    if _collector is not None:
        try:
            _collector.on_after(record)
        except Exception:
            pass
