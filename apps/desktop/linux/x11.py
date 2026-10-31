"""Small typed Xlib boundary. Errors on our displays become Python failures."""
import ctypes as c
from ctypes.util import find_library

P, U, I, L = c.c_void_p, c.c_ulong, c.c_int, c.c_long
_errors = {}


class XError(c.Structure):
    _fields_ = [("type",I),("display",P),("resource",U),("serial",U),
                ("code",c.c_ubyte),("request",c.c_ubyte),("minor",c.c_ubyte)]


class XImage(c.Structure):
    _fields_ = [("width",I),("height",I),("xoffset",I),("format",I),("data",P),
                ("byte_order",I),("bitmap_unit",I),("bitmap_bit_order",I),("bitmap_pad",I),
                ("depth",I),("bytes_per_line",I),("bits_per_pixel",I),
                ("red_mask",U),("green_mask",U),("blue_mask",U)]


class Visual(c.Structure):
    _fields_ = [("ext_data",P),("visualid",U),("visual_class",I),("red_mask",U),
                ("green_mask",U),("blue_mask",U),("bits_per_rgb",I),("map_entries",I)]


class WindowAttributes(c.Structure):
    _fields_ = [("x",I),("y",I),("width",I),("height",I),("border_width",I),("depth",I),
                ("visual",c.POINTER(Visual)),("root",U),("window_class",I),("bit_gravity",I),
                ("win_gravity",I),("backing_store",I),("backing_planes",U),("backing_pixel",U),
                ("save_under",I),("colormap",U),("map_installed",I),("map_state",I),
                ("all_event_masks",L),("your_event_mask",L),("do_not_propagate_mask",L),
                ("override_redirect",I),("screen",P)]


def bind(api,name,result,args):
    fn = getattr(api,name)
    fn.restype,fn.argtypes = result,args
    return fn


API = c.CDLL(find_library("X11") or "libX11.so.6")
# Imported by the platform dispatcher before the first Tk root is constructed.
API.XInitThreads()
bind(API,"XOpenDisplay",P,[c.c_char_p])
bind(API,"XCloseDisplay",I,[P])
bind(API,"XDefaultRootWindow",U,[P])
bind(API,"XInternAtom",U,[P,c.c_char_p,I])
bind(API,"XSync",I,[P,I])
bind(API,"XFree",I,[P])
bind(API,"XGetWindowProperty",I,[P,U,U,L,L,I,U,c.POINTER(U),c.POINTER(I),c.POINTER(U),c.POINTER(U),c.POINTER(P)])
bind(API,"XGetGeometry",I,[P,U,c.POINTER(U),c.POINTER(I),c.POINTER(I),c.POINTER(c.c_uint),c.POINTER(c.c_uint),c.POINTER(c.c_uint),c.POINTER(c.c_uint)])
bind(API,"XGetImage",c.POINTER(XImage),[P,U,I,I,c.c_uint,c.c_uint,U,I])
bind(API,"XDestroyImage",I,[c.POINTER(XImage)])
bind(API,"XFreePixmap",I,[P,U])
bind(API,"XGetWindowAttributes",I,[P,U,c.POINTER(WindowAttributes)])

ERROR_HANDLER = c.CFUNCTYPE(I,P,c.POINTER(XError))
_previous = None


@ERROR_HANDLER
def _handle(display,event):
    if display in _errors:
        _errors[display].append(event.contents.code)
        return 0
    return _previous(display,event) if _previous else 0


bind(API,"XSetErrorHandler",P,[P])
old = API.XSetErrorHandler(c.cast(_handle,P))
if old:
    _previous = ERROR_HANDLER(old)


class Display:
    def __enter__(self):
        self.pointer = API.XOpenDisplay(None)
        if not self.pointer:
            raise ValueError("X11 화면에 연결할 수 없습니다. DISPLAY와 데스크톱 세션을 확인해주세요.")
        _errors[self.pointer] = []
        self.root = API.XDefaultRootWindow(self.pointer)
        return self

    def check(self):
        API.XSync(self.pointer,False)
        errors = _errors[self.pointer]
        if errors:
            errors.clear()
            raise ValueError("선택한 X11 창을 사용할 수 없습니다. 창을 다시 선택해주세요.")

    def atom(self,name):
        return API.XInternAtom(self.pointer,name.encode(),False)

    def property(self,window,name):
        actual,form,count,remaining,raw = U(),I(),U(),U(),P()
        status = API.XGetWindowProperty(self.pointer,window,self.atom(name),0,65536,False,0,
                                       c.byref(actual),c.byref(form),c.byref(count),c.byref(remaining),c.byref(raw))
        try:
            self.check()
            if status or not raw or remaining.value:
                return None
            if form.value == 32:
                return list(c.cast(raw,c.POINTER(U))[:count.value])
            if form.value == 8:
                return c.string_at(raw,count.value)
            return None
        finally:
            if raw:
                API.XFree(raw)

    def geometry(self,drawable):
        root,x,y,w,h,border,depth = U(),I(),I(),c.c_uint(),c.c_uint(),c.c_uint(),c.c_uint()
        ok = API.XGetGeometry(self.pointer,drawable,c.byref(root),c.byref(x),c.byref(y),c.byref(w),c.byref(h),c.byref(border),c.byref(depth))
        self.check()
        if not ok or not 0 < w.value*h.value <= 33_177_600:
            raise ValueError("캡처할 화면 크기를 확인해주세요.")
        return w.value,h.value

    def __exit__(self,*args):
        API.XCloseDisplay(self.pointer)
        _errors.pop(self.pointer,None)
