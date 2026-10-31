"""Offline packaged-runtime check: hidden window, no screen capture or network."""

import json
import asyncio
from pathlib import Path
import ssl
import sys
import tempfile
import time
import tkinter as tk

from PIL import Image

from backend.storage import atomic_json


def run(report_path: Path) -> int:
    from apps.desktop.overlay import Overlay
    from apps.desktop.paths import state_directory
    from apps.desktop.capture import WindowSource

    class OfflineService:
        def __init__(self):
            import threading
            self.stop_requested = threading.Event()
            self.manual_calls = self.live_calls = 0

        def usage(self):
            return {"period": "2026-10", "timezone": "Asia/Seoul", "is_demo": True,
                    "generation_requests": 0, "generated_chats": 0, "total_generated_chats": 0}

        async def refresh_usage(self):
            return self.usage()

        async def generate(self, personas, context, *, screenshot, on_line):
            self.manual_calls += 1
            line = {"participant": 1, "persona": personas[0], "status": "ready", "comment": "버튼 테스트", "error": ""}
            on_line(line)
            return {"status": "complete", "lines": [line]}

        async def realtime(self, personas, context, *, capture, stop_event, on_event, **settings):
            self.live_calls += 1
            capture()
            on_event({"type": "ready"})
            on_event({"type": "decision", "result": "chat", "participant": 1, "persona": personas[0],
                      "comment": "실시간 테스트", "decisions": 1, "chats": 1})
            while not stop_event.is_set() and not self.stop_requested.is_set():
                await asyncio.sleep(.01)

    root = None
    try:
        ssl.create_default_context()
        with Image.new("RGB", (2, 2)) as image:
            import io
            image.save(io.BytesIO(), format="JPEG")
        with tempfile.TemporaryDirectory(prefix="streamchat-check-") as directory:
            root = tk.Tk()
            root.withdraw()
            source = WindowSource(123, 456, "Synthetic window")
            service = OfflineService()
            app = Overlay(root, Path(directory), service=service, enable_hotkey=False,
                          capture=lambda: b"synthetic", window_list=lambda: [source],
                          window_capture=lambda selected: b"synthetic" if selected == source else None)
            app._restore_window = lambda: None  # Remain hidden through both flows.
            def pump_until(condition):
                deadline = time.monotonic() + 3
                while not condition():
                    root.update()
                    if time.monotonic() > deadline:
                        raise ValueError("Overlay lifecycle timed out")
                    time.sleep(.01)
            app.generate()
            pump_until(lambda: not app.busy)
            if service.manual_calls != 1 or "버튼 테스트" not in app.chat_log.get("1.0", "end"):
                raise ValueError("Manual mode failed")
            app.mode_var.set("실시간 화면 모드")
            app._mode_changed()
            app.source_selector.current(0)
            app.generate()
            pump_until(lambda: "실시간 테스트" in app.chat_log.get("1.0", "end"))
            if not app.live_running or str(app.mode_selector.cget("state")) != "disabled":
                raise ValueError("Realtime controls failed")
            app.stop_live()
            pump_until(lambda: not app.busy)
            # A stopped live session must not poison manual mode or the next live session.
            app.generate()
            pump_until(lambda: service.live_calls == 2)
            app.stop_live()
            pump_until(lambda: not app.busy)
            app.mode_var.set("버튼 캡처 모드")
            app._mode_changed()
            app.next_trigger = 0
            app.generate()
            pump_until(lambda: not app.busy)
            if service.manual_calls != 2 or service.stop_requested.is_set() or not root.attributes("-topmost"):
                raise ValueError("Mode switching or topmost failed")
            app.close()
            root = None
            settings = json.loads((Path(directory) / "settings.json").read_text(encoding="utf-8"))
            if settings["count"] != 1:
                raise ValueError("Unexpected default settings")
        atomic_json(report_path, {"status": "ok", "frozen": bool(getattr(sys, "frozen", False)),
                                  "python": sys.version.split()[0], "tk": tk.TkVersion,
                                  "state_directory": str(state_directory()),
                                  "checks": ["tls", "jpeg", "hidden_overlay", "topmost", "manual_generation",
                                             "realtime_start_stop_restart", "mode_switch", "settings_save"],
                                  "network_calls": 0, "screenshots": 0})
        return 0
    except Exception as exc:
        atomic_json(report_path, {"status": "failed", "error_type": type(exc).__name__, "message": str(exc)})
        return 1
    finally:
        if root is not None:
            root.destroy()
