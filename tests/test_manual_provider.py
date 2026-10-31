"""Manual writer contracts: text-only inputs, explicit mock, no paid requests."""

import copy
import json
import unittest
from unittest.mock import patch

from manual_provider import GeminiManualProvider, MockManualProvider, validate_context
from providers import InvalidResponseError


def context(**updates):
    item = {"request_id": "button-1", "preset": "reaction", "channel_context": "편안한 잡담 방송",
            "situation": "", "tone": "playful", "recent_comments": []}
    item.update(updates)
    return item


class StubManual(GeminiManualProvider):
    def __init__(self, outputs):
        super().__init__("test-model", api_key="never-sent-test-key")
        self.outputs = iter(outputs)
        self.requests = []

    async def _request(self, payload):
        self.requests.append(payload)
        return copy.deepcopy(next(self.outputs)), {"totalTokenCount": 9}


class ManualProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_text_call_returns_comment_without_decision_or_media(self):
        provider = StubManual([{"comment": "분위기 예열 중이네 ㅋㅋ"}])
        result = await provider.generate(context())
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["provider"], "gemini")
        self.assertEqual(result["usage"]["totalTokenCount"], 9)
        self.assertNotIn("action", result)
        self.assertEqual(len(provider.requests), 1)
        payload = provider.requests[0]
        parts = payload["contents"][0]["parts"]
        self.assertEqual(len(parts), 1)
        self.assertEqual(set(parts[0]), {"text"})
        self.assertEqual(json.loads(parts[0]["text"]), context())
        self.assertNotIn("inlineData", json.dumps(payload))
        self.assertNotIn("never-sent-test-key", json.dumps(payload))
        schema = payload["generationConfig"]["responseFormat"]["text"]["schema"]
        self.assertEqual(set(schema["properties"]), {"comment"})
        await provider.close()

    async def test_media_unknown_fields_and_invalid_context_fail_before_request(self):
        provider = StubManual([])
        bad_inputs = [context(frames=[]), context(audio_wav=b"WAV"), context(video_s=2),
                      context(preset="invented"), context(preset=[]), context(tone=True),
                      context(situation="x" * 501), context(channel_context="x" * 1001),
                      context(recent_comments=["a"] * 9), context(recent_comments=[{}]),
                      context(recent_comments=["line\nbreak"]), context(request_id="")]
        for item in bad_inputs:
            with self.subTest(context=item), self.assertRaises(ValueError):
                await provider.generate(item)
        self.assertEqual(provider.requests, [])
        await provider.close()

    async def test_blank_oversized_multiline_and_extra_model_fields_rejected(self):
        bad_outputs = [{"comment": " "}, {"comment": "가" * 101}, {"comment": "첫 줄\n둘째 줄"},
                       {"comment": "한 줄\u2028두 줄"}, {"comment": 4},
                       {"comment": "내용", "action": "REACT"}]
        provider = StubManual(bad_outputs)
        for output in bad_outputs:
            with self.subTest(output=output), self.assertRaises(InvalidResponseError):
                await provider.generate(context())
        await provider.close()

    async def test_mock_varies_recent_preset_comments_and_always_identifies_simulation(self):
        provider = MockManualProvider(delay_s=0)
        recent = []
        for _ in range(3):
            result = await provider.generate(context(preset="mistake", recent_comments=recent))
            self.assertNotIn(result["comment"], recent)
            self.assertTrue(result["comment"].startswith("[MOCK]"))
            self.assertFalse(result["usage"]["is_ai"])
            self.assertEqual(result["model_calls"], 0)
            self.assertEqual(result["provider"], "mock")
            recent.append(result["comment"])
        fourth = await provider.generate(context(preset="mistake", recent_comments=recent))
        self.assertEqual(fourth["comment"], recent[0])
        await provider.close()


class ManualValidationTests(unittest.TestCase):
    def test_key_is_required_and_mock_delay_cannot_be_negative(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "requires GEMINI_API_KEY"):
                GeminiManualProvider()
        with self.assertRaises(ValueError):
            MockManualProvider(delay_s=-1)

    def test_context_is_copied_as_text_without_invented_situation(self):
        original = context(channel_context="  잡담  ", situation="", recent_comments=["한 줄"])
        cleaned = validate_context(original)
        self.assertEqual(cleaned["situation"], "")
        self.assertEqual(cleaned["channel_context"], "잡담")
        cleaned["recent_comments"].append("새로운 줄")
        self.assertEqual(original["recent_comments"], ["한 줄"])


if __name__ == "__main__":
    unittest.main()
