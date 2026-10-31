"""Real web provider contract with an offline transport and durable allowance."""
import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock

from backend.providers import ProviderError
from backend.web_provider import OpenAIWebProvider


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
