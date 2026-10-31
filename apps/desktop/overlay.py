"""Small replaceable Tk overlay: screenshot -> service -> Korean AI chat."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from apps.desktop.hotkey import GlobalHotkey, SingleInstance, parse_hotkey, pressed_hotkey
from apps.desktop.service_client import DESKTOP_ENV, ServiceClient
from apps.desktop.paths import state_directory
from apps.desktop.connection import ConnectionDialog
from apps.desktop.branding import apply_window_icon, set_app_identity
from backend.chzzk_target import parse_channel_id
from backend.storage import atomic_json
from backend.personas import DEFAULT_PERSONA, PERSONAS
from apps.desktop.capture import capture_primary_screen, capture_window, list_windows


MAX_PARTICIPANTS = 5
DEFAULT_SETTINGS = {"count": 1,
                    "personas": [DEFAULT_PERSONA, "warm_supporter", "hype_commentator", "dry_comic", DEFAULT_PERSONA],
                    "context": "", "hotkey": "Ctrl+Alt+Space", "topmost": True, "opacity": 1.0,
                    "mode": "manual", "interval": 5, "duration": 60,
                    "destination": "app", "channel_url": "", "onboarding_complete": False}
MODES = {"버튼 캡처 모드": "manual", "실시간 화면 모드": "realtime"}
DESTINATIONS = {"앱에만 표시 (시연)": "app", "치지직에도 전송": "chzzk"}


def clean_settings(data: dict) -> dict:
    """Explicit allowlist: API keys can never enter the saved settings object."""
    result = {**DEFAULT_SETTINGS, "personas": list(DEFAULT_SETTINGS["personas"])}
    if not isinstance(data, dict):
        raise ValueError("설정 파일 형식이 올바르지 않습니다.")
    if type(data.get("count")) is int and 1 <= data["count"] <= MAX_PARTICIPANTS:
        result["count"] = data["count"]
    if (isinstance(data.get("personas"), list) and len(data["personas"]) == MAX_PARTICIPANTS
            and all(isinstance(p, str) and p in PERSONAS for p in data["personas"])):
        result["personas"] = list(data["personas"])
    if isinstance(data.get("context"), str) and len(data["context"]) <= 1000:
        result["context"] = data["context"]
    try:
        result["hotkey"] = parse_hotkey(data.get("hotkey"))[0]
    except ValueError:
        pass
    if type(data.get("topmost")) is bool:
        result["topmost"] = data["topmost"]
    if type(data.get("onboarding_complete")) is bool:
        result["onboarding_complete"] = data["onboarding_complete"]
    elif data:
        # Existing users keep their saved setup; welcome can be reopened in the menu.
        result["onboarding_complete"] = True
    if type(data.get("opacity")) in (int, float) and .6 <= data["opacity"] <= 1:
        result["opacity"] = float(data["opacity"])
    if data.get("mode") in MODES.values():
        result["mode"] = data["mode"]
    if data.get("destination") in DESTINATIONS.values():
        result["destination"] = data["destination"]
    if isinstance(data.get("channel_url"), str) and len(data["channel_url"]) <= 2048:
        result["channel_url"] = data["channel_url"].strip()
    for key, options in (("interval", (3, 5, 10)), ("duration", (30, 60, 120))):
        if type(data.get(key)) is int and data[key] in options:
            result[key] = data[key]
    return result


class Overlay:
    def __init__(self, root: tk.Tk, state_dir: Path, *, service=None,
                 capture=capture_primary_screen, enable_hotkey=True,
                 window_list=list_windows, window_capture=capture_window):
        self.root, self.state_dir = root, state_dir
        apply_window_icon(root)
        self.settings_path = state_dir / "settings.json"
        self.settings = clean_settings(json.loads(self.settings_path.read_text(encoding="utf-8"))
                                       if self.settings_path.exists() else {})
        self.service = service or ServiceClient()
        self.capture = capture
        self.window_list, self.window_capture = window_list, window_capture
        self.sources = []
        self.live_running = False
        self.live_stop = threading.Event()
        self.usage_loading = False
        self.usage_error = None
        self.channel_loading = False
        self.connected_channel = None
        self.events = queue.Queue()
        self.busy = self.closing = self.collapsed = False
        self.configuring = False
        self.recording_hotkey = False
        self.next_trigger = 0.0
        self.worker = None
        self.hotkey = GlobalHotkey(lambda: self.events.put(("hotkey", time.monotonic()))) if enable_hotkey else None
        self.root.title("AI 채팅 오버레이")
        self.root.geometry("450x740+80+80")
        self.root.minsize(410, 660)
        self.root.option_add("*Font", ("맑은 고딕", 9))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Control-Return>", lambda event: self.generate())
        if sys.platform == "darwin":
            self.root.bind("<Command-Return>", lambda event: self.generate())
        self.status = tk.StringVar(value="화면 캡처 버튼이나 단축키로 채팅을 생성하세요.")
        self.mode_text = tk.StringVar()
        self.count_text = tk.StringVar()
        self.shortcut_text = tk.StringVar()
        self.context_count = tk.StringVar(value="0 / 1,000")
        self.persona_vars = [tk.StringVar(value=PERSONAS[p]["name"]) for p in self.settings["personas"]]
        self._build()
        self._apply_window_settings()
        self._refresh_count()
        self._refresh_mode()
        self._refresh_usage()
        self._register_hotkey()
        self._mode_changed()
        self._destination_changed()
        self.poll_id = self.root.after(50, self._poll)
        self.refresh_service_usage()

    def _build(self):
        from apps.desktop.figma_ui import FigmaView
        FigmaView(self)

    def _build_usage(self):
        ttk.Label(self.usage_tab, text="서비스 사용량", font=(self.view.family, 11, "bold")).pack(anchor="w", pady=(0, 8))
        self.usage_period = tk.StringVar(value="사용량을 불러오는 중…")
        ttk.Label(self.usage_tab, textvariable=self.usage_period, wraplength=370).pack(anchor="w", pady=(0, 12))
        self.usage_table = ttk.Treeview(self.usage_tab, columns=("metric", "value"), show="headings", height=3)
        for key, label, width in (("metric", "항목", 240), ("value", "사용량", 100)):
            self.usage_table.heading(key, text=label)
            self.usage_table.column(key, width=width, anchor="w" if key == "metric" else "e")
        self.usage_table.pack(fill="x")
        self.usage_metrics = (("generation_requests", "이번 달 생성 요청"),
                              ("generated_chats", "이번 달 생성된 채팅"),
                              ("total_generated_chats", "누적 생성된 채팅"))
        for key, label in self.usage_metrics:
            self.usage_table.insert("", "end", iid=key, values=(label, "—"))
        ttk.Button(self.usage_tab, text="사용량 새로고침", command=self.refresh_service_usage).pack(fill="x")

    def _context_changed(self, event=None):
        if self.context.edit_modified():
            length = len(self.context.get("1.0", "end-1c"))
            self.context_count.set(f"{length:,} / 1,000")
            self.context.edit_modified(False)

    def _snapshot_settings(self):
        by_name = {p["name"]: key for key, p in PERSONAS.items()}
        return clean_settings({**self.settings, "personas": [by_name[v.get()] for v in self.persona_vars],
                               "context": self.context.get("1.0", "end-1c"),
                               "mode": MODES[self.mode_var.get()],
                               "destination": DESTINATIONS[self.destination_var.get()], "channel_url": self.channel_var.get(),
                               "interval": int(self.interval_var.get()), "duration": int(self.duration_var.get())})

    def _destination_changed(self, event=None):
        self._channel_link_changed()
        if DESTINATIONS[self.destination_var.get()] == "chzzk":
            self.refresh_channel()
        else:
            self.status.set("앱에만 표시 · 치지직 로그인 없이 시연할 수 있습니다.")

    def _channel_link_changed(self):
        if DESTINATIONS[self.destination_var.get()] == "app":
            try:
                parse_channel_id(self.channel_var.get())
                self.channel_info.set("방송 링크 인식 완료 · 현재는 앱에만 표시합니다.")
            except ValueError:
                self.channel_info.set("방송 링크를 붙여 넣으세요. 앱 표시 모드에서는 전송하지 않습니다.")
            return
        try:
            target = parse_channel_id(self.channel_var.get())
            connected = self.connected_channel
            if connected and connected["channelId"] == target:
                self.channel_info.set(f"연결됨: {connected['channelName']}\n생성 시 치지직에 실제 전송합니다.")
            elif connected:
                self.channel_info.set(f"채널 ID 자동 인식: {target}\n연결된 채널({connected['channelName']})과 다릅니다.")
            else:
                self.channel_info.set(f"채널 ID 자동 인식: {target}\n연결 확인을 눌러주세요.")
        except ValueError:
            self.channel_info.set("치지직 방송 링크를 붙여 넣으면 채널 ID를 자동으로 인식합니다.")

    def refresh_channel(self):
        if self.channel_loading or self.busy or self.closing or self.configuring:
            return
        self.channel_loading = True
        service = self.service
        self.channel_info.set("치지직 연결 확인 중…")
        self.channel_check.configure(state="disabled")
        def work():
            try:
                value = asyncio.run(service.chzzk_status())
            except Exception:
                value = {"connected": False, "message": "연결을 확인하지 못했습니다. 서비스 연결을 확인해주세요."}
            self.events.put(("channel", (service, value)))
        threading.Thread(target=work, name="chzzk-status", daemon=True).start()

    def _output_options(self, snapshot):
        if snapshot["destination"] == "app":
            return {}
        target = parse_channel_id(snapshot["channel_url"])
        if not self.connected_channel or self.connected_channel["channelId"] != target:
            raise ValueError("방송 링크와 치지직 연결을 확인해주세요. 로그인 없이 시연하려면 앱에만 표시를 선택하세요.")
        return {"destination": "chzzk", "channel_id": target}

    def _mode_changed(self, event=None):
        realtime = MODES[self.mode_var.get()] == "realtime"
        self.settings["mode"] = "realtime" if realtime else "manual"
        if realtime:
            self.live_controls.pack(fill="x", before=self.live_anchor)
            self.trigger_button.configure(text="실시간 시작")
            self.capture_hint.set("선택한 창을 초당 1장 관찰 · 음성 없음\nAI가 돌아가며 반응합니다. 변화가 없으면 채팅을 쉬어갑니다.")
            self.refresh_windows()
        else:
            self.live_controls.pack_forget()
            self.trigger_button.configure(text="화면 캡처하고 채팅 생성")
            self.capture_hint.set("주 모니터 1장 · 버튼 또는 단축키를 누를 때만 촬영")

    def refresh_windows(self):
        if self.busy:
            return
        previous = self.source_var.get()
        try:
            self.sources = self.window_list()
            labels = [f"{source.title} [{source.handle:X}]" for source in self.sources]
            self.source_selector.configure(values=labels)
            self.source_var.set(previous if previous in labels else "")
            if not labels:
                self.status.set("캡처할 게임이나 OBS 창을 연 뒤 창 새로고침을 눌러주세요.")
        except ValueError as exc:
            self.status.set(str(exc))

    def _set_busy(self, busy):
        self.busy = busy
        self.trigger_button.configure(state="disabled" if busy else "normal")
        for selector in (self.mode_selector, self.source_selector, self.interval_selector, self.duration_selector,
                         self.destination_selector):
            selector.configure(state="disabled" if busy else "readonly")
        self.source_refresh.configure(state="disabled" if busy else "normal")
        self.channel_entry.configure(state="disabled" if busy else "normal")
        self.channel_check.configure(state="disabled" if busy or self.channel_loading else "normal")

    def start_live(self):
        if self.busy or self.closing or self.configuring:
            return
        index = self.source_selector.current()
        if index < 0 or index >= len(self.sources):
            self.status.set("실시간으로 볼 창을 먼저 선택해주세요.")
            return
        if len(self.context.get("1.0", "end-1c")) > 1000:
            self.status.set("상황 설명은 1,000자 이내로 입력해주세요.")
            return
        try:
            snapshot = self._snapshot_settings()
            output = self._output_options(snapshot)
            atomic_json(self.settings_path, snapshot)
        except (ValueError, OSError) as exc:
            self.status.set(str(exc))
            return
        source = self.sources[index]
        self.live_stop.clear()
        self.live_running = True
        self._set_busy(True)
        self.stop_button.configure(state="normal")
        self.status.set("실시간 연결 중… 중지 버튼이나 단축키로 종료할 수 있습니다.")
        def work():
            error = None
            try:
                asyncio.run(self.service.realtime(snapshot["personas"][:snapshot["count"]], snapshot["context"],
                    capture=lambda: self.window_capture(source), stop_event=self.live_stop,
                    interval=snapshot["interval"], duration=snapshot["duration"],
                    **output,
                    on_event=lambda event: self.events.put(("live", event))))
            except Exception as exc:
                error = str(exc) if isinstance(exc, ValueError) else "실시간 화면 처리를 종료했습니다. 선택한 창과 서비스 연결을 확인해주세요."
            finally:
                self.events.put(("live_done", error))
        self.worker = threading.Thread(target=work, name="overlay-realtime", daemon=True)
        self.worker.start()

    def stop_live(self):
        self.live_stop.set()
        self.stop_button.configure(state="disabled")
        self.status.set("실시간 화면 전송을 중지하고 있습니다…")

    def _refresh_count(self):
        self.count_text.set(f"{self.settings['count']}명")
        for row in self.persona_rows:
            row.pack_forget()
        for row in self.persona_rows[:self.settings["count"]]:
            row.pack(fill="x", pady=(6, 0), before=self.persona_hint)
        self._refresh_persona_preview()

    def _refresh_persona_preview(self, index=0):
        selected = self.persona_vars[index].get()
        persona = next(persona for persona in PERSONAS.values() if persona["name"] == selected)
        self.persona_preview.set(f"AI {index + 1} · {persona['description']}")
        self.view.refresh_persona(index)

    def change_count(self, delta):
        self.settings["count"] = max(1, min(MAX_PARTICIPANTS, self.settings["count"] + delta))
        self._refresh_count()

    def _refresh_mode(self):
        usage = self.service.usage()
        self.mode_text.set("테스트 모드" if usage and usage["is_demo"] else "화면 기반 채팅")
        self.view.refresh()

    def _refresh_usage(self):
        usage = self.service.usage()
        if usage:
            self.usage_period.set(f"{usage['period']} · 한국 시간 기준" + (" · 테스트 사용량" if usage["is_demo"] else "")
                                  + ("\n최근 확인한 사용량 · 새로고침 실패" if self.usage_error else ""))
        else:
            self.usage_period.set(self.usage_error or "사용량을 불러오는 중…")
        for key, label in self.usage_metrics:
            unit = "회" if key == "generation_requests" else "개"
            self.usage_table.item(key, values=(label, f"{usage[key]:,}{unit}" if usage else "—"))
        self.view.refresh_usage(usage)

    def refresh_service_usage(self):
        if self.usage_loading or self.busy or self.closing or self.configuring:
            return
        self.usage_loading = True
        def work():
            try:
                asyncio.run(self.service.refresh_usage())
                self.events.put(("usage", None))
            except Exception:
                self.events.put(("usage", "사용량을 불러오지 못했습니다. 서비스 연결을 확인해주세요."))
        threading.Thread(target=work, name="service-usage", daemon=True).start()

    def _apply_window_settings(self):
        self.root.attributes("-topmost", self.settings["topmost"])
        self.root.attributes("-alpha", self.settings["opacity"])
        if hasattr(self, "view"):
            self.view.settings_window.attributes("-topmost", self.settings["topmost"])
            self.view.settings_window.attributes("-alpha", self.settings["opacity"])

    def _register_hotkey(self):
        if self.hotkey is None:
            self.shortcut_text.set("창 안 단축키: Ctrl+Enter")
            return
        ok, error = self.hotkey.replace(self.settings["hotkey"])
        self.shortcut_text.set(f"전역: {self.hotkey.current} · 창 안: Ctrl+Enter" if self.hotkey.current else "창 안 단축키: Ctrl+Enter")
        if not ok:
            self.status.set(error)

    def record_hotkey(self):
        if self.busy:
            self.status.set("생성이 끝나면 단축키를 변경해주세요.")
            return
        if self.recording_hotkey:
            self._finish_hotkey_recording()
            return
        self.recording_hotkey = True
        self.hotkey_record.configure(text="취소")
        self.hotkey_hint.set("원하는 키 조합을 누르세요. Esc로 취소합니다.")
        self.hotkey_entry.focus_set()

    def _finish_hotkey_recording(self):
        if self.recording_hotkey:
            self.recording_hotkey = False
            self.next_trigger = max(self.next_trigger, time.monotonic() + .5)
            self.hotkey_record.configure(text="변경")
            self.hotkey_hint.set("설정 적용을 누르면 새 단축키가 등록됩니다.")

    def _hotkey_focus_lost(self, event):
        def finish_if_unfocused():
            if self.root.focus_get() != self.hotkey_entry:
                self._finish_hotkey_recording()
        self.root.after_idle(finish_if_unfocused)

    def _capture_hotkey(self, event):
        if not self.recording_hotkey:
            return None
        if event.keysym == "Escape":
            self._finish_hotkey_recording()
            return "break"
        try:
            name = pressed_hotkey(event.keycode, event=event)
            if name:
                self.hotkey_var.set(name)
                self._finish_hotkey_recording()
        except ValueError as exc:
            self.hotkey_hint.set(str(exc))
        return "break"

    def save_settings(self):
        if self.busy:
            self.status.set("생성이 끝나면 설정을 적용해주세요.")
            return False
        try:
            hotkey = parse_hotkey(self.hotkey_var.get())[0]
            candidate = {**self._snapshot_settings(),
                         "hotkey": hotkey,
                         "topmost": self.topmost_var.get(), "opacity": self.opacity_var.get()}
            candidate = clean_settings(candidate)
            if self.hotkey and candidate["hotkey"] != self.settings["hotkey"]:
                ok, error = self.hotkey.replace(candidate["hotkey"])
                if not ok:
                    raise ValueError(error)
            try:
                atomic_json(self.settings_path, candidate)
            except OSError:
                if self.hotkey:
                    self.hotkey.replace(self.settings["hotkey"])
                raise
            self.settings = candidate
            self.hotkey_var.set(hotkey)
            self._apply_window_settings()
            self._refresh_mode()
            self._register_hotkey()
            self.status.set("설정을 적용했습니다. 메인 원형 버튼으로 채팅을 생성하세요.")
            return True
        except (ValueError, OSError) as exc:
            self.status.set(str(exc))
            return False

    def show_page(self, page):
        self.view.show(page if isinstance(page, str) else "settings")

    def configure_connection(self):
        if self.busy or self.usage_loading or self.closing or self.configuring:
            self.status.set("현재 요청이 끝난 뒤 연결 설정을 변경해주세요.")
            return
        self.configuring = True
        try:
            dialog = ConnectionDialog(self.root, DESKTOP_ENV, self.service.base_url)
            if dialog.result:
                self.service = ServiceClient(**dialog.result)
                self.connected_channel = None
                self._channel_link_changed()
                self.usage_error = None
                self._refresh_mode()
                self._refresh_usage()
                self.status.set("서비스 연결 설정을 저장했습니다.")
        finally:
            self.configuring = False
        if dialog.result:
            self.refresh_service_usage()

    def toggle_compact(self):
        self.view.show("main")

    def generate(self):
        if self.recording_hotkey:
            return
        if self.live_running:
            self.stop_live()
            return
        if MODES[self.mode_var.get()] == "realtime":
            self.start_live()
            return
        if self.busy or self.closing or self.configuring or time.monotonic() < self.next_trigger:
            return
        context = self.context.get("1.0", "end-1c")
        if len(context) > 1000:
            self.status.set("상황 설명은 1,000자 이내로 입력해주세요.")
            return
        try:
            snapshot = self._snapshot_settings()
            self._output_options(snapshot)
            atomic_json(self.settings_path, snapshot)
        except (ValueError, OSError) as exc:
            self.status.set(str(exc))
            return
        self._set_busy(True)
        self.started = time.monotonic()
        self.status.set("오버레이를 숨기고 주 모니터를 촬영합니다…")
        self.restore_state = self.root.state()
        self.root.withdraw()
        # Let the window manager finish hiding the overlay before capture.
        self.root.after(180, lambda: self._start_worker(snapshot))

    def _start_worker(self, snapshot):
        def work():
            try:
                screenshot = self.capture()
                self.events.put(("captured", None))
                result = asyncio.run(self.service.generate(
                    snapshot["personas"][:snapshot["count"]], snapshot["context"], screenshot=screenshot,
                    **self._output_options(snapshot),
                    on_line=lambda line: self.events.put(("line", line))))
                self.events.put(("done", result))
            except Exception as exc:
                message = str(exc) if isinstance(exc, ValueError) else f"캡처 또는 생성 처리 실패 ({type(exc).__name__})"
                self.events.put(("failed", message))
        self.worker = threading.Thread(target=work, name="overlay-generation", daemon=True)
        self.worker.start()

    def _restore_window(self):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            if getattr(self, "restore_state", "normal") == "iconic":
                self.root.iconify()

    def _append_line(self, line):
        self.chat_log.configure(state="normal")
        name = PERSONAS[line["persona"]]["name"]
        self.chat_log.insert("end", f"AI {line['participant']} · {name}\n", "name")
        self.chat_log.insert("end", (line["comment"] if line["status"] == "ready" else line["error"]) + "\n\n",
                             "error" if line["status"] != "ready" else "")
        if line.get("delivery"):
            receipt = line["delivery"]
            self.chat_log.insert("end", receipt["message"] + "\n\n", "" if receipt["status"] == "sent" else "error")
        if int(self.chat_log.index("end-1c").split(".")[0]) > 300:
            self.chat_log.delete("1.0", "100.0")
        self.chat_log.configure(state="disabled")
        self.chat_log.see("end")

    def _poll(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "hotkey":
                # Do not turn a key pressed during a batch into a deferred call.
                if (not self.busy or self.live_running) and value >= self.next_trigger:
                    self.generate()
            elif kind == "channel":
                source, result = value
                self.channel_loading = False
                self.channel_check.configure(state="disabled" if self.busy else "normal")
                if source is self.service:
                    self.connected_channel = result if result["connected"] else None
                    if result["connected"]:
                        if not self.channel_var.get().strip():
                            self.channel_var.set("https://chzzk.naver.com/" + result["channelId"])
                        self._channel_link_changed()
                    else:
                        self.channel_info.set(result["message"])
            elif kind == "live":
                if not self.live_stop.is_set():
                    if value["type"] == "ready":
                        self.status.set("실시간 관찰 중 · 선택한 창을 초당 1장 촬영합니다.")
                    elif value["type"] == "decision":
                        if value["result"] == "chat":
                            self._append_line({**value, "status": "ready", "error": ""})
                        self.status.set(f"실시간 관찰 중 · 분석 {value['decisions']}회 · 채팅 {value['chats']}개")
                        self._refresh_usage()
                    elif value["type"] == "delivery":
                        receipt = value["delivery"]
                        self.chat_log.configure(state="normal")
                        self.chat_log.insert("end", f"AI {value['participant']} · {receipt['message']}\n\n",
                                             "" if receipt["status"] == "sent" else "error")
                        self.chat_log.configure(state="disabled")
                        self.chat_log.see("end")
                        self.status.set(receipt["message"])
            elif kind == "live_done":
                self.live_running = False
                self._set_busy(False)
                self.stop_button.configure(state="disabled")
                self.next_trigger = time.monotonic() + 1
                self.status.set(value or "실시간 관찰을 종료했습니다. 모드를 바꾸거나 다시 시작할 수 있습니다.")
                self._refresh_usage()
                if self.closing:
                    self._destroy()
                    return
                self.refresh_service_usage()
            elif kind == "captured":
                self._restore_window()
                self.status.set("캡처 완료 · AI 채팅을 생성하고 있습니다…")
            elif kind == "line":
                self._append_line(value)
                self._refresh_usage()
            elif kind == "usage":
                self.usage_loading = False
                self.usage_error = value
                self._refresh_usage()
                self._refresh_mode()
            elif kind in ("done", "failed"):
                self._restore_window()
                self._set_busy(False)
                self.next_trigger = time.monotonic() + 1
                self.trigger_button.configure(state="normal")
                if kind == "failed":
                    self.status.set(value)
                else:
                    good = sum(line["status"] == "ready" for line in value["lines"])
                    self.usage_error = None
                    self.status.set({"busy": "이미 생성 중입니다. 잠시 후 다시 눌러주세요.",
                                     "cooldown": "잠시 후 다시 눌러주세요."}.get(value["status"],
                                    f"{good}개 생성 · {len(value['lines']) - good}개 실패 · {time.monotonic() - self.started:.1f}초"))
                self._refresh_usage()
                self._refresh_mode()
                if self.closing:
                    self._destroy()
                    return
        self.poll_id = self.root.after(50, self._poll)

    def close(self):
        if self.closing:
            return
        self.closing = True
        if self.hotkey:
            self.hotkey.close()
        self.service.stop_requested.set()
        self.live_stop.set()
        if self.busy:
            self.status.set("서비스 연결을 정리하고 종료합니다…")
        else:
            self._destroy()

    def _destroy(self):
        try:
            atomic_json(self.settings_path, self._snapshot_settings())
        except (ValueError, OSError):
            pass
        self.root.after_cancel(self.poll_id)
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=state_directory())
    parser.add_argument("--self-test", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    set_app_identity()
    if args.self_test:
        from apps.desktop.self_test import run
        return run(args.self_test)
    root = tk.Tk()
    root.withdraw()
    apply_window_icon(root)
    instance = None
    try:
        instance = SingleInstance(args.state_dir)
        service = ServiceClient()
        app = Overlay(root, args.state_dir, service=service)
        if not service.configured:
            app.status.set("오버레이 준비 완료 · 설정 → 서비스 연결 설정에서 연결 정보를 등록해주세요.")
        root.deiconify()
        root.mainloop()
    except (ValueError, OSError) as exc:
        messagebox.showerror("오버레이를 열 수 없습니다", str(exc), parent=root)
        root.destroy()
        return 1
    finally:
        if instance:
            instance.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
