"""Windows global hotkeys on a dedicated message thread, without keyboard hooks."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
from pathlib import Path
import queue
import sys
import threading


HOTKEYS = {"Ctrl+Alt+Space": (0x0002 | 0x0001, 0x20),
           "Ctrl+Shift+Space": (0x0002 | 0x0004, 0x20),
           "Ctrl+Alt+G": (0x0002 | 0x0001, ord("G"))}


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
        if name not in HOTKEYS:
            return False, "지원하지 않는 단축키입니다."
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
                        modifiers, key = HOTKEYS[name]
                        if user32.RegisterHotKey(None, next_id, modifiers | 0x4000, key):
                            if active_id is not None:
                                user32.UnregisterHotKey(None, active_id)
                            active_id, next_id = next_id, 2 if next_id == 1 else 1
                            self.current = name
                            reply.put((True, ""))
                        else:
                            reply.put((False, "다른 앱이 사용 중인 단축키입니다. 다른 조합을 선택하세요."))
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
