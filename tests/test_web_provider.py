"""Real web provider contract with an offline transport and durable allowance."""
import asyncio
import base64
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock
from PIL import Image

from backend.providers import ProviderError
from backend.web_provider import OpenAIWebProvider
from backend.screenshot_provider import OpenAIScreenshotProvider


class WebProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"usage.json"
        self.provider = OpenAIWebProvider(self.path,api_key="test-key",daily_limit=2,today=lambda:"2026-11-01")
        self.provider._generate_payload = AsyncMock(return_value={"comment":"이 조합 괜찮네","model_calls":1})
        self.context = dict(request_id="one",persona="analyst",channel_context="방송 테스트",recent_comments=[])

    async def test_text_only_prompt_and_persistent_limit_across_sessions(self):
        result = await self.provider.generate(self.context)
        self.assertEqual(result["model_calls"],1)
        payload = self.provider._generate_payload.call_args.args[0]
        self.assertFalse(payload["store"])
        self.assertEqual([part["type"] for part in payload["input"][0]["content"]],["input_text"])
        self.assertIn("TEXT ONLY",payload["instructions"])
        await self.provider.generate(self.context)
        restarted = OpenAIWebProvider(self.path,api_key="test-key",daily_limit=2,today=lambda:"2026-11-01")
        restarted._generate_payload = AsyncMock()
        with self.assertRaisesRegex(ProviderError,"한도"):
            await restarted.generate(self.context)
        restarted._generate_payload.assert_not_called()
        restarted.today = lambda:"2026-11-02"
        self.assertEqual(restarted.remaining(),2)

    async def test_upstream_errors_hide_secrets_and_consume_allowance(self):
        self.provider._generate_payload.side_effect = RuntimeError("SECRET-UPSTREAM-DETAIL")
        with self.assertRaisesRegex(ProviderError,"채팅을 생성하지 못했습니다") as error:
            await self.provider.generate(self.context)
        self.assertNotIn("SECRET",str(error.exception))
        self.assertEqual(self.provider.remaining(),1)
        self.assertEqual(self.provider.active,0)

    async def test_frame_uses_vision_payload_and_shares_text_allowance(self):
        output = io.BytesIO()
        Image.new("RGB", (32, 24), "blue").save(output, format="JPEG")
        screenshot = output.getvalue()
        await self.provider.generate(self.context, screenshot=screenshot)
        payload = self.provider._generate_payload.call_args.args[0]
        self.assertFalse(payload["store"])
        parts = payload["input"][0]["content"]
        image = next(part for part in parts if part["type"] == "input_image")
        self.assertEqual(image["image_url"], "data:image/jpeg;base64," + base64.b64encode(screenshot).decode())
        self.assertNotIn("TEXT ONLY", payload["instructions"])
        self.assertIn("analyst", parts[0]["text"])
        await self.provider.generate(self.context)
        self.assertEqual(self.provider.remaining(), 0)
        with self.assertRaises(ProviderError):
            await self.provider.generate(self.context, screenshot=screenshot)
        self.assertEqual(self.provider._generate_payload.await_count, 2)

    async def test_concurrent_requests_do_not_overrun_budget(self):
        gate = asyncio.Event()
        async def complete(payload):
            await gate.wait()
            return {"comment":"테스트"}
        self.provider._generate_payload.side_effect = complete
        first = asyncio.create_task(self.provider.generate(self.context))
        second = asyncio.create_task(self.provider.generate(self.context))
        await asyncio.sleep(0)
        with self.assertRaises(ProviderError):
            await self.provider.generate(self.context)
        gate.set()
        await asyncio.gather(first,second)
        self.assertEqual(self.provider.remaining(),0)

    async def test_each_demo_adds_its_own_prompt_without_replacing_persona_or_image(self):
        output = io.BytesIO()
        Image.new("RGB", (32, 24), "blue").save(output, format="JPEG")
        screenshot = output.getvalue()
        base = OpenAIScreenshotProvider.payload(self.provider, self.context, screenshot)
        self.provider.daily_limit = 3
        prompts = []
        for video_id, game in (("demo-01", "오버워치"), ("demo-02", "발로란트"), ("demo-03", "배틀그라운드")):
            await self.provider.generate(self.context, screenshot=screenshot, demo_video_id=video_id)
            payload = self.provider._generate_payload.call_args.args[0]
            self.assertTrue(payload["instructions"].startswith(base["instructions"]))
            self.assertIn(game, payload["instructions"])
            self.assertIn("현재 전달된 이미지", payload["instructions"])
            self.assertEqual(payload["input"], base["input"])
            prompts.append(payload["instructions"])
        self.assertEqual(len(set(prompts)), 3)
        self.assertEqual(self.provider.remaining(), 0)

    async def test_demo_without_frame_or_with_unknown_id_never_spends_allowance(self):
        for options in ({"demo_video_id": "demo-01"}, {"screenshot": b"\xff\xd8\xff", "demo_video_id": "custom-instructions"}):
            with self.assertRaises(ValueError):
                await self.provider.generate(self.context, **options)
        self.provider._generate_payload.assert_not_called()
        self.assertEqual(self.provider.remaining(), 2)
