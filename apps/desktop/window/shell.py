import ctypes
import sys


def transparent_color():
    return "#010203"


def configure_window(root):
    root.configure(bg=transparent_color())
    if sys.platform == "win32":
        root.attributes("-transparentcolor", transparent_color())


def mapped(root):
    if sys.platform != "win32":
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    hwnd = int(root.wm_frame(), 0)
    user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
    extended = user32.GetWindowLongW(hwnd, -20)
    user32.SetWindowLongW(hwnd, -20, (extended | 0x40000) & ~0x80)
