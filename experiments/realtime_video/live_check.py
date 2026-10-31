"""Explicit paid smoke test using generated scoreboards, never the user's screen."""

import asyncio
from datetime import datetime, timezone
import io
import json
import time

from PIL import Image, ImageDraw

from experiments.realtime_video.provider import DIRECTORY, Frame, RealtimeProvider, credentials


class SyntheticTestProvider(RealtimeProvider):
    """Retain only model output for this synthetic, explicitly invoked test."""
    output = None

    async def _receive(self):
        event = await super()._receive()
        if event.get("type") == "response.done":
            self.output = event.get("response", {}).get("output", [])
        return event


def scoreboard(red):
    with Image.new("RGB", (640, 360), "#15202b") as image:
        draw = ImageDraw.Draw(image)
        draw.text((80, 80), "BLUE 3", fill="#5faaff", font_size=54)
        draw.text((80, 180), f"RED {red}", fill="#ff7070", font_size=54)
        data = io.BytesIO()
        image.save(data, format="JPEG")
        return data.getvalue()


async def run():
    provider = SyntheticTestProvider(*credentials())
    report = {"model": provider.model, "source": "synthetic scoreboard only", "screen_captures": 0,
              "audio_inputs": 0, "responses": [], "status": "running"}
    path = DIRECTORY / "runs" / ("live_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")) / "report.json"
    path.parent.mkdir(parents=True)
    started = time.monotonic()
    try:
        await provider.open()
        for sequence in range(1, 5):
            await provider.push_frame(Frame(sequence, time.monotonic(), scoreboard(1 if sequence < 3 else 4)))
            await asyncio.sleep(1)
        decision, frames, elapsed = await provider.analyze("witty_friend", "점수판이 있는 방송 화면", [])
        report["responses"].append({"decision": decision, "frames": len(frames), "generation_ms": elapsed})
        report["status"] = "complete"
    except Exception as exc:
        report["status"] = "failed"
        # Avoid persisting network exception strings which can contain request metadata.
        report["error_type"] = type(exc).__name__
        if type(exc).__name__ == "RealtimeError":
            report["message"] = str(exc)
    finally:
        await provider.close()
        report["synthetic_model_output"] = provider.output
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(path)}, ensure_ascii=False))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
