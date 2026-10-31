"""X11 capture from the selected window's own Composite pixmap, never a crop."""
import ctypes as c
from ctypes.util import find_library
import io
import os
from PIL import Image, ImageGrab
from apps.desktop.capture_types import WindowSource
from apps.desktop.linux.x11 import API, Display, WindowAttributes, bind, P, U, I


def _source(display,window):
    pid = display.property(window,"_NET_WM_PID")
    title = display.property(window,"_NET_WM_NAME") or display.property(window,"WM_NAME")
    state = display.property(window,"WM_STATE")
    if not pid or pid[0] == os.getpid() or not isinstance(title,bytes) or not title.strip() or (state and state[0] != 1):
        return None
    return WindowSource(int(window),int(pid[0]),title.decode("utf-8","replace"))


def list_windows():
    with Display() as display:
        windows = display.property(display.root,"_NET_CLIENT_LIST") or []
        sources = []
        for window in windows:
            try:
                source = _source(display,window)
                if source:
                    sources.append(source)
            except ValueError:
                continue  # A window may close while the list is being populated.
        return sorted(sources,key=lambda source:source.title.casefold())


def _jpeg(image,size=1280,quality=75):
    image = image.convert("RGB")
    image.thumbnail((size,size),Image.Resampling.LANCZOS)
    stream = io.BytesIO()
    image.save(stream,format="JPEG",quality=quality)
    return stream.getvalue()


def capture_window(source):
    composite = c.CDLL(find_library("Xcomposite") or "libXcomposite.so.1")
    bind(composite,"XCompositeRedirectWindow",None,[P,U,I])
    bind(composite,"XCompositeUnredirectWindow",None,[P,U,I])
    bind(composite,"XCompositeNameWindowPixmap",U,[P,U])
    with Display() as display:
        current = _source(display,source.handle)
        if current is None or current.pid != source.pid:
            raise ValueError("선택한 창이 닫히거나 변경됐습니다. 창을 다시 선택해주세요.")
        attributes = WindowAttributes()
        ok = API.XGetWindowAttributes(display.pointer,source.handle,c.byref(attributes))
        display.check()
        if not ok or attributes.map_state != 2 or not attributes.visual:
            raise ValueError("선택한 창이 최소화되거나 닫혔습니다. 창을 다시 선택해주세요.")
        visual = attributes.visual.contents
        pixmap,grabbed,redirected = 0,None,False
        try:
            composite.XCompositeRedirectWindow(display.pointer,source.handle,0)
            display.check()
            redirected = True
            pixmap = composite.XCompositeNameWindowPixmap(display.pointer,source.handle)
            display.check()
            width,height = display.geometry(pixmap)
            grabbed = API.XGetImage(display.pointer,pixmap,0,0,width,height,U(-1),2)
            display.check()
            if not grabbed:
                raise ValueError("선택한 창을 캡처하지 못했습니다.")
            info = grabbed.contents
            # Pixmaps have no Visual; XGetImage may leave their RGB masks at zero.
            # Use the owning window's validated TrueColor Visual instead.
            if (info.byte_order,info.bits_per_pixel,visual.visual_class,visual.red_mask,visual.green_mask,visual.blue_mask) != (0,32,4,0xff0000,0xff00,0xff):
                raise ValueError("현재 X11 화면의 픽셀 형식을 지원하지 않습니다.")
            raw = c.string_at(info.data,info.bytes_per_line*height)
            image = Image.frombytes("RGB",(width,height),raw,"raw","BGRX",info.bytes_per_line,1)
            current = _source(display,source.handle)
            if current is None or current.pid != source.pid:
                raise ValueError("캡처 중 선택한 창이 변경됐습니다.")
            return _jpeg(image)
        finally:
            if grabbed:
                API.XDestroyImage(grabbed)
            if pixmap:
                API.XFreePixmap(display.pointer,pixmap)
            if redirected:
                composite.XCompositeUnredirectWindow(display.pointer,source.handle,0)
            API.XSync(display.pointer,False)


def capture_primary_screen():
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
        raise ValueError("Wayland/WSLg의 전체 화면 캡처는 아직 지원하지 않습니다. Linux X11 세션을 사용해주세요. WSL은 Windows 방송 화면을 캡처하지 않습니다.")
    with ImageGrab.grab(xdisplay=os.environ.get("DISPLAY", "")) as image:
        return _jpeg(image,1536,85)
