"""Shared branding for source runs and the packaged desktop application."""

import ctypes
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
import tkinter as tk
import uuid


ASSETS = Path(__file__).resolve().parents[1] / "assets"
APP_ID = "StreamChat.Desktop"


class _PropertyKey(ctypes.Structure):
    _fields_ = [("format_id", ctypes.c_byte * 16), ("property_id", ctypes.c_uint32)]

    def __init__(self, property_id):
        super().__init__((ctypes.c_byte * 16).from_buffer_copy(
            uuid.UUID("9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3").bytes_le), property_id)


class _PropVariant(ctypes.Structure):
    # The pointer-sized pair preserves PROPVARIANT's full union size on x86/x64.
    # Only VT_EMPTY and VT_LPWSTR are used here.
    _fields_ = [("vt", ctypes.c_ushort), ("reserved", ctypes.c_ushort * 3),
                ("value", ctypes.c_void_p), ("padding", ctypes.c_void_p)]


@contextmanager
def _window_property_store(hwnd):
    shell = ctypes.WinDLL("shell32")
    get_store = shell.SHGetPropertyStoreForWindow
    get_store.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    get_store.restype = ctypes.c_long
    iid = (ctypes.c_byte * 16).from_buffer_copy(
        uuid.UUID("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99").bytes_le)
    store = ctypes.c_void_p()
    result = get_store(hwnd, ctypes.byref(iid), ctypes.byref(store))
    if result < 0:
        raise OSError(result, "Could not access the desktop window identity")
    table = ctypes.cast(store, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    try:
        yield store, table
    finally:
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(store)  # IUnknown::Release


def _set_taskbar_properties(hwnd, properties):
    with _window_property_store(hwnd) as (store, table):
        set_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
            ctypes.POINTER(_PropertyKey), ctypes.POINTER(_PropVariant))(table[6])
        for property_id, text in properties.items():
            key, value = _PropertyKey(property_id), _PropVariant()
            if text is not None:
                buffer = ctypes.create_unicode_buffer(text)
                value.vt, value.value = 31, ctypes.addressof(buffer)  # VT_LPWSTR; SetValue copies it.
            result = set_value(store, ctypes.byref(key), ctypes.byref(value))
            if result < 0:
                raise OSError(result, "Could not set the desktop taskbar identity")


def _relaunch_command():
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([sys.executable])
    # An absolute script also works when a pinned shortcut starts outside the repo.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    launcher = Path(__file__).resolve().parents[2] / "backend" / "desktop_demo.py"
    return subprocess.list2cmdline([str(pythonw), "-B", str(launcher)])


def _apply_taskbar_identity(root):
    root.update_idletasks()
    hwnd = int(root.wm_frame(), 0)  # Tk's native top-level wrapper, not the child widget HWND.
    if getattr(root, "_brand_hwnd", None) == hwnd:
        return
    # Relaunch fields must precede AppUserModelID, which asks Explorer to refresh.
    _set_taskbar_properties(hwnd, {2: _relaunch_command(), 3: str(ASSETS / "app.ico") + ",0",
                                   4: "Stream Chat", 5: APP_ID})
    root._brand_hwnd = hwnd
    if getattr(root, "_brand_cleanup_bound", False):
        return
    def clear(event):
        if event.widget == root:
            try:
                _set_taskbar_properties(root._brand_hwnd, dict.fromkeys((5, 2, 3, 4)))
            except OSError:
                pass  # Windows may have already destroyed the native wrapper.
    root.bind("<Destroy>", clear, add="+")
    root._brand_cleanup_bound = True


def set_app_identity():
    if sys.platform == "win32":
        set_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        set_id.argtypes = [ctypes.c_wchar_p]
        set_id.restype = ctypes.c_long
        if set_id(APP_ID) != 0:
            raise OSError("Could not set the desktop application identity")


def apply_window_icon(root: tk.Tk):
    # Keep image objects alive, and make child dialogs inherit the same icon.
    if not hasattr(root, "_brand_icons"):
        root._brand_icons = tuple(tk.PhotoImage(master=root, file=str(ASSETS / f"app-{size}.png"))
                                 for size in (16, 32, 48, 256))
    root.iconphoto(True, *root._brand_icons)
    if sys.platform == "win32":
        # Tkinter ignores `bitmap` when `default` is passed in the same call.
        # Set the current window explicitly as well as the inherited dialog icon.
        root.iconbitmap(default=str(ASSETS / "app.ico"))
        root.iconbitmap(str(ASSETS / "app.ico"))
        _apply_taskbar_identity(root)
