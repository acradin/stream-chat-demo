"""Build, verify and optionally notarize a Mac app/DMG using a Mac host."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]


def run(*command, **kwargs):
    subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sign-identity", help="Developer ID Application identity from the Mac Keychain")
    parser.add_argument("--notary-profile", help="Existing notarytool Keychain profile; no password on command line")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Build on macOS 14+ with the Mac dependencies installed.")
    if args.notary_profile and not args.sign_identity:
        parser.error("Notarization requires --sign-identity.")
    from PIL import Image
    scratch = ROOT / "build" / "mac"
    scratch.mkdir(parents=True, exist_ok=True)
    output = ROOT / "dist" / "mac"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="build-", dir=scratch) as name:
        work = Path(name)
        icon = work / "tiki.icns"
        with Image.open(ROOT / "apps/assets/app-512.png") as image:
            image.save(icon, format="ICNS")
        environment = {**os.environ, "TIKI_MAC_ICON": str(icon), "PYINSTALLER_CONFIG_DIR": str(work / "cache")}
        if args.sign_identity:
            environment["TIKI_MAC_SIGN_IDENTITY"] = args.sign_identity
        run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(work / "dist"),
            "--workpath", str(work / "work"), str(Path(__file__).with_name("desktop.spec")), env=environment)
        app = work / "dist/tiki.app"
        run(sys.executable, "-B", "apps/desktop/packaging/verify_bundle.py", str(app),
            str(work / "work/desktop/Analysis-00.toc"))
        report = work / "self-test.json"
        run(str(app / "Contents/MacOS/tiki"), "--self-test", str(report))
        if json.loads(report.read_text())["status"] != "ok":
            raise SystemExit("Packaged Mac self-test failed.")
        if args.notary_profile:
            archive = work / "tiki.zip"
            run("ditto", "-c", "-k", "--keepParent", str(app), str(archive))
            run("xcrun", "notarytool", "submit", str(archive), "--keychain-profile", args.notary_profile, "--wait")
            run("xcrun", "stapler", "staple", str(app))
        # Unique per build; never overwrite a user's existing release.
        from datetime import datetime
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        destination = output / f"tiki-0.4.0-{platform.machine()}-{stamp}.app"
        run("ditto", str(app), str(destination))
        destination.with_suffix(".self-test.json").write_bytes(report.read_bytes())
        stage = work / "dmg"
        stage.mkdir()
        run("ditto", str(app), str(stage / "tiki.app"))
        (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
        dmg = destination.with_suffix(".dmg")
        run("hdiutil", "create", "-volname", "tiki", "-srcfolder", str(stage), "-format", "UDZO", str(dmg))
        print(f"App: {destination}\nDMG: {dmg}\nNotarized: {bool(args.notary_profile)}")


if __name__ == "__main__":
    main()
