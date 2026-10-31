"""Export desktop design data using an isolated, offline UI instance.

Run: python -B -m apps.desktop.export_design
No user settings, environment credentials, network requests or screenshots.
"""

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import font, ttk
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image

from apps.desktop import panel
from apps.desktop.branding import ASSETS
from apps.desktop.connection import ConnectionDialog
from apps.desktop.overlay import Overlay

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "design" / "desktop"
SOURCES = tuple("apps/desktop/" + name for name in
                ("panel.py", "figma_ui.py", "onboarding.py", "design_widgets.py", "display.py", "vector.py", "count_slider.py", "overlay.py", "connection.py", "branding.py", "fonts.py",
                 "shell.py", "window/branding.py", "window/shell.py", "window/fonts.py",
                 "mac/branding.py", "mac/shell.py", "mac/fonts.py", "mac/artwork.py", "linux/branding.py", "linux/shell.py", "linux/fonts.py"))
IGNORE_OPTIONS = {"command", "validatecommand", "invalidcommand", "postcommand", "xscrollcommand",
                  "yscrollcommand", "textvariable", "variable", "class", "container", "use"}


class OfflineService:
    stop_requested = threading.Event()

    def usage(self):
        return dict(period="2026-11", is_demo=True, generation_requests=0,
                    generated_chats=0, total_generated_chats=0)


def plain(value):
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)


def configured(widget):
    # GenerateOrb overrides configure as a button adapter; query Tk directly.
    options = tk.Canvas.configure(widget) if isinstance(widget, tk.Canvas) else widget.configure()
    return {name: plain(value[-1]) for name, value in options.items()
            if name not in IGNORE_OPTIONS and len(value) == 5}


def image_info(widget, name):
    if not name:
        return None
    try:
        return dict(name=str(name), width=int(widget.tk.call("image", "width", name)),
                    height=int(widget.tk.call("image", "height", name)))
    except tk.TclError:
        return None


def font_info(widget, description):
    if not description:
        return None
    measured = font.Font(root=widget, font=description)
    return dict(requested=plain(description), resolved=measured.actual(), metrics=measured.metrics())


def widget_tree(widget, aliases, origin):
    options = configured(widget)
    manager = widget.winfo_manager()
    layout = getattr(widget, manager + "_info")() if manager in ("pack", "place", "grid") else {}
    result = dict(path=str(widget), name=aliases.get(str(widget)), widget_class=widget.winfo_class(),
                  manager=manager, layout=plain(layout), options=options,
                  bounds_px=dict(x=widget.winfo_rootx()-origin.winfo_rootx(),
                                 y=widget.winfo_rooty()-origin.winfo_rooty(),
                                 width=widget.winfo_width(), height=widget.winfo_height()),
                  requested_px=dict(width=widget.winfo_reqwidth(), height=widget.winfo_reqheight()))
    if isinstance(widget, ttk.Widget):
        style = ttk.Style(widget)
        name = str(widget.cget("style")) or widget.winfo_class()
        state = widget.state()
        result.update(ttk_style=name, ttk_state=state,
                      resolved_style={key: plain(style.lookup(name, key, state)) for key in
                                      ("background", "foreground", "fieldbackground", "bordercolor", "borderwidth",
                                       "padding", "relief", "font", "rowheight", "insertcolor")})
        result["font"] = font_info(widget, result["resolved_style"]["font"])
    elif "font" in options:
        result["font"] = font_info(widget, options["font"])
    if options.get("image"):
        images = widget.tk.splitlist(widget.cget("image"))
        result["images"] = [image_info(widget, name) for name in images if str(name).startswith("pyimage")]
    if isinstance(widget, tk.Canvas):
        items = []
        for item in widget.find_all():
            config = {name: plain(value[-1]) for name, value in widget.itemconfigure(item).items()
                      if name not in IGNORE_OPTIONS}
            data = dict(id=item, type=widget.type(item), coordinates_px=widget.coords(item),
                        options=config, bbox_px=widget.bbox(item))
            if config.get("font"):
                data["font"] = font_info(widget, config["font"])
            if config.get("image"):
                data["image"] = image_info(widget, config["image"])
            items.append(data)
        result["canvas_items"] = items
    if isinstance(widget, tk.Text):
        result["text_tags"] = {name: {key: plain(value[-1]) for key, value in widget.tag_configure(name).items()}
                               for name in widget.tag_names()}
    if isinstance(widget, ttk.Treeview):
        result["columns"] = {name: dict(column=plain(widget.column(name)), heading=plain(widget.heading(name)))
                             for name in widget.cget("columns")}
    if hasattr(widget, "background_owner"):
        result["paint_hierarchy"] = dict(design_node=widget.design_node,
                                          background_owner=widget.background_owner,
                                          layer_opacity=widget.layer_opacity)
    result["children"] = [widget_tree(child, aliases, origin) for child in widget.winfo_children()]
    return result


def source_inventory():
    """Retain expressions, including transient/conditional values, with locations."""
    methods = {"configure", "config", "map", "layout", "element_create", "option_add", "pack", "place", "grid",
               "column", "heading", "tag_configure", "itemconfigure", "create_line", "create_oval", "create_text",
               "create_image", "create_window", "rounded_rectangle", "geometry", "minsize", "resizable", "attributes"}
    constructors = {"Canvas", "Frame", "Label", "Button", "Entry", "Combobox", "Scale", "Checkbutton", "Text",
                    "ScrolledText", "Treeview", "Scrollbar", "PhotoImage", "GaussianBlur", "Panel", "GenerateOrb"}
    sources = []
    for name in SOURCES:
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        calls, colors = [], set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("#"):
                if len(node.value) in (4, 7, 9) and all(c in "0123456789abcdefABCDEF" for c in node.value[1:]):
                    colors.add(node.value)
            if not isinstance(node, ast.Call):
                continue
            name_part = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
            if name_part in methods | constructors:
                calls.append(dict(line=node.lineno, expression=ast.get_source_segment(source, node)))
        sources.append(dict(path=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            colors=sorted(colors), style_and_layout_calls=sorted(calls, key=lambda item: item["line"])))
    return sources


def asset_inventory():
    result = []
    for path in sorted(ASSETS.rglob("*")):
        if path.suffix not in (".png", ".svg", ".ico", ".ttf") and path.name != "LICENSE.txt":
            continue
        item = dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size,
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if path.suffix == ".svg":
            item["svg_root"] = ET.parse(path).getroot().attrib
        elif path.suffix in (".png", ".ico"):
            with Image.open(path) as image:
                item.update(width=image.width, height=image.height, mode=image.mode)
                if path.suffix == ".ico":
                    item["sizes"] = sorted(image.ico.sizes())
        result.append(item)
    return result


def export():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / "build"
    scratch.mkdir(exist_ok=True)
    runtime = {}
    root = tk.Tk()
    root.withdraw()
    try:
        with tempfile.TemporaryDirectory(prefix="design-export-", dir=scratch) as directory:
            with patch.object(Overlay, "refresh_service_usage", lambda self: None):
                app = Overlay(root, Path(directory), service=OfflineService(), enable_hotkey=False,
                              capture=lambda: (_ for _ in ()).throw(AssertionError("No screenshots allowed")),
                              window_list=lambda: [])
            # A mapped but fully invisible window gives actual widget layout.
            # The measured transparency is tooling-only, not an application token.
            root.attributes("-alpha", 0)
            root.deiconify()
            aliases = {str(value): name for owner in (app, app.view) for name, value in vars(owner).items()
                       if isinstance(value, tk.Widget)}
            runtime["environment"] = dict(tk_version=str(root.tk.call("info", "patchlevel")),
                                            tk_scaling=float(root.tk.call("tk", "scaling")),
                                            dpi=float(root.winfo_fpixels("1i")),
                                            preferred_font="Pretendard", selected_font=app.view.family,
                                            font_units="positive sizes are points, negative sizes are pixels",
                                            measurement_window_alpha=0,
                                            application_default_window_alpha=app.settings["opacity"])
            states = {}
            def snapshot(name, page):
                app.view.show(page)
                root.update_idletasks()
                states[name] = widget_tree(app.view.pages[page], aliases, app.view.pages[page])
            for page in app.view.pages:
                snapshot(page + "_default", page)
            app.view._count_changed(5)
            snapshot("main_five_members", "main")
            app.mode_var.set("실시간 화면 모드")
            app._mode_changed()
            snapshot("controls_realtime_five_members", "controls")
            app.destination_var.set("치지직에도 전송")
            app._channel_link_changed()
            app.live_running = True
            app._set_busy(True)
            app.stop_button.configure(state="normal")
            snapshot("main_observing", "main")
            snapshot("controls_observing", "controls")
            snapshot("settings_observing", "settings")
            app.live_running = False
            app._set_busy(False)
            app.mode_var.set("버튼 캡처 모드")
            app._mode_changed()
            app._set_busy(True)
            snapshot("main_generating", "main")
            app._set_busy(False)
            app.record_hotkey()
            snapshot("settings_recording_hotkey", "settings")
            app._finish_hotkey_recording()
            style = ttk.Style(root)
            names = (".", "TFrame", "TLabel", "TButton", "TEntry", "TCombobox", "TCheckbutton",
                     "Treeview", "Treeview.Heading", "Horizontal.TScale", "Vertical.TScrollbar")
            runtime["ttk_theme"] = style.theme_use()
            runtime["named_fonts"] = {name: font_info(root, name) for name in font.names(root)}
            runtime["styles"] = {}
            for name in names:
                try:
                    layout = style.layout(name)
                except tk.TclError:
                    layout = []
                runtime["styles"][name] = dict(configure=plain(style.configure(name)), map=plain(style.map(name)),
                                                 layout=plain(layout), resolved_states={})
                for state in ((), ("active",), ("disabled",), ("focus",), ("readonly",), ("selected",)):
                    runtime["styles"][name]["resolved_states"][" ".join(state) or "normal"] = {
                        key: plain(style.lookup(name, key, state)) for key in ("background", "foreground", "fieldbackground",
                                                                             "bordercolor", "padding", "font", "relief")}
            # Capture the real modal dialog body and its buttons without opening
            # a file picker, loading credentials or invoking its save method.
            dialog = ConnectionDialog.__new__(ConnectionDialog)
            tk.Toplevel.__init__(dialog, root)
            dialog.withdraw()
            dialog.attributes("-alpha", 0)
            dialog.base_url = "https://service.example.invalid"
            frame = tk.Frame(dialog)
            frame.pack(padx=5, pady=5)
            dialog.body(frame)
            dialog.buttonbox()
            dialog.deiconify()
            root.update_idletasks()
            states["connection_dialog"] = widget_tree(dialog, aliases, dialog)
            dialog.destroy()
            runtime["screens"] = states
            runtime["image_dimensions"] = {name: dict(width=int(root.tk.call("image", "width", name)),
                                                        height=int(root.tk.call("image", "height", name)))
                                             for name in root.tk.call("image", "names")}
            root.after_cancel(app.poll_id)
    finally:
        root.destroy()
    tokens = dict(
        renderer="Python tkinter/ttk + Pillow; no runtime CSS",
        colors=dict(panel=panel.BG, backdrop="#%02x%02x%02x" % panel.BACKDROP, text=panel.INK,
                    muted=panel.MUTED, input=panel.INPUT, accent=panel.MINT,
                    button_hover="#454749", disabled_text="#888888", border="#666666",
                    description_border="#777777", slider_track="#434547", slider_active="#00c5a5",
                    slider_tick="#8a8b8c", slider_thumb="#2dff8f", error="#ff938b",
                    badge="#d52b30", close="#ff736a", minimize="#febc2e", transparency_key="#010203"),
        panel=dict(radius_px=panel.RADIUS, fills_in_order=panel.FILLS, glass_fill=panel.GLASS_FILL,
                   fill_tuple_schema=["r_0_to_1", "g_0_to_1", "b_0_to_1", "opacity", "blend_mode"],
                   figma_glass_metadata=panel.GLASS, figma_shadow_metadata=panel.SHADOW,
                   implementation=dict(backdrop=panel.BACKDROP, resolved_rgb=panel.panel_color(),
                                       shadow_gaussian_sigma_px=20, external_shadow_supported=False,
                                       live_refraction_supported=False, glass_stroke_in_figma=False,
                                       simulated_edge=dict(width_px=1, alpha_mask=90,
                                                           side_fade="abs(1 - 2*y/max(1,height-1))"))),
        window=dict(default_opacity=1, allowed_opacity=[.6, 1], default_topmost=True,
                    frameless=True, resizable=False, drag_header_height_px=62),
        page_sizes_px=dict(main=[277,347], settings=[420,540], controls=[420,690], chat=[420,530], chzzk=[420,620],
                           start=[277,347], start1=[339,430], start2=[339,775], start3=[339,286], start_end=[277,347]),
        fonts=dict(default_family_preference=["Pretendard", "맑은 고딕"], default_size_px=12,
                   sizes_px=[8,11,12,14,16,24], title_and_usage_family="Pretendard SemiBold",
                   bundled_weights=[400, 600, 700], bundled_version="1.3.9", registration="process-private",
                   orb_shortcut_weight="bold", chat_name_weight="bold"),
        button_surface=dict(raster_size_px=[64,32], radius_px=8, border_px=1, stretch_border_px=8,
                            padding=[9,5]),
        images=dict(orb_base=dict(file="v2-orb-base.png", display_px=[196,196], alpha=.72, center=[99,100]),
                    orb_glow=dict(file="v2-orb-glow.png", display_px=[158,158], alpha=.72, center=[99,99]),
                    orb_face=dict(file="v2-source-orb-face.svg", display_px=[84,80], position=[57,40]),
                    header=dict(file="v2-header.svg", display_px=[70,21], position=[28,28]),
                    settings=dict(file="v2-source-settings.svg", display_px=[15,14.4776], slot=[194,28,21,21]),
                    persona=dict(file="v2-persona-*.png", display_px=[51,48], position=[28,355])))
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result = dict(schema_version=1, exported_at=datetime.now(timezone.utc).isoformat(), git_revision=revision,
                  scope="Main, Settings, five onboarding screens, Controls, Chat, service connection dialog; synthetic states",
                  privacy=dict(user_settings_read=False, secrets_included=False, network_calls=0, screenshots=0),
                  tokens=tokens, runtime=runtime, source_inventory=source_inventory(), assets=asset_inventory(),
                  limitations=["Design tokens use logical pixels. Windows scales geometry, pixel fonts and images together at startup using system DPI; macOS/Linux retain their logical layout.",
                               "Moving between Windows monitors with different DPI may require restarting the app for sharp rendering.",
                               "Tk geometry/font pixel sizes depend on local DPI and installed fonts.",
                               "Glass parameters are retained metadata; native Figma optical refraction is not implemented.",
                               "OS-owned file pickers/message boxes and titlebar metrics are system-dependent.",
                               "Source call inventory also includes constructor values overridden later; runtime is authoritative."])
    target = OUTPUT / "desktop-design.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    css = ["/* Reference variables only. The Tk desktop app does not load this CSS. */", ":root {"]
    css += [f"  --tiki-{name.replace('_','-')}: {value};" for name, value in tokens["colors"].items()]
    css += [f"  --tiki-panel-radius: {panel.RADIUS}px;", "  --tiki-button-radius: 8px;",
            "  --tiki-fill-2-opacity: 0.2;", "  --tiki-glass-fill-opacity: 0.2;",
            "  --tiki-orb-layer-opacity: 0.72;", '  --tiki-font-family: "Pretendard", "Malgun Gothic", sans-serif;',
            "  --tiki-font-size: 12px;", "}", ""]
    (OUTPUT / "reference-tokens.css").write_text("\n".join(css), encoding="utf-8")
    archive = ROOT / "dist" / "tiki-desktop-design.zip"
    archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(OUTPUT.glob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(ROOT).as_posix())
        for item in result["assets"]:
            bundle.write(ROOT / item["path"], item["path"])
        for path in SOURCES:
            bundle.write(ROOT / path, path)
        bundle.write(Path(__file__), "apps/desktop/export_design.py")
    print(json.dumps(dict(json=str(target), archive=str(archive), screens=len(runtime["screens"]),
                          assets=len(result["assets"]), source_calls=sum(len(s["style_and_layout_calls"]) for s in result["source_inventory"])),
                     ensure_ascii=False))


if __name__ == "__main__":
    export()
