"""User-facing settings apply to preview, persistence and generation together."""
import json
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from apps.desktop.export_design import OfflineService
from apps.desktop.overlay import Overlay, clean_settings
from apps.desktop.mac import hotkey as mac_hotkey, shell as mac_shell


class MacSettingsTests(unittest.TestCase):
    def test_default_migration_and_custom_option_display(self):
        with patch("apps.desktop.overlay.sys",SimpleNamespace(platform="darwin")), patch("apps.desktop.overlay.parse_hotkey",mac_hotkey.parse_hotkey):
            for data in ({},{"hotkey":"Ctrl+Alt+Space"},{"hotkey":"bad"}):
                self.assertEqual(clean_settings(data)["hotkey"],"Cmd+Shift+Space")
            self.assertEqual(clean_settings({"hotkey":"Cmd+Alt+G"})["hotkey"],"Cmd+Option+G")

    def test_frameless_mac_window_retains_keyboard_focus_support(self):
        root = Mock()
        root._w = ".settings"
        mac_shell.configure_window(root)
        root.overrideredirect.assert_called_once_with(False)
        root.tk.call.assert_called_once_with("::tk::unsupported::MacWindowStyle","style",".settings","document",("noTitleBar","noShadow"))


@unittest.skipUnless(sys.platform in ("win32","darwin") or os.environ.get("DISPLAY"),"Native Tk display required")
class DesktopSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        with patch.object(Overlay,"refresh_service_usage",lambda _:None):
            self.app = Overlay(self.root,Path(self.temp.name),service=OfflineService(),enable_hotkey=False,window_list=lambda:[])
        self.addCleanup(lambda:self.root.after_cancel(self.app.poll_id))

    def saved(self):
        return json.loads(self.app.settings_path.read_text(encoding="utf-8"))

    def test_multiple_personas_reach_count_preview_and_generation_snapshot(self):
        wizard = self.app.view.onboarding
        wizard.select_personas()
        wizard.toggle("analyst")
        wizard.toggle("coach")
        wizard.to_link()
        self.assertEqual(self.app.settings["count"],3)
        self.assertEqual(self.app.view.slider.value,3)
        self.assertEqual(self.app.count_text.get(),"3명")
        snapshot = self.app._snapshot_settings()
        self.assertEqual(snapshot["personas"][:snapshot["count"]],["witty_friend","analyst","coach"])
        self.assertEqual(self.saved()["count"],3)
        self.assertEqual(sum(self.app.view.settings.itemcget(image,"state")=="normal" for image,_ in self.app.view.persona_members),3)
        wizard.select_personas()
        self.assertEqual(wizard.selected,["witty_friend","analyst","coach"])

    def test_recording_applies_hotkey_and_conflict_retains_previous_binding(self):
        binding = Mock(current="Ctrl+Alt+Space")
        binding.replace.return_value = (True,"")
        self.app.hotkey = binding
        self.app.record_hotkey()
        with patch("apps.desktop.overlay.pressed_hotkey",return_value="Ctrl+Shift+F8"):
            self.app._capture_hotkey(SimpleNamespace(keysym="F8",keycode=119))
        self.assertEqual(self.saved()["hotkey"],"Ctrl+Shift+F8")
        self.assertEqual(self.app.trigger_button.itemcget(self.app.trigger_button.key_label,"text"),"Ctrl+Shift+F8")
        binding.replace.return_value = (False,"다른 앱에서 사용 중")
        self.app.hotkey_var.set("Ctrl+Shift+F9")
        with patch("apps.desktop.overlay.messagebox.showerror") as error:
            self.app.apply_hotkey()
            error.assert_called_once()
        self.assertEqual(self.app.hotkey_var.get(),"Ctrl+Shift+F8")
        self.assertEqual(self.saved()["hotkey"],"Ctrl+Shift+F8")

    def test_link_edit_saved_and_chat_is_accessible_from_main(self):
        link = "https://chzzk.naver.com/live/"+"a"*32
        self.app.channel_entry.delete(0,"end")
        self.app.channel_entry.insert(0,link)
        self.app.view.save_button.invoke()
        self.assertEqual(self.saved()["channel_url"],link)
        self.app.view.chat_button.invoke()
        self.assertEqual(self.app.view.current,"chat")
        self.app._append_line(dict(participant=1,persona="analyst",status="ready",comment="테스트 채팅",error=""))
        self.assertIn("테스트 채팅",self.app.chat_log.get("1.0","end"))

    def test_delivery_view_is_separate_and_toggle_persists_without_sending(self):
        app = self.app
        app.view.chzzk_button.invoke()
        self.assertEqual(app.view.current,"chzzk")
        app.channel_var.set("https://chzzk.naver.com/live/"+"b"*32)
        app.send_enabled.set(True)
        self.assertFalse(app.toggle_delivery())
        self.assertFalse(app.send_enabled.get())
        app.connected_channel = {"connected":True,"channelId":"b"*32,"channelName":"테스트"}
        with patch.object(app,"refresh_channel"):
            app.send_enabled.set(True)
            self.assertTrue(app.toggle_delivery())
        self.assertEqual(self.saved()["destination"],"chzzk")
        app._append_line(dict(participant=1,persona="analyst",status="ready",comment="분리할 채팅",error="",
                              delivery={"status":"sent","message":"전송 성공 확인","messageId":"test"}))
        self.assertIn("분리할 채팅",app.chat_log.get("1.0","end"))
        self.assertNotIn("전송 성공 확인",app.chat_log.get("1.0","end"))
        self.assertIn("분리할 채팅",app.delivery_log.get("1.0","end"))
        self.assertIn("전송 성공 확인",app.delivery_log.get("1.0","end"))
        app.send_enabled.set(False)
        self.assertTrue(app.toggle_delivery())
        self.assertEqual(self.saved()["destination"],"app")
        self.assertEqual(app._output_options(app._snapshot_settings()),{})

    def test_auth_opens_browser_and_matching_connection_does_not_enable_delivery(self):
        app = self.app
        app.channel_var.set("b"*32)
        invitation = {"authorization_url":"https://chzzk.naver.com/account-interlock?state=test", "channel_id":"b"*32,"expires_in":600}
        app.service.authorize_chzzk = AsyncMock(return_value=invitation)
        with patch("apps.desktop.overlay.webbrowser.open",return_value=True) as browser:
            app.authorize_channel()
            deadline = time.monotonic()+2
            while app.auth_loading and time.monotonic() < deadline:
                self.root.update()
                time.sleep(.01)
            browser.assert_called_once_with(invitation["authorization_url"],new=2)
            self.assertFalse(app.send_enabled.get())
            app.events.put(("channel",(app.service,{"connected":True,"channelId":"b"*32,"channelName":"테스트","message":"연결됨"})))
            self.root.after_cancel(app.poll_id)
            app._poll()
            self.assertIn("연결되어",app.auth_info.get())
            self.assertEqual(app.auth_deadline,0)
            self.assertFalse(app.send_enabled.get())
            self.assertEqual(self.saved()["destination"],"app")

    def test_stale_auth_result_and_expired_link_never_open_or_copy(self):
        app = self.app
        app.auth_target = "a"*32
        epoch = app.auth_epoch
        app.channel_var.set("b"*32)
        with patch("apps.desktop.overlay.webbrowser.open") as browser:
            app._authorization_ready(app.service,epoch,{"authorization_url":"https://chzzk.naver.com","expires_in":600},"")
            browser.assert_not_called()
        app.authorization_link = "expired-link"
        app.auth_deadline = time.monotonic()-1
        with patch.object(app.root,"clipboard_append") as copy:
            app.copy_authorization_link()
            copy.assert_not_called()
        self.assertEqual(app.authorization_link,"")
