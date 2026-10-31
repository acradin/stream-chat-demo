"""Shared shortcut interface with OS-specific key codes and registration."""
import sys

if sys.platform == "darwin":
    from apps.desktop.mac.hotkey import GlobalHotkey, SingleInstance, parse_hotkey, pressed_hotkey
elif sys.platform.startswith("linux"):
    from apps.desktop.linux.hotkey import GlobalHotkey, SingleInstance, parse_hotkey, pressed_hotkey
else:
    from apps.desktop.window.hotkey import GlobalHotkey, SingleInstance, parse_hotkey, pressed_hotkey
