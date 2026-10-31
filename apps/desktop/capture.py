"""Shared capture interface; each OS owns its native implementation."""
import sys

from apps.desktop.capture_types import WindowSource

if sys.platform == "darwin":
    from apps.desktop.mac.capture import capture_primary_screen, capture_window, list_windows
else:
    from apps.desktop.window.capture import capture_primary_screen, capture_window, list_windows
