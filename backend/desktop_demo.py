"""Operator-only source launcher: local backend + native desktop, without a browser."""

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import tkinter as tk
from tkinter import messagebox
from urllib.parse import urlsplit

# Taskbar shortcuts use an absolute script path, independent of their working directory.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.env import BACKEND_KEYS, DESKTOP_KEYS, read_env_file
from apps.desktop.service_client import ServiceClient
from apps.desktop.branding import apply_window_icon, set_app_identity

ROOT = Path(__file__).resolve().parents[1]


def desktop_environment(connection):
    # The operator launcher must not pass provider credentials to the desktop child.
    environment = {key: value for key, value in os.environ.items() if key not in BACKEND_KEYS}
    environment.update(connection)
    return environment


def ensure_service(client):
    parts = urlsplit(client.base_url)
    if parts.hostname not in ("127.0.0.1", "localhost") or parts.port != 8766:
        return
    try:
        with socket.create_connection((parts.hostname, 8766), timeout=.5):
            return  # Leave an existing service/process untouched.
    except OSError:
        pass
    log_dir = ROOT / "runs" / "service"
    log_dir.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (log_dir / "startup.log").open("ab") as log:
        process = subprocess.Popen([sys.executable, "-B", "-m", "backend.server"], cwd=ROOT,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=flags)
    for _ in range(40):
        if process.poll() is not None:
            raise ValueError("서비스를 시작하지 못했습니다. backend/.env 설정을 확인해주세요.")
        try:
            with socket.create_connection((parts.hostname, 8766), timeout=.2):
                return
        except OSError:
            time.sleep(.1)
    raise ValueError("서비스 시작 시간이 초과됐습니다. runs/service/startup.log를 확인해주세요.")


def main():
    set_app_identity()
    try:
        connection = read_env_file(ROOT / "apps/desktop/.env", DESKTOP_KEYS)
        for key in DESKTOP_KEYS:
            if key in os.environ:
                connection[key] = os.environ[key]
        client = ServiceClient(base_url=connection.get("CHAT_SERVICE_URL"), token=connection.get("CHAT_SERVICE_TOKEN"))
        if not client.configured:
            raise ValueError("apps/desktop/.env에 서비스 연결 정보를 설정해주세요.")
        ensure_service(client)
        asyncio.run(client.refresh_usage())  # Verify readiness/auth without any paid AI call.
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        subprocess.Popen([sys.executable, "-B", "-m", "apps.desktop"], cwd=ROOT,
                         env=desktop_environment(connection), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        return 0
    except (OSError, ValueError):
        root = tk.Tk()
        root.withdraw()
        apply_window_icon(root)
        messagebox.showerror("Stream Chat 시작 확인", "서비스 연결을 준비하지 못했습니다.\nbackend/.env와 apps/desktop/.env 설정을 확인해주세요.\n자세한 실행 방법은 DESKTOP.md에 있습니다.", parent=root)
        root.destroy()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
