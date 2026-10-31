"""Remote OAuth boundaries and restart persistence using fake upstream responses."""

import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from aiohttp.test_utils import TestClient, TestServer

from backend.chat_delivery import ChatDelivery
from backend.chzzk import ChzzkClient, ChzzkConfig
from backend.chzzk_remote import CALLBACK_PATH, RemoteAuthorization, public_origin
from backend.server import create_app


CHANNEL = "b" * 32
TOKEN = "test-service-token-" + "x" * 32
ORIGIN = "https://stream.example.com"


class RemoteAuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.actual_channel = CHANNEL
        self.requests = []
        self.config = ChzzkConfig("test-client", "private-secret", "a" * 32)
        self.env = patch.dict("os.environ", {"CHZZK_SERVICE_ACCOUNT": "alice"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.config_patch = patch.object(ChzzkConfig, "from_env", return_value=self.config)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        async def upstream(client, method, path, **kwargs):
            self.requests.append(path)
            if path == "/auth/v1/token":
                return {"accessToken": "private-access", "refreshToken": "private-refresh",
                        "tokenType": "Bearer", "expiresIn": 86400}
            if path == "/open/v1/users/me":
                return {"channelId": self.actual_channel, "channelName": "test broadcaster"}
            self.fail("Authorization must not send chat")
        self.api = patch.object(ChzzkClient, "_request", upstream)
        self.api.start()
        self.addCleanup(self.api.stop)
        self.deliveries = {}
        def delivery(account):
            item = ChatDelivery(account, state_dir=Path(self.temp.name) / account)
            self.deliveries[account] = item
            return item
        app = create_app(self.temp.name, accounts={"alice": TOKEN, "bob": "b" * 40},
                         delivery_factory=delivery, public_url=ORIGIN)
        self.http = TestClient(TestServer(app))
        await self.http.start_server()
        self.addAsyncCleanup(self.http.close)
        self.headers = {"Authorization": "Bearer " + TOKEN}

    async def invite(self):
        response = await self.http.post("/api/chzzk/authorize", headers=self.headers,
                                        json={"channel_url": "https://chzzk.naver.com/live/" + CHANNEL})
        self.assertEqual(response.status, 200)
        data = await response.json()
        self.assertEqual(data["channel_id"], CHANNEL)
        self.assertEqual(data["expires_in"], 600)
        self.assertNotIn("private-", str(data))
        query = parse_qs(urlsplit(data["authorization_url"]).query)
        self.assertEqual(query["redirectUri"], [ORIGIN + CALLBACK_PATH])
        return query["state"][0]

    async def callback(self, state, **params):
        return await self.http.get(CALLBACK_PATH, headers={"Host": "stream.example.com"},
                                   params={"state": state, "code": "private-code", **params})

    async def test_public_health_does_not_open_private_routes_or_issue_unauthorized_invites(self):
        self.assertEqual((await self.http.get("/healthz")).status, 200)
        for path in ("/api/usage", "/api/chzzk/status", "/api/chat/realtime"):
            self.assertEqual((await self.http.get(path)).status, 401)
        self.assertEqual((await self.http.post("/api/chzzk/authorize", json={"channel_url": CHANNEL})).status, 401)
        response = await self.http.post("/api/chzzk/authorize", json={"channel_url": CHANNEL},
                                        headers={"Authorization": "Bearer " + "b" * 40})
        self.assertEqual(response.status, 400)
        self.assertEqual(self.requests, [])

    async def test_authorization_persists_for_restart_and_app_status_without_sending_chat(self):
        state = await self.invite()
        response = await self.callback(state)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        self.assertNotIn("private-", await response.text())
        status = await self.http.get("/api/chzzk/status", headers=self.headers)
        self.assertEqual((await status.json())["channelId"], CHANNEL)
        restarted = ChatDelivery("alice", state_dir=Path(self.temp.name) / "alice")
        self.assertEqual((await restarted.status())["channelId"], CHANNEL)
        self.assertEqual((await self.callback(state)).status, 400)
        self.assertEqual(self.requests.count("/auth/v1/token"), 1)
        self.assertNotIn("/open/v1/chats/send", self.requests)

    async def test_wrong_account_keeps_existing_connection_file_unchanged(self):
        original = self.deliveries["alice"].authorization_client(CHANNEL, ORIGIN + CALLBACK_PATH)
        original._save_tokens({"existing": "preserve"})
        before = original.token_path.read_bytes()
        self.actual_channel = "c" * 32
        response = await self.callback(await self.invite())
        self.assertEqual(response.status, 400)
        self.assertEqual(original.token_path.read_bytes(), before)
        self.assertIsNone(self.deliveries["alice"].client)

    async def test_new_link_invalidates_old_and_wrong_host_or_state_cannot_consume_it(self):
        old, current = await self.invite(), await self.invite()
        self.assertEqual((await self.callback(old)).status, 400)
        self.assertEqual((await self.callback("unknown")).status, 400)
        response = await self.http.get(CALLBACK_PATH, params={"state": current, "code": "private-code"})
        self.assertEqual(response.status, 400)
        self.assertEqual(self.requests, [])
        self.assertEqual((await self.callback(current)).status, 200)

    async def test_cancel_and_concurrent_replay_exchange_at_most_once(self):
        cancelled = await self.invite()
        self.assertEqual((await self.callback(cancelled, error="denied")).status, 400)
        self.assertEqual((await self.callback(cancelled)).status, 400)
        self.assertEqual(self.requests, [])
        state = await self.invite()
        responses = await asyncio.gather(self.callback(state), self.callback(state))
        self.assertEqual(sorted(response.status for response in responses), [200, 400])
        self.assertEqual(self.requests.count("/auth/v1/token"), 1)

    async def test_invite_rejects_extra_fields_and_large_or_invalid_bodies(self):
        for body in ({"channel_url": CHANNEL, "account": "bob"}, {"channel_url": "not-a-channel"}):
            response = await self.http.post("/api/chzzk/authorize", headers=self.headers, json=body)
            self.assertEqual(response.status, 400)
        response = await self.http.post("/api/chzzk/authorize", headers=self.headers, data=b"x" * 4097)
        self.assertEqual(response.status, 413)
        self.assertEqual(self.requests, [])

    async def test_expired_link_never_exchanges_tokens(self):
        # Inspect via a standalone instance so expiry advances deterministically.
        from aiohttp import web
        now = [0]
        remote = RemoteAuthorization(ORIGIN, self.deliveries, clock=lambda: now[0])
        app = web.Application()
        async def invite(request):
            return await remote.invite(request, "alice")
        app.router.add_post("/invite", invite)
        app.router.add_get(CALLBACK_PATH, remote.callback)
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        response = await client.post("/invite", json={"channel_url": CHANNEL})
        state = parse_qs(urlsplit((await response.json())["authorization_url"]).query)["state"][0]
        now[0] = 601
        response = await client.get(CALLBACK_PATH, headers={"Host": "stream.example.com"},
                                    params={"state": state, "code": "private-code"})
        self.assertEqual(response.status, 400)
        self.assertEqual(self.requests, [])

    def test_public_origin_rejects_credentials_paths_and_insecure_urls(self):
        self.assertEqual(public_origin(ORIGIN + "/"), ORIGIN)
        for value in ("http://example.com", "https://localhost", "https://example.com/path",
                      "https://user:password@example.com", "https://example.com?key=secret"):
            with self.assertRaises(ValueError):
                public_origin(value)
