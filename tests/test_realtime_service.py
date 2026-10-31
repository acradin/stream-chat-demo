"""Synthetic images and loopback mock servers only; no screen capture or AI charges."""

import asyncio
import base64
import io
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from aiohttp import ClientSession, WSServerHandshakeError, web
from aiohttp.test_utils import TestServer
from PIL import Image

from apps.desktop.service_client import ServiceClient
from backend.chat_service import DesktopService
from backend.realtime_provider import MockProvider
from backend.realtime_service import validate_start
from backend.server import create_app

TOKEN = "a" * 40
START = {"type": "start", "personas": ["witty_friend", "warm_supporter"],
         "context": "", "interval": 3, "duration": 30}


def jpeg():
    data = io.BytesIO()
    with Image.new("RGB", (64, 36), "navy") as image:
        image.save(data, format="JPEG")
    return data.getvalue()


class DesktopRealtimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.providers = []
        self.services = []
        def factory():
            provider = MockProvider()
            self.providers.append(provider)
            return provider
        def service_factory(path):
            service = DesktopService(path, cooldown_s=0)
            self.services.append(service)
            return service
        self.server = TestServer(create_app(self.temp.name, accounts={"a": TOKEN, "b": "b" * 40},
                                            provider="mock", realtime_factory=factory, service_factory=service_factory))
        await self.server.start_server()
        self.addAsyncCleanup(self.server.close)
        self.client = ServiceClient(base_url=str(self.server.make_url("")), token=TOKEN)

    async def test_selected_frames_round_robin_wait_usage_stop_and_switch_back_to_manual(self):
        stop = threading.Event()
        events, captures = [], []
        reacted = asyncio.Event()
        def capture():
            captures.append(True)
            return jpeg()
        def event(value):
            events.append(value)
            if value["type"] == "decision" and value["result"] == "chat":
                stop.set()
                reacted.set()
        task = asyncio.create_task(self.client.realtime(START["personas"], "", capture=capture,
                                   stop_event=stop, on_event=event, interval=3, duration=30))
        try:
            await asyncio.wait_for(reacted.wait(), 10)
            await asyncio.wait_for(task, 2)
        finally:
            stop.set()
            await asyncio.gather(task, return_exceptions=True)
        self.assertGreaterEqual(len(captures), 5)
        decisions = [value for value in events if value["type"] == "decision"]
        self.assertEqual([(v["result"], v["participant"]) for v in decisions], [("wait", 1), ("chat", 2)])
        self.assertEqual((self.client.usage()["generation_requests"], self.client.usage()["generated_chats"]), (2, 1))
        for _ in range(30):
            if not self.providers[0].frames:
                break
            await asyncio.sleep(.02)
        self.assertFalse(self.providers[0].frames)
        self.assertFalse(self.client.stop_requested.is_set())
        restored = DesktopService(self.services[0].usage_path.parent)
        self.assertEqual(restored.usage()["mock"]["failed"], 0)
        self.assertEqual(restored.usage()["mock"]["silent"], 1)
        other = ServiceClient(base_url=self.client.base_url, token="b" * 40)
        self.assertEqual((await other.refresh_usage())["generation_requests"], 0)
        result = await self.client.generate(["witty_friend"], "", screenshot=jpeg())
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["usage"]["generated_chats"], 2)

    async def test_auth_validation_lock_and_invalid_start_never_open_provider(self):
        async with ClientSession() as http:
            with self.assertRaises(WSServerHandshakeError) as error:
                await http.ws_connect(self.client.base_url + "/api/chat/realtime")
            self.assertEqual(error.exception.status, 401)
            headers = {"Authorization": "Bearer " + TOKEN}
            async with http.ws_connect(self.client.base_url + "/api/chat/realtime", headers=headers) as ws:
                await ws.send_json({**START, "model": "override", "api_key": "forbidden"})
                self.assertEqual((await ws.receive_json())["type"], "error")
            self.assertEqual(self.providers, [])
            async with http.ws_connect(self.client.base_url + "/api/chat/realtime", headers=headers) as ws:
                await ws.send_json(START)
                self.assertEqual(await ws.receive_json(), {"type": "ready"})
                result = await self.client.generate(["witty_friend"], "", screenshot=jpeg())
                self.assertEqual(result["status"], "busy")
                with self.assertRaises(WSServerHandshakeError) as error:
                    await http.ws_connect(self.client.base_url + "/api/chat/realtime", headers=headers)
                self.assertEqual(error.exception.status, 409)
                await ws.send_json({"type": "stop"})
                self.assertEqual((await ws.receive_json())["type"], "stopped")

    async def test_client_stops_before_ready_without_capturing(self):
        entered = asyncio.Event()
        async def hold(provider):
            entered.set()
            await asyncio.Event().wait()
        stop = threading.Event()
        with patch.object(MockProvider, "open", hold), patch("apps.desktop.capture.capture_window") as capture:
            task = asyncio.create_task(self.client.realtime(START["personas"], "", capture=capture,
                                       stop_event=stop, on_event=lambda value: None))
            await asyncio.wait_for(entered.wait(), 2)
            stop.set()
            await asyncio.wait_for(task, 2)
            capture.assert_not_called()

    async def test_redirect_rejected_before_token_or_frames_reach_target(self):
        reached = []
        async def redirect(request):
            raise web.HTTPTemporaryRedirect("/leak")
        async def leak(request):
            reached.append(True)
            return web.Response()
        app = web.Application()
        app.router.add_get("/api/chat/realtime", redirect)
        app.router.add_get("/leak", leak)
        server = TestServer(app)
        await server.start_server()
        self.addAsyncCleanup(server.close)
        client = ServiceClient(base_url=str(server.make_url("")), token=TOKEN)
        with patch("apps.desktop.capture.capture_window") as capture, self.assertRaises(ValueError):
            await client.realtime(START["personas"], "", capture=capture,
                                  stop_event=threading.Event(), on_event=lambda value: None)
        capture.assert_not_called()
        self.assertEqual(reached, [])

    def test_realtime_start_has_bounded_duration_and_no_audio_or_key_overrides(self):
        self.assertEqual(validate_start(START), START)
        for invalid in ({**START, "duration": 3600}, {**START, "interval": True},
                        {**START, "audio": True}, {**START, "personas": []}):
            with self.assertRaises(ValueError):
                validate_start(invalid)
