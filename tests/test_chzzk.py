"""CHZZK contracts: all traffic goes to local HTTP fixtures; no broadcast sends."""

import asyncio
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer

import backend.chzzk as module
from backend.chzzk import ChzzkClient, ChzzkConfig, ChzzkError
from backend.chzzk_cli import authorization_app


CHANNEL = "a" * 32


class ChzzkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "tokens.json"
        self.config = ChzzkConfig("test-client", "private-client-secret", CHANNEL)
        self.client = ChzzkClient(self.config, token_path=self.path)
        self.requests = []
        self.actual_channel = CHANNEL
        self.send_status = 200
        self.redirect = False
        async def handler(request):
            body = await request.json() if request.can_read_body else None
            self.requests.append((request.method, request.path, body, request.headers.get("Authorization")))
            if request.path == "/auth/v1/token":
                return web.json_response({"code": 200, "content": {"accessToken": "test-access", "refreshToken": "rotated-refresh",
                                          "tokenType": "Bearer", "expiresIn": "86400"}})
            if request.path == "/open/v1/users/me":
                return web.json_response({"code": 200, "content": {"channelId": self.actual_channel, "channelName": "테스트 방송"}})
            if self.redirect:
                raise web.HTTPTemporaryRedirect("/leak")
            if self.send_status != 200:
                return web.Response(status=self.send_status, text="private-client-secret test-access private upstream body")
            return web.json_response({"code": 200, "content": {"messageId": "message-1"}})
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", handler)
        self.server = TestServer(app)
        await self.server.start_server()
        self.addAsyncCleanup(self.server.close)
        self.api_patch = patch.object(module, "API_ROOT", str(self.server.make_url("")).rstrip("/"))
        self.api_patch.start()
        self.addCleanup(self.api_patch.stop)

    def tokens(self, *, expires=None):
        self.client._save_tokens({"client_id": self.config.client_id, "channel_id": CHANNEL,
                                  "access_token": "test-access", "refresh_token": "old-refresh",
                                  "expires_at": expires if expires is not None else time.time() + 3600})

    async def test_exchange_validates_target_then_persists_tokens(self):
        identity = await self.client.authorize("test-code", "test-state")
        self.assertEqual(identity["channelId"], CHANNEL)
        self.assertEqual(self.requests[0][2], {"grantType": "authorization_code", "clientId": "test-client",
                                               "clientSecret": "private-client-secret", "code": "test-code", "state": "test-state"})
        self.assertEqual(self.requests[1][3], "Bearer test-access")
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["refresh_token"], "rotated-refresh")
        self.assertNotIn("private-client-secret", self.path.read_text())
        self.assertNotIn("test-access", json.dumps(identity))

    async def test_wrong_channel_never_saves_or_sends(self):
        self.actual_channel = "b" * 32
        with self.assertRaises(ChzzkError):
            await self.client.authorize("test-code", "test-state")
        self.assertFalse(self.path.exists())
        self.tokens()
        with self.assertRaises(ChzzkError):
            await self.client.send("[AI] 연결 테스트입니다")
        self.assertFalse(any(path == "/open/v1/chats/send" for _, path, _, _ in self.requests))

    async def test_sends_once_with_bearer_and_only_message_body(self):
        self.tokens()
        result = await self.client.send("[AI] 연결 테스트입니다")
        self.assertEqual(result["messageId"], "message-1")
        self.assertEqual(self.requests, [("GET", "/open/v1/users/me", None, "Bearer test-access"),
                                         ("POST", "/open/v1/chats/send", {"message": "[AI] 연결 테스트입니다"}, "Bearer test-access")])

    async def test_refresh_rotates_and_saves_before_send(self):
        self.tokens(expires=time.time() - 1)
        await self.client.send("[AI] 연결 테스트입니다")
        self.assertEqual(self.requests[0][2]["grantType"], "refresh_token")
        self.assertEqual(self.requests[0][2]["refreshToken"], "old-refresh")
        self.assertEqual(json.loads(self.path.read_text())["refresh_token"], "rotated-refresh")
        self.assertEqual(sum(path == "/open/v1/chats/send" for _, path, _, _ in self.requests), 1)

    async def test_invalid_message_never_reaches_network(self):
        self.tokens()
        for message in ("unlabeled", "[AI] " + "x" * 96, "[AI] line\nbreak", "[AI] ", "[AI]   ", None):
            with self.assertRaises(ChzzkError):
                await self.client.send(message)
        self.assertEqual(self.requests, [])

    async def test_send_failure_is_sanitized_and_never_retried(self):
        self.tokens()
        self.send_status = 429
        with self.assertRaises(ChzzkError) as error:
            await self.client.send("[AI] 연결 테스트입니다")
        self.assertIn("429", str(error.exception))
        self.assertNotIn("private", str(error.exception))
        self.assertNotIn("test-access", str(error.exception))
        self.assertEqual(sum(path == "/open/v1/chats/send" for _, path, _, _ in self.requests), 1)

    async def test_redirect_does_not_forward_tokens_or_chat(self):
        self.tokens()
        self.redirect = True
        with self.assertRaises(ChzzkError):
            await self.client.send("[AI] 연결 테스트입니다")
        self.assertFalse(any(path == "/leak" for _, path, _, _ in self.requests))

    async def test_callback_rejects_wrong_state_and_consumes_valid_code_once(self):
        future = asyncio.get_running_loop().create_future()
        client = type("Client", (), {"config": self.config, "authorize": AsyncMock(return_value={"channelId": CHANNEL})})()
        server = TestServer(authorization_app(client, "expected-state", future))
        await server.start_server()
        self.addAsyncCleanup(server.close)
        async with ClientSession() as session:
            headers = {"Host": "localhost:8767"}
            url = server.make_url("/oauth/chzzk/callback")
            async with session.get(url, params={"state": "wrong", "code": "secret-code"}, headers=headers) as response:
                self.assertEqual(response.status, 400)
            client.authorize.assert_not_called()
            async with session.get(url, params={"state": "expected-state", "code": "secret-code"}, headers=headers) as response:
                self.assertEqual(response.status, 200)
                self.assertNotIn("secret-code", await response.text())
            async with session.get(url, params={"state": "expected-state", "code": "secret-code"}, headers=headers) as response:
                self.assertEqual(response.status, 409)
        client.authorize.assert_awaited_once_with("secret-code", "expected-state")
        self.assertEqual(future.result(), {"channelId": CHANNEL})

    def test_authorization_url_has_no_client_secret_and_redirect_requires_https_or_loopback(self):
        url = self.config.authorization_url("test-state")
        self.assertEqual(urlsplit(url).netloc, "chzzk.naver.com")
        self.assertEqual(parse_qs(urlsplit(url).query)["redirectUri"], [self.config.redirect_uri])
        self.assertNotIn("private-client-secret", url)
        self.assertEqual(ChzzkConfig("id", "secret", CHANNEL, "https://example.com/callback").redirect_uri,
                         "https://example.com/callback")
        for redirect in ("http://example.com/callback", "https://example.com/", "https://user@example.com/callback",
                         "https://example.com/callback?code=bad", "http://localhost/callback"):
            with self.assertRaises(ChzzkError):
                ChzzkConfig("id", "secret", CHANNEL, redirect)
