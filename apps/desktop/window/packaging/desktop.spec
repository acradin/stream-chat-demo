# PyInstaller only follows desktop imports. Never collect a repository directory.
from pathlib import Path
import importlib.metadata
import sys

root = Path(SPECPATH).resolve().parents[3]
data = [(str(root / "apps/assets" / name), "apps/assets")
        for name in ("logo.svg", "app.svg", "app.ico", "app-16.png", "app-32.png", "app-48.png", "app-256.png")]
data += [(str(path), "apps/assets/figma") for path in (root / "apps/assets/figma").iterdir()
         if path.suffix in (".png", ".svg")]
data += [(str(root / "apps/assets/fonts/pretendard" / name), "apps/assets/fonts/pretendard")
         for name in ("Pretendard-Regular.ttf", "Pretendard-Bold.ttf", "LICENSE.txt")]
# Retain runtime dependency notices in the distributable.
for package in ("aiohttp", "aiohappyeyeballs", "aiosignal", "attrs", "frozenlist",
                "multidict", "propcache", "yarl", "idna", "Pillow"):
    distribution = importlib.metadata.distribution(package)
    for item in distribution.files or ():
        if any(part.lower().startswith(("license", "copying", "notice")) for part in item.parts):
            source = Path(distribution.locate_file(item))
            if source.is_file():
                data.append((str(source), "licenses/" + package + "/" + str(item.parent)))
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    data.append((str(python_license), "licenses/Python"))
for package in ("tcl8.6", "tk8.6"):
    notice = Path(sys.base_prefix) / "tcl" / package / "license.terms"
    if notice.is_file():
        data.append((str(notice), "licenses/" + package))

analysis = Analysis([str(root / "apps/desktop/packaging/entry.py")], pathex=[str(root)],
                    binaries=[], datas=data, hiddenimports=[],
                    excludes=["numpy", "pytest", "backend.server", "backend.chat_service",
                              "backend.screenshot_provider", "backend.manual_provider",
                              "backend.providers", "backend.chzzk", "backend.chat_delivery", "backend.realtime_provider",
                              "backend.realtime_service", "backend.desktop_demo", "apps.web", "experiments"],
                    noarchive=False)
archive = PYZ(analysis.pure)
exe = EXE(archive, analysis.scripts, [], exclude_binaries=True, name="StreamChat",
          debug=False, strip=False, upx=False, console=False,
          version=str(root / "apps/desktop/window/packaging/version.txt"),
          icon=str(root / "apps/assets/app.ico"))
bundle = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name="StreamChat")
