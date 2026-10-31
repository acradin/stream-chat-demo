"""Native Linux bundle; build on the oldest supported Linux distribution."""
from pathlib import Path
import sys

if not sys.platform.startswith("linux"):
    raise SystemExit("Build the Linux app on Linux, including WSL.")
root = Path(SPECPATH).resolve().parents[3]
assets = root / "apps/assets"
data = [(str(path), "apps/assets/" + path.parent.relative_to(assets).as_posix())
        for path in assets.rglob("*") if path.is_file() and
        (path.suffix in {".svg", ".png", ".ico", ".ttf"} or path.name == "LICENSE.txt")]
import importlib.metadata
for distribution in importlib.metadata.distributions():
    for item in distribution.files or ():
        if any(part.lower().startswith(("license", "copying", "notice")) for part in item.parts):
            source = Path(distribution.locate_file(item))
            if source.is_file():
                data.append((str(source), "licenses/" + distribution.metadata["Name"] + "/" + str(item.parent)))
from ctypes.util import find_library
from PyInstaller.depend.bindepend import resolve_library_path
libraries = []
for name in ("X11", "Xcomposite", "Xext", "fontconfig"):
    library = resolve_library_path(find_library(name) or name)
    if not library:
        raise SystemExit("Install Linux runtime library: " + name)
    libraries.append((library,"."))
analysis = Analysis([str(root / "apps/desktop/packaging/entry.py")], pathex=[str(root)],
    binaries=libraries, datas=data, hiddenimports=["PIL._tkinter_finder"],
    excludes=["numpy", "pytest", "AppKit", "Quartz", "ScreenCaptureKit", "CoreText", "HIServices",
              "backend.server", "backend.chat_service", "backend.screenshot_provider", "backend.manual_provider",
              "backend.providers", "backend.chzzk", "backend.chat_delivery", "backend.public_web",
              "backend.realtime_provider", "backend.realtime_service", "backend.desktop_demo", "apps.web", "experiments"],
    noarchive=False)
archive = PYZ(analysis.pure)
exe = EXE(archive, analysis.scripts, [], exclude_binaries=True, name="tiki", debug=False,
          strip=False, upx=False, console=False)
bundle = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name="tiki")
