"""Managed X11 window without decorations, with a rounded Shape extension mask."""
import ctypes as c
from ctypes.util import find_library
import math
from apps.desktop.linux.x11 import API, Display, bind, P, U, I

bind(API,"XChangeProperty",I,[P,U,U,U,I,I,P,I])


class Rectangle(c.Structure):
    _fields_ = [("x",c.c_short),("y",c.c_short),("width",c.c_ushort),("height",c.c_ushort)]


def transparent_color():
    # Tk/X11 has no Windows-style transparent color key.
    return "#151619"


def configure_window(root):
    root.configure(bg=transparent_color())
    root.wm_attributes("-type","utility")
    root.update_idletasks()
    with Display() as display:
        hints = (U*5)(2,0,0,0,0)
        atom = display.atom("_MOTIF_WM_HINTS")
        API.XChangeProperty(display.pointer,int(root.wm_frame(),0),atom,atom,32,0,c.cast(hints,P),5)
        display.check()
    root.bind("<Configure>",lambda event: mapped(root) if event.widget is root else None,add="+")


def mapped(root):
    if not root.winfo_ismapped():
        return
    width,height = root.winfo_width(),root.winfo_height()
    size = (width,height)
    if width < 52 or height < 52 or getattr(root,"_shape_size",None) == size:
        return
    rectangles = []
    radius = 26
    for y in range(height):
        distance = max(radius-y-.5,y+.5-(height-radius),0)
        inset = math.ceil(radius-math.sqrt(radius*radius-distance*distance)) if distance else 0
        rectangles.append(Rectangle(inset,y,width-2*inset,1))
    api = c.CDLL(find_library("Xext") or "libXext.so.6")
    bind(api,"XShapeCombineRectangles",None,[P,U,I,I,I,c.POINTER(Rectangle),I,I,I])
    with Display() as display:
        data = (Rectangle*len(rectangles))(*rectangles)
        api.XShapeCombineRectangles(display.pointer,int(root.wm_frame(),0),0,0,0,data,len(data),0,3)
        display.check()
    root._shape_size = size
