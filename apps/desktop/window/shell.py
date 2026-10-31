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
    # A native region cuts out the corners independently of color-keyed PNG
    # edges, which can otherwise leave an opaque fringe after DPI resampling.
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int]*6
    gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    user32.SetWindowRgn.argtypes = [ctypes.c_void_p,ctypes.c_void_p,ctypes.c_bool]
    user32.SetWindowRgn.restype = ctypes.c_int
    radius = round(26*getattr(root,"_tiki_display_scale",1))
    shape = (hwnd,root.winfo_width(),root.winfo_height(),radius)
    if getattr(root,"_rounded_shape",None) == shape:
        return
    region = gdi32.CreateRoundRectRgn(0,0,root.winfo_width()+1,root.winfo_height()+1,radius*2,radius*2)
    if region and not user32.SetWindowRgn(hwnd,region,True):
        gdi32.DeleteObject(region)  # On success Windows owns the region.
    elif region:
        root._rounded_shape = shape
