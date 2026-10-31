"""Linux native contracts. Native input/capture tests require an isolated Xvfb."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform.startswith("linux"),"Linux adapter")
class LinuxContracts(unittest.TestCase):
    def test_shortcut_parser_and_wayland_limit(self):
        from apps.desktop.linux.hotkey import parse_hotkey, GlobalHotkey
        self.assertEqual(parse_hotkey("shift+control+g")[0],"Ctrl+Shift+G")
        self.assertEqual(parse_hotkey("F12")[0],"F12")
        for value in ("A","Ctrl+Ctrl+G","Alt+garbage",None):
            with self.assertRaises(ValueError):
                parse_hotkey(value)
        hotkey = GlobalHotkey(lambda:None)
        with patch.dict(os.environ,{"WAYLAND_DISPLAY":"wayland-test"}):
            self.assertFalse(hotkey.replace("F8")[0])
        hotkey.close()

    def test_wayland_screen_capture_does_not_fall_back(self):
        from apps.desktop.linux.capture import capture_primary_screen
        with patch.dict(os.environ,{"WAYLAND_DISPLAY":"wayland-test"}), patch("PIL.ImageGrab.grab") as grab:
            with self.assertRaises(ValueError):
                capture_primary_screen()
            grab.assert_not_called()


@unittest.skipUnless(sys.platform.startswith("linux") and os.environ.get("TIKI_X11_TEST") == "1",
                     "Native tests run only inside the explicitly isolated Xvfb")
class LinuxNativeTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.overlay = tk.Tk()
        self.overlay.withdraw()
        self.addCleanup(self.overlay.destroy)

    def test_passive_hotkey_conflict_repeat_and_replacement(self):
        import ctypes as c
        from ctypes.util import find_library
        from apps.desktop.linux.x11 import API, Display, bind, P, U, I
        from apps.desktop.linux.hotkey import GlobalHotkey
        events = []
        first,second = GlobalHotkey(lambda:events.append(True)),GlobalHotkey(lambda:None)
        self.addCleanup(first.close)
        self.addCleanup(second.close)
        self.assertEqual(first.replace("F8"),(True,""))
        self.assertFalse(second.replace("F8")[0])
        self.assertEqual(second.replace("F9"),(True,""))
        self.assertFalse(first.replace("F9")[0])
        self.assertEqual(first.current,"F8")
        xtest = c.CDLL(find_library("Xtst") or "libXtst.so.6")
        bind(xtest,"XTestFakeKeyEvent",I,[P,c.c_uint,I,U])
        with Display() as display:
            key = API.XKeysymToKeycode(display.pointer,API.XStringToKeysym(b"F8"))
            xtest.XTestFakeKeyEvent(display.pointer,key,True,0)
            display.check()
            deadline = time.monotonic()+2
            while not events and time.monotonic()<deadline:
                time.sleep(.02)
            xtest.XTestFakeKeyEvent(display.pointer,key,True,0)
            display.check()
            time.sleep(.1)
            self.assertEqual(len(events),1)
            xtest.XTestFakeKeyEvent(display.pointer,key,False,0)
            display.check()
        self.assertEqual(first.replace("Ctrl+Shift+G"),(True,""))

    def test_selected_window_pixels_and_stale_identity(self):
        from PIL import Image
        from apps.desktop.linux.capture import capture_window, list_windows
        from apps.desktop.capture_types import WindowSource
        code = '''
import ctypes as c, json, os, tkinter as tk
from apps.desktop.linux.x11 import API, Display, bind, P, U, I
bind(API,"XChangeProperty",I,[P,U,U,U,I,I,P,I])
root=tk.Tk()
root.overrideredirect(True)
root.geometry("240x180+30+30")
root.configure(bg="#ee0000")
root.update()
window=root.winfo_id()
with Display() as d:
    pid=(U*1)(os.getpid())
    API.XChangeProperty(d.pointer,window,d.atom("_NET_WM_PID"),d.atom("CARDINAL"),32,0,c.cast(pid,P),1)
    title=c.create_string_buffer(b"tiki-isolated-test")
    API.XChangeProperty(d.pointer,window,d.atom("_NET_WM_NAME"),d.atom("UTF8_STRING"),8,0,c.cast(title,P),18)
    windows=(U*1)(window)
    API.XChangeProperty(d.pointer,d.root,d.atom("_NET_CLIENT_LIST"),d.atom("WINDOW"),32,0,c.cast(windows,P),1)
    d.check()
print(json.dumps(dict(window=window,pid=os.getpid())),flush=True)
root.mainloop()
'''
        process = subprocess.Popen([sys.executable,"-B","-c",code],stdout=subprocess.PIPE,text=True,
                                   cwd=Path(__file__).resolve().parents[1])
        def cleanup():
            process.terminate()
            process.wait(timeout=5)
            process.stdout.close()
        self.addCleanup(cleanup)
        data = json.loads(process.stdout.readline())
        source = WindowSource(data["window"],data["pid"],"tiki-isolated-test")
        self.assertIn(source,list_windows())
        with Image.open(io.BytesIO(capture_window(source))) as image:
            red,green,blue = image.getpixel((100,100))
            self.assertGreater(red,200)
            self.assertLess(green+blue,30)
        # A covering window must not leak into the selected window's image.
        self.overlay.overrideredirect(True)
        self.overlay.geometry("240x180+30+30")
        self.overlay.configure(bg="#00ee00")
        self.overlay.deiconify()
        self.overlay.lift()
        self.overlay.update()
        with Image.open(io.BytesIO(capture_window(source))) as image:
            red,green,blue = image.getpixel((100,100))
            self.assertGreater(red,200)
            self.assertLess(green+blue,30)
        with self.assertRaises(ValueError):
            capture_window(WindowSource(source.handle,source.pid+1,source.title))
        process.terminate()
        process.wait(timeout=5)
        with self.assertRaises(ValueError):
            capture_window(source)
