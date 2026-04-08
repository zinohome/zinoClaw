"""Container runtime detection and image management.

Supports Docker, Podman, and nerdctl with automatic priority-based detection.
Images are distributed as OCI tar archives from object storage, not a registry.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import platform
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("deskclaw.sandbox.runtime")

RUNTIMES: list[tuple[str, list[str]]] = [
    ("docker", ["docker", "--version"]),
    ("podman", ["podman", "--version"]),
    ("nerdctl", ["nerdctl", "--version"]),
]

_VERSION_RE = __import__("re").compile(r"(\d+\.\d+[\.\d]*)")


DEFAULT_IMAGE = "deskclaw-sandbox:1.1.0-alpine"

_BUILTIN_MANIFEST = Path(__file__).parent / "image" / "sandbox-images.json"

CACHE_DIR = Path.home() / ".deskclaw" / "sandbox-cache"


@dataclass
class RuntimeInfo:
    name: str  # docker | podman | nerdctl
    version: str
    path: str  # absolute path to binary

    def to_dict(self) -> dict:
        return {"name": self.name, "version": self.version, "path": self.path}


def _parse_version(output: str) -> str:
    """Extract a semver-like version from ``--version`` output."""
    m = _VERSION_RE.search(output)
    return m.group(1) if m else output.strip()


def detect_runtime() -> RuntimeInfo | None:
    """Synchronously detect the first available container runtime."""
    for name, cmd in RUNTIMES:
        bin_path = shutil.which(name)
        if not bin_path:
            logger.debug("Runtime %s binary not in PATH: %s", name, os.environ.get("PATH", ""))
            continue
        try:
            import subprocess
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                version = _parse_version(result.stdout)
                logger.info("Detected runtime: %s %s at %s", name, version, bin_path)
                return RuntimeInfo(name=name, version=version, path=bin_path)
            logger.debug("Runtime %s version cmd failed (rc=%d): %s", name, result.returncode, result.stderr.strip())
        except Exception as exc:
            logger.debug("Runtime %s detection failed: %s", name, exc)
    return None


async def detect_runtime_async() -> RuntimeInfo | None:
    """Async variant of detect_runtime for use in event loops."""
    for name, cmd in RUNTIMES:
        bin_path = shutil.which(name)
        if not bin_path:
            logger.debug("Runtime %s binary not in PATH: %s", name, os.environ.get("PATH", ""))
            continue
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode == 0:
                version = _parse_version(stdout.decode())
                logger.info("Detected runtime: %s %s at %s", name, version, bin_path)
                return RuntimeInfo(name=name, version=version, path=bin_path)
            logger.debug("Runtime %s version cmd failed (rc=%d): %s", name, proc.returncode, stderr.decode().strip())
        except Exception as exc:
            logger.debug("Runtime %s async detection failed: %s", name, exc)
    return None


def image_exists(runtime: RuntimeInfo, tag: str = DEFAULT_IMAGE) -> bool:
    """Check whether the sandbox image is available locally."""
    import subprocess
    try:
        result = subprocess.run(
            [runtime.path, "image", "inspect", tag],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            logger.warning(
                "image inspect failed (rc=%d): %s",
                result.returncode, result.stderr.strip(),
            )
        return result.returncode == 0
    except Exception as exc:
        logger.warning("image_exists check error: %s", exc)
        return False


async def pull_image(
    runtime: RuntimeInfo,
    tar_path: str | Path,
    tag: str = DEFAULT_IMAGE,
) -> bool:
    """Load a sandbox image from an OCI tar archive.

    Returns True on success.  The tar file should be pre-downloaded by the
    shell layer and passed here by absolute path.
    """
    tar_path = str(tar_path)
    try:
        proc = await asyncio.create_subprocess_exec(
            runtime.path, "load", "-i", tar_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode == 0:
            out = stdout.decode().strip()
            logger.info("Loaded image from %s: %s", tar_path, out)
            await _retag_if_needed(runtime, out, tag)
            return True
        logger.error("Image load failed: %s", stderr.decode().strip())
        return False
    except asyncio.TimeoutError:
        logger.error("Image load timed out for %s", tar_path)
        return False
    except Exception as exc:
        logger.error("Image load error: %s", exc)
        return False


_LOADED_IMAGE_RE = __import__("re").compile(r"Loaded image:\s*(.+)")


async def _retag_if_needed(
    runtime: RuntimeInfo, load_output: str, expected_tag: str,
) -> None:
    """Re-tag the loaded image to expected_tag if the tar embedded a different name.

    Docker load prints "Loaded image: <repo>:<tag>".  If that differs from
    expected_tag (e.g. arch-suffixed "...-amd64" vs plain), we docker-tag it
    so image_exists() can find it by the canonical name.
    """
    m = _LOADED_IMAGE_RE.search(load_output)
    if not m:
        return
    actual_tag = m.group(1).strip()
    if actual_tag == expected_tag:
        return
    logger.info("Re-tagging %s → %s", actual_tag, expected_tag)
    try:
        proc = await asyncio.create_subprocess_exec(
            runtime.path, "tag", actual_tag, expected_tag,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode != 0:
            logger.warning("Re-tag failed: %s", stderr.decode().strip())
    except Exception as exc:
        logger.warning("Re-tag error: %s", exc)


def remove_image(runtime: RuntimeInfo, tag: str = DEFAULT_IMAGE) -> bool:
    """Remove the sandbox image."""
    import subprocess
    try:
        result = subprocess.run(
            [runtime.path, "rmi", "-f", tag],
            capture_output=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def _docker_daemon_running_sync(runtime: RuntimeInfo) -> bool:
    """Check if Docker daemon is reachable (Docker Desktop must be running)."""
    import subprocess
    try:
        result = subprocess.run(
            [runtime.path, "info"],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_status(runtime: RuntimeInfo | None, tag: str = DEFAULT_IMAGE) -> dict:
    """Build a status dict suitable for IPC responses."""
    if runtime is None:
        return {
            "runtime_available": False,
            "runtime": None,
            "image_ready": False,
            "image_tag": tag,
        }
    status = {
        "runtime_available": True,
        "runtime": runtime.to_dict(),
        "image_ready": image_exists(runtime, tag),
        "image_tag": tag,
    }
    if runtime.name == "podman" and platform.system() != "Linux":
        status["needs_machine"] = True
        status["machine_running"] = _podman_machine_running_sync(runtime)
    elif runtime.name == "docker":
        status["daemon_running"] = _docker_daemon_running_sync(runtime)
    return status


# ── Podman Machine management (Windows / macOS) ──


def _podman_machine_running_sync(runtime: RuntimeInfo) -> bool:
    """Synchronously check if any Podman machine is running."""
    import subprocess
    try:
        result = subprocess.run(
            [runtime.path, "machine", "list", "--format", "json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            machines = json.loads(result.stdout)
            return any(m.get("Running", False) for m in machines)
    except Exception:
        pass
    return False


async def _podman_machine_list(runtime: RuntimeInfo) -> list[dict]:
    """List Podman machines as parsed JSON."""
    try:
        proc = await asyncio.create_subprocess_exec(
            runtime.path, "machine", "list", "--format", "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode == 0 and stdout.strip():
            return json.loads(stdout.decode())
    except Exception:
        pass
    return []


async def ensure_runtime_ready(runtime: RuntimeInfo) -> tuple[bool, str]:
    """Ensure the container runtime is ready for operations.

    For Podman on Windows/macOS, this means the Podman Machine must be
    initialized and running. For Docker, it checks daemon connectivity.
    On Linux, runtimes run natively and this is effectively a no-op.

    Returns (ok, error_message).
    """
    if platform.system() == "Linux":
        return True, ""

    if runtime.name == "podman":
        return await _ensure_podman_machine(runtime)

    if runtime.name == "docker":
        return await _check_docker_daemon(runtime)

    return True, ""


async def _check_docker_daemon(runtime: RuntimeInfo) -> tuple[bool, str]:
    """Verify Docker daemon is reachable (Docker Desktop must be running)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            runtime.path, "info",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode == 0:
            return True, ""
        msg = stderr.decode().strip()
        logger.warning("Docker daemon not reachable: %s", msg)
        return False, (
            "Docker is installed but the daemon is not running. "
            "Please start Docker Desktop and try again."
        )
    except asyncio.TimeoutError:
        return False, "Docker info timed out — daemon may be unresponsive"
    except Exception as exc:
        return False, f"Docker connectivity check failed: {exc}"


async def _ensure_podman_machine(runtime: RuntimeInfo) -> tuple[bool, str]:
    """Start an existing Podman Machine if needed.

    Does NOT auto-init — that downloads a ~300MB VM image and is too heavy
    to run silently inside an HTTP request. Users must run
    ``podman machine init`` themselves first.
    """
    machines = await _podman_machine_list(runtime)

    if not machines:
        return False, (
            "Podman Machine not initialized. "
            "Please run 'podman machine init' in a terminal first, "
            "then try again."
        )

    if any(m.get("Running", False) for m in machines):
        return True, ""

    name = machines[0]["Name"] if machines else "podman-machine-default"
    logger.info("Starting Podman machine '%s'...", name)
    try:
        proc = await asyncio.create_subprocess_exec(
            runtime.path, "machine", "start", name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode != 0:
            msg = stderr.decode().strip()
            logger.error("podman machine start failed: %s", msg)
            return False, f"Podman machine start failed: {msg}"
        logger.info("Podman machine '%s' started", name)
        return True, ""
    except asyncio.TimeoutError:
        return False, "Podman machine start timed out (2 min limit)"
    except Exception as exc:
        return False, f"Podman machine start error: {exc}"


# ── Image download + load ──


def _get_arch_key() -> str:
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    if machine in ("aarch64", "arm64"):
        return "arm64"
    return machine


def _detect_region() -> str:
    """Read region from Electron Store settings, fallback to 'global'."""
    settings_path = Path.home() / ".deskclaw" / "deskclaw-settings.json"
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        region = data.get("settings", {}).get("region", "")
        if region == "china":
            return "china"
    except Exception:
        pass
    return "global"


def _load_manifest() -> dict:
    """Load the image manifest from the bundled JSON file."""
    try:
        return json.loads(_BUILTIN_MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load image manifest: %s", exc)
        return {}


def resolve_download_url(variant: str = "alpine") -> tuple[str, str, float]:
    """Resolve the download URL for the current arch and region.

    Returns (url, tag, size_mb).
    """
    manifest = _load_manifest()
    images = manifest.get("images", {})
    entry = images.get(variant)
    if not entry:
        raise ValueError(f"Unknown image variant: {variant}")

    arch = _get_arch_key()
    region = _detect_region()
    urls = entry.get("urls", {})
    region_urls = urls.get(region) or urls.get("global", {})
    url = region_urls.get(arch)
    if not url:
        raise ValueError(f"No URL for {variant}/{region}/{arch}")

    return url, entry["tag"], entry.get("size_mb", 0)


async def download_and_load(
    runtime: RuntimeInfo,
    variant: str = "alpine",
    progress_cb=None,
) -> bool:
    """Download the sandbox image tar from object storage and load it.

    Uses stdlib urllib to avoid extra dependencies.

    Args:
        runtime: Detected container runtime.
        variant: "alpine" or "busybox".
        progress_cb: Optional async callback(downloaded_bytes, total_bytes).

    Returns True on success.
    """
    ready, err = await ensure_runtime_ready(runtime)
    if not ready:
        logger.error("Runtime not ready: %s", err)
        raise RuntimeError(err)

    from urllib.request import urlopen, Request

    url, tag, _ = resolve_download_url(variant)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    filename = url.rsplit("/", 1)[-1]
    tar_path = CACHE_DIR / filename

    logger.info("Downloading sandbox image: %s → %s", url, tar_path)

    def _download() -> int:
        import ssl
        req = Request(url, headers={"User-Agent": "DeskClaw-Sandbox/1.0"})
        ctx = None
        if platform.system() == "Windows":
            try:
                ctx = ssl.create_default_context()
            except Exception:
                ctx = ssl._create_unverified_context()
        try:
            resp_cm = urlopen(req, timeout=600, context=ctx)
        except Exception:
            ctx = ssl._create_unverified_context()
            resp_cm = urlopen(req, timeout=600, context=ctx)
        with resp_cm as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tar_path, "wb") as f:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
            return downloaded

    try:
        loop = asyncio.get_running_loop()
        downloaded = await loop.run_in_executor(None, _download)
        logger.info("Download complete: %s (%d bytes)", tar_path, downloaded)
    except Exception as exc:
        logger.error("Download error: %s", exc)
        tar_path.unlink(missing_ok=True)
        return False

    ok = await pull_image(runtime, tar_path, tag)

    tar_path.unlink(missing_ok=True)
    return ok
