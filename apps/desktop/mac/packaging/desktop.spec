"""Build only on macOS; retain the host architecture (arm64 or x86_64)."""
from pathlib import Path
import importlib.metadata
import os
import sys

if sys.platform != "darwin":
    raise SystemExit("The Mac application must be built on macOS.")
root = Path(SPECPATH).resolve().parents[3]
assets = root / "apps/assets"
data = [(str(assets / name), "apps/assets") for name in
        ("logo.svg", "app.svg", "app.ico", "app-16.png", "app-32.png", "app-48.png", "app-256.png", "app-512.png")]
data += [(str(path), "apps/assets/figma") for path in (assets / "figma").iterdir() if path.suffix in (".png", ".svg")]
data += [(str(assets / "fonts/pretendard" / name), "apps/assets/fonts/pretendard") for name in
         ("Pretendard-Regular.ttf", "Pretendard-Bold.ttf", "LICENSE.txt")]
for distribution in importlib.metadata.distributions():
    name = distribution.metadata["Name"]
    for item in distribution.files or ():
        if any(part.lower().startswith(("license", "copying", "notice")) for part in item.parts):
            source = Path(distribution.locate_file(item))
            if source.is_file():
                data.append((str(source), "licenses/" + name + "/" + str(item.parent)))
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    data.append((str(python_license), "licenses/Python"))
analysis = Analysis([str(root / "apps/desktop/packaging/entry.py")], pathex=[str(root)],
    binaries=[], datas=data, hiddenimports=["ScreenCaptureKit", "Quartz", "CoreText", "AppKit", "Foundation", "HIServices"],
    excludes=["numpy", "pytest", "backend.server", "backend.chat_service", "backend.screenshot_provider",
              "backend.manual_provider", "backend.providers", "backend.chzzk", "backend.chat_delivery",
              "backend.realtime_provider", "backend.realtime_service", "backend.desktop_demo", "apps.web", "experiments"],
    noarchive=False)
archive = PYZ(analysis.pure)
exe = EXE(archive, analysis.scripts, [], exclude_binaries=True, name="tiki", debug=False,
          strip=False, upx=False, console=False, argv_emulation=False,
          codesign_identity=os.environ.get("TIKI_MAC_SIGN_IDENTITY"),
          entitlements_file=str(Path(SPECPATH) / "entitlements.plist"))
collected = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name="tiki")
app = BUNDLE(collected, name="tiki.app", icon=os.environ["TIKI_MAC_ICON"],
    bundle_identifier="com.tiki.streamchat", info_plist={
        "CFBundleDisplayName": "tiki", "CFBundleShortVersionString": "0.4.0", "CFBundleVersion": "0.4.0",
        "LSMinimumSystemVersion": "14.0", "NSHighResolutionCapable": True,
        "NSScreenCaptureUsageDescription": "선택한 방송 화면을 분석하여 AI 채팅을 생성합니다.",
        "NSAccessibilityUsageDescription": "다른 앱을 사용하는 동안에도 지정한 채팅 생성 단축키에 반응합니다."
    })
