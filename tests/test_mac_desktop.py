"""Mac adapter contracts runnable without macOS; native checks remain separate."""
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest
from unittest.mock import Mock, patch

from apps.desktop.capture_types import WindowSource
from apps.desktop.mac import capture, hotkey
from apps.desktop.paths import state_directory


def window(handle=123, pid=456, title="Game"):
    return NS(windowID=lambda: handle, owningApplication=lambda: NS(processID=lambda: pid),
              title=lambda: title, windowLayer=lambda: 0,
              frame=lambda: NS(size=NS(width=2560, height=1440)))


class MacCaptureTests(unittest.TestCase):
    def test_missing_or_reused_window_never_captures_another_source(self):
        for windows in ([], [window(pid=999)]):
            with patch.object(capture, "_frameworks", return_value=(Mock(), Mock())), \
                 patch.object(capture, "_shareable_content", return_value=NS(windows=lambda: windows)), \
                 patch.object(capture, "_capture") as grab:
                with self.assertRaises(ValueError):
                    capture.capture_window(WindowSource(123, 456, "Game"))
                grab.assert_not_called()

    def test_title_change_preserves_window_identity_and_capture_bounds(self):
        selected = window(title="New title")
        kit = Mock()
        with patch.object(capture, "_frameworks", return_value=(Mock(), kit)), \
             patch.object(capture, "_shareable_content", return_value=NS(windows=lambda: [selected])), \
             patch.object(capture, "_capture", return_value=b"jpeg") as grab:
            self.assertEqual(capture.capture_window(WindowSource(123, 456, "Old title")), b"jpeg")
        kit.SCContentFilter.alloc.return_value.initWithDesktopIndependentWindow_.assert_called_once_with(selected)
        self.assertEqual(grab.call_args.args[1:], (2560, 1440, 1280, .75))

    def test_denied_permission_never_requests_shareable_content(self):
        quartz, kit = Mock(), Mock()
        quartz.CGPreflightScreenCaptureAccess.return_value = False
        with patch.object(capture, "_frameworks", return_value=(quartz, kit)), self.assertRaises(ValueError):
            capture._shareable_content()
        quartz.CGRequestScreenCaptureAccess.assert_called_once_with()
        kit.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_.assert_not_called()

    def test_native_callback_errors_and_timeouts_are_bounded(self):
        self.assertEqual(capture._complete(lambda callback: callback("image", None)), "image")
        with self.assertRaises(ValueError):
            capture._complete(lambda callback: callback(None, "permission error"))
        with self.assertRaises(ValueError):
            capture._complete(lambda callback: None, timeout=0)

    def test_screenshot_configuration_preserves_aspect_ratio_and_has_no_audio(self):
        kit = Mock()
        kit.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_.side_effect = (
            lambda content_filter, config, callback: callback("image", None))
        with patch.object(capture, "_frameworks", return_value=(Mock(), kit)), \
             patch.object(capture, "_jpeg", return_value=b"jpeg"):
            self.assertEqual(capture._capture("selected-window", 2560, 1440, 1280, .75), b"jpeg")
        config = kit.SCStreamConfiguration.alloc.return_value.init.return_value
        config.setWidth_.assert_called_once_with(1280)
        config.setHeight_.assert_called_once_with(720)
        config.setCapturesAudio_.assert_called_once_with(False)

    def test_primary_capture_selects_main_display_and_excludes_own_windows(self):
        quartz, kit = Mock(), Mock()
        quartz.CGMainDisplayID.return_value = 42
        primary = NS(displayID=lambda: 42, width=lambda: 1920, height=lambda: 1080)
        other = NS(displayID=lambda: 99)
        own, foreign = window(pid=111), window()
        content = NS(displays=lambda: [other, primary], windows=lambda: [own, foreign])
        with patch.object(capture, "_frameworks", return_value=(quartz, kit)), \
             patch.object(capture, "_shareable_content", return_value=content), \
             patch.object(capture.os, "getpid", return_value=111), patch.object(capture, "_capture"):
            capture.capture_primary_screen()
        kit.SCContentFilter.alloc.return_value.initWithDisplay_excludingWindows_.assert_called_once_with(primary, [own])


class MacShortcutTests(unittest.TestCase):
    def test_pre_tk_identity_does_not_create_a_cocoa_application(self):
        from apps.desktop.mac import branding
        application = Mock()
        with patch.dict(sys.modules, {"AppKit": NS(NSApplication=application)}):
            branding.set_app_identity()
        application.sharedApplication.assert_not_called()

    def test_cmd_option_and_physical_key_mapping(self):
        self.assertEqual(hotkey.parse_hotkey("command+shift+g"), ("Cmd+Shift+G", (1 << 17) | (1 << 20), 5))
        self.assertEqual(hotkey.parse_hotkey("option+Space"), ("Option+Space", 1 << 19, 49))
        self.assertEqual(hotkey.parse_hotkey("alt+Space"), ("Option+Space", 1 << 19, 49))
        self.assertEqual(hotkey.parse_hotkey("F12"), ("F12", 0, 111))
        for invalid in (None, "A", "Cmd", "Cmd+Cmd+G", "Cmd+invalid", "F25"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                hotkey.parse_hotkey(invalid)

    def test_monitor_ignores_repeat_extra_modifiers_and_other_keys(self):
        callback = Mock()
        binding = hotkey.GlobalHotkey(callback)
        binding.binding = (hotkey.MODIFIERS["Cmd"], 5)
        for flags, code, repeat in ((1 << 20, 5, True), (1 << 20, 4, False), (1 << 20 | 1 << 17, 5, False)):
            binding._global(NS(modifierFlags=lambda: flags, keyCode=lambda: code, isARepeat=lambda: repeat))
        callback.assert_not_called()
        event = NS(modifierFlags=lambda: 1 << 20, keyCode=lambda: 5, isARepeat=lambda: False)
        self.assertIs(binding._local(event), event)
        callback.assert_called_once_with()

    def test_permission_failure_keeps_previous_binding_and_close_removes_monitors(self):
        events = Mock()
        events.addGlobalMonitorForEventsMatchingMask_handler_.return_value = "global"
        events.addLocalMonitorForEventsMatchingMask_handler_.return_value = "local"
        trusted = Mock(return_value=True)
        with patch.dict(sys.modules, {"AppKit": NS(NSEvent=events, NSEventMaskKeyDown=1024),
                        "HIServices": NS(AXIsProcessTrustedWithOptions=trusted, kAXTrustedCheckOptionPrompt="prompt")}):
            binding = hotkey.GlobalHotkey(Mock())
            self.assertTrue(binding.replace("Cmd+G")[0])
            previous = binding.binding
            trusted.return_value = False
            self.assertFalse(binding.replace("Cmd+H")[0])
            self.assertEqual(binding.binding, previous)
            binding.close()
            self.assertEqual([call.args[0] for call in events.removeMonitor_.call_args_list], ["global", "local"])

    def test_mac_installed_data_is_outside_app_bundle(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "platform", "darwin"):
            self.assertEqual(state_directory(), Path.home() / "Library/Application Support/tiki/desktop")
