"""Figma panel paints, kept separate from content and native window opacity.

Tk cannot sample/composite the desktop behind each widget. These layers use a
neutral backdrop and a restrained edge-light approximation for Figma's GLASS.
No background screen capture is performed merely to render the interface.
"""

from functools import lru_cache
import tkinter as tk
from tkinter import ttk, font

from PIL import Image, ImageDraw, ImageFilter, ImageTk
from apps.desktop.fonts import load_bundled_fonts
from apps.desktop.shell import transparent_color

RADIUS = 26
FILLS = ((.15, .15, .15, 1., "COLOR_DODGE"), (0., 0., 0., .2, "NORMAL"))
GLASS_FILL = (0., 0., 0., .2, "SCREEN")
GLASS = dict(radius=12, refraction=1, depth=16, lightAngle=315,
             lightIntensity=.67, dispersion=0, splay=.06)
SHADOW = dict(alpha=.12, x=0, y=8, blur=40, spread=0,
              blendMode="NORMAL", showShadowBehindNode=False)
BACKDROP = (22, 24, 26)


def composite(color, paint):
    """Apply a single solid Figma paint to an RGB backdrop (0..255)."""
    r, g, b, alpha, mode = paint
    result = []
    for base, source in zip(color, (r, g, b)):
        base /= 255
        if mode == "COLOR_DODGE":
            mixed = 1 if source == 1 else min(1, base / (1 - source))
        elif mode == "SCREEN":
            mixed = 1 - (1 - base) * (1 - source)
        else:
            mixed = source
        result.append(round(255 * (alpha * mixed + (1 - alpha) * base)))
    return tuple(result)


def panel_color(variant="main"):
    color = BACKDROP
    paints = FILLS if variant == "main" else (FILLS[0], (0., 0., 0., .4, "NORMAL"))
    for paint in paints:
        color = composite(color, paint)
    return color


BG = "#%02x%02x%02x" % panel_color()
INK, MUTED, INPUT, MINT = "#ffffff", "#c5c5c5", "#303234", "#03ffd5"


def configure_theme(root):
    load_bundled_fonts()
    family = "Pretendard" if "Pretendard" in font.families(root) else "맑은 고딕"
    for name in font.names(root):
        font.nametofont(name, root=root).configure(family=family)
    root.option_add("*Font", (family, -12))
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=INK, bordercolor="#666666", font=(family, -12))
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=INK)
    style.configure("TButton", background=INPUT, foreground=INK, padding=(9, 5), relief="flat")
    style.map("TButton", background=[("active", "#454749"), ("disabled", BG)],
              foreground=[("disabled", "#888888")])
    root._button_surfaces = []
    for color in (INPUT, "#454749", BG):
        surface = Image.new("RGBA", (64, 32))
        ImageDraw.Draw(surface).rounded_rectangle((0, 0, 63, 31), radius=8,
                                                  fill=color, outline="#666666", width=1)
        root._button_surfaces.append(ImageTk.PhotoImage(surface, master=root))
    style.element_create("Figma.Button.surface", "image", root._button_surfaces[0],
                         ("disabled", root._button_surfaces[2]), ("active", root._button_surfaces[1]),
                         border=8, sticky="nsew")
    style.layout("TButton", [("Figma.Button.surface", {"sticky": "nsew", "children": [
        ("Button.focus", {"sticky": "nsew", "children": [
            ("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})]})]})])
    style.configure("TEntry", fieldbackground=INPUT, foreground=INK, insertcolor=INK, padding=5)
    style.configure("TCombobox", fieldbackground=INPUT, background=INPUT, foreground=INK, padding=5)
    style.map("TCombobox", fieldbackground=[("readonly", INPUT)],
              foreground=[("readonly", INK), ("disabled", "#888888")])
    style.configure("TCheckbutton", background=BG, foreground=INK)
    style.map("TCheckbutton", background=[("active", BG)])
    style.configure("Treeview", background=BG, fieldbackground=BG, foreground=INK,
                    rowheight=24, borderwidth=0)
    style.configure("Treeview.Heading", background=INPUT, foreground=INK, relief="flat", font=(family, 9, "bold"))
    style.configure("Horizontal.TScale", background=BG, troughcolor=INPUT)
    root.option_add("*TCombobox*Listbox.background", INPUT)
    root.option_add("*TCombobox*Listbox.foreground", INK)
    return family


@lru_cache(maxsize=8)
def paint_layers(width, height, variant="main"):
    # Separate base, shadow and glass images; content never inherits their alpha.
    size = width, height
    mask = Image.new("L", size)
    ImageDraw.Draw(mask).rounded_rectangle((1, 1, width-2, height-2), RADIUS, fill=255)
    base = Image.new("RGBA", size, panel_color(variant) + (255,))
    if variant == "welcome":
        draw = ImageDraw.Draw(base)
        backdrop = composite(BACKDROP, FILLS[0])
        for y in range(height):
            t = y / max(1, height - 1)
            color = tuple(round((1-t)*start + t*end) for start, end in zip((3,255,213), (45,255,143)))
            draw.line((0, y, width, y), fill=tuple(round(.8*c + .2*b) for c,b in zip(color, backdrop)))
    base.putalpha(mask)
    shadow = Image.new("L", size)
    ImageDraw.Draw(shadow).rounded_rectangle((1, 9, width-2, height+6), RADIUS,
                                            fill=round(255 * SHADOW["alpha"]))
    shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW["blur"] / 2))
    # showShadowBehindNode=false: no shadow is painted through the panel.
    shadow.paste(0, mask=mask)
    shadow_rgba = Image.new("RGBA", size, (0, 0, 0, 0))
    shadow_rgba.putalpha(shadow)
    glass = Image.new("RGBA", size)
    # Black SCREEN leaves the base RGB unchanged. The edge light approximates
    # the optical effect; it is not an actual stroke in the source design.
    screen_rgb = composite(panel_color(), GLASS_FILL)
    glass.paste(screen_rgb + (0,), (0, 0, width, height))
    edge = Image.new("L", size)
    draw = ImageDraw.Draw(edge)
    draw.rounded_rectangle((1, 1, width-2, height-2), RADIUS, outline=90, width=1)
    for y in range(height):
        strength = abs(1 - 2*y/max(1, height-1))
        for x in (0, 1, width-2, width-1):
            edge.putpixel((x, y), round(edge.getpixel((x, y)) * strength))
    glass.paste((255, 255, 255), mask=edge)
    return shadow_rgba, base, glass


class Panel(tk.Canvas):
    def __init__(self, parent, width, height, *, settings=False, variant="main"):
        super().__init__(parent, width=width, height=height, bg=transparent_color(),
                         highlightthickness=0, borderwidth=0)
        self.design_node = "Screen/Settings" if settings else "Screen/Main"
        self.background_owner = "Fill + Shadow" if settings else "Screen/Main"
        self.layer_opacity = 1.0
        layers = paint_layers(width, height, variant)
        self.surface = layers[1]
        self.variant = variant
        # Composite before handing the image to Tk. On transparent macOS
        # windows, drawing a mostly transparent PhotoImage over another image
        # can clear the native backing surface instead of preserving the body.
        surface = Image.new("RGBA", (width, height))
        for layer in layers:
            surface = Image.alpha_composite(surface, layer)
        self.images = [ImageTk.PhotoImage(surface, master=self)]
        self.create_image(0, 0, image=self.images[0], anchor="nw",
                          tags=("Drop shadow", self.background_owner, "Glass Effect"))
