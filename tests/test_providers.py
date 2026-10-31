"""Provider contract checks; all model responses are stubs, no paid API calls."""

import copy
import io
import json
import unittest
from unittest.mock import patch

from PIL import Image

from backend.providers import (GeminiProvider, InvalidResponseError, MockProvider,
                       ProviderError, _parse_response)


def snapshot(color=(25, 42, 68)):
    image = io.BytesIO()
    Image.new("RGB", (16, 16), color).save(image, "JPEG")
    return {"request_id": "test-1", "input_cutoff_video_s": 2.0,
            "frames": [{"frame_id": "f1", "video_s": 1.5, "jpeg": image.getvalue()}],
            "audio_wav": None, "audio_start_s": None, "audio_end_s": None,
            "recent_comments": [], "trigger": "periodic", "signals": {}}


def decision(action="REACT", comment="분위기 전환은 확실하네 ㅋㅋ"):
    return {"action": action, "event": "배경색이 바뀜", "evidence_frame_ids": ["f1"],
            "comment": comment if action == "REACT" else ""}


class StubGemini(GeminiProvider):
    def __init__(self, outputs):
        super().__init__("test-model", api_key="stub-never-sent")
        self.outputs = iter(outputs)
        self.requests = []

    async def _request(self, model, payload):
        self.requests.append((model, payload))
        return copy.deepcopy(next(self.outputs)), {"totalTokenCount": 11}


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_joint_has_one_call_and_documented_multimodal_payload(self):
        provider = StubGemini([decision()])
        item = snapshot()
        item.update(audio_wav=b"RIFF-stub-wav", audio_start_s=1.0, audio_end_s=2.0)
        result = await provider.infer(item)
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(result["generation_ms"], 0)
        self.assertEqual(result["provider"], "gemini")
        payload = provider.requests[0][1]
        media = [p["inlineData"] for p in payload["contents"][0]["parts"] if "inlineData" in p]
        self.assertEqual([p["mimeType"] for p in media], ["image/jpeg", "audio/wav"])
        self.assertEqual(payload["generationConfig"]["responseFormat"]["text"]["mimeType"], "APPLICATION_JSON")
        self.assertNotIn("thinkingConfig", payload["generationConfig"])
        self.assertNotIn("stub-never-sent", json.dumps(payload))
        self.assertEqual(result["usage"]["totalTokenCount"], 11)

    async def test_no_network_call_when_frame_or_audio_is_in_future(self):
        provider = StubGemini([decision()])
        item = snapshot()
        item["frames"][0]["video_s"] = 2.1
        with self.assertRaisesRegex(ValueError, "after its input cutoff"):
            await provider.infer(item)
        item = snapshot()
        item.update(audio_wav=b"WAV", audio_start_s=1.0, audio_end_s=2.1)
        with self.assertRaisesRegex(ValueError, "input cutoff"):
            await provider.infer(item)
        self.assertEqual(provider.requests, [])

    async def test_rejects_unknown_evidence_and_nonempty_wait_comment(self):
        wrong_frame = decision()
        wrong_frame["evidence_frame_ids"] = ["future-f2"]
        provider = StubGemini([wrong_frame, {**decision(), "action": "WAIT"}])
        with self.assertRaisesRegex(InvalidResponseError, "frame ID"):
            await provider.infer(snapshot())
        with self.assertRaisesRegex(InvalidResponseError, "empty comment"):
            await provider.infer(snapshot())

    async def test_split_wait_never_calls_writer(self):
        provider = StubGemini([decision("WAIT")])
        result = await provider.infer(snapshot(), mode="split")
        self.assertEqual(result["action"], "WAIT")
        self.assertEqual(result["model_calls"], 1)
        self.assertEqual(len(provider.requests), 1)

    async def test_split_react_calls_text_only_writer_and_sums_usage(self):
        provider = StubGemini([decision(comment=""), {"comment": "색깔도 퇴근하고 싶었나 봄 ㅋㅋ"}])
        provider.writer_model = "writer-test-model"
        result = await provider.infer(snapshot(), mode="split")
        self.assertEqual(result["action"], "REACT")
        self.assertEqual(result["model_calls"], 2)
        self.assertEqual(result["usage"]["totalTokenCount"], 22)
        self.assertEqual(provider.requests[1][0], "writer-test-model")
        self.assertTrue(all("text" in part for part in provider.requests[1][1]["contents"][0]["parts"]))

    async def test_mock_waits_initially_reacts_on_color_change_and_marks_no_ai(self):
        provider = MockProvider(delay_s=0)
        first = await provider.infer(snapshot())
        second = await provider.infer(snapshot((136, 44, 52)))
        third = await provider.infer(snapshot((136, 44, 52)))
        self.assertEqual([first["action"], second["action"], third["action"]], ["WAIT", "REACT", "WAIT"])
        self.assertEqual(second["provider"], "mock")
        self.assertEqual(second["model_calls"], 0)
        self.assertFalse(second["usage"]["is_ai"])
        self.assertIn("MOCK", second["comment"])

    async def test_http_error_omits_credential_and_upstream_body(self):
        class Response:
            status = 403

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

        class Session:
            closed = False

            def post(self, *args, **kwargs):
                self.headers = kwargs["headers"]
                self.redirects = kwargs["allow_redirects"]
                return Response()

        provider = GeminiProvider("test-model", api_key="a-secret-test-key")
        provider._session = Session()
        with self.assertRaises(ProviderError) as error:
            await provider._request("test-model", {})
        self.assertIn("403", str(error.exception))
        self.assertNotIn("a-secret-test-key", str(error.exception))
        self.assertFalse(provider._session.redirects)


class ParsingTests(unittest.TestCase):
    def test_credentials_required_and_model_cannot_redirect_request(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "requires GEMINI_API_KEY"):
                GeminiProvider("test-model")
        with self.assertRaisesRegex(ValueError, "not a URL"):
            GeminiProvider("https://example.org", api_key="stub")

    def test_filters_thought_parts_and_rejects_truncated_candidate(self):
        body = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"thought": True, "text": "not output"}, {"text": json.dumps(decision())}]}}]}
        result, usage = _parse_response(body)
        self.assertEqual(result["action"], "REACT")
        self.assertEqual(usage, {})
        body["candidates"][0]["finishReason"] = "MAX_TOKENS"
        with self.assertRaisesRegex(InvalidResponseError, "did not finish"):
            _parse_response(body)


if __name__ == "__main__":
    unittest.main()
