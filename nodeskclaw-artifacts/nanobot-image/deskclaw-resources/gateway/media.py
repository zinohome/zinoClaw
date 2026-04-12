"""Media persistence utility — download/link uploaded media into workspace."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import urllib.request
from functools import partial
from pathlib import Path
from uuid import uuid4

from loguru import logger

_DIR_SAFE_RE = re.compile(r"[^a-zA-Z0-9_.-]")
_FILE_SAFE_RE = re.compile(r'[/\\:<>"|?*\x00-\x1f]')
_HASH_CHUNK = 8192
_DOWNLOAD_TIMEOUT_S = 60


def _safe_dir_name(name: str) -> str:
    """Sanitize for directory names — must match sessionKeyToDirName in ipc-router.ts."""
    return _DIR_SAFE_RE.sub("_", name)[:80]


def _safe_name(name: str) -> str:
    """Sanitize for filenames — preserves CJK and other Unicode characters."""
    return _FILE_SAFE_RE.sub("_", name)[:80]


def _unique_dest(target_dir: Path, preferred_name: str, fallback_ext: str = "") -> Path:
    """Pick a destination path preserving *preferred_name*, adding a counter on collision."""
    safe = _safe_name(preferred_name) if preferred_name else ""
    if not safe or safe.startswith("."):
        safe = f"{uuid4().hex[:12]}{fallback_ext}"
    dest = target_dir / safe
    if not dest.exists():
        return dest
    stem, ext = dest.stem, dest.suffix
    counter = 1
    while dest.exists():
        dest = target_dir / f"{stem}_{counter}{ext}"
        counter += 1
    return dest


def _download_with_timeout(url: str, dest: str, timeout: int = _DOWNLOAD_TIMEOUT_S) -> str:
    """urlretrieve with a socket-level timeout to avoid hanging forever."""
    import socket
    old = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        urllib.request.urlretrieve(url, dest)
    finally:
        socket.setdefaulttimeout(old)
    return dest


def _file_hash(path: Path) -> str:
    """Fast content hash (first 8KB + file size) for dedup. Not cryptographic."""
    h = hashlib.blake2b(digest_size=16)
    try:
        size = path.stat().st_size
        h.update(size.to_bytes(8, "little"))
        with open(path, "rb") as f:
            h.update(f.read(_HASH_CHUNK))
            if size > _HASH_CHUNK:
                f.seek(max(0, size - _HASH_CHUNK))
                h.update(f.read(_HASH_CHUNK))
    except OSError:
        return ""
    return h.hexdigest()


def _resolve_through_symlink(p: Path) -> Path:
    """Resolve a path, following symlinks to get the real file."""
    try:
        return p.resolve()
    except OSError:
        return p


def _build_dedup_index(target_dir: Path) -> dict[str, Path]:
    """Build hash->path index of existing files in target_dir."""
    index: dict[str, Path] = {}
    try:
        for child in target_dir.iterdir():
            if child.name.startswith(".") or child.is_dir():
                continue
            real = _resolve_through_symlink(child)
            if not real.is_file():
                continue
            h = _file_hash(real)
            if h:
                index[h] = child
    except OSError:
        pass
    return index


async def persist_media(
    paths: list[str],
    session_id: str,
    workspace: str | Path,
    registry: "AssetRegistry | None" = None,
) -> list[str]:
    """Persist media files into workspace/media/{session_id}/.

    Deduplicates by content hash — if an identical file already exists
    in the session dir, it is reused instead of creating a new entry.
    If *registry* is provided, each persisted file is registered in the
    SQLite index.

    Returns a list of workspace-relative paths (e.g. "media/sess/abc.png").
    """
    from .asset_registry import guess_kind as _guess_kind
    ws = Path(workspace).resolve()
    target_dir = ws / "media" / _safe_dir_name(session_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_target = target_dir.resolve()

    loop = asyncio.get_running_loop()
    dedup = await loop.run_in_executor(None, _build_dedup_index, target_dir)
    result: list[str] = []

    for p in paths:
        try:
            if p.startswith(("http://", "https://")):
                ext = Path(p.split("?")[0]).suffix or ".png"
                dest = target_dir / f"{uuid4().hex[:12]}{ext}"
                await loop.run_in_executor(
                    None, partial(_download_with_timeout, p, str(dest)),
                )
                h = await loop.run_in_executor(None, _file_hash, dest)
                if h and h in dedup:
                    dest.unlink()
                    existing = dedup[h]
                    rel = str(existing.relative_to(ws))
                    result.append(rel)
                    logger.info("persist_media: download dedup, reusing {}", existing.name)
                else:
                    if h:
                        dedup[h] = dest
                    rel = str(dest.relative_to(ws))
                    result.append(rel)
                    logger.info("persist_media: downloaded {} -> {}", p[:80], dest)
                    if registry:
                        registry.register(session_id, "user", _guess_kind(dest.name),
                                          dest.name, path=str(dest), content_hash=h)
            else:
                src = _resolve_through_symlink(Path(p))
                if not src.is_file():
                    logger.warning("persist_media: not found, skipping: {}", p)
                    continue

                if src.parent == resolved_target:
                    rel = str(src.relative_to(ws))
                    result.append(rel)
                    if registry:
                        fh = await loop.run_in_executor(None, _file_hash, src)
                        registry.register(session_id, "user", _guess_kind(src.name),
                                          src.name, path=str(src), content_hash=fh or None)
                    logger.info("persist_media: already in session dir: {}", src.name)
                    continue

                h = await loop.run_in_executor(None, _file_hash, src)
                if h and h in dedup:
                    existing = dedup[h]
                    result.append(str(existing.relative_to(ws)))
                    if registry:
                        registry.register(session_id, "user", _guess_kind(existing.name),
                                          existing.name, path=str(existing), content_hash=h)
                    logger.info("persist_media: dedup match, reusing {}", existing.name)
                    continue

                dest = _unique_dest(target_dir, src.name, src.suffix)
                try:
                    await loop.run_in_executor(None, os.symlink, str(src), str(dest))
                    logger.info("persist_media: symlinked {} -> {}", src, dest)
                except OSError:
                    await loop.run_in_executor(None, shutil.copy2, str(src), str(dest))
                    logger.info("persist_media: copy fallback {} -> {}", src, dest)

                if h:
                    dedup[h] = dest
                rel = str(dest.relative_to(ws))
                result.append(rel)
                if registry:
                    registry.register(session_id, "user", _guess_kind(dest.name),
                                      dest.name, path=str(dest), content_hash=h)
        except Exception as exc:
            logger.warning("persist_media: failed {}: {}", p, exc)
            if not p.startswith(("http://", "https://")) and Path(p).is_file():
                result.append(str(Path(p).relative_to(ws)))

    return result


async def persist_agent_outputs(
    items: list[str],
    session_id: str,
    workspace: str | Path,
    registry: "AssetRegistry | None" = None,
) -> list[str]:
    """Download agent-produced media into workspace/outputs/{session}/.

    URLs are downloaded; local paths are symlinked. Returns workspace-relative paths.
    """
    from .asset_registry import guess_kind as _guess_kind

    ws = Path(workspace).resolve()
    target_dir = ws / "outputs" / _safe_dir_name(session_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_target = target_dir.resolve()

    loop = asyncio.get_running_loop()
    dedup = await loop.run_in_executor(None, _build_dedup_index, target_dir)
    result: list[str] = []

    for item in items:
        try:
            if item.startswith(("http://", "https://")):
                ext = Path(item.split("?")[0]).suffix or ".png"
                dest = target_dir / f"{uuid4().hex[:12]}{ext}"
                await loop.run_in_executor(
                    None, partial(_download_with_timeout, item, str(dest)),
                )
                h = await loop.run_in_executor(None, _file_hash, dest)
                if h and h in dedup:
                    dest.unlink()
                    existing = dedup[h]
                    rel = str(existing.relative_to(ws))
                    result.append(rel)
                    if registry:
                        registry.register(session_id, "agent", _guess_kind(existing.name),
                                          existing.name, path=str(existing), url=item, content_hash=h)
                    logger.info("persist_output: download dedup, reusing {}", existing.name)
                else:
                    if h:
                        dedup[h] = dest
                    rel = str(dest.relative_to(ws))
                    result.append(rel)
                    if registry:
                        registry.register(session_id, "agent", _guess_kind(dest.name),
                                          dest.name, path=str(dest), url=item, content_hash=h)
                    logger.info("persist_output: downloaded {} -> {}", item[:80], dest)
            else:
                src = _resolve_through_symlink(Path(item))
                if not src.is_file():
                    continue

                if src.parent == resolved_target:
                    rel = str(src.relative_to(ws))
                    result.append(rel)
                    if registry:
                        fh = await loop.run_in_executor(None, _file_hash, src)
                        registry.register(session_id, "agent", _guess_kind(src.name),
                                          src.name, path=str(src), content_hash=fh or None)
                    continue

                h = await loop.run_in_executor(None, _file_hash, src)
                if h and h in dedup:
                    existing = dedup[h]
                    result.append(str(existing.relative_to(ws)))
                    if registry:
                        registry.register(session_id, "agent", _guess_kind(existing.name),
                                          existing.name, path=str(existing), content_hash=h)
                    continue
                dest = _unique_dest(target_dir, src.name, src.suffix)
                try:
                    await loop.run_in_executor(None, os.symlink, str(src), str(dest))
                except OSError:
                    try:
                        await loop.run_in_executor(None, shutil.copy2, str(src), str(dest))
                    except shutil.SameFileError:
                        pass
                if h:
                    dedup[h] = dest
                rel = str(dest.relative_to(ws))
                result.append(rel)
                if registry:
                    registry.register(session_id, "agent", _guess_kind(dest.name),
                                      dest.name, path=str(dest), content_hash=h)
        except Exception as exc:
            logger.warning("persist_output: failed {}: {}", item, exc)

    return result
