"""Fail a build if it includes local config or server/provider modules."""

import ast
from pathlib import Path
import sys


def verify(bundle: Path, analysis: Path):
    if not any((bundle / name).is_file() for name in ("StreamChat.exe", "Contents/MacOS/tiki", "tiki")):
        raise ValueError("Desktop executable is missing")
    forbidden_names = {".env", "tokens.json", "settings.json", "usage.json"}
    for path in bundle.rglob("*"):
        if path.name in forbidden_names or path.name.startswith(".env."):
            raise ValueError("A private configuration file was included")
    forbidden_modules = {"backend.server", "backend.chat_service", "backend.screenshot_provider",
                         "backend.manual_provider", "backend.providers", "backend.chzzk", "backend.chzzk_cli",
                         "backend.realtime_provider", "backend.realtime_service", "backend.desktop_demo", "backend.chat_delivery"}
    def visit(value):
        # Analysis also stores the list of excluded module names. Only inspect
        # collected TOC entries: (module_name, source_path, collection_type).
        if (isinstance(value, tuple) and len(value) == 3
                and value[2] in ("PYMODULE", "PYSOURCE") and value[0] in forbidden_modules):
            raise ValueError("A backend provider module was included")
        if isinstance(value, (list, tuple)):
            for item in value:
                visit(item)
    visit(ast.literal_eval(analysis.read_text(encoding="utf-8")))


if __name__ == "__main__":
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
    print("Bundle verified: no local settings, credentials or provider modules.")
