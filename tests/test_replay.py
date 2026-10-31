"""Critical replay correctness checks; no network or model API calls."""

from __future__ import annotations

import asyncio
from contextlib import redirect_stdout
import json
import io
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np
from PIL import Image

from experiments.artifacts import MOCK_LABEL, _visible_comments, write_report
from experiments.media import ClipMedia, Frame
from experiments.replay import ReplayConfig, ReplayEngine, score_matches


class _SlowProvider:
    provider = "mock"
    model = "qa-artificial-delay"

    def __init__(self, delay_s):
        self.delay_s = delay_s
        self.snapshots = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def infer(self, snapshot, *, mode="joint"):
        self.snapshots.append(snapshot)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.delay_s)
            return {"action": "REACT", "event": "QA supplied past frame",
                    "comment": f"MOCK {snapshot['request_id']}",
                    "evidence_frame_ids": [snapshot["frames"][-1]["frame_id"]],
                    "provider": self.provider, "model": self.model,
                    "decision_ms": self.delay_s * 1000, "generation_ms": 0.0,
                    "usage": {"is_ai": False}, "model_calls": 0}
        finally:
            self.in_flight -= 1


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def _replay(self, directory, *, duration_s, delay_s, max_age_s):
        image = directory / "past.jpg"
        Image.new("RGB", (16, 16), "blue").save(image)
        frames = [Frame(f"f{index}", index * 0.03, image)
                  for index in range(int(duration_s / 0.03) + 1)
                  if index * 0.03 < duration_s]
        media = ClipMedia(frames, duration_s=duration_s)
        config = ReplayConfig(observe_interval_s=0.025, min_trigger_gap_s=0.02,
                              context_window_s=0.2, max_frames=4, cooldown_s=0,
                              max_snapshot_age_s=max_age_s, request_timeout_s=2,
                              visual_threshold=1)
        provider = _SlowProvider(delay_s)
        engine = ReplayEngine(config, directory / "run")
        with redirect_stdout(io.StringIO()):
            run = await engine.run(media, provider)
        return engine, provider, run

    async def test_playback_keeps_advancing_replaces_pending_and_never_backdates_display(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine, provider, run = await self._replay(
                Path(temporary), duration_s=0.42, delay_s=0.16, max_age_s=1)
            self.assertEqual(provider.max_in_flight, 1)
            self.assertGreater(run["summary"]["replaced_pending"], 0)
            self.assertGreaterEqual(len(provider.snapshots), 2)
            # A blocking replay or FIFO would send the 0.03s snapshot next.
            self.assertGreaterEqual(provider.snapshots[1]["input_cutoff_video_s"], 0.09)
            self.assertLessEqual(len(provider.snapshots), 4)
            self.assertGreaterEqual(run["summary"]["wall_elapsed_s"], 0.42)
            self.assertTrue(run["is_mock"])
            self.assertIsNone(run["summary"]["event_to_display_ms"])
            self.assertIn(MOCK_LABEL, run["limitations"])
            displayed = [event for event in engine.records if event["status"] == "displayed"]
            self.assertTrue(displayed)
            for event in displayed:
                self.assertGreaterEqual(event["displayed_video_s"], event["response_completed_video_s"])
                self.assertGreater(event["displayed_video_s"], event["input_cutoff_video_s"])
                self.assertLess(event["displayed_video_s"], 0.42)
            self.assertTrue(any(event["status"] == "after_end" for event in engine.records))
            self.assertTrue(all(event["displayed_video_s"] is None
                                for event in engine.records if event["status"] != "displayed"))
            for snapshot in provider.snapshots:
                self.assertTrue(all(frame["video_s"] <= snapshot["input_cutoff_video_s"]
                                    for frame in snapshot["frames"]))

    async def test_expired_outputs_are_recorded_but_never_displayed(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine, _, run = await self._replay(
                Path(temporary), duration_s=0.23, delay_s=0.12, max_age_s=0.05)
            self.assertGreater(run["summary"]["status_counts"]["expired"], 0)
            self.assertEqual(run["summary"]["status_counts"]["displayed"], 0)
            self.assertTrue(all(event["displayed_video_s"] is None for event in engine.records))


class HumanMatchTests(unittest.TestCase):
    def test_event_latency_requires_explicit_human_match_and_observable_past_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "run.json").write_text(json.dumps({"is_mock": True, "duration_s": 1}), encoding="utf-8")
            record = {"request_id": "r1", "status": "displayed",
                      "input_cutoff_video_s": 0.2, "displayed_video_s": 0.5}
            (directory / "events.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
            annotations = {"events": [{"event_id": "e1", "onset_s": 0.1,
                                        "observable_s": 0.13, "valid_until_s": 0.8}]}
            annotation_path = directory / "annotations.json"
            annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
            review = {"reviewed_by_human": False, "matches": [
                {"request_id": "r1", "event_id": "e1", "judgment": "appropriate"}]}
            matches_path = directory / "matches.json"
            matches_path.write_text(json.dumps(review), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reviewed_by_human"):
                score_matches(directory, str(annotation_path), str(matches_path))
            self.assertFalse((directory / "human_review.json").exists())

            review["reviewed_by_human"] = True
            matches_path.write_text(json.dumps(review), encoding="utf-8")
            score = score_matches(directory, str(annotation_path), str(matches_path))
            self.assertTrue(score["is_mock"])
            self.assertAlmostEqual(score["matched_reactions"][0]["event_to_display_ms"], 400)
            self.assertAlmostEqual(score["matched_reactions"][0]["observable_to_display_ms"], 370)
            self.assertEqual(score["latency_for_appropriate_matches_ms"]["n"], 1)

            annotations["events"][0]["observable_s"] = 0.25
            annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not yet observable"):
                score_matches(directory, str(annotation_path), str(matches_path))


class MediaCausalityTests(unittest.TestCase):
    def test_future_frames_are_unreadable_and_audio_ends_before_fractional_cutoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            past_paths = []
            for index, color in enumerate(("red", "green")):
                path = directory / f"past-{index}.jpg"
                Image.new("RGB", (8, 8), color).save(path)
                past_paths.append(path)
            # A future frame that cannot even be read proves that selecting a
            # past snapshot does not inspect future media bytes.
            media = ClipMedia([
                Frame("f0", 0.0, past_paths[0]),
                Frame("f1", 0.1, past_paths[1]),
                Frame("future", 0.2, directory / "future-unavailable.jpg"),
            ], duration_s=0.4, audio=np.arange(400, dtype=np.int16), sample_rate=1000)
            cutoff = 0.1499
            frames = media.frames_until(cutoff, window_s=1, max_frames=6)
            self.assertEqual([frame["frame_id"] for frame in frames], ["f0", "f1"])
            self.assertTrue(all(frame["video_s"] <= cutoff for frame in frames))
            self.assertEqual(media.frames_until(cutoff, 1, 1)[0]["frame_id"], "f1")

            wav, start, end = media.audio_window(cutoff, window_s=0.1)
            self.assertEqual((start, end), (0.049, 0.149))
            self.assertLessEqual(end, cutoff)
            with wave.open(io.BytesIO(wav), "rb") as source:
                self.assertEqual(source.getframerate(), 1000)
                samples = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2")
            np.testing.assert_array_equal(samples, np.arange(49, 149, dtype=np.int16))
            self.assertEqual(media.audio_window(0.0004, 0.1), (None, None, None))


class ArtifactTimingTests(unittest.TestCase):
    def test_comments_use_actual_display_time_and_never_show_suppressed_results(self):
        events = [
            {"request_id": "old-input", "status": "displayed",
             "input_cutoff_video_s": 0.25, "response_completed_video_s": 1.7,
             "displayed_video_s": 1.73, "comment": "ready"},
            {"request_id": "suppressed", "status": "expired",
             "input_cutoff_video_s": 0.5, "displayed_video_s": 0.6,
             "comment": "must not appear"},
        ]
        self.assertEqual(_visible_comments(events, 1.72), [])
        self.assertEqual([e["request_id"] for e in _visible_comments(events, 1.73)],
                         ["old-input"])

    def test_mock_report_preserves_timing_caveats_and_escapes_model_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            # An individual mock result must keep the mock warning visible even
            # if run metadata accidentally omits the top-level is_mock marker.
            run = {"provider": "test", "model": "fixture", "mode": "joint",
                   "duration_s": 3.0, "measured_realtime": True, "settings": {}}
            event = {"request_id": "r1", "provider": "mock", "status": "displayed",
                     "input_cutoff_video_s": 0.4, "response_completed_video_s": 1.0,
                     "displayed_video_s": 1.05, "api_latency_ms": 600.0,
                     "snapshot_age_ms": 600.0, "event": "color changed",
                     "comment": '<script>alert("joke")</script> 드립'}
            (directory / "run.json").write_text(json.dumps(run), encoding="utf-8")
            (directory / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
            report = Path(write_report(str(directory))).read_text(encoding="utf-8")
            self.assertIn(MOCK_LABEL, report)
            self.assertIn("Pipeline timings (mock)", report)
            self.assertIn("not event-onset-to-chat latency", report)
            self.assertIn("No human-matched event onset annotations", report)
            self.assertNotIn('<script>alert("joke")</script>', report)
            self.assertIn("&lt;script&gt;", report)
            self.assertIn("드립", report)


if __name__ == "__main__":
    unittest.main()
