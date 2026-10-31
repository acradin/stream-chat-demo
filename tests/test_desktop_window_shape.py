"""Native Windows region ownership/resize contracts, runnable on any OS."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from apps.desktop.window import shell


class WindowsShapeTests(unittest.TestCase):
    def test_round_region_follows_physical_dpi_and_is_not_recreated_on_moves(self):
        user = SimpleNamespace(GetWindowLongW=Mock(return_value=0),SetWindowLongW=Mock(),SetWindowRgn=Mock(return_value=1))
        gdi = SimpleNamespace(CreateRoundRectRgn=Mock(return_value=123),DeleteObject=Mock())
        root = SimpleNamespace(wm_frame=lambda:"0x100",winfo_width=lambda:416,winfo_height=lambda:520,_tiki_display_scale=1.5)
        with patch.object(shell,"sys",SimpleNamespace(platform="win32")),patch.object(shell.ctypes,"WinDLL",side_effect=lambda name,**_:user if name=="user32" else gdi,create=True):
            shell.mapped(root)
            shell.mapped(root)
        gdi.CreateRoundRectRgn.assert_called_once_with(0,0,417,521,78,78)
        user.SetWindowRgn.assert_called_once_with(256,123,True)
        gdi.DeleteObject.assert_not_called()

    def test_failed_region_transfer_frees_the_handle(self):
        user = SimpleNamespace(GetWindowLongW=Mock(return_value=0),SetWindowLongW=Mock(),SetWindowRgn=Mock(return_value=0))
        gdi = SimpleNamespace(CreateRoundRectRgn=Mock(return_value=123),DeleteObject=Mock())
        root = SimpleNamespace(wm_frame=lambda:"0x100",winfo_width=lambda:277,winfo_height=lambda:347)
        with patch.object(shell,"sys",SimpleNamespace(platform="win32")),patch.object(shell.ctypes,"WinDLL",side_effect=lambda name,**_:user if name=="user32" else gdi,create=True):
            shell.mapped(root)
        gdi.DeleteObject.assert_called_once_with(123)
