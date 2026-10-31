"""Installed apps keep writable data outside their bundled program files."""

import os
from pathlib import Path
import sys


def installed() -> bool:
    return bool(getattr(sys, "frozen", False))


def state_directory() -> Path:
    if installed():
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "tiki" / "desktop"
        if sys.platform.startswith("linux"):
            return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "tiki/desktop"
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "StreamChat" / "desktop"
    return Path(__file__).resolve().parents[2] / "runs" / "desktop"


def connection_file() -> Path:
    if installed():
        return state_directory() / ".env"
    return Path(__file__).resolve().parent / ".env"
