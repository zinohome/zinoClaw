"""Container sandbox subsystem — runtime detection, image management, and execution."""

from .runtime import detect_runtime, RuntimeInfo, pull_image, image_exists, ensure_runtime_ready
from .executor import ContainerExecutor, ExecutionResult

__all__ = [
    "detect_runtime",
    "RuntimeInfo",
    "pull_image",
    "image_exists",
    "ensure_runtime_ready",
    "ContainerExecutor",
    "ExecutionResult",
]
