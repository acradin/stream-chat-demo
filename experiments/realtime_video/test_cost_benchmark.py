"""Offline accounting, causal selection and no-call policy checks."""

import unittest

from experiments.realtime_video.cost_benchmark import ARMS, dollars, summarize, trial
from experiments.realtime_video.cost_cases import cases, model_frames, scheduling_probe, select
from experiments.realtime_video.provider import RealtimeError


def usage():
    return {"input_tokens": 3033, "output_tokens": 85,
            "input_token_details": {"text_tokens": 1095, "image_tokens": 1938, "audio_tokens": 0,
                "cached_tokens": 0, "cached_tokens_details": {"text_tokens": 0, "image_tokens": 0}},
            "output_token_details": {"text_tokens": 85, "audio_tokens": 0, "reasoning_tokens": 50}}


class AccountingTests(unittest.TestCase):
    def test_measured_usage_prices_reasoning_once(self):
        self.assertAlmostEqual(dollars(usage(), "gpt-realtime-2.1"), .01611)
        self.assertAlmostEqual(dollars(usage(), "gpt-realtime-2.1-mini"), .0024114)

    def test_cached_modalities_get_their_own_discount_and_missing_usage_is_not_free(self):
        value = usage()
        value["input_token_details"].update(cached_tokens=600, cached_tokens_details={"text_tokens": 100, "image_tokens": 500})
        self.assertAlmostEqual(dollars(value, "gpt-realtime-2.1"), .01611-.00036-.00225)
        with self.assertRaises(ValueError):
            dollars(None, "gpt-realtime-2.1")
        value["input_token_details"]["cached_tokens"] = 700
        with self.assertRaises(ValueError):
            dollars(value, "gpt-realtime-2.1")


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = {case.name: case for case in cases()}

    def test_endpoints_miss_middle_event_but_change_pair_contains_it(self):
        case = self.values["transient"]
        endpoints, _ = select(case, "endpoints")
        changed, _ = select(case, "change")
        self.assertFalse({i+1 for i in endpoints} & set(case.evidence_sequences))
        self.assertTrue({i+1 for i in changed} & set(case.evidence_sequences))
        frames = model_frames(case, changed, now=100)
        self.assertTrue(all(frame.received_at <= 100 for frame in frames))
        self.assertLess(frames[0].sequence, frames[1].sequence)

    def test_static_skips_and_motion_is_not_assumed_semantic(self):
        self.assertEqual(select(self.values["still"], "change")[0], ())
        self.assertEqual(len(select(self.values["motion_only"], "change")[0]), 2)
        self.assertEqual(self.values["motion_only"].expected, "WAIT")

    def test_precall_cooldown_reduces_paid_calls_in_explicit_scheduler_assumption(self):
        old = scheduling_probe(5, False)
        new = scheduling_probe(5, True)
        self.assertGreater(old["suppressed_after_paid_call"], 0)
        self.assertEqual(new["suppressed_after_paid_call"], 0)
        self.assertLess(new["calls"], old["calls"])
        self.assertEqual(new["displayed"], old["displayed"])


class TrialTests(unittest.IsolatedAsyncioTestCase):
    async def test_gate_never_constructs_provider(self):
        def forbidden(*args):
            raise AssertionError("No provider should be constructed")
        row = await trial(cases()[0], ARMS[3], 1, "unused", factory=forbidden)
        self.assertFalse(row["called"])
        self.assertTrue(row["action_correct"])
        self.assertEqual(row["cost_usd"], 0)

    async def test_invalid_response_keeps_paid_usage_and_counts_as_miss(self):
        class Fake:
            def __init__(self, *args):
                self.usage, self.response_status, self.raw_text = usage(), "completed", "invalid output"
            async def open(self):
                pass
            async def push_frame(self, frame):
                pass
            async def analyze(self, *args):
                raise RealtimeError("Invalid output")
            async def close(self):
                pass
        row = await trial(cases()[1], ARMS[0], 1, "unused", factory=Fake)
        self.assertTrue(row["called"])
        self.assertFalse(row["valid"])
        self.assertTrue(row["missed_event"])
        self.assertAlmostEqual(row["cost_usd"], .01611)
        result = summarize([row])["large_6"]
        self.assertEqual(result["correct_actions"], 0)
        self.assertEqual(result["api_calls"], 1)
        self.assertAlmostEqual(result["total_usd"], .01611)


if __name__ == "__main__":
    unittest.main()
