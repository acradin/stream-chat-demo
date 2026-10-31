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


def check_taskbar_identity(root):
    if sys.platform != "win32":
        return
    import ctypes
    from apps.desktop.window.branding import APP_ID, ASSETS, _PropertyKey, _PropVariant, _window_property_store
    hwnd = int(root.wm_frame(), 0)
    send = ctypes.WinDLL("user32").SendMessageW
    send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
    send.restype = ctypes.c_ssize_t
    # WM_GETICON must return explicit caption/Alt+Tab icons, not Python's class fallback.
    if not all(send(hwnd, 0x007F, size, 0) for size in (0, 1)):
        raise ValueError("The title bar or Alt+Tab window icon is missing")
    clear = ctypes.WinDLL("ole32").PropVariantClear
    clear.argtypes, clear.restype = [ctypes.POINTER(_PropVariant)], ctypes.c_long
    with _window_property_store(hwnd) as (store, table):
        get_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
            ctypes.POINTER(_PropertyKey), ctypes.POINTER(_PropVariant))(table[5])
        values = {}
        for property_id in (2, 3, 4, 5):
            value = _PropVariant()
            try:
                if get_value(store, ctypes.byref(_PropertyKey(property_id)), ctypes.byref(value)) < 0 or value.vt != 31:
                    raise ValueError("Windows taskbar branding is missing")
                values[property_id] = ctypes.wstring_at(value.value)
            finally:
                clear(ctypes.byref(value))
    if values[3] != str(ASSETS / "app.ico") + ",0" or values[4] != "Stream Chat" or values[5] != APP_ID:
        raise ValueError("Windows taskbar identity does not match the app")
    if not values[2] or (not getattr(sys, "frozen", False) and "desktop_demo.py" not in values[2]):
        raise ValueError("Taskbar relaunch command is missing")


def run(report_path: Path) -> int:
    from apps.desktop.overlay import Overlay
    from apps.desktop.paths import state_directory
    from apps.desktop.capture import WindowSource
    from apps.desktop.branding import ASSETS

    class OfflineService:
        def __init__(self):
            import threading
            self.stop_requested = threading.Event()
            self.manual_calls = self.live_calls = 0
            self.outputs = []

        def usage(self):
            return {"period": "2026-10", "timezone": "Asia/Seoul", "is_demo": True,
                    "generation_requests": 0, "generated_chats": 0, "total_generated_chats": 0}

        async def refresh_usage(self):
            return self.usage()

        async def chzzk_status(self):
            return {"connected": True, "channelId": "b" * 32, "channelName": "테스트 방송", "message": "connected"}

        async def generate(self, personas, context, *, screenshot, on_line, **settings):
            self.manual_calls += 1
            self.outputs.append(settings.get("destination", "app"))
            line = {"participant": 1, "persona": personas[0], "status": "ready", "comment": "버튼 테스트", "error": ""}
            if settings.get("destination") == "chzzk":
                if settings.get("channel_id") != "b" * 32:
                    raise ValueError("Channel link was not extracted")
                line["delivery"] = {"status": "sent", "message": "모의 전송 완료", "messageId": "synthetic"}
            on_line(line)
            return {"status": "complete", "lines": [line]}

        async def realtime(self, personas, context, *, capture, stop_event, on_event, **settings):
            self.live_calls += 1
            self.outputs.append(settings.get("destination", "app"))
            capture()
            on_event({"type": "ready"})
            on_event({"type": "decision", "result": "chat", "participant": 1, "persona": personas[0],
                      "comment": "실시간 테스트", "decisions": 1, "chats": 1})
            if settings.get("destination") == "chzzk":
                on_event({"type": "delivery", "participant": 1, "persona": personas[0],
                          "delivery": {"status": "sent", "message": "실시간 모의 전송 완료", "messageId": "synthetic"}})
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
            from apps.desktop.fonts import load_bundled_fonts
            from tkinter import font
            if len(load_bundled_fonts()) != 3 or app.view.family != "Pretendard":
                raise ValueError("Bundled Pretendard fonts did not load")
            for weight in ("normal", "bold"):
                resolved = font.Font(root=root, family=app.view.family, size=9, weight=weight).actual()
                if resolved["family"] != "Pretendard" or resolved["weight"] != weight:
                    raise ValueError("Pretendard resolved to a fallback font")
            if "SIL OPEN FONT LICENSE" not in (ASSETS / "fonts/pretendard/LICENSE.txt").read_text(encoding="utf-8"):
                raise ValueError("Bundled font license is missing")
            if tuple(image.width() for image in root._brand_icons) != (16, 32, 48, 256):
                raise ValueError("Desktop branding images did not load")
            with Image.open(ASSETS / "app.ico") as icon:
                if not {(16, 16), (32, 32), (48, 48), (256, 256)} <= icon.ico.sizes():
                    raise ValueError("Desktop icon sizes are missing")
            if "<svg" not in (ASSETS / "logo.svg").read_text(encoding="utf-8"):
                raise ValueError("Original SVG is missing from the distribution")
            check_taskbar_identity(root)
            if app.view.current != "start":
                raise ValueError("A new installation did not open the welcome screen")
            wizard = app.view.onboarding
            wizard.to_personas()
            wizard.to_link()
            wizard.finish()
            if not app.settings["onboarding_complete"] or app.view.current != "start_end":
                raise ValueError("Onboarding did not save without a broadcast link")
            app.view.show("main")
            if app.view.current != "main" or app.view.main.background_owner != "Screen/Main":
                raise ValueError("Figma main panel was not installed")
            if app.view.settings.background_owner != "Fill + Shadow":
                raise ValueError("Settings background was duplicated on its root")
            if root.attributes("-alpha") != 1.0:
                raise ValueError("Panel paint opacity leaked into window/content opacity")
            for page in ("start", "start1", "start2", "start3", "start_end", "settings", "controls", "chat", "main"):
                app.view.show(page)
                root.update_idletasks()
                if app.view.current != page:
                    raise ValueError("Desktop page navigation failed")
            app.view._count_changed(5)
            if len([row for row in app.persona_rows if row.winfo_manager() == "pack"]) != 5:
                raise ValueError("Member slider did not reveal all persona controls")
            app.view._count_changed(1)
            if app.channel_controls.winfo_manager() != "pack":
                raise ValueError("Broadcast link input is hidden in local mode")
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
            if sys.platform.startswith("linux"):
                # X11 acknowledges topmost only on mapped, WM-managed windows.
                root.attributes("-alpha",0)
                root.deiconify()
                pump_until(lambda: bool(root.attributes("-topmost")))
            if service.manual_calls != 2 or service.stop_requested.is_set() or not root.attributes("-topmost"):
                raise ValueError("Mode switching or topmost failed")
            if sys.platform.startswith("linux"):
                root.withdraw()
            app.channel_var.set("https://chzzk.naver.com/live/" + "B" * 32 + "?share=1")
            app.destination_var.set("치지직에도 전송")
            app._destination_changed()
            pump_until(lambda: app.connected_channel is not None)
            app.next_trigger = 0
            app.generate()
            pump_until(lambda: not app.busy)
            if service.outputs[-1] != "chzzk" or "모의 전송 완료" not in app.chat_log.get("1.0", "end"):
                raise ValueError("Manual delivery switch failed")
            app.mode_var.set("실시간 화면 모드")
            app._mode_changed()
            app.source_selector.current(0)
            app.generate()
            pump_until(lambda: "실시간 모의 전송 완료" in app.chat_log.get("1.0", "end"))
            if service.outputs[-1] != "chzzk" or str(app.destination_selector.cget("state")) != "disabled":
                raise ValueError("Realtime delivery switch failed")
            app.stop_live()
            pump_until(lambda: not app.busy)
            app.destination_var.set("앱에만 표시 (시연)")
            app._destination_changed()
            app.connected_channel = None  # Local display does not require CHZZK authorization.
            app.mode_var.set("버튼 캡처 모드")
            app._mode_changed()
            app.next_trigger = 0
            app.generate()
            pump_until(lambda: not app.busy)
            if service.outputs[-1] != "app":
                raise ValueError("Switching back to local display failed")
            if app.channel_controls.winfo_manager() != "pack" or "현재는 앱에만" not in app.channel_info.get():
                raise ValueError("Broadcast link or local-mode explanation disappeared")
            app.hotkey_var.set("shift + control + f8")
            app.save_settings()
            if app.settings["hotkey"] != "Ctrl+Shift+F8":
                raise ValueError("Custom hotkey was not saved")
            app.hotkey_var.set("Ctrl+unknown")
            app.save_settings()
            if app.settings["hotkey"] != "Ctrl+Shift+F8":
                raise ValueError("Invalid hotkey replaced the saved setting")
            app.record_hotkey()
            calls = service.manual_calls
            app.generate()
            if service.manual_calls != calls:
                raise ValueError("Recording a hotkey triggered generation")
            app._finish_hotkey_recording()
            app.close()
            root = None
            settings = json.loads((Path(directory) / "settings.json").read_text(encoding="utf-8"))
            if settings["count"] != 1 or settings["hotkey"] != "Ctrl+Shift+F8":
                raise ValueError("Unexpected default settings")
        atomic_json(report_path, {"status": "ok", "frozen": bool(getattr(sys, "frozen", False)),
                                  "python": sys.version.split()[0], "tk": tk.TkVersion,
                                  "state_directory": str(state_directory()),
                                  "checks": ["tls", "jpeg", "bundled_pretendard_regular_semibold_bold", "font_license", "app_icons", "bundled_original_svg", "figma_panels", "onboarding_without_broadcast_link", "page_navigation", "member_slider", "content_opacity", "hidden_overlay", "topmost", "manual_generation",
                                             "realtime_start_stop_restart", "mode_switch", "output_switch",
                                             "channel_link_extraction", "broadcast_link_always_visible", "custom_hotkey", "settings_save"]
                                            + (["titlebar_icon", "taskbar_identity"] if sys.platform == "win32" else []),
                                  "network_calls": 0, "screenshots": 0})
        return 0
    except Exception as exc:
        atomic_json(report_path, {"status": "failed", "error_type": type(exc).__name__, "message": str(exc)})
        return 1
    finally:
        if root is not None:
            root.destroy()
