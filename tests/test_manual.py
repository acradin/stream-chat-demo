"""Critical HTTP-flow checks for explicit, text-only button generation.

All providers here are local fakes. These tests do not measure AI latency.
"""

from __future__ import annotations

import asyncio
import copy
import csv
import json
from pathlib import Path
import tempfile
import time
import unittest
import uuid

from aiohttp.test_utils import TestClient, TestServer

from apps.web.server import create_app


class ControlledProvider:
    provider = "mock"
    model = "manual-http-test"

    def __init__(self, *, hold: bool = False, delay: float = 0):
        self.calls = []
        self.hold = hold
        self.delay = delay
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, context):
        self.calls.append(copy.deepcopy(context))
        self.entered.set()
        started = time.perf_counter()
        if self.hold:
            await self.release.wait()
        elif self.delay:
            await asyncio.sleep(self.delay)
        return {"comment": "[MOCK] 채팅창에 웃음 한 스푼 놓고 갑니다 ㅋㅋ",
                "provider": self.provider, "model": self.model,
                "generation_ms": (time.perf_counter() - started) * 1000,
                "usage": {"is_ai": False}, "model_calls": 0}

    async def close(self):
        self.release.set()


def trigger_payload(**changes):
    result = {"client_request_id": str(uuid.uuid4()), "persona": "witty_friend",
              "channel_context": "편하게 이야기하는 게임 방송", "clicked_video_s": 6.25,
              "video_session_id": "local-clip-a"}
    result.update(changes)
    return result


class ManualFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="manual-http-tests-")
        self.clients = []

    async def asyncTearDown(self):
        for client in reversed(self.clients):
            await client.close()
        self.temp.cleanup()

    async def open_client(self, provider, **settings):
        options = {"cooldown_s": 0.0, "max_age_s": 8.0, "timeout_s": 1.0}
        options.update(settings)
        directory = Path(self.temp.name) / f"run-{len(self.clients)}"
        client = TestClient(TestServer(create_app(provider, directory, **options)))
        self.clients.append(client)
        await client.start_server()
        config_response = await client.get("/api/config")
        self.assertEqual(config_response.status, 200)
        config = await config_response.json()
        self.assertEqual({item["id"] for item in config["personas"]},
                         {"witty_friend", "warm_supporter", "hype_commentator", "dry_comic"})
        self.assertEqual(config["default_persona"], "witty_friend")
        self.assertTrue(all(set(item) == {"id", "name", "description"} for item in config["personas"]))
        headers = {"X-Demo-Token": config["session_token"]}
        return client, headers, directory

    async def records(self, client):
        response = await client.get("/api/export")
        self.assertEqual(response.status, 200)
        return [json.loads(line) for line in (await response.text()).splitlines() if line.strip()]

    async def test_idle_is_free_and_only_client_ack_records_button_latency(self):
        provider = ControlledProvider()
        client, headers, directory = await self.open_client(provider)
        await client.get("/api/config")
        self.assertEqual(await self.records(client), [])
        self.assertEqual(provider.calls, [])

        payload = trigger_payload()
        response = await client.post("/api/trigger", json=payload, headers=headers)
        data = await response.json()
        self.assertEqual(data["status"], "ready", data)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(set(provider.calls[0]), {
            "request_id", "persona", "channel_context", "recent_comments"})
        self.assertEqual(provider.calls[0]["persona"], "witty_friend")
        self.assertEqual(provider.calls[0]["channel_context"], payload["channel_context"])
        # Playback position is log metadata, never media/context for the model.
        self.assertNotIn("clicked_video_s", provider.calls[0])
        before = (await self.records(client))[0]
        self.assertEqual(before["status"], "ready")
        self.assertIsNone(before["button_to_display_ms"])

        acknowledgement = {"request_id": data["request_id"], "button_to_display_ms": 37.5,
                           "displayed_video_s": 6.2875, "video_session_id": "local-clip-a",
                           "status": "displayed", "reason": ""}
        ack = await client.post("/api/display", json=acknowledgement, headers=headers)
        self.assertLess(ack.status, 400, await ack.text())
        after = (await self.records(client))[0]
        self.assertEqual(after["status"], "displayed")
        self.assertEqual(after["button_to_display_ms"], 37.5)
        self.assertEqual(after["displayed_video_s"], 6.2875)
        self.assertEqual(len(provider.calls), 1)
        self.assertTrue((directory / "events.jsonl").is_file())
        self.assertEqual(after["persona"], "witty_friend")
        self.assertEqual(after["channel_context"], payload["channel_context"])
        with (directory / "events.csv").open(encoding="utf-8-sig", newline="") as handle:
            csv_record = next(csv.DictReader(handle))
        self.assertEqual(csv_record["persona"], "witty_friend")
        self.assertEqual(csv_record["channel_context"], payload["channel_context"])
        self.assertNotIn("preset", csv_record)

    async def test_concurrent_click_is_rejected_and_same_id_does_not_call_again(self):
        provider = ControlledProvider(hold=True)
        client, headers, _ = await self.open_client(provider)
        payload = trigger_payload()
        first_task = asyncio.create_task(client.post("/api/trigger", json=payload, headers=headers))
        await asyncio.wait_for(provider.entered.wait(), 1)
        second_response = await client.post("/api/trigger", json=trigger_payload(), headers=headers)
        second = await second_response.json()
        self.assertEqual(second["status"], "busy", second)
        self.assertEqual(len(provider.calls), 1)
        provider.release.set()
        first = await (await first_task).json()
        self.assertEqual(first["status"], "ready", first)
        repeated = await (await client.post("/api/trigger", json=payload, headers=headers)).json()
        self.assertIn(repeated["status"], ("ready", "duplicate"), repeated)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(len(await self.records(client)), 1)

    async def test_wrong_token_media_and_invalid_persona_payload_never_reach_provider(self):
        provider = ControlledProvider()
        client, headers, _ = await self.open_client(provider)
        denied = await client.post("/api/trigger", json=trigger_payload(),
                                   headers={"X-Demo-Token": "not-the-session-token"})
        self.assertGreaterEqual(denied.status, 400)
        for key, value in (("frames", []), ("audio_wav", "not-allowed"),
                           ("persona", "invented"), ("persona", []),
                           ("preset", "mistake"), ("tone", "warm"), ("situation", "성공"),
                           ("channel_context", "x" * 1001)):
            bad = trigger_payload(**{key: value})
            response = await client.post("/api/trigger", json=bad, headers=headers)
            self.assertGreaterEqual(response.status, 400, await response.text())
        self.assertEqual(provider.calls, [])
        self.assertEqual(await self.records(client), [])

    async def test_persona_and_optional_info_are_snapshotted_at_trigger(self):
        provider = ControlledProvider()
        client, headers, directory = await self.open_client(provider)
        supplied = "=방송 정보: 빵 굽기 연습\n시청자에게 알려줄 별명은 빵장"
        first = await (await client.post("/api/trigger", headers=headers, json=trigger_payload(
            persona="warm_supporter", channel_context=supplied))).json()
        self.assertEqual(first["status"], "ready", first)
        second = await (await client.post("/api/trigger", headers=headers, json=trigger_payload(
            persona="dry_comic", channel_context="", clicked_video_s=None, video_session_id=None))).json()
        self.assertEqual(second["status"], "ready", second)
        self.assertEqual([(call["persona"], call["channel_context"]) for call in provider.calls],
                         [("warm_supporter", supplied), ("dry_comic", "")])
        records = await self.records(client)
        self.assertEqual(records[0]["channel_context"], supplied)
        self.assertEqual(records[1]["channel_context"], "")
        with (directory / "events.csv").open(encoding="utf-8-sig", newline="") as handle:
            exported = list(csv.DictReader(handle))
        self.assertEqual(exported[0]["channel_context"], "'" + supplied)

    async def test_expired_and_timed_out_results_never_get_display_latency(self):
        for settings, expected in (({"max_age_s": 0.01, "timeout_s": 0.5}, "expired"),
                                   ({"max_age_s": 1.0, "timeout_s": 0.01}, "error")):
            with self.subTest(expected=expected):
                provider = ControlledProvider(delay=0.06)
                client, headers, _ = await self.open_client(provider, **settings)
                response = await client.post("/api/trigger", json=trigger_payload(), headers=headers)
                result = await response.json()
                self.assertEqual(result["status"], expected, result)
                record = (await self.records(client))[0]
                self.assertEqual(record["status"], expected)
                self.assertIsNone(record["button_to_display_ms"])
                ack = {"request_id": result["request_id"], "button_to_display_ms": 1.0,
                       "displayed_video_s": 6.251, "video_session_id": "local-clip-a",
                       "status": "displayed", "reason": ""}
                blocked = await client.post("/api/display", json=ack, headers=headers)
                self.assertGreaterEqual(blocked.status, 400)
                self.assertIsNone((await self.records(client))[0]["button_to_display_ms"])
                self.assertEqual(len(provider.calls), 1)


if __name__ == "__main__":
    unittest.main()
