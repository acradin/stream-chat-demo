"""Service boundary tests use local HTTP and fake providers, never paid APIs."""

import asyncio
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer

from apps.desktop.service_client import ServiceClient
from backend.chat_service import DesktopService
from backend.server import create_app, validate_accounts
from test_desktop_service import FakeProvider
from test_screenshot_provider import jpeg


TOKEN_A = "a" * 40
TOKEN_B = "b" * 40


class ServiceApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.providers = []
        self.operator_inputs = []
        def provider_factory(name, model, key):
            self.operator_inputs.append((name, model, key))
            provider = FakeProvider()
            self.providers.append(provider)
            return provider
        def service_factory(directory):
            return DesktopService(directory, provider_factory=provider_factory, cooldown_s=0)
        self.server = TestServer(create_app(self.temp.name, accounts={"alice": TOKEN_A, "bob": TOKEN_B},
                                            service_factory=service_factory))
        await self.server.start_server()
        self.addAsyncCleanup(self.server.close)
        self.client = ServiceClient(base_url=str(self.server.make_url("")), token=TOKEN_A)

    def payload(self):
        return {"personas": ["witty_friend", "warm_supporter"], "context": "방송 상황",
                "screenshot": base64.b64encode(jpeg()).decode()}

    async def test_public_home_does_not_open_authenticated_service_routes(self):
        async with ClientSession() as session:
            async with session.get(self.client.base_url + "/?token=do-not-reflect") as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.content_type, "text/html")
                body = await response.text()
                self.assertIn("데스크톱 앱에서 만나요.", body)
                for private in (TOKEN_A, TOKEN_B, "do-not-reflect"):
                    self.assertNotIn(private, body)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
            async with session.head(self.client.base_url + "/") as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(await response.read(), b"")
            for method, path in (("GET", "/api/usage"), ("GET", "/api/chzzk/status"),
                                 ("GET", "/api/chat/realtime"), ("POST", "/api/chat/generate"),
                                 ("POST", "/")):
                async with session.request(method, self.client.base_url + path) as response:
                    self.assertEqual(response.status, 401, (method, path))
        self.assertEqual(self.providers, [])

    async def test_desktop_uses_service_and_usage_is_account_scoped(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "must-not-be-sent-by-desktop"}):
            lines = []
            result = await self.client.generate(["witty_friend", "warm_supporter"], "방송 상황",
                                                screenshot=jpeg(), on_line=lines.append)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(lines), 2)
        self.assertEqual(self.operator_inputs, [("openai", "gpt-6-astra", None)])
        self.assertEqual(self.providers[0].calls[0][1], jpeg())
        usage = await self.client.refresh_usage()
        self.assertEqual((usage["generation_requests"], usage["generated_chats"]), (1, 2))
        other = ServiceClient(base_url=self.client.base_url, token=TOKEN_B)
        self.assertEqual((await other.refresh_usage())["generated_chats"], 0)
        self.assertNotIn("tokens", json.dumps(result))
        self.assertNotIn("gpt-", json.dumps(result))
        self.assertNotIn("must-not-be-sent", json.dumps(result))

    async def test_missing_auth_and_client_provider_overrides_never_reach_model(self):
        async with ClientSession() as session:
            for payload, token, status in ((self.payload(), "bad", 401),
                                            ({**self.payload(), "api_key": "attacker-key"}, TOKEN_A, 400),
                                            ({**self.payload(), "model": "other"}, TOKEN_A, 400),
                                            ({**self.payload(), "account": "bob"}, TOKEN_A, 400),
                                            ({**self.payload(), "screenshot": "!"}, TOKEN_A, 400)):
                async with session.post(self.client.base_url + "/api/chat/generate", json=payload,
                                        headers={"Authorization": "Bearer " + token}) as response:
                    self.assertEqual(response.status, status)
        self.assertEqual(self.providers, [])
        self.assertEqual((await self.client.refresh_usage())["generation_requests"], 0)

    async def test_provider_failure_returns_service_language_without_secrets(self):
        from backend.providers import ProviderError
        with patch.object(FakeProvider, "generate", side_effect=ProviderError("OpenAI sk-private-secret billing tokens")):
            result = await self.client.generate(["witty_friend"], "", screenshot=jpeg())
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["usage"]["generated_chats"], 0)
        self.assertEqual(result["usage"]["generation_requests"], 1)
        self.assertNotIn("OpenAI", json.dumps(result))
        self.assertNotIn("sk-private", json.dumps(result))

    async def test_client_never_follows_redirect_with_screenshot(self):
        reached = []
        async def redirect(request):
            raise web.HTTPTemporaryRedirect("/leak")
        async def leak(request):
            reached.append(True)
            return web.json_response({})
        app = web.Application()
        app.router.add_post("/api/chat/generate", redirect)
        app.router.add_post("/leak", leak)
        server = TestServer(app)
        await server.start_server()
        self.addAsyncCleanup(server.close)
        client = ServiceClient(base_url=str(server.make_url("")), token=TOKEN_A)
        with self.assertRaises(ValueError):
            await client.generate(["witty_friend"], "", screenshot=jpeg())
        self.assertEqual(reached, [])

    async def test_close_cancels_waiting_client_without_retry(self):
        entered = asyncio.Event()
        calls = []
        async def hold(*args, **kwargs):
            calls.append(True)
            entered.set()
            await asyncio.Event().wait()
        with patch.object(self.client, "_request", side_effect=hold):
            task = asyncio.create_task(self.client.generate(["witty_friend"], "", screenshot=jpeg()))
            await asyncio.wait_for(entered.wait(), 1)
            self.client.stop_requested.set()
            self.assertEqual((await asyncio.wait_for(task, 1))["status"], "stopped")
        self.assertEqual(len(calls), 1)

    def test_remote_http_and_invalid_operator_tokens_are_rejected(self):
        with self.assertRaises(ValueError):
            ServiceClient(base_url="http://example.com", token=TOKEN_A)
        for accounts in ({}, {"alice": "short"}, {"../bad": TOKEN_A}, {"a": TOKEN_A, "b": TOKEN_A}):
            with self.assertRaises(ValueError):
                validate_accounts(accounts)

    def test_client_ignores_late_usage_refresh(self):
        usage = {"period": "2026-10", "timezone": "Asia/Seoul", "is_demo": False,
                 "generation_requests": 2, "generated_chats": 4, "total_generated_chats": 4}
        self.client._set_usage(usage)
        self.client._set_usage({**usage, "generation_requests": 1, "generated_chats": 2, "total_generated_chats": 2})
        self.assertEqual(self.client.usage(), usage)
