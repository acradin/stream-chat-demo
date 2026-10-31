"""Windows global hotkeys on a dedicated message thread, without keyboard hooks."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
from pathlib import Path
import queue
import sys
import threading


MODIFIERS = {"Ctrl": 0x0002, "Alt": 0x0001, "Shift": 0x0004, "Win": 0x0008}
KEYS = {**{chr(code): code for code in range(ord("A"), ord("Z") + 1)},
        **{str(number): ord(str(number)) for number in range(10)},
        **{f"F{number}": 0x6F + number for number in range(1, 25)},
        **{f"Num{number}": 0x60 + number for number in range(10)},
        "Space": 0x20, "Tab": 0x09, "Enter": 0x0D, "Escape": 0x1B,
        "Backspace": 0x08, "Delete": 0x2E, "Insert": 0x2D, "Home": 0x24,
        "End": 0x23, "PageUp": 0x21, "PageDown": 0x22,
        "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28,
        "Minus": 0xBD, "Equals": 0xBB, "Comma": 0xBC, "Period": 0xBE,
        "Slash": 0xBF, "Backslash": 0xDC, "Semicolon": 0xBA, "Quote": 0xDE,
        "BracketLeft": 0xDB, "BracketRight": 0xDD, "Backtick": 0xC0,
        "NumMultiply": 0x6A, "NumAdd": 0x6B, "NumSubtract": 0x6D,
        "NumDecimal": 0x6E, "NumDivide": 0x6F}
ALIASES = {name.casefold(): name for name in (*MODIFIERS, *KEYS)}
ALIASES.update({"control": "Ctrl", "windows": "Win", "super": "Win", "return": "Enter",
                "esc": "Escape", "spacebar": "Space", "pgup": "PageUp", "pgdn": "PageDown",
                "del": "Delete", "ins": "Insert"})


def parse_hotkey(value):
    if not isinstance(value, str):
        raise ValueError("단축키 조합을 입력해주세요.")
    parts = [ALIASES.get(part.strip().casefold()) for part in value.split("+")]
    if not parts or None in parts or len(set(parts)) != len(parts):
        raise ValueError("단축키를 확인해주세요. 예: Ctrl+Shift+G 또는 F8")
    keys = [part for part in parts if part not in MODIFIERS]
    if len(keys) != 1:
        raise ValueError("Ctrl/Alt/Shift/Win과 함께 사용할 키 하나를 지정해주세요.")
    key = keys[0]
    if key == "F12":
        raise ValueError("F12는 Windows에서 예약된 키입니다. 다른 키를 지정해주세요.")
    modifiers = [name for name in MODIFIERS if name in parts]
    if not modifiers and not (key.startswith("F") and key[1:].isdigit()):
        raise ValueError("문자·숫자·일반 키에는 Ctrl/Alt/Shift/Win을 함께 눌러주세요. F키는 단독으로 사용할 수 있습니다.")
    return "+".join([*modifiers, key]), sum(MODIFIERS[name] for name in modifiers), KEYS[key]


def pressed_hotkey(keycode, event=None):
    """Read only while the focused shortcut field is recording; no keyboard hook."""
    if keycode in (0x10, 0x11, 0x12, 0x5B, 0x5C, *range(0xA0, 0xA6)):
        return None
    key = next((name for name, code in KEYS.items() if code == keycode), None)
    if key is None:
        raise ValueError("이 키는 단축키로 사용할 수 없습니다. 다른 키를 눌러주세요.")
    get_state = ctypes.WinDLL("user32").GetKeyState
    get_state.argtypes, get_state.restype = [ctypes.c_int], ctypes.c_short
    modifiers = [name for name, codes in (("Ctrl", (0x11,)), ("Alt", (0x12,)),
                 ("Shift", (0x10,)), ("Win", (0x5B, 0x5C)))
                 if any(get_state(code) & 0x8000 for code in codes)]
    return parse_hotkey("+".join([*modifiers, key]))[0]


class SingleInstance:
    """Prevent two processes sharing one settings/usage directory on Windows."""
    def __init__(self, state_dir: Path):
        self.handle = None
        if sys.platform != "win32":
            return
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        suffix = hashlib.sha256(str(state_dir.resolve()).casefold().encode()).hexdigest()[:24]
        self.handle = self.kernel.CreateMutexW(None, False, "Local\\StreamChatDemo-" + suffix)
        if not self.handle:
            raise OSError("앱 실행 잠금을 만들지 못했습니다.")
        if ctypes.get_last_error() == 183:
            self.close()
            raise ValueError("이 오버레이가 이미 실행 중입니다. 기존 창을 사용해주세요.")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class GlobalHotkey:
    def __init__(self, callback):
        self.callback = callback
        self.commands = queue.Queue()
        self.stopping = threading.Event()
        self.current = None
        self.thread = None
        if sys.platform == "win32":
            self.thread = threading.Thread(target=self._run, name="overlay-hotkey", daemon=True)
            self.thread.start()

    def replace(self, name: str) -> tuple[bool, str]:
        try:
            name, _, _ = parse_hotkey(name)
        except ValueError as exc:
            return False, str(exc)
        if self.thread is None:
            return False, "전역 단축키는 Windows에서 지원합니다. 창 안에서는 Ctrl+Enter를 사용하세요."
        reply = queue.Queue(maxsize=1)
        self.commands.put((name, reply))
        try:
            return reply.get(timeout=2)
        except queue.Empty:
            return False, "단축키 등록 응답이 없습니다. 생성 버튼을 사용하세요."

    def _run(self):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.UnregisterHotKey.restype = wintypes.BOOL
        user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                      wintypes.UINT, wintypes.UINT, wintypes.UINT]
        user32.PeekMessageW.restype = wintypes.BOOL
        active_id = None
        next_id = 1
        message = wintypes.MSG()
        try:
            while not self.stopping.is_set():
                try:
                    name, reply = self.commands.get_nowait()
                    if name == self.current:
                        reply.put((True, ""))
                    else:
                        _, modifiers, key = parse_hotkey(name)
                        if user32.RegisterHotKey(None, next_id, modifiers | 0x4000, key):
                            if active_id is not None:
                                user32.UnregisterHotKey(None, active_id)
                            active_id, next_id = next_id, 2 if next_id == 1 else 1
                            self.current = name
                            reply.put((True, ""))
                        else:
                            reply.put((False, "다른 앱이 사용 중이거나 Windows가 예약한 단축키입니다. 기존 단축키는 유지됩니다."))
                except queue.Empty:
                    pass
                while user32.PeekMessageW(ctypes.byref(message), None, 0x0312, 0x0312, 1):
                    if message.wParam == active_id:
                        self.callback()
                self.stopping.wait(.02)
        finally:
            if active_id is not None:
                user32.UnregisterHotKey(None, active_id)

    def close(self):
        self.stopping.set()
        if self.thread is not None:
            self.thread.join(timeout=1)
