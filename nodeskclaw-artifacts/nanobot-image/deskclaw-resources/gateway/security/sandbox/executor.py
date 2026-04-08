"""ContainerExecutor — manages a long-running sandbox container and runs commands inside it.

The container stays alive for the application lifetime to avoid per-command startup cost.
All exec calls use `docker/podman exec` into the running container (~50ms overhead).
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field

from ...paths import resolve_workspace_path
from .runtime import RuntimeInfo, DEFAULT_IMAGE

logger = logging.getLogger("deskclaw.sandbox.executor")

CONTAINER_NAME = "deskclaw-sandbox"


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    def to_output(self) -> str:
        """Format for agent consumption — mimics host exec output."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        if self.timed_out:
            parts.append("[sandbox] Command timed out")
        return "\n".join(parts) if parts else ""


@dataclass
class SandboxConfig:
    memory: str = "512m"
    cpus: int = 1
    pids_limit: int = 128
    tmp_size: str = "64m"
    network: str = "none"
    image: str = DEFAULT_IMAGE


class ContainerExecutor:
    """Manages a persistent sandbox container for isolated command execution."""

    def __init__(self, runtime: RuntimeInfo, workspace: str | None = None, config: SandboxConfig | None = None):
        self.runtime = runtime
        if workspace:
            resolved_workspace = workspace
        else:
            resolved_workspace = str(resolve_workspace_path())
        self.workspace = resolved_workspace
        self.config = config or SandboxConfig()
        self._running = False

    async def start(self) -> bool:
        """Start the sandbox container (or reuse existing one).

        Cleans up stale containers from previous sessions before creating a new one.
        """
        if self._running and await self.is_running():
            return True

        await self._cleanup_stale()

        cmd = [
            self.runtime.path, "run", "-d",
            "--name", CONTAINER_NAME,
            "-v", f"{self.workspace}:/workspace",
            "-w", "/workspace",
            f"--network={self.config.network}",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--read-only",
            f"--tmpfs=/tmp:size={self.config.tmp_size}",
            f"--memory={self.config.memory}",
            f"--cpus={self.config.cpus}",
            f"--pids-limit={self.config.pids_limit}",
            self.config.image,
            "sleep", "infinity",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0:
                self._running = True
                logger.info("Sandbox container started: %s", stdout.decode().strip()[:12])
                return True
            logger.error("Failed to start sandbox: %s", stderr.decode().strip())
            return False
        except asyncio.TimeoutError:
            logger.error("Sandbox container start timed out")
            return False
        except Exception as exc:
            logger.error("Sandbox container start error: %s", exc)
            return False

    async def exec(self, command: str, timeout: int = 60) -> ExecutionResult:
        """Execute a command inside the sandbox container."""
        if not self._running:
            started = await self.start()
            if not started:
                return ExecutionResult(
                    exit_code=-1, stdout="", stderr="[sandbox] Container unavailable",
                )

        cmd = [
            self.runtime.path, "exec",
            "-w", "/workspace",
            CONTAINER_NAME,
            "sh", "-c", command,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
            return ExecutionResult(
                exit_code=proc.returncode or 0,
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
            )
        except asyncio.TimeoutError:
            try:
                proc.terminate()
                await asyncio.sleep(2)
                proc.kill()
            except Exception:
                pass
            return ExecutionResult(
                exit_code=-1, stdout="", stderr="", timed_out=True,
            )
        except Exception as exc:
            return ExecutionResult(
                exit_code=-1, stdout="",
                stderr=f"[sandbox] Execution error: {exc}",
            )

    async def exec_with_stdin(self, command: str, stdin_data: str, timeout: int = 60) -> ExecutionResult:
        """Execute a command inside the container, piping stdin_data to it."""
        if not self._running:
            started = await self.start()
            if not started:
                return ExecutionResult(
                    exit_code=-1, stdout="", stderr="[sandbox] Container unavailable",
                )

        cmd = [
            self.runtime.path, "exec", "-i",
            "-w", "/workspace",
            CONTAINER_NAME,
            "sh", "-c", command,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(stdin_data.encode("utf-8")), timeout=timeout,
            )
            return ExecutionResult(
                exit_code=proc.returncode or 0,
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
            )
        except asyncio.TimeoutError:
            try:
                proc.terminate()
                await asyncio.sleep(2)
                proc.kill()
            except Exception:
                pass
            return ExecutionResult(exit_code=-1, stdout="", stderr="", timed_out=True)
        except Exception as exc:
            return ExecutionResult(
                exit_code=-1, stdout="",
                stderr=f"[sandbox] Execution error: {exc}",
            )

    async def is_running(self) -> bool:
        """Check if the sandbox container is currently running."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.runtime.path, "inspect", "-f", "{{.State.Running}}", CONTAINER_NAME,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            return stdout.decode().strip().lower() == "true"
        except Exception:
            return False

    async def inspect_network(self) -> str | None:
        """Return the actual network mode of the running container via docker inspect."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.runtime.path, "inspect",
                "-f", "{{.HostConfig.NetworkMode}}",
                CONTAINER_NAME,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode == 0:
                return stdout.decode().strip()
            return None
        except Exception:
            return None

    async def cleanup(self) -> None:
        """Stop and remove the sandbox container."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.runtime.path, "rm", "-f", CONTAINER_NAME,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=15)
            self._running = False
            logger.info("Sandbox container cleaned up")
        except Exception as exc:
            logger.warning("Sandbox cleanup error: %s", exc)

    async def _cleanup_stale(self) -> None:
        """Remove any leftover container from a previous session."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.runtime.path, "inspect", CONTAINER_NAME,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode == 0:
                logger.info("Cleaning up stale sandbox container")
                await self.cleanup()
        except Exception:
            pass
