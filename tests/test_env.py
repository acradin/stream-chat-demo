import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.env import BACKEND_KEYS, load_env_file
from apps.desktop.service_client import ServiceClient


class EnvTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / ".env"

    def test_loads_bom_quotes_comments_and_literal_values(self):
        self.path.write_text("# operator settings\nexport OPENAI_API_KEY='sk-test-$literal#part' # comment\n"
                             'OPENAI_MODEL="gpt-6-astra"\n'
                             'CHAT_SERVICE_ACCOUNTS=\'{"alice":"token"}\'\n'
                             'CHAT_SERVICE_TOKEN=plain-value # comment\n', encoding="utf-8-sig")
        with patch.dict(os.environ, {}, clear=True):
            load_env_file(self.path, BACKEND_KEYS)
            self.assertEqual(os.environ["OPENAI_API_KEY"], "sk-test-$literal#part")
            self.assertEqual(os.environ["OPENAI_MODEL"], "gpt-6-astra")
            self.assertEqual(os.environ["CHAT_SERVICE_ACCOUNTS"], '{"alice":"token"}')
            self.assertEqual(os.environ["CHAT_SERVICE_TOKEN"], "plain-value")

    def test_existing_environment_wins_even_when_empty(self):
        self.path.write_text("OPENAI_API_KEY=file-key\nOPENAI_MODEL=file-model\n", encoding="utf-8")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "deployment-key", "OPENAI_MODEL": ""}, clear=True):
            load_env_file(self.path, BACKEND_KEYS)
            self.assertEqual(os.environ["OPENAI_API_KEY"], "deployment-key")
            self.assertEqual(os.environ["OPENAI_MODEL"], "")

    def test_missing_file_is_optional(self):
        with patch.dict(os.environ, {}, clear=True):
            load_env_file(self.path, BACKEND_KEYS)
            self.assertEqual(dict(os.environ), {})

    def test_empty_value_with_comment_stays_empty(self):
        self.path.write_text("OPENAI_API_KEY= # fill later\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True):
            load_env_file(self.path, BACKEND_KEYS)
            self.assertEqual(os.environ["OPENAI_API_KEY"], "")

    def test_invalid_file_is_atomic_and_error_does_not_echo_secrets(self):
        for bad in ("secret-value-without-equals", "OPENAI_API_KEY='secret-unclosed", "OPENAI_API_KEY=secret\0value"):
            self.path.write_text("OPENAI_MODEL=gpt-6-astra\n" + bad, encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ValueError) as error:
                    load_env_file(self.path, BACKEND_KEYS)
                self.assertNotIn("secret", str(error.exception))
                self.assertNotIn("OPENAI_MODEL", os.environ)

    def test_desktop_loads_only_its_service_settings(self):
        self.path.write_text("CHAT_SERVICE_URL=http://127.0.0.1:8766\nCHAT_SERVICE_TOKEN=local-token\n"
                             "OPENAI_API_KEY=must-stay-out\nPATH=must-stay-out\n", encoding="utf-8")
        with patch.dict(os.environ, {}, clear=True), patch("apps.desktop.service_client.DESKTOP_ENV", self.path):
            client = ServiceClient()
            self.assertEqual(client.base_url, "http://127.0.0.1:8766")
            self.assertEqual(client._token, "local-token")
            self.assertNotIn("OPENAI_API_KEY", os.environ)
            self.assertNotIn("PATH", os.environ)

    def test_backend_main_loads_file_before_validating_provider(self):
        from backend import server
        self.path.write_text("OPENAI_API_KEY=server-only-test-key\nOPENAI_MODEL=gpt-6-astra\n"
                             "CHAT_SERVICE_TOKEN=" + "a" * 40, encoding="utf-8")
        with (patch.dict(os.environ, {}, clear=True), patch.object(server, "BACKEND_ENV", self.path),
              patch("sys.argv", ["server"]), patch.object(server, "OpenAIScreenshotProvider") as provider,
              patch.object(server, "create_app") as create, patch.object(server.web, "run_app") as run):
            provider.side_effect = lambda **kwargs: self.assertEqual(os.environ["OPENAI_API_KEY"], "server-only-test-key")
            server.main()
            self.assertEqual(create.call_args.kwargs["accounts"], {"development": "a" * 40})
            self.assertEqual(create.call_args.kwargs["model"], "gpt-6-astra")
            run.assert_called_once()
