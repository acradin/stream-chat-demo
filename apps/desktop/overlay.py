"""Small replaceable Tk overlay: screenshot -> service -> Korean AI chat."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from apps.desktop.hotkey import GlobalHotkey, HOTKEYS, SingleInstance
from apps.desktop.service_client import DESKTOP_ENV, ServiceClient
from apps.desktop.paths import state_directory
from apps.desktop.connection import ConnectionDialog
from backend.storage import atomic_json
from backend.personas import DEFAULT_PERSONA, PERSONAS
from apps.desktop.capture import capture_primary_screen, capture_window, list_windows


MAX_PARTICIPANTS = 5
DEFAULT_SETTINGS = {"count": 1,
                    "personas": [DEFAULT_PERSONA, "warm_supporter", "hype_commentator", "dry_comic", DEFAULT_PERSONA],
                    "context": "", "hotkey": "Ctrl+Alt+Space", "topmost": True, "opacity": 1.0,
                    "mode": "manual", "interval": 5, "duration": 60}
MODES = {"버튼 캡처 모드": "manual", "실시간 화면 모드": "realtime"}


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
    if data.get("hotkey") in HOTKEYS:
        result["hotkey"] = data["hotkey"]
    if type(data.get("topmost")) is bool:
        result["topmost"] = data["topmost"]
    if type(data.get("opacity")) in (int, float) and .6 <= data["opacity"] <= 1:
        result["opacity"] = float(data["opacity"])
    if data.get("mode") in MODES.values():
        result["mode"] = data["mode"]
    for key, options in (("interval", (3, 5, 10)), ("duration", (30, 60, 120))):
        if type(data.get(key)) is int and data[key] in options:
            result[key] = data[key]
    return result


class Overlay:
    def __init__(self, root: tk.Tk, state_dir: Path, *, service=None,
                 capture=capture_primary_screen, enable_hotkey=True,
                 window_list=list_windows, window_capture=capture_window):
        self.root, self.state_dir = root, state_dir
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
        self.events = queue.Queue()
        self.busy = self.closing = self.collapsed = False
        self.configuring = False
        self.next_trigger = 0.0
        self.worker = None
        self.hotkey = GlobalHotkey(lambda: self.events.put(("hotkey", time.monotonic()))) if enable_hotkey else None
        self.root.title("AI 채팅 오버레이")
        self.root.geometry("450x740+80+80")
        self.root.minsize(410, 660)
        self.root.option_add("*Font", ("맑은 고딕", 9))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Control-Return>", lambda event: self.generate())
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
        self.poll_id = self.root.after(50, self._poll)
        self.refresh_service_usage()

    def _build(self):
        header = ttk.Frame(self.root, padding=(10, 8))
        header.pack(fill="x")
        ttk.Label(header, text="AI 채팅", font=("맑은 고딕", 12, "bold")).pack(side="left")
        ttk.Label(header, textvariable=self.mode_text).pack(side="left", padx=8)
        self.fold_button = ttk.Button(header, text="접기", width=5, command=self.toggle_compact)
        self.fold_button.pack(side="right")
        ttk.Button(header, text="설정", width=5, command=lambda: self.show_page(self.settings_tab)).pack(side="right", padx=4)
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=8)
        self.chat_tab = ttk.Frame(self.tabs, padding=10)
        self.settings_tab = ttk.Frame(self.tabs, padding=12)
        self.usage_tab = ttk.Frame(self.tabs, padding=12)
        for frame, name in ((self.chat_tab, "채팅"), (self.settings_tab, "설정"), (self.usage_tab, "사용량")):
            self.tabs.add(frame, text=name)
        self._build_chat()
        self._build_settings()
        self._build_usage()
        self.footer = ttk.Label(self.root, textvariable=self.status, wraplength=400, padding=(12, 8))
        self.footer.pack(fill="x")

    def _build_chat(self):
        self.mode_var = tk.StringVar(value=next(label for label, mode in MODES.items() if mode == self.settings["mode"]))
        self.mode_selector = ttk.Combobox(self.chat_tab, textvariable=self.mode_var,
                                         values=list(MODES), state="readonly")
        self.mode_selector.pack(fill="x", pady=(0, 8))
        self.mode_selector.bind("<<ComboboxSelected>>", self._mode_changed)
        top = ttk.Frame(self.chat_tab)
        top.pack(fill="x")
        ttk.Label(top, text="AI 참여 인원").pack(side="left")
        ttk.Button(top, text="−", width=3, command=lambda: self.change_count(-1)).pack(side="left", padx=(12, 4))
        ttk.Label(top, textvariable=self.count_text, width=5, anchor="center").pack(side="left")
        ttk.Button(top, text="+", width=3, command=lambda: self.change_count(1)).pack(side="left", padx=4)
        self.persona_rows = []
        for index, variable in enumerate(self.persona_vars, 1):
            row = ttk.Frame(self.chat_tab)
            ttk.Label(row, text=f"AI {index}", width=7).pack(side="left")
            selector = ttk.Combobox(row, textvariable=variable, state="readonly",
                                   values=[p["name"] for p in PERSONAS.values()])
            selector.pack(side="left", fill="x", expand=True)
            selector.bind("<<ComboboxSelected>>", lambda event, slot=index - 1: self._refresh_persona_preview(slot))
            self.persona_rows.append(row)
        self.persona_preview = tk.StringVar()
        self.persona_hint = ttk.Label(self.chat_tab, textvariable=self.persona_preview, wraplength=370,
                                      foreground="#555555")
        self.persona_hint.pack(fill="x", pady=(6, 0))
        self._refresh_persona_preview()
        self.context_header = ttk.Frame(self.chat_tab)
        self.context_header.pack(fill="x", pady=(10, 3))
        ttk.Label(self.context_header, text="상황 설명 (선택)").pack(side="left")
        ttk.Label(self.context_header, textvariable=self.context_count).pack(side="right")
        self.context = tk.Text(self.chat_tab, height=3, wrap="word", relief="solid", borderwidth=1, undo=True)
        self.context.pack(fill="x")
        self.context.insert("1.0", self.settings["context"])
        self.context.bind("<<Modified>>", self._context_changed)
        self.live_controls = ttk.Frame(self.chat_tab)
        source_row = ttk.Frame(self.live_controls)
        source_row.pack(fill="x", pady=(8, 4))
        self.source_var = tk.StringVar()
        self.source_selector = ttk.Combobox(source_row, textvariable=self.source_var, state="readonly")
        self.source_selector.pack(side="left", fill="x", expand=True)
        self.source_refresh = ttk.Button(source_row, text="창 새로고침", command=self.refresh_windows)
        self.source_refresh.pack(side="right", padx=(4, 0))
        options = ttk.Frame(self.live_controls)
        options.pack(fill="x")
        self.interval_var = tk.StringVar(value=str(self.settings["interval"]))
        self.duration_var = tk.StringVar(value=str(self.settings["duration"]))
        ttk.Label(options, text="분석 간격(초)").pack(side="left")
        self.interval_selector = ttk.Combobox(options, textvariable=self.interval_var, values=(3, 5, 10), width=4, state="readonly")
        self.interval_selector.pack(side="left", padx=4)
        ttk.Label(options, text="자동 종료(초)").pack(side="left", padx=(8, 0))
        self.duration_selector = ttk.Combobox(options, textvariable=self.duration_var, values=(30, 60, 120), width=5, state="readonly")
        self.duration_selector.pack(side="left", padx=4)
        self.trigger_button = ttk.Button(self.chat_tab, text="화면 캡처하고 채팅 생성", command=self.generate)
        self.trigger_button.pack(fill="x", pady=(10, 4), ipady=4)
        self.stop_button = ttk.Button(self.live_controls, text="실시간 중지", command=self.stop_live, state="disabled")
        self.stop_button.pack(fill="x", pady=(6, 0))
        ttk.Label(self.chat_tab, textvariable=self.shortcut_text, wraplength=370).pack(fill="x")
        self.capture_hint = tk.StringVar()
        ttk.Label(self.chat_tab, textvariable=self.capture_hint, wraplength=390, foreground="#555555").pack(fill="x", pady=(2, 8))
        self.chat_log = scrolledtext.ScrolledText(self.chat_tab, height=7, wrap="word", state="disabled", relief="flat")
        self.chat_log.pack(fill="both", expand=True)
        self.chat_log.tag_configure("name", foreground="#2455a4", font=("맑은 고딕", 9, "bold"))
        self.chat_log.tag_configure("error", foreground="#a32f26")
        ttk.Label(self.chat_tab, text="결과는 이 창에 표시됩니다.", foreground="#666666").pack(anchor="w", pady=(6, 0))

    def _build_settings(self):
        frame = self.settings_tab
        self.hotkey_var = tk.StringVar(value=self.settings["hotkey"])
        self.topmost_var = tk.BooleanVar(value=self.settings["topmost"])
        self.opacity_var = tk.DoubleVar(value=self.settings["opacity"])
        ttk.Label(frame, text="전역 단축키").pack(anchor="w")
        ttk.Combobox(frame, textvariable=self.hotkey_var, state="readonly", values=list(HOTKEYS)).pack(fill="x", pady=(3, 10))
        ttk.Checkbutton(frame, text="항상 위에 표시", variable=self.topmost_var).pack(anchor="w")
        ttk.Label(frame, text="창 불투명도 (60~100%)").pack(anchor="w", pady=(8, 0))
        ttk.Scale(frame, variable=self.opacity_var, from_=.6, to=1).pack(fill="x")
        ttk.Button(frame, text="설정 적용", command=self.save_settings).pack(fill="x", pady=(12, 8))
        ttk.Button(frame, text="서비스 연결 설정", command=self.configure_connection).pack(fill="x", pady=(0, 8))
        ttk.Label(frame, text="채팅을 만들 때 캡처한 화면과 상황 설명을 서비스에\n전송합니다. 스크린샷은 로컬 파일로 저장하지 않습니다.",
                  wraplength=370, foreground="#555555").pack(anchor="w")

    def _build_usage(self):
        ttk.Label(self.usage_tab, text="서비스 사용량", font=("맑은 고딕", 11, "bold")).pack(anchor="w", pady=(0, 8))
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
        ttk.Label(self.usage_tab, text="버튼 모드: 클릭 1회가 생성 요청 1회입니다.\n실시간 모드: 화면 분석 1회가 생성 요청 1회입니다.\n화면에 표시된 채팅만 채팅 수에 포함됩니다.\n사용량은 서비스 계정 기준으로 집계됩니다.",
                  wraplength=370).pack(anchor="w", pady=12)
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
                               "interval": int(self.interval_var.get()), "duration": int(self.duration_var.get())})

    def _mode_changed(self, event=None):
        realtime = MODES[self.mode_var.get()] == "realtime"
        self.settings["mode"] = "realtime" if realtime else "manual"
        if realtime:
            self.live_controls.pack(fill="x", before=self.trigger_button)
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
        for selector in (self.mode_selector, self.source_selector, self.interval_selector, self.duration_selector):
            selector.configure(state="disabled" if busy else "readonly")
        self.source_refresh.configure(state="disabled" if busy else "normal")

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

    def change_count(self, delta):
        self.settings["count"] = max(1, min(MAX_PARTICIPANTS, self.settings["count"] + delta))
        self._refresh_count()

    def _refresh_mode(self):
        usage = self.service.usage()
        self.mode_text.set("테스트 모드" if usage and usage["is_demo"] else "화면 기반 채팅")

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

    def _register_hotkey(self):
        if self.hotkey is None:
            self.shortcut_text.set("창 안 단축키: Ctrl+Enter")
            return
        ok, error = self.hotkey.replace(self.settings["hotkey"])
        self.shortcut_text.set(f"전역: {self.hotkey.current} · 창 안: Ctrl+Enter" if self.hotkey.current else "창 안 단축키: Ctrl+Enter")
        if not ok:
            self.status.set(error)

    def save_settings(self):
        if self.busy:
            self.status.set("생성이 끝나면 설정을 적용해주세요.")
            return
        try:
            candidate = {**self._snapshot_settings(),
                         "hotkey": self.hotkey_var.get(),
                         "topmost": self.topmost_var.get(), "opacity": self.opacity_var.get()}
            candidate = clean_settings(candidate)
            if self.hotkey:
                ok, error = self.hotkey.replace(candidate["hotkey"])
                if not ok:
                    raise ValueError(error)
            atomic_json(self.settings_path, candidate)
            self.settings = candidate
            self._apply_window_settings()
            self._refresh_mode()
            self._register_hotkey()
            self.status.set("설정을 적용했습니다. 채팅 탭에서 화면을 캡처하고 생성하세요.")
        except (ValueError, OSError) as exc:
            self.status.set(str(exc))

    def show_page(self, page):
        if self.collapsed:
            self.toggle_compact()
        self.tabs.select(page)

    def configure_connection(self):
        if self.busy or self.usage_loading or self.closing or self.configuring:
            self.status.set("현재 요청이 끝난 뒤 연결 설정을 변경해주세요.")
            return
        self.configuring = True
        try:
            dialog = ConnectionDialog(self.root, DESKTOP_ENV, self.service.base_url)
            if dialog.result:
                self.service = ServiceClient(**dialog.result)
                self.usage_error = None
                self._refresh_mode()
                self._refresh_usage()
                self.status.set("서비스 연결 설정을 저장했습니다.")
        finally:
            self.configuring = False
        if dialog.result:
            self.refresh_service_usage()

    def toggle_compact(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.expanded_geometry = self.root.geometry()
            self.tabs.pack_forget()
            self.root.minsize(410, 100)
            self.root.geometry(f"430x110+{self.root.winfo_x()}+{self.root.winfo_y()}")
            self.fold_button.configure(text="펼치기")
        else:
            self.tabs.pack(fill="both", expand=True, padx=8, before=self.footer)
            self.root.minsize(410, 660)
            self.root.geometry(self.expanded_geometry)
            self.fold_button.configure(text="접기")

    def generate(self):
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
            atomic_json(self.settings_path, snapshot)
        except (ValueError, OSError) as exc:
            self.status.set(f"설정을 저장하지 못했습니다: {exc}")
            return
        self._set_busy(True)
        self.started = time.monotonic()
        self.status.set("오버레이를 숨기고 주 모니터를 촬영합니다…")
        self.restore_state = self.root.state()
        self.root.withdraw()
        # Let Windows finish removing this window before capturing the screen.
        self.root.after(180, lambda: self._start_worker(snapshot))

    def _start_worker(self, snapshot):
        def work():
            try:
                screenshot = self.capture()
                self.events.put(("captured", None))
                result = asyncio.run(self.service.generate(
                    snapshot["personas"][:snapshot["count"]], snapshot["context"], screenshot=screenshot,
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
            elif kind == "live":
                if not self.live_stop.is_set():
                    if value["type"] == "ready":
                        self.status.set("실시간 관찰 중 · 선택한 창을 초당 1장 촬영합니다.")
                    elif value["type"] == "decision":
                        if value["result"] == "chat":
                            self._append_line({**value, "status": "ready", "error": ""})
                        self.status.set(f"실시간 관찰 중 · 분석 {value['decisions']}회 · 채팅 {value['chats']}개")
                        self._refresh_usage()
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
    if args.self_test:
        from apps.desktop.self_test import run
        return run(args.self_test)
    root = tk.Tk()
    root.withdraw()
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
