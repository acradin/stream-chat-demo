import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from apps.desktop.connection import save_connection
from apps.desktop.paths import connection_file, state_directory
from backend.env import DESKTOP_KEYS, read_env_file
from apps.desktop.packaging.verify_bundle import verify


class DesktopInstallTests(unittest.TestCase):
    def test_bundle_gate_distinguishes_exclusions_from_collected_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "StreamChat.exe").touch()
            analysis = bundle / "Analysis.toc"
            analysis.write_text(repr((["backend.server"], [("backend.env", "env.py", "PYMODULE")])), encoding="utf-8")
            verify(bundle, analysis)
            analysis.write_text(repr([("backend.server", "server.py", "PYMODULE")]), encoding="utf-8")
            with self.assertRaises(ValueError):
                verify(bundle, analysis)
            analysis.write_text("[]", encoding="utf-8")
            (bundle / ".env").write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                verify(bundle, analysis)

    def test_frozen_paths_use_user_data_not_installation_directory(self):
        with patch.object(sys, "frozen", True, create=True), patch.dict(os.environ, {"LOCALAPPDATA": "C:/Users/Example/AppData/Local"}):
            expected = Path("C:/Users/Example/AppData/Local/StreamChat/desktop")
            self.assertEqual(state_directory(), expected)
            self.assertEqual(connection_file(), expected / ".env")

    def test_source_paths_preserve_existing_development_settings(self):
        with patch.object(sys, "frozen", False, create=True):
            root = Path(__file__).resolve().parents[1]
            self.assertEqual(state_directory(), root / "runs/desktop")
            self.assertEqual(connection_file(), root / "apps/desktop/.env")

    def test_connection_save_roundtrip_only_contains_service_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            with patch.dict(os.environ, {}, clear=True), patch("apps.desktop.service_client.DESKTOP_ENV", path):
                result = save_connection(path, "https://service.example.com/", "sample-connection-code")
                self.assertEqual(result["base_url"], "https://service.example.com")
                self.assertEqual(read_env_file(path, DESKTOP_KEYS), {
                    "CHAT_SERVICE_URL": "https://service.example.com", "CHAT_SERVICE_TOKEN": "sample-connection-code"})
                self.assertNotIn("OPENAI", path.read_text())
                self.assertFalse(any(p.name.startswith(".connection-") for p in path.parent.iterdir()))

    def test_invalid_connection_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            original = "CHAT_SERVICE_URL=https://service.example.com\nCHAT_SERVICE_TOKEN=old-token\n"
            path.write_text(original, encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True), patch("apps.desktop.service_client.DESKTOP_ENV", path):
                for url, token in (("http://remote.example.com", "token"), ("", "token"),
                                   ("https://service.example.com", "bad\nnew-key=value"),
                                   ("https://service.example.com", "")):
                    with self.assertRaises(ValueError):
                        save_connection(path, url, token)
                    self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_import_reads_allowlist_without_changing_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("CHAT_SERVICE_URL=https://service.example.com\nCHAT_SERVICE_TOKEN=code\nOPENAI_API_KEY=must-stay-out\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                values = read_env_file(path, DESKTOP_KEYS)
                self.assertEqual(set(values), DESKTOP_KEYS)
                self.assertEqual(dict(os.environ), {})
