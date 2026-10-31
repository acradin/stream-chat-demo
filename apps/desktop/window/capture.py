"""Explicit-trigger desktop screenshot capture. No files or network I/O."""

import io
import ctypes
from ctypes import wintypes
import os
import sys

from PIL import Image, ImageGrab
from apps.desktop.capture_types import WindowSource


def _user32():
    if sys.platform != "win32":
        raise ValueError("창 선택 캡처는 Windows에서 사용할 수 있습니다.")
    api = ctypes.WinDLL("user32", use_last_error=True)
    for name in ("IsWindow", "IsWindowVisible", "IsIconic"):
        getattr(api, name).argtypes = [wintypes.HWND]
        getattr(api, name).restype = wintypes.BOOL
    api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    api.GetWindowThreadProcessId.restype = wintypes.DWORD
    api.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    api.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    api.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    api.GetWindowLongW.restype = wintypes.LONG
    return api


def _window_info(handle):
    api = _user32()
    if not api.IsWindow(handle) or not api.IsWindowVisible(handle) or api.IsIconic(handle):
        return None
    pid = wintypes.DWORD()
    api.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    if pid.value == os.getpid() or api.GetWindowLongW(handle, -20) & 0x80:
        return None
    length = api.GetWindowTextLengthW(handle)
    if length <= 0:
        return None
    title = ctypes.create_unicode_buffer(length + 1)
    api.GetWindowTextW(handle, title, len(title))
    return WindowSource(int(handle), pid.value, title.value)


def list_windows():
    """Enumerate visible app windows; never capture pixels while listing."""
    api = _user32()
    windows = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(handle, parameter):
        source = _window_info(handle)
        if source is not None:
            windows.append(source)
        return True
    callback = callback_type(visit)
    api.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    api.EnumWindows.restype = wintypes.BOOL
    if not api.EnumWindows(callback, 0):
        raise ValueError("열려 있는 창 목록을 불러오지 못했습니다.")
    return sorted(windows, key=lambda source: source.title.casefold())


def capture_window(source: WindowSource) -> bytes:
    current = _window_info(source.handle)
    if current is None or current.pid != source.pid:
        raise ValueError("선택한 창이 닫히거나 최소화됐습니다. 창을 다시 선택해주세요.")
    # A window handle is mandatory: never fall back to the whole screen.
    try:
        with ImageGrab.grab(window=source.handle) as grabbed:
            image = grabbed.convert("RGB")
        try:
            image.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            stream = io.BytesIO()
            image.save(stream, format="JPEG", quality=75)
            return stream.getvalue()
        finally:
            image.close()
    except (OSError, TypeError):
        raise ValueError("이 창을 캡처할 수 없습니다. 창 모드의 게임이나 OBS 미리보기 창을 선택해주세요.") from None


def capture_primary_screen() -> bytes:
    with ImageGrab.grab(all_screens=False) as source:
        image = source.convert("RGB")
    try:
        image.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
        stream = io.BytesIO()
        image.save(stream, format="JPEG", quality=85)
        return stream.getvalue()
    finally:
        image.close()
