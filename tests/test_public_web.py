"""Public demo sessions stay isolated from private desktop APIs and one another."""
import json
import base64
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from aiohttp import ClientSession
from aiohttp.test_utils import TestServer
from PIL import Image
from backend.server import create_app

ORIGIN = "https://tiki.example.org"


class PublicWebTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        static = self.directory / "web"
        static.mkdir()
        (static / "index.html").write_text('<html><div id="root">tiki</div></html>')
        (static / "main.js").write_text("console.log('tiki')")
        (static / "clip.mp4").write_bytes(b"0123456789")
        (static / ".env").write_text("NEVER-PUBLIC")
        self.server = TestServer(create_app(self.directory / "private", accounts={"demo": "s"*40},
                                            provider="mock", public_url=ORIGIN, web_dir=static))
        await self.server.start_server()
        self.addAsyncCleanup(self.server.close)
        self.http = ClientSession()
        self.addAsyncCleanup(self.http.close)

    async def request(self, method, path, **kwargs):
        response = await self.http.request(method, self.server.make_url(path), **kwargs)
        await response.read()
        return response

    async def visitor(self):
        response = await self.request("GET", "/api/config")
        self.assertEqual(response.status, 200)
        cookie = response.cookies["__Host-tiki-demo"]
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        config = await response.json()
        self.assertTrue(config["is_mock"])
        return {"Cookie": cookie.key + "=" + cookie.value, "Origin": ORIGIN,
                "X-Demo-Token": config["session_token"]}

    def payload(self):
        return dict(client_request_id="first", persona="witty_friend", channel_context="private browser context",
                    clicked_video_s=None, video_session_id=None)

    async def test_public_assets_do_not_open_private_desktop_or_unknown_routes(self):
        for path, content_type in (("/", "text/html"), ("/main.js", "text/javascript")):
            response = await self.request("GET", path)
            self.assertEqual(response.status, 200)
            self.assertIn(content_type.split("/")[1], response.content_type)
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        for path in ("/.env", "/../backend/.env", "/api/usage", "/api/chzzk/status", "/api/chat/realtime"):
            response = await self.request("GET", path)
            self.assertEqual(response.status, 401)
        response = await self.request("POST", "/api/chat/generate", json=self.payload(), headers=await self.visitor())
        self.assertEqual(response.status, 401)

    async def test_independent_browser_generation_ack_and_export(self):
        first, second = await self.visitor(), await self.visitor()
        self.assertNotEqual(first["Cookie"], second["Cookie"])
        response = await self.request("POST", "/api/trigger", json=self.payload(), headers=first)
        self.assertEqual(response.status, 200)
        result = await response.json()
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["comment"])
        ack = dict(request_id=result["request_id"], button_to_display_ms=250,
                   displayed_video_s=None, video_session_id=None, status="displayed", reason="")
        self.assertEqual((await self.request("POST", "/api/display", json=ack, headers=second)).status, 400)
        self.assertEqual((await self.request("POST", "/api/display", json=ack, headers=first)).status, 200)
        self.assertEqual(await (await self.request("GET", "/api/export", headers=second)).text(), "")
        exported = json.loads(await (await self.request("GET", "/api/export", headers=first)).text())
        self.assertEqual(exported["status"], "displayed")
        self.assertEqual(exported["model_calls"], 0)
        self.assertEqual(list((self.directory / "web").glob("*.json*")), [])

    async def test_origin_cookie_token_and_body_boundaries(self):
        headers = await self.visitor()
        for altered in ({**headers, "Origin": "https://evil.example"}, {**headers, "Origin": "null"},
                        {**headers, "X-Demo-Token": "wrong"}, {**headers, "Cookie": ""},
                        {key:value for key,value in headers.items() if key != "Origin"}):
            self.assertEqual((await self.request("POST", "/api/trigger", headers=altered, json=self.payload())).status, 403)
        response = await self.request("POST", "/api/trigger", headers=headers,
                                      json={**self.payload(), "channel_context": "x" * 20000})
        self.assertEqual(response.status, 413)

    async def test_expiry_and_memory_limits(self):
        from backend.public_web import PublicWeb
        from aiohttp.test_utils import make_mocked_request
        now = [10]
        demo = PublicWeb(self.directory / "web", ORIGIN, capacity=1, ttl=30, clock=lambda: now[0])
        response = await demo.dispatch(make_mocked_request("GET", "/api/config"))
        self.assertEqual(response.status, 200)
        self.assertEqual((await demo.dispatch(make_mocked_request("GET", "/api/config"))).status, 503)
        now[0] += 31
        self.assertEqual((await demo.dispatch(make_mocked_request("GET", "/api/config"))).status, 200)
        self.assertEqual(len(demo.sessions), 1)

    async def test_video_range_and_frame_request_keep_authentication(self):
        response = await self.request("GET", "/clip.mp4", headers={"Range": "bytes=2-5"})
        self.assertEqual(response.status, 206)
        self.assertEqual(await response.read(), b"2345")
        output = io.BytesIO()
        Image.new("RGB", (32, 24), "red").save(output, format="JPEG")
        payload = {**self.payload(), "video_session_id": "clip", "clicked_video_s": 2,
                   "frame_jpeg": base64.b64encode(output.getvalue()).decode()}
        headers = await self.visitor()
        response = await self.request("POST", "/api/trigger", json=payload, headers={**headers, "X-Demo-Token": "wrong"})
        self.assertEqual(response.status, 403)
        response = await self.request("POST", "/api/trigger", json=payload, headers=headers)
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["status"], "ready")
        exported = await (await self.request("GET", "/api/export", headers=headers)).text()
        self.assertNotIn(payload["frame_jpeg"], exported)
        self.assertNotIn("frame_jpeg", exported)

    async def test_live_web_uses_server_provider_and_keeps_desktop_private(self):
        from backend.manual_provider import MockManualProvider
        provider = MockManualProvider(0)
        provider.provider, provider.model = "openai", "private-model"
        provider.generate = AsyncMock(return_value={"comment":"새로운 AI 응답","model_calls":1,"usage":{"private":"not-public"}})
        with patch("backend.web_provider.OpenAIWebProvider",return_value=provider):
            app = create_app(self.directory/"live",accounts={"demo":"s"*40},provider="openai",public_url=ORIGIN,web_dir=self.directory/"web")
        server = TestServer(app)
        await server.start_server()
        self.addAsyncCleanup(server.close)
        response = await self.http.get(server.make_url("/api/config"))
        config = await response.json()
        self.assertFalse(config["is_mock"])
        self.assertEqual(config["session_limit"],10)
        self.assertEqual(config["model"],"")
        cookie = response.cookies["__Host-tiki-demo"]
        headers = {"Origin":ORIGIN,"Cookie":cookie.key+"="+cookie.value,"X-Demo-Token":config["session_token"]}
        for _ in range(2):
            response = await self.http.post(server.make_url("/api/trigger"),json=self.payload(),headers=headers)
            self.assertEqual((await response.json())["comment"],"새로운 AI 응답")
        provider.generate.assert_awaited_once()
        exported = await (await self.http.get(server.make_url("/api/export"),headers=headers)).text()
        self.assertNotIn("not-public",exported)
        self.assertNotIn("private-model",exported)
        self.assertEqual((await self.http.get(server.make_url("/api/usage"),headers=headers)).status,401)
