"""Mac Dock branding; common PNGs are also used by Tk dialogs."""
from pathlib import Path
import tkinter as tk

ASSETS = Path(__file__).resolve().parents[2] / "assets"


def set_app_identity():
    from AppKit import NSApplication, NSImage
    application = NSApplication.sharedApplication()
    application.setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(str(ASSETS / "app-512.png")))


def apply_window_icon(root):
    if not hasattr(root, "_brand_icons"):
        root._brand_icons = tuple(tk.PhotoImage(master=root, file=str(ASSETS / f"app-{size}.png"))
                                 for size in (16, 32, 48, 256))
    root.iconphoto(True, *root._brand_icons)
