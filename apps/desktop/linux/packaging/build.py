"""Build and smoke-test a Linux archive using a native Linux display (or Xvfb)."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[4]


def main():
    if not sys.platform.startswith("linux"):
        raise SystemExit("Build on Linux or WSL; macOS bundles require macOS.")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    work = ROOT / "build/linux" / stamp
    output = ROOT / "dist/linux"
    work.mkdir(parents=True)
    output.mkdir(parents=True,exist_ok=True)
    def run(*args):
        subprocess.run(args,cwd=ROOT,check=True,env={**os.environ,"PYINSTALLER_CONFIG_DIR":str(work/"cache")})
    run(sys.executable,"-m","PyInstaller","--noconfirm","--distpath",str(work/"dist"),
        "--workpath",str(work/"work"),str(Path(__file__).with_name("desktop.spec")))
    bundle = work / "dist/tiki"
    run(sys.executable,"-B","apps/desktop/packaging/verify_bundle.py",str(bundle),str(work/"work/desktop/Analysis-00.toc"))
    report = work / "self-test.json"
    run(str(bundle/"tiki"),"--self-test",str(report))
    if json.loads(report.read_text())["status"] != "ok":
        raise SystemExit("Packaged Linux self-test failed.")
    destination = output / f"tiki-0.4.0-{platform.machine()}-{stamp}.tar.gz"
    with tarfile.open(destination,"w:gz") as archive:
        archive.add(bundle,arcname="tiki")
    destination.with_suffix(".sha256").write_text(hashlib.sha256(destination.read_bytes()).hexdigest()+"  "+destination.name+"\n")
    destination.with_suffix(".self-test.json").write_bytes(report.read_bytes())
    print(f"Linux archive: {destination}\nHost: {platform.platform()}\nExtract and run tiki/tiki.")


if __name__ == "__main__":
    main()
