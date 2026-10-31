"""Native geometry checks for the fixed layout at real desktop scale factors."""
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from apps.desktop.export_design import OfflineService
from apps.desktop.overlay import Overlay
from backend.personas import PERSONAS


@unittest.skipUnless(sys.platform in ("win32","darwin") or os.environ.get("DISPLAY"), "Native Tk display required")
class DesktopLayoutTests(unittest.TestCase):
    def test_images_text_and_slider_stay_aligned_at_desktop_scales(self):
        for factor in (1.0, 1.25, 1.5):
            with self.subTest(scale=factor), tempfile.TemporaryDirectory() as directory:
                root = tk.Tk()
                root.withdraw()
                try:
                    with patch("apps.desktop.figma_ui.display_scale",return_value=factor), patch("apps.desktop.vector.sys",SimpleNamespace(platform="win32")), patch.object(Overlay,"refresh_service_usage",lambda _:None):
                        app = Overlay(root,Path(directory),service=OfflineService(),enable_hotkey=False,window_list=lambda:[])
                    view = app.view
                    root.update_idletasks()
                    self.assertEqual(int(view.main.cget("width")),round(277*factor))
                    for page in (view.main,view.settings,view.onboarding.persona_page):
                        for item in page.find_all():
                            if page.type(item) == "image" and page.coords(item) == [0.0,0.0]:
                                name = page.itemcget(item,"image")
                                self.assertEqual(int(root.tk.call("image","width",name)),int(page.cget("width")))
                    app.view._count_changed(5)
                    knob = view.slider.coords(view.slider_knob)
                    self.assertAlmostEqual((knob[0]+knob[2])/2,169*factor)
                    self.assertEqual(app.settings["count"],5)
                    view.show("chzzk")
                    root.update_idletasks()
                    self.assertGreaterEqual(app.delivery_log.winfo_height(),60*factor)
                    self.assertLessEqual(app.auth_copy.winfo_x()+app.auth_copy.winfo_width(),app.channel_controls.winfo_width())
                    view.show("settings")
                    root.update_idletasks()
                    self.assertEqual(view.main.winfo_manager(),"pack")
                    self.assertEqual(int(view.settings.cget("width")),round(420*factor))
                    self.assertEqual(int(view.settings.cget("height")),round(540*factor))
                    self.assertEqual(str(view.settings_window.transient()),str(root))
                    for page in (view.main,view.settings):
                        header = next(item for item in page.find_all() if page.type(item)=="image" and any(tag.startswith("vector-header-") for tag in page.gettags(item)))
                        self.assertEqual(int(root.tk.call("image","width",page.itemcget(header,"image"))),round(70*factor))
                    self.assertEqual(sum(view.settings.itemcget(avatar,"state") == "normal" for avatar,_ in view.persona_members),5)
                    view._count_changed(1)
                    for key in PERSONAS:
                        app.persona_vars[0].set(PERSONAS[key]["name"])
                        view.refresh_persona()
                        bounds = view.settings.bbox(view.persona_description)
                        self.assertLess(bounds[2],313*factor)
                        self.assertLess(bounds[3],415*factor)
                    for card in view.onboarding.cards:
                        for item in card.find_all():
                            if card.type(item) == "text":
                                bounds = card.bbox(item)
                                if bounds:
                                    self.assertGreaterEqual(bounds[0],0)
                                    self.assertLessEqual(bounds[2],int(card.cget("width")))
                                    self.assertLessEqual(bounds[3],int(card.cget("height")))
                    root.after_cancel(app.poll_id)
                finally:
                    root.destroy()
