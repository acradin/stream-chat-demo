"""X11 passive key grabs; only the configured shortcut is observed."""
import ctypes as c
import os
import threading
from apps.desktop.mac.hotkey import KEYS as MAC_KEYS, SingleInstance
from apps.desktop.linux.x11 import API, Display, bind, P, U, I

MODIFIERS = {"Ctrl":4, "Alt":8, "Shift":1, "Win":64}
KEYS = {name: name for name in MAC_KEYS}
KEYS.update({"Insert":"Insert", **{f"F{i}":f"F{i}" for i in range(21,25)}})
KEYS.update(dict(Enter="Return", Escape="Escape", Space="space", Backspace="BackSpace",
                 PageUp="Prior", PageDown="Next", Minus="minus", Equals="equal", Comma="comma",
                 Period="period", Slash="slash", Backslash="backslash", Semicolon="semicolon",
                 Quote="apostrophe", BracketLeft="bracketleft", BracketRight="bracketright", Backtick="grave"))
KEYS.update({f"Num{i}":f"KP_{i}" for i in range(10)})
KEYS.update({"Num"+key:"KP_"+key for key in ("Enter", "Multiply", "Add", "Subtract", "Decimal", "Divide")})
ALIASES = {name.casefold():name for name in (*MODIFIERS, *KEYS)}
ALIASES.update(control="Ctrl", super="Win", windows="Win", cmd="Win", command="Win",
               option="Alt", return_="Enter", esc="Escape", spacebar="Space", pgup="PageUp", pgdn="PageDown", ins="Insert", **{"return":"Enter"})
bind(API,"XStringToKeysym",U,[c.c_char_p])
bind(API,"XKeysymToKeycode",c.c_ubyte,[P,U])
bind(API,"XGrabKey",I,[P,I,c.c_uint,U,I,I,I])
bind(API,"XUngrabKey",I,[P,I,c.c_uint,U])
bind(API,"XPending",I,[P])
bind(API,"XNextEvent",I,[P,P])
bind(API,"XkbSetDetectableAutoRepeat",I,[P,I,c.POINTER(I)])


class KeyEvent(c.Structure):
    _fields_ = [("type",I),("serial",U),("send_event",I),("display",P),
                ("window",U),("root",U),("subwindow",U),("time",U),
                ("x",I),("y",I),("x_root",I),("y_root",I),
                ("state",c.c_uint),("keycode",c.c_uint),("same_screen",I)]


class Event(c.Union):
    _fields_ = [("key",KeyEvent),("padding",c.c_long*24)]


def parse_hotkey(value):
    if not isinstance(value,str):
        raise ValueError("단축키 조합을 입력해주세요.")
    parts = [ALIASES.get(part.strip().casefold()) for part in value.split("+")]
    keys = [part for part in parts if part not in MODIFIERS]
    if None in parts or len(set(parts)) != len(parts) or len(keys) != 1:
        raise ValueError("단축키를 확인해주세요. 예: Ctrl+Shift+G 또는 F8")
    key = keys[0]
    mods = [name for name in MODIFIERS if name in parts]
    if not mods and not (key.startswith("F") and key[1:].isdigit()):
        raise ValueError("일반 키에는 Ctrl/Alt/Shift/Win을 함께 눌러주세요.")
    symbol = API.XStringToKeysym(KEYS[key].encode())
    if not symbol:
        raise ValueError("이 키를 사용할 수 없습니다.")
    return "+".join([*mods,key]),sum(MODIFIERS[name] for name in mods),symbol


def pressed_hotkey(keycode,event=None):
    if event is None:
        return None
    key = next((name for name,symbol in KEYS.items() if symbol.casefold() == event.keysym.casefold()),None)
    if key is None:
        return None
    mods = [name for name,mask in MODIFIERS.items() if event.state & mask]
    return parse_hotkey("+".join([*mods,key]))[0]


class GlobalHotkey:
    def __init__(self,callback):
        self.callback, self.current = callback,None
        self.display, self.thread, self.binding = None,None,None
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.down = False
        self.locks = {0,2,16,18}  # CapsLock + the standard X11 NumLock modifier.

    def replace(self,name):
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
            return False,"Wayland/WSLg 전역 단축키는 아직 지원하지 않습니다. 생성 버튼 또는 Linux X11 세션을 사용해주세요."
        try:
            name,mods,symbol = parse_hotkey(name)
            with self.lock:
                if name == self.current:
                    return True,""
                if self.display is None:
                    self.display = Display().__enter__()
                    supported = I()
                    if not API.XkbSetDetectableAutoRepeat(self.display.pointer,True,c.byref(supported)) or not supported.value:
                        self.display.__exit__()
                        self.display = None
                        return False,"현재 X11 서버의 단축키 반복 방지 기능을 사용할 수 없습니다. 생성 버튼을 사용해주세요."
                d = self.display
                key = API.XKeysymToKeycode(d.pointer,symbol)
                if not key:
                    return False,"현재 키보드 배열에 해당 키가 없습니다."
                new = {(key,mods|mask) for mask in self.locks}
                old = self.binding or set()
                for code,mask in new-old:
                    API.XGrabKey(d.pointer,code,mask,d.root,False,1,1)
                try:
                    d.check()
                except ValueError:
                    for code,mask in new-old:
                        API.XUngrabKey(d.pointer,code,mask,d.root)
                    d.check()
                    return False,"다른 앱이 사용 중인 단축키입니다. 기존 단축키는 유지됩니다."
                for code,mask in old-new:
                    API.XUngrabKey(d.pointer,code,mask,d.root)
                d.check()
                self.current,self.binding,self.down = name,new,False
                if self.thread is None:
                    self.thread = threading.Thread(target=self._run,daemon=True,name="tiki-x11-hotkey")
                    self.thread.start()
            return True,""
        except (ValueError,OSError) as exc:
            return False,str(exc)

    def _run(self):
        event = Event()
        while not self.stopping.wait(.02):
            fire = False
            with self.lock:
                d = self.display
                while API.XPending(d.pointer):
                    API.XNextEvent(d.pointer,c.byref(event))
                    if event.key.type == 3:
                        self.down = False
                    elif event.key.type == 2 and (event.key.keycode,event.key.state & 255) in self.binding:
                        fire = fire or not self.down
                        self.down = True
            if fire:
                self.callback()

    def close(self):
        self.stopping.set()
        if self.thread is not None:
            self.thread.join(timeout=1)
        with self.lock:
            if self.display is not None:
                self.display.__exit__()
            self.display,self.current,self.binding = None,None,None
