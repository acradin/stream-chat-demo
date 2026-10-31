import io
import unittest
from unittest.mock import patch

from PIL import Image
from apps.desktop.window.capture import WindowSource, capture_window
from apps.desktop.overlay import clean_settings


class WindowCaptureTests(unittest.TestCase):
    def test_capture_is_window_only_and_bounded(self):
        source = WindowSource(123, 456, "Game")
        with patch("apps.desktop.window.capture._window_info", return_value=source), \
                patch("apps.desktop.window.capture.ImageGrab.grab", return_value=Image.new("RGB", (2560, 1440))) as grab:
            data = capture_window(source)
        grab.assert_called_once_with(window=123)
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (1280, 720))

    def test_missing_or_reused_window_never_falls_back_to_desktop(self):
        source = WindowSource(123, 456, "Game")
        for current in (None, WindowSource(123, 999, "Different process")):
            with patch("apps.desktop.window.capture._window_info", return_value=current), \
                    patch("apps.desktop.window.capture.ImageGrab.grab") as grab:
                with self.assertRaises(ValueError):
                    capture_window(source)
                grab.assert_not_called()

    def test_saved_mode_is_validated_and_never_saves_window_handle_or_api_key(self):
        result = clean_settings({"mode": "realtime", "duration": 120, "interval": 10,
                                 "handle": 123, "OPENAI_API_KEY": "secret"})
        self.assertEqual((result["mode"], result["duration"], result["interval"]), ("realtime", 120, 10))
        self.assertNotIn("handle", result)
        self.assertNotIn("OPENAI_API_KEY", result)
        result = clean_settings({"mode": "invalid", "duration": True, "interval": -1})
        self.assertEqual((result["mode"], result["duration"], result["interval"]), ("manual", 60, 5))
