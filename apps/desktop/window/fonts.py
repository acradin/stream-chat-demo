"""Process-private GDI fonts; no registry or system font installation."""
import ctypes


def register_font(path):
    add = ctypes.WinDLL("gdi32").AddFontResourceExW
    add.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
    add.restype = ctypes.c_int
    return add(str(path), 0x10, None) > 0  # FR_PRIVATE, released on process exit.
