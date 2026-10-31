"""Window shape and lifecycle integration selected by the host OS."""
import sys

if sys.platform == "darwin":
    from apps.desktop.mac.shell import configure_window, mapped, transparent_color
elif sys.platform.startswith("linux"):
    from apps.desktop.linux.shell import configure_window, mapped, transparent_color
else:
    from apps.desktop.window.shell import configure_window, mapped, transparent_color
