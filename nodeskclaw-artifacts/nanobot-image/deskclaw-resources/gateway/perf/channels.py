"""Channel send() patches — URL media pre-download, Feishu reaction auto-cleanup."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from loguru import logger


# ── 5. Channel URL media pre-download ──────────────────────────────

_URL_NATIVE_CHANNELS = frozenset({"telegram", "dingtalk", "mochat"})

_CONTENT_TYPE_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "application/pdf": ".pdf",
}


def _guess_ext(url: str, headers: Any) -> str:
    """Guess a file extension from Content-Type header or URL path."""
    import mimetypes
    from urllib.parse import urlparse

    ct = None
    if headers:
        raw = headers.get("content-type", "")
        ct = raw.split(";", 1)[0].strip().lower() if raw else None
    if ct and ct in _CONTENT_TYPE_EXT:
        return _CONTENT_TYPE_EXT[ct]
    if ct:
        ext = mimetypes.guess_extension(ct)
        if ext:
            return ext

    path = urlparse(url).path
    dot = path.rfind(".")
    if dot != -1:
        ext = path[dot:].split("?", 1)[0].lower()
        if 1 < len(ext) <= 6:
            return ext
    return ""


async def _materialize_url_media(
    media: list[str],
) -> tuple[list[str], list[str]]:
    """Download remote URLs to temp files, pass local paths through.

    Returns (patched_media_list, list_of_temp_files_to_cleanup).
    """
    import os
    import tempfile

    import httpx

    result: list[str] = []
    temp_files: list[str] = []

    has_urls = any(m.startswith(("http://", "https://")) for m in media)
    if not has_urls:
        return media, temp_files

    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        for item in media:
            if not item.startswith(("http://", "https://")):
                result.append(item)
                continue
            try:
                resp = await client.get(item)
                resp.raise_for_status()
                ext = _guess_ext(item, resp.headers)
                fd, tmp_path = tempfile.mkstemp(suffix=ext)
                try:
                    os.write(fd, resp.content)
                finally:
                    os.close(fd)
                temp_files.append(tmp_path)
                result.append(tmp_path)
                logger.debug("Downloaded media URL → {}", tmp_path)
            except Exception as exc:
                logger.warning("Failed to download media URL {}: {}", item, exc)
                result.append(item)

    return result, temp_files


def _cleanup_temps(paths: list[str]) -> None:
    import os

    for p in paths:
        try:
            os.unlink(p)
        except OSError:
            pass


def patch_channel_url_media() -> None:
    """Wrap send() on channels that don't handle remote URLs natively.

    Channels like Feishu, Discord, Slack, Matrix only accept local file
    paths in msg.media.  This patch transparently downloads URL media to
    temp files before forwarding to the original send(), then cleans up.

    Uses __init_subclass__ to hook future subclass definitions, because
    install_perf_patches() runs before discover_all() imports channel modules.
    """
    from nanobot.channels.base import BaseChannel

    _wrapped_ids: set[int] = set()

    def _maybe_wrap(subcls):
        if id(subcls) in _wrapped_ids:
            return
        ch_name = getattr(subcls, "name", "")
        if ch_name in _URL_NATIVE_CHANNELS:
            return
        if getattr(subcls.send, "__isabstractmethod__", False):
            return

        orig_send = subcls.send

        async def _wrapped_send(self, msg, _orig=orig_send):
            if not msg.media:
                return await _orig(self, msg)

            patched_media, temp_files = await _materialize_url_media(msg.media)
            if not temp_files:
                return await _orig(self, msg)

            saved_media = msg.media
            msg.media = patched_media
            try:
                return await _orig(self, msg)
            finally:
                msg.media = saved_media
                _cleanup_temps(temp_files)

        subcls.send = _wrapped_send
        _wrapped_ids.add(id(subcls))
        print(
            f"[Perf] URL media: wrapped {ch_name or subcls.__name__}.send()",
            file=sys.stderr, flush=True,
        )

    for subcls in BaseChannel.__subclasses__():
        _maybe_wrap(subcls)

    _orig_isc = BaseChannel.__init_subclass__

    @classmethod  # type: ignore[misc]
    def _hooked_init_subclass(cls, **kwargs):
        super(BaseChannel, cls).__init_subclass__(**kwargs)
        _maybe_wrap(cls)

    BaseChannel.__init_subclass__ = _hooked_init_subclass  # type: ignore[assignment]
    print("[Perf] Channel URL media hook installed", file=sys.stderr, flush=True)


# ── 6. Feishu reaction auto-cleanup ────────────────────────────────


def patch_feishu_reaction_cleanup() -> None:
    """Remove the "processing" reaction after the final reply is sent.

    Wraps FeishuChannel._add_reaction to capture reaction_id, and wraps
    send() to delete the reaction once a non-progress reply is dispatched.

    Streaming replies skip ``send()`` (only ``send_delta`` + ``_streamed`` noop),
    so we also wrap ``send_delta``: on final ``_stream_end`` (not ``_resuming``),
    resolve the user message via ``chat_id`` (recorded in ``_handle_message``)
    and remove the pending reaction.

    Must be called AFTER patch_channel_url_media so that our send() wrapper
    sits on the outermost layer.

    Best-effort only: incompatible nanobot or lark_oapi versions skip patching
    so the gateway still starts (Feishu may lack streaming reaction cleanup).
    """
    from nanobot.channels.base import BaseChannel

    _patched_ids: set[int] = set()

    try:
        from lark_oapi.api.im.v1 import (
            CreateMessageReactionRequest,
            CreateMessageReactionRequestBody,
            DeleteMessageReactionRequest,
            Emoji,
        )
    except ImportError as e:
        logger.warning("Feishu reaction patch skipped (lark_oapi IM API unavailable): {}", e)
        return

    def _maybe_patch(subcls):
        if id(subcls) in _patched_ids:
            return
        if getattr(subcls, "name", "") != "feishu":
            return

        for attr in ("send", "send_delta", "_handle_message", "_add_reaction", "_add_reaction_sync"):
            if not hasattr(subcls, attr):
                logger.warning(
                    "Feishu reaction patch skipped: {} missing on {}",
                    attr,
                    getattr(subcls, "__name__", subcls),
                )
                return

        _patched_ids.add(id(subcls))

        try:
            # ── replace _add_reaction_sync to return reaction_id ──

            def _new_add_reaction_sync(self, message_id: str, emoji_type: str) -> str | None:
                try:
                    request = (
                        CreateMessageReactionRequest.builder()
                        .message_id(message_id)
                        .request_body(
                            CreateMessageReactionRequestBody.builder()
                            .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                            .build()
                        )
                        .build()
                    )
                    response = self._client.im.v1.message_reaction.create(request)
                    if not response.success():
                        logger.warning("Failed to add reaction: code={}, msg={}", response.code, response.msg)
                        return None
                    logger.debug("Added {} reaction to message {}", emoji_type, message_id)
                    data = getattr(response, "data", None)
                    rid = getattr(data, "reaction_id", None) if data is not None else None
                    return str(rid) if rid else None
                except Exception as e:
                    logger.warning("Error adding reaction: {}", e)
                    return None

            subcls._add_reaction_sync = _new_add_reaction_sync

            async def _new_add_reaction(self, message_id: str, emoji_type: str = "THUMBSUP") -> None:
                if not self._client or not emoji_type:
                    return
                if not hasattr(self, "_pending_reactions"):
                    self._pending_reactions: dict[str, str] = {}
                loop = asyncio.get_running_loop()
                rid = await loop.run_in_executor(
                    None, self._add_reaction_sync, message_id, emoji_type,
                )
                if rid:
                    self._pending_reactions[message_id] = rid

            subcls._add_reaction = _new_add_reaction

            def _remove_reaction_sync(self, message_id: str, reaction_id: str) -> None:
                try:
                    request = (
                        DeleteMessageReactionRequest.builder()
                        .message_id(message_id)
                        .reaction_id(reaction_id)
                        .build()
                    )
                    response = self._client.im.v1.message_reaction.delete(request)
                    if not response.success():
                        logger.debug("Failed to remove reaction: code={}, msg={}", response.code, response.msg)
                    else:
                        logger.debug("Removed reaction {} from message {}", reaction_id, message_id)
                except Exception as e:
                    logger.debug("Error removing reaction: {}", e)

            subcls._remove_reaction_sync = _remove_reaction_sync

            _orig_handle_message = subcls._handle_message

            async def _reaction_map_handle_message(
                self,
                sender_id,
                chat_id,
                content,
                media=None,
                metadata=None,
                session_key=None,
                _orig=_orig_handle_message,
            ):
                mid = (metadata or {}).get("message_id")
                if mid:
                    if not hasattr(self, "_reaction_message_for_chat"):
                        self._reaction_message_for_chat = {}
                    self._reaction_message_for_chat[str(chat_id)] = str(mid)
                return await _orig(
                    self, sender_id, chat_id, content,
                    media=media, metadata=metadata, session_key=session_key,
                )

            subcls._handle_message = _reaction_map_handle_message

            _orig_send_delta = subcls.send_delta

            async def _reaction_cleanup_send_delta(
                self, chat_id, delta, metadata=None, _orig=_orig_send_delta,
            ):
                meta = metadata or {}
                await _orig(self, chat_id, delta, meta)
                if not meta.get("_stream_end") or meta.get("_resuming"):
                    return
                rmap = getattr(self, "_reaction_message_for_chat", None)
                if not rmap:
                    return
                mid = rmap.pop(str(chat_id), None)
                if not mid:
                    return
                pending = getattr(self, "_pending_reactions", {})
                rid = pending.pop(mid, None)
                if rid and self._client:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None, self._remove_reaction_sync, mid, rid,
                    )

            subcls.send_delta = _reaction_cleanup_send_delta

            _orig_send = subcls.send

            async def _reaction_cleanup_send(self, msg, _orig=_orig_send):
                await _orig(self, msg)
                if msg.metadata.get("_tool_hint") or msg.metadata.get("_progress"):
                    return
                mid = msg.metadata.get("message_id")
                if not mid:
                    return
                pending = getattr(self, "_pending_reactions", {})
                rid = pending.pop(mid, None)
                if rid and self._client:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None, self._remove_reaction_sync, mid, rid,
                    )
                rmap = getattr(self, "_reaction_message_for_chat", None)
                if rmap and mid:
                    for k, v in list(rmap.items()):
                        if v == mid:
                            del rmap[k]

            subcls.send = _reaction_cleanup_send

            print("[Perf] Feishu reaction auto-cleanup patched", file=sys.stderr, flush=True)
        except Exception as exc:
            _patched_ids.discard(id(subcls))
            logger.warning(
                "Feishu reaction patch failed for {}: {}",
                getattr(subcls, "__name__", subcls),
                exc,
            )

    for subcls in BaseChannel.__subclasses__():
        _maybe_patch(subcls)

    _prev_isc = BaseChannel.__init_subclass__

    @classmethod  # type: ignore[misc]
    def _chained_init_subclass(cls, **kwargs):
        _prev_isc.__func__(cls, **kwargs)
        try:
            _maybe_patch(cls)
        except Exception as exc:
            logger.warning("Feishu reaction hook on new channel subclass failed: {}", exc)

    BaseChannel.__init_subclass__ = _chained_init_subclass  # type: ignore[assignment]
    print("[Perf] Feishu reaction cleanup hook installed", file=sys.stderr, flush=True)
