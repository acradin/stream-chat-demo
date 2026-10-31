"""Figma artwork: native SVG on Retina, antialiased 4x sources on Windows.

Tk 8.6 PhotoImage always renders into a 1x buffer on macOS. Enlarging a PNG
there cannot improve Retina detail; AppKit must draw the SVG directly instead.
"""
import sys
from tkinter import font
from xml.etree import ElementTree as ET
from PIL import Image, ImageTk

from apps.desktop.branding import ASSETS


def source(name):
    return ASSETS / "figma" / ("v2-header.svg" if name == "header" else f"v2-source-{name}.svg")


def draw(canvas, name, x, y, *, scale=1, tags=()):
    """Place artwork at its SVG origin and retain a Canvas tag for input."""
    path = source(name)
    node = ET.parse(path).getroot()
    width, height = float(node.attrib["width"])*scale, float(node.attrib["height"])*scale
    tag = f"vector-{name}-{len(canvas.find_all())}"
    tags = (tag, *tags)
    if sys.platform == "darwin":
        from apps.desktop.mac.artwork import mount
        canvas.create_rectangle(x,y,x+width,y+height,fill="",outline="",tags=tags)
        if not hasattr(canvas,"_artwork_refresh"):
            canvas._artwork_refresh = {}
        canvas._artwork_refresh[tag] = mount(canvas,path,x,y,width,height,tag)
    else:
        # Never enlarge the old 1x exports. The bundled render preserves SVG
        # strokes, filters and compound paths, with LANCZOS antialiasing.
        with Image.open(ASSETS / "figma" / f"v2-{name}@4x.png") as image:
            original = image.convert("RGBA")
            photo = ImageTk.PhotoImage(original.resize((round(width),round(height)),Image.Resampling.LANCZOS),master=canvas)
        top = canvas.winfo_toplevel()
        if not hasattr(top,"_design_image_sources"):
            top._design_image_sources = {}
        top._design_image_sources[str(photo)] = original
        if not hasattr(canvas,"_vector_photos"):
            canvas._vector_photos = []
        canvas._vector_photos.append(photo)
        canvas.create_image(x,y,anchor="nw",image=photo,tags=tags)
    return tag


def visible(canvas, tag, show):
    canvas.itemconfigure(tag,state="normal" if show else "hidden")
    refresh = getattr(canvas,"_artwork_refresh",{}).get(tag)
    if refresh:
        refresh()


class StatusBadge:
    """Common/Online: vector background and native text, sized to live status."""
    def __init__(self, canvas, x, y, family):
        self.canvas, self.x, self.y = canvas, x, y
        self.font = font.Font(root=canvas, family=family, size=-8)
        # Figma: F52F32 at 90%, radius 4, height 12.2, horizontal padding 4.
        self.background = canvas.create_polygon(0,0,0,0,0,0,
            fill="#df2d30",outline="#ef8586",width=.1,smooth=True)
        self.text = canvas.create_text(x+18,y+6.1,text="",fill="white",font=self.font)
        self.configure(text="• Demo")

    def configure(self, *, text):
        scale = getattr(self.canvas,"_tiki_display_scale",1)
        self.font.configure(size=-round(8*scale))
        x, y = self.x*scale, self.y*scale
        w, h, r = max(36.2*scale,self.font.measure(text)+8*scale), 12.2*scale, 4*scale
        self.canvas.coords(self.background,x+r,y,x+w-r,y,x+w,y,x+w,y+r,
            x+w,y+h-r,x+w,y+h,x+w-r,y+h,x+r,y+h,x,y+h,x,y+h-r,x,y+r,x,y)
        self.canvas.coords(self.text,x+w/2,y+h/2)
        self.canvas.itemconfigure(self.text,text=text)
