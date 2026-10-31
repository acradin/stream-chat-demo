"""Scale the fixed Figma layout once, before showing its native window."""
import sys
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk


def display_scale(root):
    # macOS/Tk already uses logical pixels; Linux keeps its existing X11 layout.
    return round(root.winfo_fpixels("1i") / 96, 2) if sys.platform == "win32" else 1.0


def scale_layout(root, factor, photos=()):
    """Resize geometry, pixel fonts and image content together, exactly once."""
    if factor == 1:
        return
    widgets = []
    def collect(widget):
        widgets.append(widget)
        for child in widget.winfo_children():
            collect(child)
    collect(root)
    images = {str(photo): photo for photo in photos}
    for widget in widgets:
        for name in ("photo", "photos", "images"):
            value = getattr(widget, name, ())
            values = value.values() if isinstance(value, dict) else value if isinstance(value, (list, tuple)) else (value,)
            images.update((str(photo), photo) for photo in values if isinstance(photo, ImageTk.PhotoImage))
    resized = {}
    originals = getattr(root, "_design_image_sources", {})
    def image(name):
        if name not in resized:
            photo = images[name]
            source = originals.get(name)
            if source is None:
                source = ImageTk.getimage(photo)
            size = (round(photo.width()*factor), round(photo.height()*factor))
            resized[name] = ImageTk.PhotoImage(source.resize(size, Image.Resampling.LANCZOS), master=root)
        return resized[name]
    def scaled_font(value):
        parts = root.tk.splitlist(value)
        # Positive point fonts already follow the native DPI; only pixel fonts need conversion.
        if len(parts) > 1 and str(parts[1]).lstrip("-").isdigit() and int(parts[1]) < 0:
            return (parts[0], -round(abs(int(parts[1]))*factor), *parts[2:])
        return value
    def distances(value):
        values = (value,) if isinstance(value,(int,float)) else root.tk.splitlist(value)
        return tuple(round(float(item)*factor) for item in values)
    for widget in widgets:
        if widget is root:
            continue
        if isinstance(widget, tk.Canvas):
            tk.Canvas.configure(widget, width=round(float(widget.cget("width"))*factor),
                                height=round(float(widget.cget("height"))*factor))
            widget.scale("all", 0, 0, factor, factor)
            for item in widget.find_all():
                options = widget.itemconfigure(item)
                if "font" in options:
                    widget.itemconfigure(item, font=scaled_font(widget.itemcget(item,"font")))
                for option in ("width", "height"):
                    if option in options:
                        widget.itemconfigure(item, **{option: float(widget.itemcget(item,option))*factor})
                if "image" in options:
                    name = widget.itemcget(item,"image")
                    if name in images:
                        widget.itemconfigure(item, image=image(name))
        else:
            options = widget.configure()
            if "font" in options and widget.cget("font"):
                widget.configure(font=scaled_font(widget.cget("font")))
            if "wraplength" in options and widget.cget("wraplength"):
                widget.configure(wraplength=round(float(widget.cget("wraplength"))*factor))
            if "image" in options and str(widget.cget("image")) in images:
                widget.configure(image=image(str(widget.cget("image"))))
        if widget.winfo_manager() == "place":
            info = widget.place_info()
            widget.place_configure(**{key: round(float(info[key])*factor) for key in ("x","y","width","height") if info.get(key)})
        elif widget.winfo_manager() == "pack":
            info = widget.pack_info()
            widget.pack_configure(**{key: distances(info[key]) for key in ("padx","pady","ipadx","ipady") if info.get(key)})
        if isinstance(widget, ttk.Treeview):
            for column in widget.cget("columns"):
                widget.column(column, width=round(widget.column(column,"width")*factor),
                              minwidth=round(widget.column(column,"minwidth")*factor))
    style = ttk.Style(root)
    style.configure(".", font=scaled_font(style.lookup(".","font")))
    for name in ("TButton", "TEntry", "TCombobox"):
        padding = style.lookup(name,"padding")
        if padding:
            style.configure(name, padding=distances(padding))
    style.configure("Treeview",rowheight=round(24*factor))
    root._scaled_design_images = resized  # Keep images alive for Tk.
