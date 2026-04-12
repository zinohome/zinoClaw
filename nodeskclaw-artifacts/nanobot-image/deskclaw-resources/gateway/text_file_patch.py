"""Best-effort text decoding patches for nanobot prompt inputs.

DeskClaw does not modify nanobot source directly. Instead, patch the small set
of text-file reads that feed system prompt construction so user-edited files on
Windows do not crash sessions when they are not UTF-8 encoded.
"""

from __future__ import annotations

import locale
import mimetypes
from pathlib import Path
from typing import Any

from loguru import logger


def _decode_text_best_effort(raw: bytes, path: Path, default: str = "") -> str:
    if not raw:
        return ""

    tried: set[str] = set()
    for encoding in ("utf-8", "utf-8-sig", locale.getpreferredencoding(False), "gb18030"):
        if not encoding:
            continue
        normalized = encoding.lower()
        if normalized in tried:
            continue
        tried.add(normalized)
        try:
            text = raw.decode(encoding)
            if normalized != "utf-8":
                logger.warning(
                    "[deskclaw] Decoded {} with fallback encoding {}",
                    path,
                    encoding,
                )
            return text
        except UnicodeDecodeError:
            continue

    fallback = locale.getpreferredencoding(False) or "utf-8"
    logger.warning(
        "[deskclaw] Decoding {} with replacement using fallback encoding {}",
        path,
        fallback,
    )
    try:
        return raw.decode(fallback, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _read_text_best_effort(path: Path, default: str = "") -> str:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return default
    except OSError:
        return default

    return _decode_text_best_effort(raw, path, default=default)


def install() -> None:
    """Patch nanobot prompt-related text readers once."""
    import nanobot.agent.context as context_mod
    import nanobot.agent.memory as memory_mod
    import nanobot.agent.skills as skills_mod
    import nanobot.agent.tools.filesystem as filesystem_mod

    if getattr(memory_mod.MemoryStore.read_file, "_deskclaw_text_patch", False):
        return

    @staticmethod
    def _patched_read_file(path: Path) -> str:
        return _read_text_best_effort(path)

    _patched_read_file._deskclaw_text_patch = True  # type: ignore[attr-defined]
    memory_mod.MemoryStore.read_file = _patched_read_file

    def _patched_load_bootstrap_files(self) -> str:
        parts: list[str] = []
        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                parts.append(f"## {filename}\n\n{_read_text_best_effort(file_path)}")
        return "\n\n".join(parts) if parts else ""

    context_mod.ContextBuilder._load_bootstrap_files = _patched_load_bootstrap_files

    def _patched_load_skill(self, name: str) -> str | None:
        workspace_skill = self.workspace_skills / name / "SKILL.md"
        if workspace_skill.exists():
            return _read_text_best_effort(workspace_skill)

        if self.builtin_skills:
            builtin_skill = self.builtin_skills / name / "SKILL.md"
            if builtin_skill.exists():
                return _read_text_best_effort(builtin_skill)

        return None

    skills_mod.SkillsLoader.load_skill = _patched_load_skill

    _orig_read_execute = filesystem_mod.ReadFileTool.execute
    _orig_edit_execute = filesystem_mod.EditFileTool.execute

    async def _patched_read_execute(
        self,
        path: str | None = None,
        offset: int = 1,
        limit: int | None = None,
        **kwargs: Any,
    ) -> Any:
        try:
            if not path:
                return "Error reading file: Unknown path"
            fp = self._resolve(path)
            if not fp.exists():
                return f"Error: File not found: {path}"
            if not fp.is_file():
                return f"Error: Not a file: {path}"

            raw = fp.read_bytes()
            if not raw:
                return f"(Empty file: {path})"

            mime = filesystem_mod.detect_image_mime(raw) or mimetypes.guess_type(path)[0]
            if mime and mime.startswith("image/"):
                return filesystem_mod.build_image_content_blocks(raw, mime, str(fp), f"(Image file: {path})")

            text_content = _decode_text_best_effort(raw, fp)
            all_lines = text_content.splitlines()
            total = len(all_lines)

            if offset < 1:
                offset = 1
            if offset > total:
                return f"Error: offset {offset} is beyond end of file ({total} lines)"

            start = offset - 1
            end = min(start + (limit or self._DEFAULT_LIMIT), total)
            numbered = [f"{start + i + 1}| {line}" for i, line in enumerate(all_lines[start:end])]
            result = "\n".join(numbered)

            if len(result) > self._MAX_CHARS:
                trimmed, chars = [], 0
                for line in numbered:
                    chars += len(line) + 1
                    if chars > self._MAX_CHARS:
                        break
                    trimmed.append(line)
                end = start + len(trimmed)
                result = "\n".join(trimmed)

            if end < total:
                result += f"\n\n(Showing lines {offset}-{end} of {total}. Use offset={end + 1} to continue.)"
            else:
                result += f"\n\n(End of file — {total} lines total)"
            return result
        except PermissionError as e:
            return f"Error: {e}"
        except Exception:
            return await _orig_read_execute(self, path=path, offset=offset, limit=limit, **kwargs)

    async def _patched_edit_execute(
        self,
        path: str | None = None,
        old_text: str | None = None,
        new_text: str | None = None,
        replace_all: bool = False,
        **kwargs: Any,
    ) -> str:
        try:
            if not path:
                raise ValueError("Unknown path")
            if old_text is None:
                raise ValueError("Unknown old_text")
            if new_text is None:
                raise ValueError("Unknown new_text")

            fp = self._resolve(path)
            if not fp.exists():
                return f"Error: File not found: {path}"

            raw = fp.read_bytes()
            uses_crlf = b"\r\n" in raw
            content = _decode_text_best_effort(raw, fp).replace("\r\n", "\n")
            match, count = filesystem_mod._find_match(content, old_text.replace("\r\n", "\n"))

            if match is None:
                return self._not_found_msg(old_text, content, path)
            if count > 1 and not replace_all:
                return (
                    f"Warning: old_text appears {count} times. "
                    "Provide more context to make it unique, or set replace_all=true."
                )

            norm_new = new_text.replace("\r\n", "\n")
            new_content = content.replace(match, norm_new) if replace_all else content.replace(match, norm_new, 1)
            if uses_crlf:
                new_content = new_content.replace("\n", "\r\n")

            fp.write_bytes(new_content.encode("utf-8"))
            return f"Successfully edited {fp}"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception:
            return await _orig_edit_execute(
                self,
                path=path,
                old_text=old_text,
                new_text=new_text,
                replace_all=replace_all,
                **kwargs,
            )

    filesystem_mod.ReadFileTool.execute = _patched_read_execute
    filesystem_mod.EditFileTool.execute = _patched_edit_execute
