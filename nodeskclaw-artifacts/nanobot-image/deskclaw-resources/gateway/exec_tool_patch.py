"""Replace nanobot ``shell.ExecTool`` with a DeskClaw variant that prepends PATH per exec only.

Must be installed (``install()``) **before** ``import nanobot.agent.loop`` so SubagentManager
and AgentLoop both bind to the patched class. No nanobot source edits.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from loguru import logger

_installed = False


def install() -> None:
    """Monkey-patch ``nanobot.agent.tools.shell.ExecTool`` once."""
    global _installed
    if _installed:
        return

    import nanobot.agent.tools.shell as shell_mod

    from .exec_path import deskclaw_exec_path_prepend

    _Base = shell_mod.ExecTool

    class _DeskclawExecTool(_Base):
        async def execute(
            self,
            command: str,
            working_dir: str | None = None,
            timeout: int | None = None,
            **kwargs: Any,
        ) -> str:
            cwd = working_dir or self.working_dir or os.getcwd()
            guard_error = self._guard_command(command, cwd)
            if guard_error:
                return guard_error

            effective_timeout = min(timeout or self.timeout, self._MAX_TIMEOUT)

            env = os.environ.copy()
            prep = deskclaw_exec_path_prepend()
            if prep:
                env["PATH"] = prep + os.pathsep + env.get("PATH", "")
            if self.path_append:
                env["PATH"] = env.get("PATH", "") + os.pathsep + self.path_append

            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=effective_timeout,
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        pass
                    finally:
                        if sys.platform != "win32":
                            try:
                                os.waitpid(process.pid, os.WNOHANG)
                            except (ProcessLookupError, ChildProcessError) as e:
                                logger.debug("Process already reaped or not found: {}", e)
                    return f"Error: Command timed out after {effective_timeout} seconds"

                output_parts = []

                if stdout:
                    output_parts.append(stdout.decode("utf-8", errors="replace"))

                if stderr:
                    stderr_text = stderr.decode("utf-8", errors="replace")
                    if stderr_text.strip():
                        output_parts.append(f"STDERR:\n{stderr_text}")

                if self._is_win_gui_command(command) and process.returncode == 1:
                    output_parts.append(
                        "\nExit code: 0 (explorer.exe returns 1 on Windows even on success, normalized to 0)"
                    )
                else:
                    output_parts.append(f"\nExit code: {process.returncode}")

                result = "\n".join(output_parts) if output_parts else "(no output)"

                max_len = self._MAX_OUTPUT
                if len(result) > max_len:
                    half = max_len // 2
                    result = (
                        result[:half]
                        + f"\n\n... ({len(result) - max_len:,} chars truncated) ...\n\n"
                        + result[-half:]
                    )

                return result

            except Exception as e:
                return f"Error executing command: {str(e)}"

    shell_mod.ExecTool = _DeskclawExecTool
    _installed = True
