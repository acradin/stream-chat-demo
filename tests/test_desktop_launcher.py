import os
from unittest import TestCase
from unittest.mock import MagicMock, patch

from backend.desktop_demo import desktop_environment, ensure_service


class DesktopLauncherTests(TestCase):
    def test_operator_secrets_never_enter_desktop_child_environment(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "private", "CHZZK_CLIENT_SECRET": "private",
                                      "REALTIME_MODEL": "server-only", "PATH": "keep"}, clear=True):
            environment = desktop_environment({"CHAT_SERVICE_URL": "http://127.0.0.1:8766", "CHAT_SERVICE_TOKEN": "service-code"})
        self.assertEqual(set(environment), {"PATH", "CHAT_SERVICE_URL", "CHAT_SERVICE_TOKEN"})

    def test_existing_or_remote_service_is_not_restarted(self):
        client = MagicMock(base_url="http://127.0.0.1:8766")
        with patch("backend.desktop_demo.socket.create_connection"), patch("backend.desktop_demo.subprocess.Popen") as process:
            ensure_service(client)
            process.assert_not_called()
        client.base_url = "https://service.example.com"
        with patch("backend.desktop_demo.socket.create_connection") as connect:
            ensure_service(client)
            connect.assert_not_called()
