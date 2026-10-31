"""Load bundled fonts privately before Tk enumerates font families."""
from functools import lru_cache
import sys

from apps.desktop.branding import ASSETS

FONT_FILES = tuple(ASSETS / "fonts" / "pretendard" / f"Pretendard-{weight}.ttf"
                   for weight in ("Regular", "Bold"))


@lru_cache(maxsize=1)
def load_bundled_fonts():
    if sys.platform == "win32":
        from apps.desktop.window.fonts import register_font
    elif sys.platform == "darwin":
        from apps.desktop.mac.fonts import register_font
    else:
        return ()
    loaded = []
    for path in FONT_FILES:
        if not path.is_file() or not register_font(path):
            raise OSError(f"Bundled font could not be loaded: {path.name}")
        loaded.append(path.name)
    return tuple(loaded)
