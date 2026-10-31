"""Real-time causal replay CLI for an AI livestream cohost experiment."""

from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys
import time

import numpy as np

from experiments.media import ClipMedia, prepare_clip
from backend.providers import GeminiProvider, MockProvider, InvalidResponseError, ProviderError


@dataclass
class ReplayConfig:
    observe_interval_s: float = 2.0
    min_trigger_gap_s: float = 0.75
    context_window_s: float = 4.0
    max_frames: int = 6
    cooldown_s: float = 6.0
    max_snapshot_age_s: float = 5.0
    request_timeout_s: float = 20.0
    visual_threshold: float = 0.12
    audio_spike_threshold: float = 3.0
    audio_min_rms: float = 0.04
    mode: str = "joint"

    def validate(self) -> None:
        for key in ("observe_interval_s", "min_trigger_gap_s", "context_window_s",
                    "max_snapshot_age_s", "request_timeout_s", "audio_spike_threshold"):
            value = getattr(self, key)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be finite and positive")
        for key in ("cooldown_s", "visual_threshold", "audio_min_rms"):
            value = getattr(self, key)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{key} must be finite and nonnegative")
        if not 1 <= self.max_frames <= 32:
            raise ValueError("max_frames must be between 1 and 32")
        if self.mode not in ("joint", "split"):
            raise ValueError("mode must be joint or split")


def distribution(values: list[float]) -> dict:
    return {"n": len(values), "p50": round(float(np.percentile(values, 50)), 3) if values else None,
            "p95": round(float(np.percentile(values, 95)), 3) if values else None,
            "max": round(max(values), 3) if values else None}


def _write_json(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


class ReplayEngine:
    """One inference in flight plus one replaceable, newest pending snapshot.

    The media clock never pauses for inference. Result completion and display
    times are actual monotonic times relative to replay start, not source PTS.
    """

    def __init__(self, config: ReplayConfig, run_dir: str | Path):
        config.validate()
        self.config = config
        self.run_dir = Path(run_dir)
        self.records: list[dict] = []
        self.comments: list[dict] = []
        self.replaced_pending = 0
        self.pending_discarded_at_end = 0
        self._started = 0.0
        self._counter = 0

    def _now(self) -> float:
        return time.monotonic() - self._started

    async def _at(self, video_s: float) -> None:
        await asyncio.sleep(max(0.0, self._started + video_s - time.monotonic()))

    def _snapshot(self, media: ClipMedia, cutoff: float, trigger: str, signals: dict) -> dict:
        self._counter += 1
        frames = media.frames_until(cutoff, self.config.context_window_s, self.config.max_frames)
        audio, audio_start, audio_end = media.audio_window(cutoff, self.config.context_window_s)
        return {"request_id": f"r{self._counter:06d}", "input_cutoff_video_s": cutoff,
                "frames": frames, "audio_wav": audio, "audio_start_s": audio_start,
                "audio_end_s": audio_end, "trigger": trigger, "signals": signals,
                "recent_comments": [dict(c) for c in self.comments[-8:]
                                    if c["displayed_video_s"] <= cutoff]}

    @staticmethod
    def _valid_response(result: dict, snapshot: dict) -> bool:
        if not isinstance(result, dict) or result.get("action") not in ("WAIT", "REACT"):
            return False
        comment = result.get("comment")
        event = result.get("event")
        ids = result.get("evidence_frame_ids")
        if not isinstance(comment, str) or len(comment) > 100 or "\n" in comment or "\r" in comment:
            return False
        if not isinstance(event, str) or len(event) > 600 or not isinstance(ids, list):
            return False
        valid_ids = {f["frame_id"] for f in snapshot["frames"]}
        if any(not isinstance(i, str) or i not in valid_ids for i in ids):
            return False
        if len(set(ids)) != len(ids):
            return False
        if result["action"] == "WAIT":
            return not comment.strip()
        return bool(comment.strip() and event.strip() and (ids or snapshot["audio_wav"]))

    def _log(self, record: dict, log) -> None:
        self.records.append(record)
        log.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        log.flush()
        line = f"[{record['response_completed_video_s']:6.2f}s] {record['status']:>9}"
        if record["status"] == "displayed":
            line += f"  {record['comment']}"
        elif record.get("error"):
            line += f"  {record['error']}"
        print(line, flush=True)

    async def _consume(self, queue: asyncio.Queue, media: ClipMedia, provider, log) -> None:
        cfg = self.config
        while True:
            snapshot = await queue.get()
            if snapshot is None:
                return
            begin = self._now()
            cutoff = snapshot["input_cutoff_video_s"]
            record = {"request_id": snapshot["request_id"], "input_cutoff_video_s": cutoff,
                      "snapshot_first_video_s": min(
                          [f["video_s"] for f in snapshot["frames"]] +
                          ([snapshot["audio_start_s"]] if snapshot["audio_wav"] else [])),
                      "frame_times_s": [f["video_s"] for f in snapshot["frames"]],
                      "frame_ids": [f["frame_id"] for f in snapshot["frames"]],
                      "audio_start_s": snapshot["audio_start_s"], "audio_end_s": snapshot["audio_end_s"],
                      "trigger": snapshot["trigger"], "signals": snapshot["signals"],
                      "request_started_video_s": begin, "response_completed_video_s": begin,
                      "api_latency_ms": 0.0, "snapshot_age_ms": (begin - cutoff) * 1000,
                      "snapshot_to_display_ms": None, "displayed_video_s": None,
                      "action": None, "event": "", "comment": "", "evidence_frame_ids": [],
                      "status": "error", "error": None,
                      "provider": provider.provider, "model": provider.model,
                      "decision_ms": 0.0, "generation_ms": 0.0, "usage": {}, "model_calls": 0,
                      "call_attempted": False}
            # A queued input can become stale before it even gets a model slot.
            if begin >= media.duration_s or begin - cutoff > cfg.max_snapshot_age_s:
                record["status"] = "after_end" if begin >= media.duration_s else "expired"
                self._log(record, log)
                continue
            record["call_attempted"] = True
            result = None
            try:
                result = await asyncio.wait_for(provider.infer(snapshot, mode=cfg.mode), cfg.request_timeout_s)
            except InvalidResponseError as exc:
                record["status"], record["error"] = "invalid", str(exc)
            except ProviderError as exc:
                record["status"], record["error"] = "error", str(exc)
            except asyncio.TimeoutError:
                record["status"], record["error"] = "error", "Inference timeout; no retry or fallback"
            except Exception as exc:
                # Unknown exception details can contain transport headers/URLs.
                record["status"], record["error"] = "error", f"Inference failed ({type(exc).__name__})"
            completed = self._now()
            record.update(response_completed_video_s=completed,
                          api_latency_ms=(completed - begin) * 1000,
                          snapshot_age_ms=(completed - cutoff) * 1000)
            if result is not None:
                if not self._valid_response(result, snapshot):
                    record["status"], record["error"] = "invalid", "Response violated action/evidence/comment contract"
                else:
                    record.update({k: result[k] for k in (
                        "action", "event", "comment", "evidence_frame_ids", "provider", "model",
                        "decision_ms", "generation_ms", "usage", "model_calls") if k in result})
                    if completed >= media.duration_s:
                        record["status"] = "after_end"
                    elif completed - cutoff > cfg.max_snapshot_age_s:
                        record["status"] = "expired"
                    elif record["action"] == "WAIT":
                        record["status"] = "wait"
                    elif self.comments and completed - self.comments[-1]["displayed_video_s"] < cfg.cooldown_s:
                        record["status"] = "cooldown"
                    elif re.sub(r"\s+", "", record["comment"]).casefold() in {
                        re.sub(r"\s+", "", c["comment"]).casefold() for c in self.comments[-8:]
                    }:
                        record["status"] = "duplicate"
                    else:
                        # No backdating. Render from the first output frame at or
                        # after this real publish time (quantized by render fps).
                        shown = self._now()
                        if shown >= media.duration_s:
                            record["status"] = "after_end"
                        else:
                            record["status"] = "displayed"
                            record["displayed_video_s"] = shown
                            record["snapshot_to_display_ms"] = (shown - cutoff) * 1000
                            self.comments.append({"comment": record["comment"], "displayed_video_s": shown})
            self._log(record, log)

    async def run(self, media: ClipMedia, provider) -> dict:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if (self.run_dir / "events.jsonl").exists() or (self.run_dir / "run.json").exists():
            raise ValueError("Run already exists; use a new output directory")
        if self._started:
            raise ValueError("ReplayEngine instances can only run once")
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        last_trigger = -math.inf
        last_periodic = -math.inf
        last_thumb = None
        audio_baseline = 0.005
        self._started = time.monotonic()
        with (self.run_dir / "events.jsonl").open("w", encoding="utf-8") as log:
            worker = asyncio.create_task(self._consume(queue, media, provider, log))
            try:
                for frame in media.frames:
                    await self._at(frame.video_s)
                    if self._now() >= media.duration_s:
                        break
                    thumb = media.thumbnail(frame)
                    delta = float(np.mean(np.abs(thumb - last_thumb))) if last_thumb is not None else 0.0
                    last_thumb = thumb
                    rms = media.audio_rms(frame.video_s)
                    spike = rms / max(audio_baseline, 0.005)
                    # Baseline contains only preceding windows, then is updated.
                    audio_baseline = 0.9 * audio_baseline + 0.1 * rms
                    trigger = None
                    if frame.video_s - last_trigger >= self.config.min_trigger_gap_s:
                        if rms >= self.config.audio_min_rms and spike >= self.config.audio_spike_threshold:
                            trigger = "audio"
                        elif delta >= self.config.visual_threshold:
                            trigger = "visual"
                        elif frame.video_s - last_periodic >= self.config.observe_interval_s:
                            trigger = "periodic"
                    if trigger is None:
                        continue
                    signals = {"visual_delta": delta, "audio_rms": rms, "audio_spike": spike}
                    snapshot = self._snapshot(media, frame.video_s, trigger, signals)
                    if not snapshot["frames"] and not snapshot["audio_wav"]:
                        continue
                    if queue.full():
                        queue.get_nowait()
                        self.replaced_pending += 1
                    queue.put_nowait(snapshot)
                    last_trigger = frame.video_s
                    if trigger == "periodic":
                        last_periodic = frame.video_s
                await self._at(media.duration_s)
                if queue.full():
                    queue.get_nowait()
                    self.pending_discarded_at_end += 1
                queue.put_nowait(None)
                await worker  # Finishes the in-flight request, but cannot publish after clip end.
            except BaseException:
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
                raise
        statuses = {key: sum(r["status"] == key for r in self.records) for key in (
            "displayed", "wait", "expired", "cooldown", "duplicate", "invalid", "error", "after_end")}
        observed_usage = {}
        for record in self.records:
            for key, value in record.get("usage", {}).items():
                if key.endswith("TokenCount") and isinstance(value, (int, float)):
                    observed_usage[key] = observed_usage.get(key, 0) + value
        summary = {"status_counts": statuses, "completed_records": len(self.records),
                   "replaced_pending": self.replaced_pending,
                   "pending_discarded_at_end": self.pending_discarded_at_end,
                   "inference_attempts": sum(r["call_attempted"] for r in self.records),
                   "reported_model_calls": sum(r["model_calls"] for r in self.records),
                   "model_call_count_note": "Successful responses only; failures/timeouts may also incur provider usage.",
                   "reported_usage": observed_usage,
                   "api_latency_ms": distribution([r["api_latency_ms"] for r in self.records
                                                   if r["call_attempted"] and r["action"] is not None]),
                   "snapshot_to_display_ms": distribution([r["snapshot_to_display_ms"] for r in self.records
                                                           if r["status"] == "displayed"]),
                   "event_to_display_ms": None,
                   "event_latency_note": "Unavailable without human event annotations and response matches.",
                   "wall_elapsed_s": self._now()}
        run = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
               "provider": provider.provider, "model": provider.model, "mode": self.config.mode,
               "input_video": media.metadata.get("input_video", ""), "duration_s": media.duration_s,
               "measured_realtime": True, "is_mock": provider.provider == "mock",
               "settings": asdict(self.config), "media": media.metadata, "summary": summary,
               "limitations": ["Prerecorded file at 1x; preparation/capture/stream transport excluded.",
                               "snapshot_to_display is not event-onset latency.",
                               "No humor-quality score without human review."]}
        if run["is_mock"]:
            run["limitations"].insert(0, "PIPELINE TEST / MOCK — NO AI LATENCY RESULT")
        _write_json(self.run_dir / "run.json", run)
        self._csv()
        return run

    def _csv(self) -> None:
        keys = ["request_id", "trigger", "input_cutoff_video_s", "request_started_video_s",
                "response_completed_video_s", "displayed_video_s", "api_latency_ms", "snapshot_age_ms",
                "snapshot_to_display_ms", "status", "action", "event", "comment", "error", "model_calls"]
        with (self.run_dir / "events.csv").open("w", newline="", encoding="utf-8-sig") as out:
            writer = csv.DictWriter(out, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            for record in self.records:
                row = {k: record.get(k) for k in keys}
                # Model text opened in spreadsheet software must remain text.
                for key in ("event", "comment", "error"):
                    if isinstance(row[key], str) and row[key].lstrip().startswith(("=", "+", "-", "@")):
                        row[key] = "'" + row[key]
                writer.writerow(row)


def score_matches(run_dir: str | Path, annotations_path: str, matches_path: str) -> dict:
    """Compute true event latency only from explicit, separately human matches."""
    root = Path(run_dir)
    run = json.loads((root / "run.json").read_text(encoding="utf-8"))
    annotation = json.loads(Path(annotations_path).read_text(encoding="utf-8"))
    review = json.loads(Path(matches_path).read_text(encoding="utf-8"))
    if review.get("reviewed_by_human") is not True:
        raise ValueError("Event latency requires reviewed_by_human=true and explicit human matches")
    events = {e["event_id"]: e for e in annotation["events"]}
    records = {r["request_id"]: r for r in (json.loads(line) for line in
               (root / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())}
    matched = []
    seen = set()
    for link in review["matches"]:
        request_id, event_id = link["request_id"], link["event_id"]
        if request_id in seen:
            raise ValueError("Each response can match only one event")
        seen.add(request_id)
        record, event = records[request_id], events[event_id]
        if record["status"] != "displayed":
            raise ValueError("Only actually displayed comments can be scored")
        onset = float(event["onset_s"])
        observable = float(event.get("observable_s", onset))
        end = float(event.get("valid_until_s", run["duration_s"]))
        shown = record["displayed_video_s"]
        if not all(math.isfinite(x) for x in (onset, observable, end)) or not (0 <= onset <= observable <= end <= run["duration_s"]):
            raise ValueError("Invalid event timeline")
        if observable > record["input_cutoff_video_s"] or shown < onset:
            raise ValueError("The matched event was not yet observable at the snapshot cutoff")
        matched.append({"request_id": request_id, "event_id": event_id,
                        "judgment": link.get("judgment", "unrated"),
                        "event_to_display_ms": (shown - onset) * 1000,
                        "observable_to_display_ms": (shown - observable) * 1000,
                        "within_valid_window": shown <= end})
    appropriate = [m for m in matched if m["judgment"] == "appropriate" and m["within_valid_window"]]
    score = {"schema_version": 1, "is_mock": run["is_mock"], "reviewed_by_human": True,
             "latency_for_appropriate_matches_ms": distribution([m["event_to_display_ms"] for m in appropriate]),
             "matched_reactions": matched,
             "note": "Explicit human matches only; no inferred recall/precision or automatic humor score."}
    _write_json(root / "human_review.json", score)
    return score


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Replay one video at 1x and measure actual completion timestamps")
    run.add_argument("video")
    run.add_argument("--provider", choices=["gemini", "mock"], default="gemini")
    run.add_argument("--model", default="gemini-3.5-flash-lite")
    run.add_argument("--writer-model")
    run.add_argument("--thinking-level", choices=["minimal", "low", "medium", "high"])
    run.add_argument("--mode", choices=["joint", "split"], default="joint")
    run.add_argument("--duration", type=float, default=60)
    run.add_argument("--output", default=None)
    run.add_argument("--sample-fps", type=float, default=10)
    run.add_argument("--observe-interval", type=float, default=2)
    run.add_argument("--min-trigger-gap", type=float, default=0.75)
    run.add_argument("--context-window", type=float, default=4)
    run.add_argument("--max-frames", type=int, default=6)
    run.add_argument("--cooldown", type=float, default=6)
    run.add_argument("--max-age", type=float, default=5)
    run.add_argument("--timeout", type=float, default=20)
    run.add_argument("--visual-threshold", type=float, default=0.12)
    run.add_argument("--audio-spike-threshold", type=float, default=3)
    run.add_argument("--audio-min-rms", type=float, default=0.04)
    run.add_argument("--mock-delay", type=float, default=0.2)
    run.add_argument("--font", default=None)
    run.add_argument("--no-render", action="store_true")
    score = commands.add_parser("score", help="Compute event latency from separate human annotations/matches")
    score.add_argument("run_dir")
    score.add_argument("--annotations", required=True)
    score.add_argument("--matches", required=True)
    return cli


async def run_cli(args) -> None:
    config = ReplayConfig(observe_interval_s=args.observe_interval, min_trigger_gap_s=args.min_trigger_gap,
                          context_window_s=args.context_window, max_frames=args.max_frames,
                          cooldown_s=args.cooldown, max_snapshot_age_s=args.max_age,
                          request_timeout_s=args.timeout, visual_threshold=args.visual_threshold,
                          audio_spike_threshold=args.audio_spike_threshold, audio_min_rms=args.audio_min_rms,
                          mode=args.mode)
    config.validate()
    # Validate credentials before decoding or creating a run. No silent mock.
    provider = (MockProvider(delay_s=args.mock_delay) if args.provider == "mock" else
                GeminiProvider(args.model, writer_model=args.writer_model, timeout_s=args.timeout,
                               thinking_level=args.thinking_level))
    output = Path(args.output or ("runs/" + datetime.now().strftime("%Y%m%d_%H%M%S"))).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory is not empty; choose a new --output")
    try:
        print("Preparing source samples outside the measured replay clock...", flush=True)
        media = prepare_clip(args.video, output / "media_cache", duration_s=args.duration, sample_fps=args.sample_fps)
        print(f"1x replay: {media.duration_s:.2f}s | {provider.provider}/{provider.model} | {args.mode}", flush=True)
        if args.provider == "mock":
            print("PIPELINE TEST / MOCK — NO AI LATENCY RESULT", flush=True)
        result = await ReplayEngine(config, output).run(media, provider)
    finally:
        await provider.close()
    from experiments.artifacts import render_replay, write_report
    if not args.no_render:
        print("Rendering comments at their actual display times...", flush=True)
        render_replay(str(Path(args.video).resolve()), str(output), font_path=args.font)
    write_report(str(output))
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"Results: {output}")


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "run":
            asyncio.run(run_cli(args))
        else:
            print(json.dumps(score_matches(args.run_dir, args.annotations, args.matches), ensure_ascii=False, indent=2))
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted; partial JSONL records are retained. Run is not a completed benchmark.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
