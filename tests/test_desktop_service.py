import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from apps.desktop.overlay import clean_settings
from backend.chat_service import DesktopService
from backend.providers import ProviderError
from test_screenshot_provider import jpeg


class FakeProvider:
    def __init__(self, *, fail_at=None, hold=False):
        self.calls = []
        self.closed = False
        self.fail_at = fail_at
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        if not hold:
            self.release.set()

    async def generate(self, context, screenshot):
        self.calls.append((context, screenshot))
        self.entered.set()
        await asyncio.wait_for(self.release.wait(), 3)
        if len(self.calls) == self.fail_at:
            raise ProviderError("모델 연결 실패")
        return {"comment": f"테스트 채팅 {len(self.calls)}", "generation_ms": 1,
                "usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110}}

    async def close(self):
        self.closed = True


class DesktopServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_onboarding_migration_preserves_existing_setup(self):
        self.assertFalse(clean_settings({})["onboarding_complete"])
        prior = clean_settings({"count":3,"context":"기존 방송 설명"})
        self.assertTrue(prior["onboarding_complete"])
        self.assertEqual((prior["count"],prior["context"]),(3,"기존 방송 설명"))
        self.assertFalse(clean_settings({"count":3,"onboarding_complete":False})["onboarding_complete"])
        self.assertTrue(clean_settings({"onboarding_complete":True})["onboarding_complete"])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def service(self, provider):
        return DesktopService(self.directory, provider_factory=lambda *args: provider, cooldown_s=0)

    async def run_batch(self, service, count=2, **kwargs):
        return await service.generate(["witty_friend"] * count, "방송 상황", screenshot=jpeg(),
                                      provider_name=kwargs.pop("provider_name", "openai"), **kwargs)

    async def test_participants_share_one_screenshot_and_persist_real_usage(self):
        provider = FakeProvider()
        service = self.service(provider)
        lines = []
        result = await self.run_batch(service, 3, api_key="secret-test-key", on_line=lines.append)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(lines), 3)
        self.assertEqual(provider.calls[0][0]["recent_comments"], [])
        self.assertEqual(provider.calls[2][0]["recent_comments"], ["테스트 채팅 1", "테스트 채팅 2"])
        self.assertTrue(all(image == jpeg() for _, image in provider.calls))
        self.assertTrue(provider.closed)
        restored = DesktopService(self.directory).usage()["openai"]
        self.assertEqual((restored["attempts"], restored["succeeded"], restored["total_tokens"]), (3, 3, 330))
        persisted = (self.directory / "usage.json").read_text(encoding="utf-8")
        self.assertNotIn("secret-test-key", persisted)
        self.assertNotIn("방송 상황", persisted)
        self.assertNotIn("테스트 채팅", persisted)

    async def test_busy_click_does_not_queue_or_call_more(self):
        provider = FakeProvider(hold=True)
        service = self.service(provider)
        first = asyncio.create_task(self.run_batch(service, 1))
        await asyncio.wait_for(provider.entered.wait(), 2)
        self.assertEqual((await self.run_batch(service))["status"], "busy")
        self.assertEqual(len(provider.calls), 1)
        provider.release.set()
        await first
        self.assertEqual(service.usage()["openai"]["attempts"], 1)

    async def test_partial_failure_still_shows_success_and_marks_unknown_usage(self):
        provider = FakeProvider(fail_at=2)
        service = self.service(provider)
        result = await self.run_batch(service, 3)
        self.assertEqual([line["status"] for line in result["lines"]], ["ready", "error", "ready"])
        usage = service.usage()["openai"]
        self.assertEqual((usage["attempts"], usage["succeeded"], usage["failed"], usage["unmetered"]), (3, 2, 1, 1))
        self.assertEqual(usage["total_tokens"], 220)

    async def test_close_finishes_current_call_but_stops_remaining_participants(self):
        provider = FakeProvider(hold=True)
        service = self.service(provider)
        task = asyncio.create_task(self.run_batch(service, 5))
        await asyncio.wait_for(provider.entered.wait(), 2)
        service.stop_requested.set()
        provider.release.set()
        result = await task
        self.assertTrue(result["stopped"])
        self.assertEqual(len(provider.calls), 1)
        self.assertTrue(provider.closed)

    async def test_invalid_input_or_missing_key_never_counts_a_call(self):
        provider = FakeProvider()
        service = self.service(provider)
        for people, context, image in (([], "", jpeg()), (["bad"], "", jpeg()),
                                       (["witty_friend"] * 6, "", jpeg()),
                                       (["witty_friend"], "a" * 1001, jpeg()),
                                       (["witty_friend"], "", b"")):
            with self.assertRaises(ValueError):
                await service.generate(people, context, screenshot=image, provider_name="openai")
        self.assertEqual(provider.calls, [])
        self.assertEqual(service.usage()["openai"]["attempts"], 0)
        def no_key(*args):
            raise ValueError("missing key")
        service.provider_factory = no_key
        with self.assertRaises(ValueError):
            await self.run_batch(service)
        self.assertEqual(service.usage()["openai"]["attempts"], 0)

    async def test_mock_is_separate_and_never_counts_api_tokens(self):
        service = self.service(FakeProvider())
        await self.run_batch(service, provider_name="mock")
        usage = service.usage()
        self.assertEqual(usage["openai"]["attempts"], 0)
        self.assertEqual(usage["mock"]["succeeded"], 2)
        self.assertEqual(usage["mock"]["total_tokens"], 0)

    async def test_cancelled_request_records_unknown_usage_and_releases_lock(self):
        provider = FakeProvider(hold=True)
        service = self.service(provider)
        task = asyncio.create_task(self.run_batch(service))
        await asyncio.wait_for(provider.entered.wait(), 2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(provider.closed)
        self.assertEqual(service.usage()["openai"]["failed"], 1)
        self.assertEqual(service.usage()["openai"]["unmetered"], 1)
        provider.release.set()
        self.assertEqual((await self.run_batch(service, 1))["status"], "complete")

    def test_usage_corruption_is_not_silently_overwritten(self):
        path = self.directory / "usage.json"
        path.write_text('{"schema_version":999}', encoding="utf-8")
        with self.assertRaises(ValueError):
            DesktopService(self.directory)
        self.assertEqual(json.loads(path.read_text())["schema_version"], 999)

    def test_settings_exclude_provider_credentials_and_operator_settings(self):
        settings = clean_settings({"api_key": "secret", "OPENAI_API_KEY": "secret", "count": 5,
                                   "model": "old-model", "provider": "mock", "service_token": "secret"})
        self.assertNotIn("model", settings)
        self.assertNotIn("provider", settings)
        self.assertEqual(settings["count"], 5)
        self.assertNotIn("secret", json.dumps(settings))

    async def test_service_units_count_batch_once_and_only_successful_chats(self):
        service = self.service(FakeProvider(fail_at=2))
        await self.run_batch(service, 3)
        usage = service.service_usage()
        self.assertEqual((usage["generation_requests"], usage["generated_chats"], usage["total_generated_chats"]), (1, 2, 2))
        self.assertNotIn("total_tokens", usage)
        self.assertEqual(DesktopService(self.directory).service_usage(), usage)

    async def test_service_month_rollover_keeps_lifetime_total_and_mock_separate(self):
        service = self.service(FakeProvider())
        service.month_clock = lambda: "2026-10"
        await self.run_batch(service, 2)
        await self.run_batch(service, 1, provider_name="mock")
        service.month_clock = lambda: "2026-11"
        self.assertEqual(service.service_usage()["generated_chats"], 0)
        await self.run_batch(service, 1)
        usage = service.service_usage()
        self.assertEqual((usage["generation_requests"], usage["generated_chats"], usage["total_generated_chats"]), (1, 1, 3))
        self.assertEqual(service.service_usage("mock")["total_generated_chats"], 1)
