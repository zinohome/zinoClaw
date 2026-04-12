"""DeskClaw Extension Plugin System.

Each extension lives in its own directory under ``~/.deskclaw/extensions/``::

    ~/.deskclaw/extensions/<name>/
    ├── <name>.py       # Extension code
    ├── config.json     # {"enabled": true, ...}
    └── README.md       # Documentation
"""

from .base import DeskClawExtension, ExtensionContext  # noqa: F401
from .loader import DiscoveredExtension  # noqa: F401
