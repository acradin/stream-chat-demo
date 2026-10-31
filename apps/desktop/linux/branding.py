from pathlib import Path
import tkinter as tk

ASSETS = Path(__file__).resolve().parents[2] / "assets"


def set_app_identity():
    pass


def apply_window_icon(root):
    if not hasattr(root,"_brand_icons"):
        root._brand_icons = tuple(tk.PhotoImage(master=root,file=str(ASSETS/f"app-{size}.png")) for size in (16,32,48,256))
    root.iconphoto(True,*root._brand_icons)
