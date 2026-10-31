"""Decode a clip once, then expose only media available at the replay clock.

Preparation is deliberately outside the timed run. This experiment measures
scheduled observation -> model response -> displayed chat, not live capture or
stream transport. Original presentation timestamps are retained; the fps filter
is NOT used because nearest-frame resampling can expose future source frames.
"""

from __future__ import annotations

import bisect
import io
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import time
import wave
from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Frame:
    frame_id: str
    video_s: float
    path: Path


class ClipMedia:
    def __init__(self, frames: list[Frame], *, duration_s: float,
                 audio: np.ndarray | None = None, sample_rate: int = 16000,
                 metadata: dict | None = None):
        if not frames or not math.isfinite(duration_s) or duration_s <= 0:
            raise ValueError("A clip needs video frames and a positive duration")
        self.frames = sorted(frames, key=lambda f: f.video_s)
        self.times = [f.video_s for f in self.frames]
        if self.times[0] < 0 or self.times[-1] >= duration_s + 1e-6:
            raise ValueError("Frame timestamps must belong to the replay interval")
        self.duration_s = float(duration_s)
        self.audio = audio
        self.sample_rate = sample_rate
        self.metadata = metadata or {}

    def frames_until(self, cutoff_s: float, window_s: float, max_frames: int) -> list[dict]:
        """Select past frames uniformly, always including the newest available."""
        if cutoff_s < 0 or window_s <= 0 or max_frames < 1:
            raise ValueError("Invalid frame window")
        right = bisect.bisect_right(self.times, cutoff_s)
        left = bisect.bisect_left(self.times, max(0.0, cutoff_s - window_s))
        pool = self.frames[left:right]
        if not pool:
            return []
        if len(pool) > max_frames:
            indices = ([len(pool) - 1] if max_frames == 1 else
                       np.linspace(0, len(pool) - 1, max_frames, dtype=int).tolist())
            pool = [pool[i] for i in indices]
        return [{"frame_id": f.frame_id, "video_s": f.video_s,
                 "jpeg": f.path.read_bytes()} for f in pool]

    def audio_window(self, cutoff_s: float, window_s: float) -> tuple[bytes | None, float | None, float | None]:
        """The last included sample ENDS by cutoff; never round into the future."""
        if cutoff_s < 0 or window_s <= 0:
            raise ValueError("Invalid audio window")
        if self.audio is None:
            return None, None, None
        end = min(len(self.audio), math.floor(cutoff_s * self.sample_rate))
        start = max(0, end - math.floor(window_s * self.sample_rate))
        if end <= start:
            return None, None, None
        buf = io.BytesIO()
        with wave.open(buf, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(self.sample_rate)
            out.writeframes(np.asarray(self.audio[start:end], dtype="<i2").tobytes())
        return buf.getvalue(), start / self.sample_rate, end / self.sample_rate

    def audio_rms(self, cutoff_s: float, window_s: float = 0.2) -> float:
        if self.audio is None:
            return 0.0
        end = min(len(self.audio), math.floor(cutoff_s * self.sample_rate))
        start = max(0, end - math.floor(window_s * self.sample_rate))
        if end <= start:
            return 0.0
        values = self.audio[start:end].astype(np.float32) / 32768.0
        return float(np.sqrt(np.mean(values * values)))

    @staticmethod
    def thumbnail(frame: Frame) -> np.ndarray:
        with Image.open(frame.path) as im:
            return np.asarray(im.convert("L").resize((64, 36)), dtype=np.float32) / 255.0


def _run(args: list[str], *, timeout: float = 300) -> subprocess.CompletedProcess:
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} failed: {result.stderr[-2000:]}")
    return result


def prepare_clip(video_path: str | Path, cache_dir: str | Path, *, duration_s: float = 60,
                 sample_fps: float = 10, width: int = 640) -> ClipMedia:
    """Pre-extract timestamped source samples; no semantic analysis occurs here."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("Install FFmpeg and put both ffmpeg and ffprobe on PATH")
    if not (0 < sample_fps <= 30) or not math.isfinite(duration_s) or duration_s <= 0 or width < 64:
        raise ValueError("Expected fps in (0,30], positive duration, and width >=64")
    video = Path(video_path).resolve()
    if not video.is_file():
        raise FileNotFoundError(f"Video file not found: {video}")
    started = time.monotonic()
    info = json.loads(_run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                            "-of", "json", str(video)]).stdout)
    streams = info.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")]
    if not videos:
        raise ValueError("Input has no video stream")
    raw_duration = info.get("format", {}).get("duration", videos[0].get("duration"))
    try:
        source_duration = float(raw_duration)
    except (TypeError, ValueError):
        raise ValueError("Input has no finite duration; provide a prerecorded file") from None
    if not math.isfinite(source_duration) or source_duration <= 0:
        raise ValueError("Input duration must be finite and positive")
    duration = min(float(duration_s), source_duration)
    cache = Path(cache_dir).resolve()
    frame_dir = cache / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    if any(frame_dir.iterdir()):
        raise ValueError("Media cache must be empty; use a new output directory")
    # copyts/start_at_zero preserve inter-stream offsets while moving the file
    # presentation origin to zero. Never independently reset each track's PTS.
    vf = (f"trim=start=0:end={duration:.9f},"
          f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{1/sample_fps-1e-7:.9f})',"
          f"scale='min({width},iw)':-2,showinfo")
    result = _run(["ffmpeg", "-hide_banner", "-nostdin", "-copyts", "-start_at_zero",
                   "-i", str(video), "-map", f"0:{videos[0]['index']}", "-an", "-vf", vf,
                   "-fps_mode", "vfr", "-q:v", "3", str(frame_dir / "%06d.jpg")])
    stamps = [float(m.group(1)) for m in re.finditer(
        r"\[Parsed_showinfo_[^\]]+\]\s+n:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([\d.eE+\-]+)", result.stderr)]
    paths = sorted(frame_dir.glob("*.jpg"))
    if len(stamps) != len(paths) or not paths:
        raise RuntimeError(f"Could not match FFmpeg source timestamps ({len(stamps)}) to frames ({len(paths)})")
    if stamps[0] > 1e-6:
        # The offline renderer's rawvideo stream starts at zero. Reject unusual
        # delayed-video inputs instead of silently shifting the visible event.
        raise ValueError("This prototype requires the first video frame at file timeline zero; normalize initial stream offsets before replay")
    frames = [Frame(f"f{i:06d}", stamp, path) for i, (stamp, path) in enumerate(zip(stamps, paths))]
    audio = None
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if audio_stream:
        audio_path = cache / "audio.wav"
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-copyts", "-start_at_zero",
              "-i", str(video), "-map", f"0:{audio_stream['index']}", "-vn",
              "-af", f"atrim=start=0:end={duration:.9f},aresample=16000:async=1:first_pts=0",
              "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio_path)])
        with wave.open(str(audio_path), "rb") as src:
            audio = np.frombuffer(src.readframes(src.getnframes()), dtype="<i2").copy()
    return ClipMedia(frames, duration_s=duration, audio=audio, metadata={
        "input_video": str(video), "source_duration_s": source_duration,
        "source_width": videos[0].get("width"), "source_height": videos[0].get("height"),
        "sampled_frames": len(frames), "sample_fps_target": sample_fps,
        "preparation_ms": round((time.monotonic() - started) * 1000, 3),
        "preparation_included_in_latency": False,
        "timestamp_policy": "source PTS, file presentation origin normalized to zero; no fps resampling",
        "audio_sample_rate": 16000 if audio is not None else None,
        "audio_available": audio is not None,
    })
