"""Output switching with synthetic screenshots and fake CHZZK; no live sends."""

import asyncio
import base64
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import TestClient, TestServer

from apps.desktop.overlay import clean_settings
from apps.desktop.service_client import ServiceClient
from backend.chat_delivery import ChatDelivery
from backend.chat_service import DesktopService
from backend.chzzk import ChzzkConfig
from backend.chzzk_target import parse_channel_id
from backend.realtime_service import RealtimeSession, validate_start
from backend.realtime_provider import MockProvider
from backend.server import create_app
from test_desktop_service import FakeProvider
from test_screenshot_provider import jpeg


CHANNEL = "a" * 32
TOKEN = "a" * 40


class LinkTests(unittest.TestCase):
    def test_extracts_channel_and_broadcast_links_without_accepting_other_hosts(self):
        for value in (CHANNEL.upper(), f"https://chzzk.naver.com/{CHANNEL}",
                      f"https://chzzk.naver.com/live/{CHANNEL}?share=1#chat",
                      f"https://m.chzzk.naver.com/live/{CHANNEL}/"):
            self.assertEqual(parse_channel_id(value), CHANNEL)
        for value in (None, "", "abc", f"https://chzzk.naver.com.evil.test/live/{CHANNEL}",
                      f"https://chzzk.naver.com@evil.test/{CHANNEL}",
                      f"http://chzzk.naver.com/{CHANNEL}", f"https://chzzk.naver.com/video/{CHANNEL}"):
            with self.assertRaises(ValueError):
                parse_channel_id(value)
        self.assertEqual(ChzzkConfig("id", "secret", f"https://chzzk.naver.com/live/{CHANNEL}").channel_id, CHANNEL)

    def test_local_demo_is_default_and_saved_settings_exclude_secrets(self):
        self.assertEqual(clean_settings({})["destination"], "app")
        self.assertEqual(clean_settings({"destination": "bad"})["destination"], "app")
        saved = clean_settings({"destination": "chzzk", "channel_url": f"https://chzzk.naver.com/{CHANNEL}",
                                "access_token": "secret", "CHZZK_CLIENT_SECRET": "secret"})
        self.assertEqual(saved["destination"], "chzzk")
        self.assertNotIn("access_token", saved)
        self.assertNotIn("CHZZK_CLIENT_SECRET", saved)


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_account_and_target_must_match_and_failed_send_is_not_retried(self):
        config = ChzzkConfig("id", "secret", CHANNEL)
        client = type("Client", (), {"config": config, "status": AsyncMock(), "send": AsyncMock()})()
        client.send.return_value = {"messageId": "sent-1"}
        with patch.dict("os.environ", {"CHZZK_SERVICE_ACCOUNT": "alice"}), patch.object(ChzzkConfig, "from_env", return_value=config):
            factory = unittest.mock.Mock(return_value=client)
            unauthorized = ChatDelivery("bob", client_factory=factory)
            self.assertFalse((await unauthorized.status())["connected"])
            self.assertEqual((await unauthorized.send("hello", CHANNEL))["status"], "failed")
            factory.assert_not_called()
            sender = ChatDelivery("alice", client_factory=factory)
            self.assertEqual((await sender.send("hello", "b" * 32))["status"], "failed")
            client.send.assert_not_called()
            self.assertEqual((await sender.send("x" * 100, CHANNEL))["status"], "sent")
            client.send.assert_awaited_once_with("[AI] " + "x" * 95)
            client.send.reset_mock()
            client.send.side_effect = TimeoutError("private-token")
            result = await sender.send("hello", CHANNEL)
            self.assertEqual(result["status"], "failed")
            self.assertNotIn("private-token", str(result))
            client.send.assert_awaited_once()
            client.send.side_effect = asyncio.CancelledError()
            with self.assertRaises(asyncio.CancelledError):
                await sender.send("hello", CHANNEL)

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.deliveries = {}
        def delivery_factory(account):
            sender = type("Delivery", (), {
                "send": AsyncMock(return_value={"status": "sent", "message": "sent", "messageId": "message-1"}),
                "status": AsyncMock(return_value={"connected": True, "channelId": CHANNEL, "channelName": "test", "message": "connected"})})()
            self.deliveries[account] = sender
            return sender
        def service_factory(directory):
            return DesktopService(directory, provider_factory=lambda *args: FakeProvider(), cooldown_s=0)
        def realtime_factory():
            engine = MockProvider()
            engine.calls = 1  # A synthetic REACT on the first analysis.
            return engine
        app = create_app(self.temp.name, accounts={"alice": TOKEN, "bob": "b" * 40},
                         service_factory=service_factory, delivery_factory=delivery_factory, realtime_factory=realtime_factory)
        self.http = TestClient(TestServer(app, host="127.0.0.1"))
        await self.http.start_server()
        self.addAsyncCleanup(self.http.close)
        self.client = ServiceClient(base_url=str(self.http.make_url("")), token=TOKEN)

    async def test_manual_switch_keeps_local_chat_and_sends_only_ready_lines_once(self):
        people = ["witty_friend", "warm_supporter"]
        result = await self.client.generate(people, "", screenshot=jpeg())
        self.assertEqual(len(result["lines"]), 2)
        self.deliveries["alice"].send.assert_not_called()
        self.deliveries["alice"].status.assert_not_called()
        self.assertTrue((await self.client.chzzk_status())["connected"])
        result = await self.client.generate(people, "", screenshot=jpeg(), destination="chzzk",
                                            channel_id=f"https://chzzk.naver.com/live/{CHANNEL}")
        self.assertEqual(self.deliveries["alice"].send.await_count, 2)
        self.assertTrue(all(line["delivery"]["status"] == "sent" for line in result["lines"]))
        self.deliveries["bob"].send.assert_not_called()
        self.deliveries["alice"].send.reset_mock()
        await self.client.generate(people, "", screenshot=jpeg())
        self.deliveries["alice"].send.assert_not_called()

    async def test_failed_publish_preserves_generation_and_stops_rest_of_batch(self):
        self.deliveries["alice"].send.return_value = {"status": "failed", "message": "check chat", "messageId": ""}
        lines = []
        result = await self.client.generate(["witty_friend", "warm_supporter"], "", screenshot=jpeg(),
                                            destination="chzzk", channel_id=CHANNEL, on_line=lines.append)
        self.assertEqual(result["status"], "complete")
        self.assertEqual([line["delivery"]["status"] for line in lines], ["failed", "skipped"])
        self.assertTrue(all(line["status"] == "ready" and line["comment"] for line in lines))
        self.deliveries["alice"].send.assert_awaited_once()
        self.assertEqual(result["usage"]["generated_chats"], 2)

    async def test_invalid_destination_and_target_are_rejected_before_generation(self):
        data = {"personas": ["witty_friend"], "context": "", "screenshot": base64.b64encode(jpeg()).decode()}
        for extra in ({"destination": "bad"}, {"destination": "chzzk"},
                      {"destination": "chzzk", "channel_id": "https://evil.test"}, {"access_token": "injected"}):
            response = await self.http.post('/api/chat/generate', json={**data, **extra},
                                            headers={"Authorization": "Bearer " + TOKEN})
            self.assertEqual(response.status, 400)
        self.assertEqual((await self.client.refresh_usage())["generation_requests"], 0)
        response = await self.http.get('/api/chzzk/status')
        self.assertEqual(response.status, 401)

    async def test_realtime_client_receives_chat_and_delivery_receipt(self):
        stop = threading.Event()
        events = []
        def event(value):
            events.append(value)
            if value["type"] == "delivery":
                stop.set()
        await asyncio.wait_for(self.client.realtime(["witty_friend"], "", capture=jpeg, stop_event=stop,
                               on_event=event, interval=3, duration=30, destination="chzzk", channel_id=CHANNEL), 8)
        self.assertEqual([e["type"] for e in events if e["type"] in ("decision", "delivery")], ["decision", "delivery"])
        receipt = next(event["delivery"] for event in events if event["type"] == "delivery")
        self.assertEqual(receipt["status"], "sent")
        self.deliveries["alice"].send.assert_awaited_once()

    async def test_realtime_emits_local_chat_before_delivery_and_stops_sends_after_failure(self):
        import time
        from backend.realtime_provider import Frame
        frame = Frame(1, time.monotonic(), b"synthetic")
        provider = type("Provider", (), {"analyze": AsyncMock(return_value=(
            {"action": "REACT", "comment": "test reaction", "evidence_frame_id": frame.id}, (frame,), 1))})()
        events = []
        socket = type("Socket", (), {"send_json": AsyncMock(side_effect=lambda event: events.append(event))})()
        service = type("Service", (), {"realtime_attempt": lambda *a: None, "realtime_result": lambda *a, **k: None,
                                       "service_usage": lambda *a: {}})()
        settings = validate_start({"type": "start", "personas": ["witty_friend"], "context": "", "interval": 3,
                                   "duration": 30, "destination": "chzzk", "channel_id": CHANNEL})
        delivery = self.deliveries["alice"]
        async def send(comment, target):
            self.assertEqual(events[-1]["type"], "decision")
            self.assertEqual(events[-1]["comment"], comment)
            return {"status": "failed", "message": "check chat", "messageId": ""}
        delivery.send.side_effect = send
        session = RealtimeSession(socket, provider, settings, service, "mock", delivery=delivery)
        session.last_sequence = 1
        session.last_frame_at = time.monotonic()
        # One judge pass, then cancellation; no real-time delays or network.
        with patch("backend.realtime_service.asyncio.sleep", AsyncMock(side_effect=[None, asyncio.CancelledError()])):
            with self.assertRaises(asyncio.CancelledError):
                await session.judge()
        self.assertEqual([e["type"] for e in events], ["decision", "delivery"])
        self.assertTrue(session.delivery_failed)
        session.last_reply_at = float("-inf")
        session.recent.clear()
        with patch("backend.realtime_service.asyncio.sleep", AsyncMock(side_effect=[None, asyncio.CancelledError()])):
            with self.assertRaises(asyncio.CancelledError):
                await session.judge()
        delivery.send.assert_awaited_once()
        self.assertEqual(events[-1]["delivery"]["status"], "skipped")
