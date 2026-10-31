"""Native Tk implementation of the Figma main/settings screens.

UI only: generation, delivery, usage, persistence and hotkeys stay in Overlay.
The additional controls/log pages preserve capabilities absent from the mockup.
"""

import sys
import tkinter as tk
from tkinter import ttk, scrolledtext

from PIL import Image, ImageTk

from apps.desktop.branding import ASSETS, apply_window_icon
from apps.desktop.panel import Panel, BG, INPUT, INK, MUTED, MINT, configure_theme
from backend.personas import PERSONAS


def asset(master, name):
    source = {"orb-base": "orb-original-base", "orb-glow": "orb-original-glow"}.get(name, name)
    with Image.open(ASSETS / "figma" / (source + ".png")) as image:
        if name in ("orb-base", "orb-glow"):
            image = image.resize((image.width//2, image.height//2), Image.Resampling.LANCZOS)
            image.putalpha(image.getchannel("A").point(lambda alpha: round(alpha * .72)))
        return ImageTk.PhotoImage(image, master=master)


class GenerateOrb(tk.Canvas):
    def __init__(self, master, app):
        super().__init__(master, width=198, height=198, bg=BG, highlightthickness=0,
                         takefocus=1, cursor="hand2")
        self.app, self.disabled = app, False
        self.photos = [asset(self, name) for name in ("orb-base", "orb-glow", "orb-face")]
        self.create_image(99, 100, image=self.photos[0])
        self.create_image(99, 99, image=self.photos[1])
        self.create_image(99, 80, image=self.photos[2])
        self.key_label = self.create_text(99, 130, fill=INK, font=(app.view.family, 10, "bold"),
                                          text=app.settings["hotkey"])
        self.caption = self.create_text(99, 150, fill=INK, font=(app.view.family, 7), text="채팅을 생성하세요!")
        self.bind("<Button-1>", self.invoke)
        self.bind("<Return>", self.invoke)
        self.bind("<space>", self.invoke)
        self.bind("<FocusIn>", lambda _: self.configure(highlightthickness=1, highlightbackground=MINT))
        self.bind("<FocusOut>", lambda _: self.configure(highlightthickness=0))

    def invoke(self, event=None):
        # A running observation can be stopped from the same orb.
        if not self.disabled or self.app.live_running:
            self.app.generate()
        return "break"

    def configure(self, cnf=None, **kwargs):
        text = kwargs.pop("text", None)
        if text is not None:
            self.itemconfigure(self.caption, text="채팅을 생성하세요!" if text == "화면 캡처하고 채팅 생성" else text)
        state = kwargs.pop("state", None)
        if state is not None:
            self.disabled = state == "disabled"
            self.itemconfigure(self.caption, text=("관찰 중 · 눌러서 중지" if self.app.live_running else "생성 중…")
                               if self.disabled else ("실시간 시작" if self.app.settings["mode"] == "realtime" else "채팅을 생성하세요!"))
        if kwargs or cnf:
            super().configure(cnf, **kwargs)


class FigmaView:
    def __init__(self, app):
        self.app, self.root = app, app.root
        app.view = self
        self.family = configure_theme(self.root)
        self.root.title("tiki")
        self.root.resizable(False, False)
        self.root.minsize(1, 1)
        self.root.configure(bg="#010203")
        if sys.platform == "win32":
            self.root.attributes("-transparentcolor", "#010203")
        self.root.overrideredirect(True)
        self.root.bind("<Map>", self._mapped, add="+")
        self.root.bind("<Alt-F4>", lambda _: app.close())
        self.root.bind("<Escape>", lambda _: self.show("main") if not app.recording_hotkey else None)
        self.pages = {}
        self.current = "main"
        self.photos = {name: asset(self.root, name) for name in ("header", "settings", "persona")}
        self.main = self._page("main", 278, 448)
        self.settings = self._page("settings", 420, 666)
        self.controls = self._page("controls", 420, 690)
        self.chat = self._page("chat", 420, 530)
        self._main()
        self._settings()
        self._controls()
        self._chat()
        self.show("main")
        apply_window_icon(self.root)

    def _page(self, name, width, height):
        page = Panel(self.root, width, height, settings=name != "main")
        self.pages[name] = page
        page.create_image(28, 27, anchor="nw", image=self.photos["header"])
        badge = ttk.Label(page, text="Demo", foreground=INK, background="#d52b30", font=(self.family, 6))
        badge.place(x=106, y=31)
        # The badge is truthful: service status switches it after usage returns.
        if not hasattr(self, "badges"):
            self.badges = []
        self.badges.append(badge)
        if name == "main":
            button = tk.Button(page, image=self.photos["settings"], command=lambda: self.show("settings"),
                               bg=BG, activebackground=INPUT, borderwidth=0, cursor="hand2", takefocus=1)
            button.place(x=197, y=29, width=18, height=18)
        else:
            ttk.Button(page, text="‹", width=2, command=lambda: self.show("main")).place(x=width-112, y=21)
        for x, color, command, symbol in ((width-53, "#ff736a", self.app.close, "×"),
                                          (width-36, "#febc2e", self.minimize, "−")):
            dot = tk.Canvas(page, bg=BG, highlightthickness=0, borderwidth=0, cursor="hand2", takefocus=1)
            dot.create_oval(0, 0, 10, 10, fill=color, outline="")
            dot.bind("<Button-1>", lambda _, action=command: action())
            dot.bind("<Return>", lambda _, action=command: action())
            dot.bind("<space>", lambda _, action=command: action())
            dot.place(x=x, y=32, width=11, height=11)
        page.bind("<ButtonPress-1>", self._drag_start)
        page.bind("<B1-Motion>", self._drag)
        return page

    def _drag_start(self, event):
        self.drag = (event.x_root-self.root.winfo_x(), event.y_root-self.root.winfo_y()) if event.y < 62 else None

    def _drag(self, event):
        if getattr(self, "drag", None):
            self.root.geometry(f"+{event.x_root-self.drag[0]}+{event.y_root-self.drag[1]}")

    def _mapped(self, event):
        if event.widget is self.root and self.root.state() == "normal":
            self.root.overrideredirect(True)
            # Keep a frameless native window available in taskbar and Alt+Tab.
            if sys.platform == "win32":
                import ctypes
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                hwnd = int(self.root.wm_frame(), 0)
                user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
                user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
                extended = user32.GetWindowLongW(hwnd, -20)
                user32.SetWindowLongW(hwnd, -20, (extended | 0x40000) & ~0x80)
            apply_window_icon(self.root)

    def minimize(self):
        self.root.overrideredirect(False)
        self.root.iconify()

    def show(self, name):
        if name not in self.pages:
            return
        if self.app.recording_hotkey and name != "settings":
            self.app._finish_hotkey_recording()
        for page in self.pages.values():
            page.pack_forget()
        self.current = name
        page = self.pages[name]
        page.pack()
        self.root.geometry(f"{page.cget('width')}x{page.cget('height')}+{max(0,self.root.winfo_x())}+{max(0,self.root.winfo_y())}")

    def _content(self, page, y=66, bottom=24):
        width = int(page.cget("width"))-56
        height = int(page.cget("height"))-y-bottom
        if page is self.chat:
            frame = ttk.Frame(page)
            frame.place(x=28, y=y, width=width, height=height)
            return frame
        viewport = tk.Canvas(page, bg=BG, highlightthickness=0, width=width, height=height)
        viewport.place(x=28, y=y, width=width, height=height)
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=viewport.yview)
        scrollbar.place(x=int(page.cget("width"))-20, y=y, width=10, height=height)
        viewport.configure(yscrollcommand=scrollbar.set)
        frame = ttk.Frame(viewport)
        viewport.create_window(0, 0, window=frame, anchor="nw", width=width)
        frame.bind("<Configure>", lambda _: viewport.configure(scrollregion=viewport.bbox("all")))
        def scroll(event):
            target = self.root.winfo_containing(event.x_root, event.y_root)
            if not target or isinstance(target, (tk.Text, ttk.Combobox, ttk.Scale)):
                return
            parent = target
            while parent is not None:
                if parent is viewport:
                    viewport.yview_scroll(-int(event.delta/120), "units")
                    return "break"
                parent = getattr(parent, "master", None)
        self.root.bind("<MouseWheel>", scroll, add="+")
        return frame

    def _label(self, frame, text, **kwargs):
        label = ttk.Label(frame, text=text, **kwargs)
        label.pack(anchor="w", pady=(0, 5))
        return label

    def _main(self):
        app = self.app
        app.trigger_button = GenerateOrb(self.main, app)
        app.trigger_button.place(x=40, y=49)
        self.main.create_text(48, 257, text="채팅 멤버", fill=INK, anchor="w", font=(self.family, 10))
        ttk.Label(self.main, textvariable=app.count_text).place(x=218, y=247)
        self.count = tk.IntVar(value=app.settings["count"])
        self.slider = tk.Canvas(self.main, width=186, height=24, bg=BG, highlightthickness=0,
                                takefocus=1, cursor="hand2")
        self.slider.place(x=46, y=274)
        self.slider.create_line(7, 12, 179, 12, fill="#434547", width=8, capstyle="round")
        self.slider_active = self.slider.create_line(7, 12, 7, 12, fill="#00c5a5", width=8, capstyle="round")
        for x in (7, 50, 93, 136, 179):
            self.slider.create_line(x, 7, x, 17, fill="#8a8b8c")
        self.slider_knob = self.slider.create_oval(1, 6, 13, 18, fill="#2dff8f", outline="#ffffff", width=1)
        for event in ("<Button-1>", "<B1-Motion>"):
            self.slider.bind(event, lambda e: self._count_changed(max(1, min(5, round((e.x-7)/43)+1))))
        self.slider.bind("<Left>", lambda _: self._count_changed(max(1, self.count.get()-1)))
        self.slider.bind("<Right>", lambda _: self._count_changed(min(5, self.count.get()+1)))
        self.slider.bind("<FocusIn>", lambda _: self.slider.configure(highlightthickness=1, highlightbackground=MINT))
        self.slider.bind("<FocusOut>", lambda _: self.slider.configure(highlightthickness=0))
        self.count.trace_add("write", lambda *_: self._draw_count())
        self._draw_count()
        for i in range(5):
            self.main.create_text(53+i*42, 307, text=str(i+1), fill=INK, font=(self.family, 7))
        self.main.create_text(139, 329, text="데모 · 1~5명 모두 사용할 수 있어요", fill=MUTED, font=(self.family, 7))
        ttk.Button(self.main, text="사용 방식", command=lambda: self.show("controls")).place(x=28, y=348, width=104)
        ttk.Button(self.main, text="채팅 보기", command=lambda: self.show("chat")).place(x=140, y=348, width=110)
        app.footer = ttk.Label(self.main, textvariable=app.status, wraplength=222, foreground=MUTED,
                               font=(self.family, 8))
        app.footer.place(x=28, y=391, width=222, height=43)

    def _count_changed(self, value):
        self.count.set(value)
        self.app.change_count(value-self.app.settings["count"])

    def _draw_count(self):
        x = 7 + (self.count.get()-1)*43
        self.slider.coords(self.slider_active, 7, 12, x, 12)
        self.slider.coords(self.slider_knob, x-6, 6, x+6, 18)

    def _settings(self):
        app, frame = self.app, self._content(self.settings, bottom=100)
        app.settings_tab = frame
        app.channel_controls = ttk.Frame(frame)
        app.channel_controls.pack(fill="x")
        self._label(app.channel_controls, "방송 링크")
        row = ttk.Frame(app.channel_controls)
        row.pack(fill="x")
        app.channel_var = tk.StringVar(value=app.settings["channel_url"])
        app.channel_entry = ttk.Entry(row, textvariable=app.channel_var)
        app.channel_entry.pack(side="left", fill="x", expand=True)
        app.channel_check = ttk.Button(row, text="확인", width=4, command=app.refresh_channel)
        app.channel_check.pack(side="right", padx=(6, 0))
        app.channel_info = tk.StringVar()
        ttk.Label(app.channel_controls, textvariable=app.channel_info, wraplength=355,
                  foreground=MUTED, font=(self.family, 8)).pack(fill="x", pady=(4, 12))
        app.channel_var.trace_add("write", lambda *_: app._channel_link_changed())
        self._label(frame, "단축키 설정")
        row = ttk.Frame(frame)
        row.pack(fill="x")
        app.hotkey_var = tk.StringVar(value=app.settings["hotkey"])
        app.hotkey_entry = ttk.Entry(row, textvariable=app.hotkey_var, width=21)
        app.hotkey_entry.pack(side="left")
        app.hotkey_entry.bind("<KeyPress>", app._capture_hotkey)
        app.hotkey_entry.bind("<FocusOut>", app._hotkey_focus_lost)
        app.hotkey_record = ttk.Button(row, text="키로 지정", command=app.record_hotkey)
        app.hotkey_record.pack(side="right")
        app.hotkey_hint = tk.StringVar(value="직접 입력하거나 키 조합을 눌러 지정하세요.")
        ttk.Label(frame, textvariable=app.hotkey_hint, foreground=MUTED, wraplength=355,
                  font=(self.family, 8)).pack(anchor="w", pady=(4, 12))
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(0, 5))
        ttk.Label(row, text="방송 설명").pack(side="left")
        ttk.Label(row, textvariable=app.context_count, foreground=MUTED, font=(self.family, 7)).pack(side="right")
        app.context = tk.Text(frame, height=4, bg=INPUT, fg=INK, insertbackground=INK, relief="flat",
                              padx=12, pady=10, wrap="word", undo=True, highlightthickness=1,
                              highlightbackground="#777777", highlightcolor=MINT)
        app.context.pack(fill="x", pady=(0, 12))
        app.context.insert("1.0", app.settings["context"])
        app.context.bind("<<Modified>>", app._context_changed)
        self._label(frame, "페르소나")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(0, 12))
        ttk.Label(row, image=self.photos["persona"]).pack(side="left", padx=(0, 8))
        app.persona_preview = tk.StringVar()
        ttk.Label(row, textvariable=app.persona_preview, wraplength=208, font=(self.family, 8)).pack(side="left")
        ttk.Button(row, text="수정", width=5, command=lambda: self.show("controls")).pack(side="right")
        app.usage_tab = ttk.Frame(frame)
        app.usage_tab.pack(fill="x")
        app._build_usage()
        row = ttk.Frame(self.settings)
        row.place(x=28, y=580, width=364)
        ttk.Button(row, text="설정 적용", command=app.save_settings).pack(side="right")
        ttk.Button(row, text="사용 방식 / 연결", command=lambda: self.show("controls")).pack(side="left")
        ttk.Label(self.settings, textvariable=app.status, wraplength=355, foreground=MUTED,
                  font=(self.family, 8)).place(x=28, y=619, width=364, height=36)

    def _controls(self):
        from apps.desktop.overlay import MODES, DESTINATIONS
        app, frame = self.app, self._content(self.controls)
        app.chat_tab = frame
        self._label(frame, "사용 방식")
        app.mode_var = tk.StringVar(value=next(label for label, value in MODES.items() if value == app.settings["mode"]))
        app.mode_selector = ttk.Combobox(frame, textvariable=app.mode_var, values=list(MODES), state="readonly")
        app.mode_selector.pack(fill="x", pady=(0, 10))
        app.mode_selector.bind("<<ComboboxSelected>>", app._mode_changed)
        self._label(frame, "채팅 표시 위치")
        app.destination_var = tk.StringVar(value=next(label for label, value in DESTINATIONS.items() if value == app.settings["destination"]))
        app.destination_selector = ttk.Combobox(frame, textvariable=app.destination_var, values=list(DESTINATIONS), state="readonly")
        app.destination_selector.pack(fill="x", pady=(0, 10))
        app.destination_selector.bind("<<ComboboxSelected>>", app._destination_changed)
        self._label(frame, "멤버별 페르소나")
        app.persona_rows = []
        for index, variable in enumerate(app.persona_vars):
            row = ttk.Frame(frame)
            ttk.Label(row, text=f"AI {index+1}", width=5).pack(side="left")
            selector = ttk.Combobox(row, textvariable=variable, values=[p["name"] for p in PERSONAS.values()], state="readonly")
            selector.pack(side="left", fill="x", expand=True)
            selector.bind("<<ComboboxSelected>>", lambda _, slot=index: app._refresh_persona_preview(slot))
            app.persona_rows.append(row)
        app.persona_hint = ttk.Label(frame, text="선택한 인원만 채팅을 생성합니다.", foreground=MUTED)
        app.persona_hint.pack(fill="x", pady=(6, 8))
        app.live_controls = ttk.Frame(frame)
        row = ttk.Frame(app.live_controls)
        row.pack(fill="x", pady=(0, 4))
        app.source_var = tk.StringVar()
        app.source_selector = ttk.Combobox(row, textvariable=app.source_var, state="readonly")
        app.source_selector.pack(side="left", fill="x", expand=True)
        app.source_refresh = ttk.Button(row, text="창 새로고침", command=app.refresh_windows)
        app.source_refresh.pack(side="right", padx=(4, 0))
        row = ttk.Frame(app.live_controls)
        row.pack(fill="x")
        app.interval_var, app.duration_var = tk.StringVar(value=str(app.settings["interval"])), tk.StringVar(value=str(app.settings["duration"]))
        ttk.Label(row, text="분석 간격(초)").pack(side="left")
        app.interval_selector = ttk.Combobox(row, textvariable=app.interval_var, values=(3, 5, 10), width=3, state="readonly")
        app.interval_selector.pack(side="left", padx=4)
        ttk.Label(row, text="종료(초)").pack(side="left", padx=(8, 0))
        app.duration_selector = ttk.Combobox(row, textvariable=app.duration_var, values=(30, 60, 120), width=4, state="readonly")
        app.duration_selector.pack(side="left", padx=4)
        app.stop_button = ttk.Button(app.live_controls, text="실시간 중지", command=app.stop_live, state="disabled")
        app.stop_button.pack(fill="x", pady=(6, 0))
        app.live_anchor = ttk.Frame(frame)
        app.live_anchor.pack(fill="x")
        app.capture_hint = tk.StringVar()
        ttk.Label(frame, textvariable=app.capture_hint, foreground=MUTED, wraplength=355, font=(self.family, 8)).pack(fill="x", pady=8)
        app.topmost_var = tk.BooleanVar(value=app.settings["topmost"])
        app.opacity_var = tk.DoubleVar(value=app.settings["opacity"])
        ttk.Checkbutton(frame, text="항상 위에 표시", variable=app.topmost_var).pack(anchor="w")
        self._label(frame, "창 불투명도 (60~100%)")
        ttk.Scale(frame, variable=app.opacity_var, from_=.6, to=1).pack(fill="x")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(10, 6))
        ttk.Button(row, text="서비스 연결 설정", command=app.configure_connection).pack(side="left")
        ttk.Button(row, text="설정 적용", command=app.save_settings).pack(side="right")
        ttk.Label(frame, textvariable=app.status, foreground=MUTED, wraplength=355, font=(self.family, 8)).pack(fill="x", pady=(6, 0))

    def _chat(self):
        app, frame = self.app, self._content(self.chat)
        self._label(frame, "생성된 채팅", font=(self.family, 11, "bold"))
        app.chat_log = scrolledtext.ScrolledText(frame, height=14, wrap="word", state="disabled", relief="flat",
                                                bg=BG, fg=INK, padx=4, pady=4)
        app.chat_log.pack(fill="both", expand=True)
        app.chat_log.tag_configure("name", foreground=MINT, font=(self.family, 9, "bold"))
        app.chat_log.tag_configure("error", foreground="#ff938b")
        ttk.Label(frame, textvariable=app.status, wraplength=355, foreground=MUTED).pack(fill="x", pady=8)
        ttk.Button(frame, text="화면 캡처 / 실시간 시작·중지", command=app.generate).pack(fill="x")

    def refresh(self):
        usage = self.app.service.usage()
        for badge in self.badges:
            badge.configure(text="Demo" if usage and usage["is_demo"] else "Online" if usage else "Offline")
        self.app.trigger_button.itemconfigure(self.app.trigger_button.key_label, text=self.app.settings["hotkey"])
