"""Generate an original synthetic clip for scheduling tests, not humor evaluation."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from artifacts import _font_file


def make_fixture(output: str, duration: float = 18.0) -> str:
    if not math.isfinite(duration) or not 1 <= duration <= 300:
        raise ValueError("Fixture duration must be between 1 and 300 seconds.")
    target = Path(output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    width, height, fps, sample_rate = 640, 360, 20, 16000
    font_file = _font_file()
    fonts = {size: ImageFont.truetype(font_file, size=size) for size in (14, 18, 26, 36)}
    phases = [((25, 42, 68), "READY", "Move the shape to the target"),
              ((136, 44, 52), "TRY AGAIN", "The target moved. Oops."),
              ((24, 92, 70), "SUCCESS", "A very geometric victory")]
    with tempfile.TemporaryDirectory(prefix="fixture-", dir=str(target.parent)) as temporary_dir:
        temporary = Path(temporary_dir)
        audio_path = temporary / "tones.wav"
        audio = np.zeros(round(duration * sample_rate), dtype=np.float32)
        for index, moment in enumerate([duration / 3, 2 * duration / 3]):
            length = min(round(0.24 * sample_rate), len(audio) - round(moment * sample_rate))
            time = np.arange(length) / sample_rate
            envelope = np.sin(np.linspace(0, np.pi, length)) ** 2
            tone = 0.55 * np.sin(2 * np.pi * (660 if index == 0 else 880) * time) * envelope
            start = round(moment * sample_rate)
            audio[start:start + length] += tone
        with wave.open(str(audio_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes((audio * 32767).astype("<i2").tobytes())
        encoded = temporary / "fixture.mp4"
        with tempfile.TemporaryFile() as error_log:
            process = subprocess.Popen(
                ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                 "-s:v", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0",
                 "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "96k", "-t", str(duration), "-movflags", "+faststart", str(encoded)],
                stdin=subprocess.PIPE, stderr=error_log,
            )
            try:
                assert process.stdin is not None
                for frame_index in range(math.ceil(duration * fps)):
                    moment = frame_index / fps
                    phase = min(2, int(moment / (duration / 3)))
                    background, headline, subtitle = phases[phase]
                    frame = Image.new("RGB", (width, height), background)
                    draw = ImageDraw.Draw(frame)
                    draw.rectangle((0, 0, width, 40), fill="#101624")
                    draw.text((18, 11), "SYNTHETIC TEST / NO REAL BROADCASTER", font=fonts[14], fill="#ffdc99")
                    draw.text((24, 61), headline, font=fonts[36], fill="#ffffff")
                    draw.text((24, 108), subtitle, font=fonts[18], fill="#e0e7f1")
                    # Original geometric animation: no borrowed footage or real voice.
                    x = 55 + int((moment * 82) % 505)
                    y = 209 + int(36 * math.sin(moment * 2.4))
                    draw.rounded_rectangle((494, 176, 598, 282), radius=16, outline="#f3d68a", width=5)
                    if phase == 2:
                        x, y = 545, 228 + int(8 * math.sin(moment * 5))
                    draw.ellipse((x - 23, y - 23, x + 23, y + 23), fill="#e5f0ff", outline="#93b9f2", width=3)
                    draw.ellipse((x - 10, y - 7, x - 6, y - 3), fill="#293d60")
                    draw.ellipse((x + 6, y - 7, x + 10, y - 3), fill="#293d60")
                    draw.arc((x - 9, y - 5, x + 9, y + 12), start=0, end=180, fill="#293d60", width=2)
                    draw.rectangle((0, 310, width, height), fill="#101624")
                    draw.text((18, 320), f"{moment:05.2f}s   SCENE {phase + 1}/3   AUDIO: SYNTHETIC TONES", font=fonts[14], fill="#bdcce2")
                    process.stdin.write(frame.tobytes())
                process.stdin.close()
                return_code = process.wait()
                if return_code:
                    error_log.seek(0)
                    raise RuntimeError("Fixture encoding failed: " + error_log.read().decode(errors="replace")[-4000:])
            except BaseException as exc:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                if isinstance(exc, BrokenPipeError):
                    error_log.seek(0)
                    raise RuntimeError("Fixture encoder stopped: " + error_log.read().decode(errors="replace")[-4000:]) from exc
                raise
        os.replace(encoded, target)
    annotation_path = target.with_suffix(".events.json")
    annotations = {
        "synthetic": True,
        "purpose": "Pipeline scheduling checks only. Never feed this annotation file into model requests.",
        "duration_s": duration,
        "events": [
            {"video_s": duration / 3, "event": "Synthetic blue-to-red scene change and 660 Hz tone"},
            {"video_s": 2 * duration / 3, "event": "Synthetic red-to-green scene change and 880 Hz tone"},
        ],
    }
    annotation_tmp = annotation_path.with_suffix(annotation_path.suffix + ".tmp")
    annotation_tmp.write_text(json.dumps(annotations, indent=2), encoding="utf-8")
    os.replace(annotation_tmp, annotation_path)
    return str(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="samples/fixture.mp4")
    parser.add_argument("--duration", type=float, default=18.0)
    args = parser.parse_args()
    print(make_fixture(args.output, args.duration))


if __name__ == "__main__":
    main()
