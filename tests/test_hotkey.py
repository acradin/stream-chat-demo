import sys
import unittest
from unittest.mock import patch

from apps.desktop.window.hotkey import GlobalHotkey, parse_hotkey, pressed_hotkey
from apps.desktop.overlay import clean_settings


class HotkeyTests(unittest.TestCase):
    def test_custom_combinations_normalize_and_map_to_windows_keys(self):
        for text, expected in (
            ("shift + control + g", ("Ctrl+Shift+G", 6, 0x47)),
            ("F8", ("F8", 0, 0x77)),
            ("windows+alt+9", ("Alt+Win+9", 9, 0x39)),
            ("ctrl+pgdn", ("Ctrl+PageDown", 2, 0x22)),
            ("alt+Num4", ("Alt+Num4", 1, 0x64)),
            ("Ctrl+Alt+Space", ("Ctrl+Alt+Space", 3, 0x20)),
        ):
            with self.subTest(text=text):
                self.assertEqual(parse_hotkey(text), expected)

    def test_invalid_and_reserved_keys_do_not_silently_replace_settings(self):
        for text in (None, "", "A", "Space", "Ctrl", "Ctrl+A+B", "Ctrl+Ctrl+A",
                     "Ctrl+unknown", "F12", "Ctrl+F12", "F25", "Ctrl++A"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_hotkey(text)
        self.assertEqual(clean_settings({"hotkey": "ctrl+shift+f8"})["hotkey"], "Ctrl+Shift+F8")
        self.assertEqual(clean_settings({"hotkey": "invalid"})["hotkey"], "Ctrl+Alt+Space")

    @unittest.skipUnless(sys.platform == "win32", "Windows key state")
    def test_recording_uses_physical_keys_even_with_a_non_latin_keyboard(self):
        with patch("apps.desktop.window.hotkey.ctypes.WinDLL") as dll:
            dll.return_value.GetKeyState.side_effect = lambda code: -32768 if code in (0x11, 0x10) else 0
            self.assertEqual(pressed_hotkey(0x47), "Ctrl+Shift+G")
            self.assertIsNone(pressed_hotkey(0x11))

    @unittest.skipUnless(sys.platform == "win32", "Windows RegisterHotKey")
    def test_real_registration_conflict_keeps_previous_hotkey_active(self):
        owner, contender = GlobalHotkey(lambda: None), GlobalHotkey(lambda: None)
        self.addCleanup(owner.close)
        self.addCleanup(contender.close)
        choices = [f"Ctrl+Alt+Shift+F{number}" for number in range(13, 25)]
        occupied = next((name for name in choices if owner.replace(name)[0]), None)
        self.assertIsNotNone(occupied, "No available test hotkey")
        previous = next((name for name in choices if name != occupied and contender.replace(name)[0]), None)
        self.assertIsNotNone(previous, "No second test hotkey")
        self.assertFalse(contender.replace(occupied)[0])
        self.assertEqual(contender.current, previous)
        self.assertFalse(owner.replace(previous)[0])
        owner.close()
        self.assertTrue(contender.replace(occupied)[0])
        self.assertEqual(contender.current, occupied)
