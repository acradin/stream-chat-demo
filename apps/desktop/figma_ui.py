"""Native Tk implementation of the Figma main/settings screens.

UI only: generation, delivery, usage, persistence and hotkeys stay in Overlay.
The additional controls/log pages preserve capabilities absent from the mockup.
"""

import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, font, messagebox

from PIL import Image, ImageTk

from apps.desktop.branding import ASSETS, apply_window_icon
from apps.desktop.shell import configure_window, mapped
from apps.desktop.panel import Panel, BG, INPUT, INK, MUTED, MINT, configure_theme
from backend.personas import PERSONAS
from apps.desktop.design_widgets import DesignButton, field, surface
from apps.desktop.display import display_scale, scale_layout
from apps.desktop.vector import draw as draw_vector, StatusBadge
from apps.desktop.count_slider import CountSlider

PERSONA_ASSETS = {"witty_friend": "persona-witty", "analyst": "persona-analyst",
                  "coach": "persona-coach", "hype_commentator": "persona-reaction",
                  "chatter": "persona-chatter", "warm_supporter": "persona-supporter"}


def asset(master, name):
    source = "v2-" + name
    with Image.open(ASSETS / "figma" / (source + ".png")) as image:
        original = image.convert("RGBA")
        high_resolution = ASSETS / "figma" / (source + "@3x.png")
        if high_resolution.is_file():
            with Image.open(high_resolution) as high:
                original = high.convert("RGBA")
        if name in ("orb-base", "orb-glow"):
            image = image.resize((image.width//2, image.height//2), Image.Resampling.LANCZOS)
            image.putalpha(image.getchannel("A").point(lambda alpha: round(alpha * .72)))
            original.putalpha(original.getchannel("A").point(lambda alpha: round(alpha * .72)))
        photo = ImageTk.PhotoImage(image, master=master)
        root = master.winfo_toplevel()
        if not hasattr(root,"_design_image_sources"):
            root._design_image_sources = {}
        root._design_image_sources[str(photo)] = original
        return photo


class GenerateOrb(tk.Canvas):
    def __init__(self, master, app):
        super().__init__(master, width=198, height=198, bg=BG, highlightthickness=0,
                         takefocus=1, cursor="hand2")
        self.app, self.disabled = app, False
        self.photos = [asset(self, name) for name in ("orb-base", "orb-glow")]
        self.create_image(99, 100, image=self.photos[0])
        self.create_image(99, 99, image=self.photos[1])
        draw_vector(self, "orb-face", 57, 40)
        self.key_label = self.create_text(99, 127, fill=INK, font=(app.view.semibold, -16),
                                          text=app.settings["hotkey"])
        self.caption = self.create_text(99, 146, fill=INK, font=(app.view.family, -8), text="채팅을 생성하세요!")
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
        self.scale = 1.0
        app.view = self
        self.family = configure_theme(self.root)
        self.semibold = "Pretendard SemiBold" if "Pretendard SemiBold" in font.families(self.root) else self.family
        self.root.title("tiki")
        self.root.resizable(False, False)
        self.root.minsize(1, 1)
        configure_window(self.root)
        # Linux retains WM management for topmost/minimize, with Motif decorations disabled.
        self.root.overrideredirect(sys.platform == "win32")
        self.root.bind("<Map>", self._mapped, add="+")
        self.root.bind("<Alt-F4>", lambda _: app.close())
        self.root.bind("<Escape>", self._escape)
        self.pages = {}
        self.current = "main"
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.withdraw()
        self.settings_window.title("tiki — 설정")
        self.settings_window.transient(self.root)
        self.settings_window.resizable(False, False)
        configure_window(self.settings_window)
        self.settings_window.overrideredirect(sys.platform == "win32")
        self.settings_window.protocol("WM_DELETE_WINDOW", self.close_settings)
        self.settings_window.bind("<Escape>", self._escape)
        self.settings_window.bind("<Map>", self._settings_mapped, add="+")
        self.photos = {name: asset(self.root, name) for name in PERSONA_ASSETS.values()}
        for key, name in PERSONA_ASSETS.items():
            self.photos["member-"+key] = ImageTk.PhotoImage(
                ImageTk.getimage(self.photos[name]).resize((38,36), Image.Resampling.LANCZOS), master=self.root)
        self.main = self._page("main", 277, 347)
        self.settings = self._page("settings", 420, 540)
        self.controls = self._page("controls", 420, 690)
        self.chat = self._page("chat", 420, 530)
        self.chzzk = self._page("chzzk", 420, 620)
        self._main()
        self._settings()
        self._controls()
        self._chat()
        self._chzzk()
        self._menu()
        from apps.desktop.onboarding import Onboarding
        self.onboarding = Onboarding(self)
        factor = display_scale(self.root)
        scale_layout(self.root, factor, self.photos.values())
        self.scale = factor
        self.root._tiki_display_scale = factor
        self.settings_window._tiki_display_scale = factor
        scaled = getattr(self.root,"_scaled_design_images",{})
        self.photos = {name:scaled.get(str(photo),photo) for name,photo in self.photos.items()}
        self.show("main" if app.settings["onboarding_complete"] else "start")
        self.root.bind("<Configure>", self._shape_changed, add="+")
        self.settings_window.bind("<Configure>", self._shape_changed, add="+")
        apply_window_icon(self.root)

    def _shape_changed(self, event):
        window = event.widget
        if window in (self.root, self.settings_window) and window.state() == "normal":
            mapped(window)

    def _page(self, name, width, height, *, variant="main", header=True):
        page = Panel(self.settings_window if name == "settings" else self.root,
                     width, height, settings=name == "settings", variant=variant)
        self.pages[name] = page
        if header:
            logo = draw_vector(page, "header", 28, 28)
            page.tag_bind(logo,"<Button-1>",self.open_menu)
            badge = StatusBadge(page, 105, 32, self.family)
        # The badge is truthful: service status switches it after usage returns.
        if not hasattr(self, "badges"):
            self.badges = []
        if header:
            self.badges.append(badge)
        if name == "main":
            button = tk.Canvas(page, bg=BG, highlightthickness=0, bd=0,
                               cursor="hand2", takefocus=1)
            draw_vector(button, "settings", 3, 3)
            button.bind("<Button-1>", lambda _: self.show("settings"))
            button.bind("<Return>", lambda _: self.show("settings"))
            button.bind("<space>", lambda _: self.show("settings"))
            button.place(x=194, y=28, width=21, height=21)
            self.settings_button = button
        elif header and name != "settings":
            ttk.Button(page, text="‹", width=2, command=lambda: self.show("main")).place(x=width-112, y=21)
        for x, color, command, symbol in ((width-53, "#ff736a", self.close_settings if name == "settings" else self.app.close, "×"),
                                          (width-36, "#febc2e", self.minimize_settings if name == "settings" else self.minimize, "−")):
            top = 30 if not header else 33
            dot = page.create_oval(x, top, x+10, top+10, fill=color, outline="")
            page.tag_bind(dot,"<Button-1>",lambda _,action=command: action())
        page.bind("<Button-3>", self.open_menu)
        page.bind("<ButtonPress-1>", self._drag_start)
        page.bind("<B1-Motion>", self._drag)
        return page

    def text(self,page,x,y,text,size=14,*,anchor="nw",weight=False,fill=INK,width=0):
        return page.create_text(x,y,text=text,anchor=anchor,fill=fill,
                                font=(self.semibold if weight else self.family,-size),width=width)

    def _menu(self):
        self.menu = tk.Menu(self.root,tearoff=False)
        for title,name in (("메인","main"),("설정","settings"),("사용 방식 / 서비스 연결","controls"),("채팅 보기","chat"),("치지직 전송","chzzk")):
            self.menu.add_command(label=title,command=lambda page=name: self.show(page))
        self.menu.add_separator()
        self.menu.add_command(label="설정 적용",command=self.app.save_settings)
        self.menu.add_command(label="치지직 연결 확인",command=self.app.refresh_channel)
        self.menu.add_command(label="시작 안내 다시 보기",command=lambda: self.onboarding.start())
        self.menu.add_command(label="종료",command=self.app.close)

    def open_menu(self,event):
        if hasattr(self,"menu"):
            try:
                self.menu.tk_popup(event.x_root,event.y_root)
            finally:
                self.menu.grab_release()
        return "break"

    def _escape(self,event):
        if not self.app.recording_hotkey:
            self.show("main")

    def _drag_start(self, event):
        window = event.widget.winfo_toplevel()
        self.drag = (window, event.x_root-window.winfo_x(), event.y_root-window.winfo_y()) if event.y < 62*self.scale else None

    def _drag(self, event):
        if getattr(self, "drag", None):
            window, x, y = self.drag
            window.geometry(f"+{event.x_root-x}+{event.y_root-y}")

    def _settings_mapped(self, event):
        if event.widget is self.settings_window and self.settings_window.state() == "normal":
            self.settings_window.overrideredirect(sys.platform == "win32")
            mapped(self.settings_window)

    def minimize_settings(self):
        if self.close_settings():
            self.current = "main"

    def close_settings(self):
        if self.settings_window.state() == "withdrawn":
            return True
        if not self.app.save_settings():
            messagebox.showerror("설정 확인", self.app.status.get(), parent=self.settings_window)
            return False
        if self.app.recording_hotkey:
            self.app._finish_hotkey_recording()
        self.settings_window.withdraw()
        self.current = "main"
        return True

    def open_settings(self):
        if self.settings_window.state() != "withdrawn":
            self.settings_window.lift()
            return
        self.show("main")
        self.settings.pack()
        self.root.update_idletasks()
        width, height = int(self.settings.cget("width")), int(self.settings.cget("height"))
        screen_width = self.root.winfo_screenwidth()
        x = self.root.winfo_x()+self.root.winfo_width()+12
        if x+width > screen_width:
            x = max(0, self.root.winfo_x()-width-12)
        y = max(0, min(self.root.winfo_y(), self.root.winfo_screenheight()-height-40))
        self.settings_window.geometry(f"{width}x{height}+{x}+{y}")
        self.settings_window.attributes("-topmost", self.root.attributes("-topmost"))
        self.settings_window.attributes("-alpha", self.root.attributes("-alpha"))
        # Export/packaged self-tests intentionally keep the root withdrawn.
        if self.root.state() != "withdrawn":
            self.settings_window.deiconify()
            self.settings_window.lift()
            self.settings_window.focus_set()
        self.current = "settings"

    def _mapped(self, event):
        if event.widget is self.root and self.root.state() == "normal":
            self.root.overrideredirect(sys.platform == "win32")
            # Keep a frameless native window available in taskbar and Alt+Tab.
            mapped(self.root)
            apply_window_icon(self.root)

    def minimize(self):
        self.root.overrideredirect(False)
        self.root.iconify()

    def show(self, name):
        if name not in self.pages:
            return
        if name == "settings":
            self.open_settings()
            return
        if not self.close_settings():
            return
        if self.app.recording_hotkey and name != "settings":
            self.app._finish_hotkey_recording()
        for key, page in self.pages.items():
            if key != "settings":
                page.pack_forget()
        self.current = name
        page = self.pages[name]
        page.pack()
        width,height = int(page.cget("width")),int(page.cget("height"))
        x = max(0,min(self.root.winfo_x(),self.root.winfo_screenwidth()-width))
        y = max(0,min(self.root.winfo_y(),self.root.winfo_screenheight()-height-40))
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _content(self, page, y=66, bottom=24):
        width = int(page.cget("width"))-56
        height = int(page.cget("height"))-y-bottom
        if page in (self.chat, self.chzzk):
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
                    delta = event.delta if sys.platform == "darwin" else event.delta/120
                    viewport.yview_scroll(-int(delta), "units")
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
        app.trigger_button.place(x=40, y=45)
        self.text(self.main,50,239,"채팅 멤버")
        ttk.Label(self.main,textvariable=app.count_text,font=(self.family,-14)).place(x=200,y=237,width=30,height=20)
        self.count = tk.IntVar(value=app.settings["count"])
        self.slider = CountSlider(self.main,self._count_changed)
        self.slider.place(x=48,y=267)
        self.slider_active, self.slider_knob = self.slider.active, self.slider.knob
        self.count.trace_add("write",lambda *_:self._draw_count())
        self._draw_count()
        self.chat_button = DesignButton(self.main,self,"채팅 보기",lambda:self.show("chat"),28,305,107,29)
        self.chzzk_button = DesignButton(self.main,self,"치지직 전송",lambda:self.show("chzzk"),142,305,107,29)

    def _count_changed(self, value):
        self.count.set(value)
        self.app.change_count(value-self.app.settings["count"])

    def _draw_count(self):
        self.slider.set_value(self.count.get())

    def _settings(self):
        app, page = self.app, self.settings
        app.settings_tab = page
        self.text(page,32,65,"방송 링크")
        app.channel_var = tk.StringVar(value=app.settings["channel_url"])
        app.channel_entry = field(page,self,31,89,359,31,variable=app.channel_var,placeholder="https://chzzk.naver.com/")
        app.channel_info = tk.StringVar()
        app.channel_var.trace_add("write",lambda *_:app._channel_link_changed())
        self.text(page,30,136,"단축키 설정")
        app.hotkey_var = tk.StringVar(value=app.settings["hotkey"])
        app.hotkey_entry = field(page,self,31,160,180,31,variable=app.hotkey_var,opacity=.3,component="Shortcut/KeyDisplay")
        app.hotkey_entry.configure(justify="center")
        app.hotkey_entry.bind("<KeyPress>",app._capture_hotkey)
        app.hotkey_entry.bind("<FocusOut>",app._hotkey_focus_lost)
        app.hotkey_record = DesignButton(page,self,"변경",app.record_hotkey,311,161,height=29)
        app.hotkey_hint = tk.StringVar(value="키 조합을 입력하고 메인으로 돌아가면 저장됩니다.")
        tk.Label(page,textvariable=app.hotkey_hint,bg=BG,fg=MUTED,font=(self.family,-8),anchor="w").place(x=31,y=193,width=358,height=11)
        self.text(page,30,210,"방송 설명")
        app.context = field(page,self,28,227,364,92,multiline=True,component="Settings/Description")
        app.context.insert("1.0",app.settings["context"])
        app.context.bind("<<Modified>>",app._context_changed)
        draw_vector(app.context.design_surface,"edit",329,14)
        counter = tk.Label(app.context.design_surface,textvariable=app.context_count,bg=app.context.cget("bg"),fg=INK,font=(self.family,-8))
        counter.place(x=275,y=70,width=74,height=12)
        self.persona_heading = self.text(page,30,331,"페르소나")
        self.persona_image = page.create_image(28,355,anchor="nw",image=self.photos["persona-witty"])
        self.persona_title = self.text(page,89,355,"")
        self.persona_description = self.text(page,89,375,"",12,fill="#eaeaea",width=210)
        app.persona_preview = tk.StringVar()
        DesignButton(page,self,"수정",lambda:self.onboarding.select_personas(),313,329,height=29)
        self.persona_members = []
        for index in range(5):
            x = 28+72*index
            avatar = page.create_image(x,359,anchor="nw",image=self.photos["member-witty_friend"],state="hidden")
            label = page.create_text(x+19,403,text="",anchor="center",fill=INK,font=(self.family,-8),state="hidden")
            self.persona_members.append((avatar,label))
        self.text(page,30,415,"사용량")
        self.usage_caption = self.text(page,30,439,"이번 달 생성 요청",8)
        self.usage_value = self.text(page,372,439,"—",8,anchor="ne")
        self.usage_track = page.create_line(32,459,370,459,width=8,capstyle="round",fill="#3c3e40")
        # There is no server quota contract yet; an empty rail must not imply a made-up limit.
        for item in (self.usage_caption,self.usage_value,self.usage_track):
            page.tag_bind(item,"<Button-1>",lambda _:self.show("controls"))
        tk.Label(page,textvariable=app.status,bg=BG,fg=MUTED,font=(self.family,-9),anchor="w",justify="left",wraplength=260).place(x=28,y=486,width=270,height=38)
        self.save_button = DesignButton(page,self,"저장",self.save_settings,311,493,height=29)

    def save_settings(self):
        if not self.app.save_settings():
            messagebox.showerror("설정 확인", self.app.status.get(), parent=self.settings_window)
            return False
        return True

    def refresh_persona(self,index=0):
        selected = self.app.persona_vars[index].get()
        key = next(key for key,p in PERSONAS.items() if p["name"] == selected)
        persona = PERSONAS[key]
        self.settings.itemconfigure(self.persona_title,text=persona["name"])
        self.settings.itemconfigure(self.persona_description,text=persona["description"])
        self.settings.itemconfigure(self.persona_image,image=self.photos[PERSONA_ASSETS.get(key,"persona-witty")])
        count = self.app.settings["count"]
        multiple = count > 1
        self.settings.itemconfigure(self.persona_heading,text=f"페르소나 · {count}명")
        for item in (self.persona_image,self.persona_title,self.persona_description):
            self.settings.itemconfigure(item,state="hidden" if multiple else "normal")
        by_name = {p["name"]:key for key,p in PERSONAS.items()}
        for slot,(avatar,label) in enumerate(self.persona_members):
            visible = multiple and slot < count
            name = self.app.persona_vars[slot].get()
            member = by_name[name]
            self.settings.itemconfigure(avatar,image=self.photos["member-"+(member if member in PERSONA_ASSETS else "witty_friend")],state="normal" if visible else "hidden")
            self.settings.itemconfigure(label,text=name,state="normal" if visible else "hidden")

    def refresh_usage(self,usage):
        label = "이번 달 생성 요청" + (" · 데모" if usage and usage["is_demo"] else "")
        if self.app.usage_error:
            label = "최근 확인한 사용량 · 연결 확인 필요"
        self.settings.itemconfigure(self.usage_caption,text=label)
        self.settings.itemconfigure(self.usage_value,text=f"{usage['generation_requests']:,}회 · 한도 미설정" if usage else "확인 중")

    def _controls(self):
        from apps.desktop.overlay import MODES
        app, frame = self.app, self._content(self.controls)
        app.chat_tab = frame
        ttk.Button(frame,text="치지직 인증 / 전송 설정",command=lambda:self.show("chzzk")).pack(fill="x",pady=(0,8))
        ttk.Label(frame,textvariable=app.hotkey_hint,wraplength=350,foreground=MUTED).pack(fill="x",pady=6)
        self._label(frame, "사용 방식")
        app.mode_var = tk.StringVar(value=next(label for label, value in MODES.items() if value == app.settings["mode"]))
        app.mode_selector = ttk.Combobox(frame, textvariable=app.mode_var, values=list(MODES), state="readonly")
        app.mode_selector.pack(fill="x", pady=(0, 10))
        app.mode_selector.bind("<<ComboboxSelected>>", app._mode_changed)
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

        app.usage_tab = ttk.Frame(frame)
        app.usage_tab.pack(fill="x",pady=12)
        app._build_usage()

    def _chat(self):
        app, frame = self.app, self._content(self.chat)
        self._label(frame, "생성된 채팅", font=(self.family, 11, "bold"))
        self._label(frame, "전송 여부와 관계없이 생성된 채팅을 모아 보여줍니다.", foreground=MUTED, wraplength=355)
        app.chat_log = scrolledtext.ScrolledText(frame, height=14, wrap="word", state="disabled", relief="flat",
                                                bg=BG, fg=INK, padx=4, pady=4)
        app.chat_log.pack(fill="both", expand=True)
        app.chat_log.tag_configure("name", foreground=MINT, font=(self.family, 9, "bold"))
        app.chat_log.tag_configure("error", foreground="#ff938b")
        ttk.Label(frame, textvariable=app.status, wraplength=355, foreground=MUTED).pack(fill="x", pady=8)
        ttk.Button(frame, text="화면 캡처 / 실시간 시작·중지", command=app.generate).pack(fill="x")

    def _chzzk(self):
        from apps.desktop.overlay import DESTINATIONS
        app, frame = self.app, self._content(self.chzzk)
        self._label(frame,"치지직 전송",font=(self.family,11,"bold"))
        self._label(frame,"방송 계정으로 인증한 뒤 전송을 켜세요.\n생성된 채팅은 앱에서도 항상 볼 수 있습니다.",foreground=MUTED)
        self._label(frame,"방송 링크")
        app.delivery_channel_entry = ttk.Entry(frame,textvariable=app.channel_var)
        app.delivery_channel_entry.pack(fill="x",pady=(0,8))
        app.channel_controls = ttk.Frame(frame)
        app.channel_controls.pack(fill="x")
        app.channel_authorize = ttk.Button(app.channel_controls,text="치지직 인증",command=app.authorize_channel)
        app.channel_authorize.pack(side="left")
        app.channel_check = ttk.Button(app.channel_controls,text="연결 확인",command=app.refresh_channel)
        app.channel_check.pack(side="left",padx=6)
        app.auth_copy = ttk.Button(app.channel_controls,text="인증 링크 복사",command=app.copy_authorization_link,state="disabled")
        app.auth_copy.pack(side="right")
        ttk.Label(frame,textvariable=app.channel_info,wraplength=355).pack(fill="x",pady=(8,4))
        app.auth_info = tk.StringVar(value="인증 버튼을 누르면 브라우저에서 치지직 승인을 진행합니다.")
        ttk.Label(frame,textvariable=app.auth_info,wraplength=355,foreground=MUTED).pack(fill="x",pady=(0,8))
        app.destination_var = tk.StringVar(value=next(label for label,value in DESTINATIONS.items() if value == app.settings["destination"]))
        app.send_enabled = tk.BooleanVar(value=app.settings["destination"] == "chzzk")
        app.destination_selector = ttk.Checkbutton(frame,text="치지직으로 전송",variable=app.send_enabled,command=app.toggle_delivery)
        app.destination_selector.pack(anchor="w",pady=(0,4))
        self._label(frame,"켜면 다음 생성부터 방송에 전송합니다. 관찰 중에는 먼저 중지해주세요.",foreground=MUTED,wraplength=355)
        ttk.Button(frame,text="실시간 관찰 중지",command=app.stop_live).pack(fill="x",pady=(0,8))
        self._label(frame,"전송 내역",font=(self.family,10,"bold"))
        app.delivery_log = scrolledtext.ScrolledText(frame,height=5,wrap="word",state="disabled",relief="flat",bg=BG,fg=INK,padx=4,pady=4)
        app.delivery_log.pack(fill="both",expand=True)
        app.delivery_log.tag_configure("name",foreground=MINT)
        app.delivery_log.tag_configure("error",foreground="#ff938b")

    def refresh(self):
        usage = self.app.service.usage()
        for badge in self.badges:
            badge.configure(text="• Demo" if usage and usage["is_demo"] else "• Online" if usage else "• Offline")
        self.app.trigger_button.itemconfigure(self.app.trigger_button.key_label, text=self.app.settings["hotkey"])
