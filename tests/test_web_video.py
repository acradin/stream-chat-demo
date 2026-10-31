"""Offline HTTP coverage for a single captured video frame, never a live AI call."""
import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock

from aiohttp.test_utils import TestClient, TestServer
from PIL import Image

from apps.web.server import create_app
from backend.web_provider import MockWebProvider


def jpeg(size=(32, 24), format="JPEG"):
    output = io.BytesIO()
    Image.new("RGB", size, "blue").save(output, format=format)
    return output.getvalue()


class WebVideoTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "run"
        self.provider = MockWebProvider(0)
        self.provider.generate = AsyncMock(return_value={"comment": "장면 테스트", "model_calls": 0})
        self.client = TestClient(TestServer(create_app(self.provider, self.directory, cooldown_s=0)))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)
        config = await (await self.client.get("/api/config")).json()
        self.assertTrue(config["supports_frames"])
        self.headers = {"X-Demo-Token": config["session_token"]}
        self.image = jpeg()
        self.payload = dict(client_request_id="frame-one", persona="witty_friend", channel_context="게임 방송",
                            clicked_video_s=2.5, video_session_id="sample-1",
                            frame_jpeg=base64.b64encode(self.image).decode())

    async def test_frame_reaches_provider_once_and_is_excluded_from_logs(self):
        for _ in range(2):
            response = await self.client.post("/api/trigger", json=self.payload, headers=self.headers)
            self.assertEqual(response.status, 200)
            self.assertEqual((await response.json())["status"], "ready")
        self.provider.generate.assert_awaited_once()
        call = self.provider.generate.call_args
        self.assertEqual(call.kwargs["screenshot"], self.image)
        self.assertNotIn("frame_jpeg", call.args[0])
        for path in self.directory.iterdir():
            content = path.read_text(encoding="utf-8-sig")
            self.assertNotIn(self.payload["frame_jpeg"], content)
            self.assertNotIn("frame_jpeg", content)
        report = json.loads((self.directory / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(report["mode"], "manual_image")
        self.assertFalse(report["input_media_sent_to_model"])

    async def test_invalid_media_and_missing_timing_never_reach_provider(self):
        cases = [
            {"frame_jpeg": "not base64!"},
            {"frame_jpeg": base64.b64encode(b"not a picture").decode()},
            {"frame_jpeg": base64.b64encode(jpeg(format="PNG")).decode()},
            {"frame_jpeg": base64.b64encode(jpeg((1281, 20))).decode()},
            {"frame_jpeg": "a" * 700001},
            {"clicked_video_s": None, "video_session_id": None},
            {"audio_wav": "unrequested audio"},
        ]
        for change in cases:
            with self.subTest(keys=list(change)):
                response = await self.client.post("/api/trigger", json={**self.payload, **change}, headers=self.headers)
                self.assertEqual(response.status, 400)
        self.provider.generate.assert_not_called()
        self.assertEqual(await (await self.client.get("/api/export")).text(), "")

    async def test_oversized_request_is_rejected_before_provider(self):
        response = await self.client.post("/api/trigger", json={**self.payload, "frame_jpeg": "a" * 750000}, headers=self.headers)
        self.assertEqual(response.status, 413)
        self.provider.generate.assert_not_called()

    async def test_text_only_provider_rejects_frame_without_calling_model(self):
        self.provider.supports_frames = False
        response = await self.client.post("/api/trigger", json=self.payload, headers=self.headers)
        self.assertEqual(response.status, 400)
        self.provider.generate.assert_not_called()

    async def test_selected_demo_reaches_provider_separately_from_user_context(self):
        for index in range(1, 4):
            video_id = f"demo-0{index}"
            payload = {**self.payload, "demo_video_id": video_id, "client_request_id": video_id}
            response = await self.client.post("/api/trigger", json=payload, headers=self.headers)
            self.assertEqual(response.status, 200)
            self.assertEqual((await response.json())["status"], "ready")
            call = self.provider.generate.call_args
            self.assertEqual(call.kwargs["demo_video_id"], video_id)
            self.assertEqual(call.kwargs["screenshot"], self.image)
            self.assertEqual(call.args[0]["channel_context"], self.payload["channel_context"])
            self.assertNotIn("demo_video_id", call.args[0])

    async def test_unknown_demo_or_demo_without_image_is_rejected(self):
        for value in ("unknown", None, [], "", "x" * 100):
            response = await self.client.post("/api/trigger", json={**self.payload, "demo_video_id": value}, headers=self.headers)
            self.assertEqual(response.status, 400)
        payload = {key: value for key, value in self.payload.items() if key != "frame_jpeg"}
        response = await self.client.post("/api/trigger", json={**payload, "demo_video_id": "demo-01"}, headers=self.headers)
        self.assertEqual(response.status, 400)
        self.provider.generate.assert_not_called()
