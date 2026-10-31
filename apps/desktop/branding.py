"""Shared assets with platform-specific window branding."""
from pathlib import Path
import sys

ASSETS = Path(__file__).resolve().parents[1] / "assets"
APP_ID = "StreamChat.Desktop"

if sys.platform == "darwin":
    from apps.desktop.mac.branding import apply_window_icon, set_app_identity
else:
    from apps.desktop.window.branding import apply_window_icon, set_app_identity
