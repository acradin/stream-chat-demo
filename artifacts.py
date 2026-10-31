"""Render recorded observations without moving comments back in time.

The renderer is intentionally offline: it visualizes the measured replay log,
and its encoding time is never reported as model or reaction latency.
"""

from __future__ import annotations

import html
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import BinaryIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont


MOCK_LABEL = "PIPELINE TEST / MOCK — NO AI LATENCY RESULT"
FPS = 20
WIDTH, HEIGHT = 1280, 720
SOURCE_WIDTH, SOURCE_HEIGHT = 800, 450


def _load_run(run_dir: Path) -> tuple[dict, list[dict]]:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    events = []
    with (run_dir / "events.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    return run, events


def _is_mock(run: dict, events: list[dict]) -> bool:
    return bool(run.get("is_mock") or run.get("provider") == "mock"
                or any(e.get("provider") == "mock" for e in events))


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def _visible_comments(events: list[dict], video_s: float) -> list[dict]:
    """Never backdate a comment to its input cutoff or trigger time."""
    return sorted(
        (e for e in events
         if e.get("status") == "displayed"
         and _finite(e.get("displayed_video_s"))
         and float(e["displayed_video_s"]) <= video_s),
        key=lambda event: event["displayed_video_s"],
    )


def _font_file(font_path: str | None = None) -> str:
    if font_path:
        path = Path(font_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Font file not found: {path}")
        return str(path)
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/malgun.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    # Fontconfig is optional, and this lookup never involves a shell.
    if shutil.which("fc-match"):
        result = subprocess.run(
            ["fc-match", "-f", "%{file}", "sans:lang=ko"],
            check=True, capture_output=True, text=True,
        )
        if Path(result.stdout.strip()).is_file():
            return result.stdout.strip()
    fallback = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if fallback.is_file():
        return str(fallback)
    raise RuntimeError("No usable font found. Pass --font with a .ttf/.ttc font path.")


def _missing_glyphs(text: str, font: ImageFont.FreeTypeFont) -> set[str]:
    """FreeType uses the font's .notdef mask for unsupported codepoints."""
    notdef = font.getmask(chr(0x10FFFF))
    signature = (notdef.size, bytes(notdef))
    missing = set()
    for char in set(text):
        if ord(char) > 127 and not char.isspace():
            mask = font.getmask(char)
            if (mask.size, bytes(mask)) == signature:
                missing.add(char)
    return missing


def _wrap(text: str, draw: ImageDraw.ImageDraw,
          font: ImageFont.FreeTypeFont, max_width: int, max_lines: int) -> list[str]:
    """Character wrapping also supports Korean without spaces."""
    lines, current = [], ""
    for char in text.replace("\r", ""):
        if char == "\n":
            lines.append(current.rstrip())
            current = ""
        elif current and draw.textlength(current + char, font=font) > max_width:
            split = current.rfind(" ")
            if split > 0:
                lines.append(current[:split].rstrip())
                current = (current[split + 1:] + char).lstrip()
            else:
                lines.append(current.rstrip())
                current = char.lstrip()
        else:
            current += char
    if current:
        lines.append(current.rstrip())
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and draw.textlength(lines[-1] + "...", font=font) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "..."
    return lines


def _probe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path], check=True, capture_output=True, text=True,
    )
    duration = float(json.loads(result.stdout)["format"]["duration"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Input video duration must be finite and positive.")
    return duration


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    parts, remaining = [], size
    while remaining:
        data = stream.read(remaining)
        if not data:
            break
        parts.append(data)
        remaining -= len(data)
    return b"".join(parts)


def _error_text(handle: BinaryIO) -> str:
    handle.seek(0)
    return handle.read().decode("utf-8", errors="replace")[-4000:]


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def render_replay(input_video: str, run_dir: str, output_path: str | None = None,
                  font_path: str | None = None) -> str:
    """Create an MP4 with original audio and comments at display timestamps.

    A 20 fps rendering can show a comment up to 50 ms after its exact log time;
    it can never show it before that time. Metrics retain the exact log values.
    """
    directory = Path(run_dir).resolve()
    source = Path(input_video).expanduser().resolve()
    run, events = _load_run(directory)
    output = Path(output_path).expanduser().resolve() if output_path else directory / "replay.mp4"
    if output == source:
        raise ValueError("Output replay must not overwrite the input video.")
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = min(_probe_duration(str(source)), float(run["duration_s"]))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("run.duration_s must be finite and positive.")
    font_file = _font_file(font_path)
    fonts = {size: ImageFont.truetype(font_file, size=size) for size in (14, 16, 18, 22, 28)}
    mock = _is_mock(run, events)
    missing = set().union(*(_missing_glyphs(str(e.get("comment", "")), fonts[22]) for e in events))
    warnings = []
    if missing:
        warnings.append(
            "The selected video font lacks some comment glyphs (including Korean if present). "
            "Affected comments are explicitly replaced in the MP4; report.html and events.jsonl "
            "retain the exact Unicode text. Re-render with --font pointing to Noto Sans CJK KR "
            "or Windows malgun.ttf."
        )
    # At most a single source frame is resident; long source files are not loaded into RAM.
    with tempfile.TemporaryDirectory(prefix="render-", dir=str(output.parent)) as temp_dir:
        temporary = Path(temp_dir) / "replay.mp4"
        with tempfile.TemporaryFile() as decode_log, tempfile.TemporaryFile() as encode_log:
            decoder = subprocess.Popen(
                ["ffmpeg", "-v", "error", "-nostdin", "-i", str(source), "-an",
                 "-t", f"{duration:.6f}", "-vf",
                 f"fps={FPS},scale={SOURCE_WIDTH}:{SOURCE_HEIGHT}:force_original_aspect_ratio=decrease,"
                 f"pad={SOURCE_WIDTH}:{SOURCE_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,setsar=1",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                stdout=subprocess.PIPE, stderr=decode_log,
            )
            encoder = None
            try:
                encoder = subprocess.Popen(
                    ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                     "-s:v", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "pipe:0",
                     "-i", str(source), "-map", "0:v:0", "-map", "1:a:0?",
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                     "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                     "-t", f"{duration:.6f}", "-movflags", "+faststart", str(temporary)],
                    stdin=subprocess.PIPE, stderr=encode_log,
                )
                frame_index = 0
                assert decoder.stdout is not None and encoder.stdin is not None
                while True:
                    pixels = _read_exact(decoder.stdout, SOURCE_WIDTH * SOURCE_HEIGHT * 3)
                    if not pixels:
                        break
                    if len(pixels) != SOURCE_WIDTH * SOURCE_HEIGHT * 3:
                        raise RuntimeError("ffmpeg returned a partial decoded video frame.")
                    video_s = frame_index / FPS
                    canvas = Image.new("RGB", (WIDTH, HEIGHT), "#0c1220")
                    draw = ImageDraw.Draw(canvas)
                    draw.text((32, 24), "STREAM REPLAY LAB", fill="#f5f7ff", font=fonts[28])
                    draw.text((850, 32), f"{video_s:05.2f}s / {duration:05.2f}s", fill="#9faecc", font=fonts[18])
                    if mock:
                        draw.rounded_rectangle((32, 76, 1248, 117), radius=8, fill="#613c12")
                        draw.text((48, 85), MOCK_LABEL, fill="#ffdb92", font=fonts[18])
                    else:
                        draw.text((32, 87), "Recorded model run | comments follow actual display timestamps",
                                  fill="#8bb8ff", font=fonts[18])
                    canvas.paste(Image.frombytes("RGB", (SOURCE_WIDTH, SOURCE_HEIGHT), pixels), (32, 140))
                    draw.rounded_rectangle((856, 140, 1248, 674), radius=12, fill="#151f31")
                    draw.text((878, 158), "AI CHAT / OBSERVED OUTPUT", fill="#9fb6da", font=fonts[16])
                    visible = _visible_comments(events, video_s)
                    if not visible:
                        draw.text((879, 223), "Waiting for a displayed comment...", fill="#8393ae", font=fonts[16])
                        draw.text((879, 252), "WAIT decisions are kept in the log.", fill="#8393ae", font=fonts[16])
                    for slot, event in enumerate(visible[-3:]):
                        y = 201 + slot * 145
                        draw.rounded_rectangle((873, y, 1231, y + 131), radius=8, fill="#213049")
                        badge = "MOCK BOT" if mock else "AI BOT"
                        draw.text((887, y + 10), f"{badge}  ·  {event['displayed_video_s']:.2f}s",
                                  fill="#8ed8cb", font=fonts[14])
                        comment = str(event.get("comment", ""))
                        if any(char in missing for char in comment):
                            comment = "[Font missing] Read exact comment in report.html."
                        for line_number, line in enumerate(_wrap(comment, draw, fonts[22], 326, 3)):
                            draw.text((887, y + 34 + line_number * 27), line, fill="#f1f5fc", font=fonts[22])
                    draw.rounded_rectangle((32, 610, 832, 618), radius=4, fill="#25314a")
                    progress = min(1, video_s / duration)
                    if progress > 0:
                        draw.rounded_rectangle((32, 610, 32 + 800 * progress, 618), radius=4, fill="#6eb6ff")
                    completed = [e for e in events if _finite(e.get("response_completed_video_s"))
                                 and e["response_completed_video_s"] <= video_s]
                    latest = max(completed, key=lambda e: e["response_completed_video_s"], default=None)
                    label = f"Displayed comments: {len(visible)}"
                    if latest:
                        label += f"   |   Latest result: {latest.get('action', '?')} / {latest.get('status', '?')}"
                    draw.text((32, 634), label, fill="#c2cde0", font=fonts[16])
                    footer = "20 fps visualization: text appears on the first frame at/after its logged display time."
                    if missing:
                        footer = "FONT WARNING: some characters are missing; report.html preserves every original comment."
                    draw.text((32, 687), footer, fill="#ffcc86" if missing else "#8192b0", font=fonts[14])
                    encoder.stdin.write(canvas.tobytes())
                    frame_index += 1
                decoder.stdout.close()
                encoder.stdin.close()
                decode_return = decoder.wait()
                encode_return = encoder.wait()
                if decode_return:
                    raise RuntimeError(f"Video decoding failed: {_error_text(decode_log)}")
                if encode_return:
                    raise RuntimeError(f"Replay encoding failed: {_error_text(encode_log)}")
                if frame_index == 0:
                    raise RuntimeError("No frames decoded from the source video.")
            except BaseException as exc:
                for process in (decoder, encoder):
                    if process is not None and process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                if isinstance(exc, BrokenPipeError):
                    raise RuntimeError(f"Replay encoder stopped: {_error_text(encode_log)}") from exc
                raise
        os.replace(temporary, output)
    _atomic_json(directory / "render.json", {
        "output_path": str(output), "fps": FPS, "duration_s": duration,
        "font_path": font_file, "font_warning": bool(missing), "warnings": warnings,
        "display_quantization_max_ms": 1000 / FPS,
        "is_mock": mock,
    })
    return str(output)


def _number(value: object, decimals: int = 1) -> str:
    return f"{float(value):.{decimals}f}" if _finite(value) else "—"


def write_report(run_dir: str) -> str:
    """Write a local static audit report, preserving original Unicode strings."""
    directory = Path(run_dir).resolve()
    run, events = _load_run(directory)
    render_file = directory / "render.json"
    render = json.loads(render_file.read_text(encoding="utf-8")) if render_file.is_file() else {}
    mock = _is_mock(run, events)
    escape = lambda value: html.escape(str(value), quote=True)
    summary = run.get("summary", {})
    status_counts: dict[str, int] = dict(summary.get("status_counts", {}))
    if not status_counts:
        for event in events:
            status = str(event.get("status", "unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1
    metric_rows = []
    for key, label in [
        ("api_latency_ms", "Request start → response completion (api_latency_ms)"),
        ("snapshot_age_ms", "Input cutoff → response completion (snapshot_age_ms)"),
        ("snapshot_to_display_ms", "Input cutoff → actual display (snapshot_to_display_ms)"),
    ]:
        # Prefer the runner's distributions so report and run.json use the same
        # inclusion criteria (e.g. unattempted, expired requests are excluded).
        distribution = summary.get(key)
        if not isinstance(distribution, dict):
            values = [float(e[key]) for e in events
                      if _finite(e.get(key)) and e.get("status") != "error"
                      and e.get("call_attempted", True)
                      and (key != "snapshot_to_display_ms" or e.get("status") == "displayed")]
            if not values:
                continue
            p50, p95 = np.percentile(values, [50, 95])
            distribution = {"n": len(values), "p50": p50, "p95": p95, "max": max(values)}
        metric_rows.append(f"<tr><th>{label}</th><td>{escape(distribution.get('n', 0))}</td>"
                           f"<td>{_number(distribution.get('p50'))} ms</td>"
                           f"<td>{_number(distribution.get('p95'))} ms</td>"
                           f"<td>{_number(distribution.get('max'))} ms</td></tr>")
    video_markup = "<p>Replay MP4 has not been rendered.</p>"
    replay_path = Path(render.get("output_path", directory / "replay.mp4"))
    if replay_path.is_file():
        from urllib.parse import quote
        relative_path = os.path.relpath(replay_path, directory).replace(os.sep, "/")
        video_markup = (f'<video controls preload="metadata" src="{escape(quote(relative_path, safe="/"))}"></video>'
                        '<p class="muted">The MP4 is a local companion file. Keep it beside this report when sharing.</p>')
    rows = []
    for event in events:
        rows.append("<tr>" + "".join(f"<td>{value}</td>" for value in [
            escape(event.get("request_id", "")),
            _number(event.get("input_cutoff_video_s"), 3),
            _number(event.get("response_completed_video_s"), 3),
            _number(event.get("displayed_video_s"), 3),
            escape(event.get("status", "")),
            _number(event.get("api_latency_ms")),
            _number(event.get("snapshot_age_ms")),
            _number(event.get("snapshot_to_display_ms")),
            escape(event.get("event", "")),
            escape(event.get("comment", "")),
            escape(event.get("error") or ""),
        ]) + "</tr>")
    banner = (f'<div class="banner">{MOCK_LABEL}<br><small>Deterministic simulated responses. '
              'These measurements validate replay scheduling and rendering only; they do not '
              'measure AI speed, understanding, or humor.</small></div>') if mock else ""
    warning_markup = "".join(f'<p class="warning">{escape(w)}</p>' for w in render.get("warnings", []))
    timing_note = ("The source was replayed at wall-clock speed (1×). Input preprocessing and offline "
                   "MP4 rendering are outside the measured interval; camera/screen capture overhead "
                   "is not included.") if run.get("measured_realtime") else (
                   "This run is not marked as a measured 1× real-time replay. Do not interpret its "
                   "video timestamps as a live latency benchmark.")
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stream replay experiment</title><style>
:root{{color-scheme:dark}}body{{margin:0;background:#0c1220;color:#e8edf8;font:16px/1.6 system-ui,'Malgun Gothic','Noto Sans CJK KR',sans-serif}}
main{{max-width:1180px;margin:auto;padding:32px}}h1{{margin-bottom:6px}}h2{{margin-top:32px}}
.muted{{color:#9caecb}}.banner{{padding:18px;background:#613c12;color:#ffdb92;border-radius:12px;margin:20px 0;font-weight:700}}
.banner small{{font-weight:400}}.warning{{padding:14px;border:1px solid #bc873e;background:#332919;border-radius:8px}}
video{{width:100%;max-height:720px;background:#000;border-radius:12px}}table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{padding:10px;text-align:left;border-bottom:1px solid #2a3850;vertical-align:top}}th{{color:#a8c5ed}}td{{overflow-wrap:anywhere}}
.scroll{{overflow-x:auto}}code{{background:#202d42;padding:2px 5px;border-radius:4px}}dl{{display:grid;grid-template-columns:160px 1fr;gap:8px}}dt{{color:#9caecb}}dd{{margin:0}}
</style></head><body><main>
<h1>Stream replay experiment</h1><p class="muted">Local experiment report · timestamps come from events.jsonl</p>
{banner}{warning_markup}
<dl><dt>Provider / model</dt><dd>{escape(run.get('provider', ''))} / {escape(run.get('model', ''))}</dd>
<dt>Mode</dt><dd>{escape(run.get('mode', ''))}</dd>
<dt>Input</dt><dd>{escape(run.get('input_video', ''))}</dd>
<dt>Replay duration</dt><dd>{_number(run.get('duration_s'), 3)} s</dd>
<dt>Result counts</dt><dd>{escape(', '.join(f'{k}: {v}' for k,v in sorted(status_counts.items())) or 'No completed requests')}</dd></dl>
{video_markup}
<h2>{'Pipeline timings (mock)' if mock else 'Measured request timings'}</h2>
<p>{timing_note}</p>
<div class="scroll"><table><thead><tr><th>Exact metric definition</th><th>Samples</th><th>p50</th><th>p95</th><th>Maximum</th></tr></thead>
<tbody>{''.join(metric_rows) or '<tr><td colspan="5">No completed timing samples.</td></tr>'}</tbody></table></div>
<p><code>snapshot_age_ms</code> is input-cutoff-to-response time. It is <strong>not event-onset-to-chat latency</strong>.
<code>snapshot_to_display_ms</code> measures input cutoff to the actual logged display event, including the small local publication step.
No human-matched event onset annotations are included in these summary metrics. Neither snapshot metric identifies true event onset.
The MP4 samples that timestamp at {render.get('fps', FPS)} fps, so text appears on the first frame at or after the logged time (up to {_number(render.get('display_quantization_max_ms', 1000/FPS), 0)} ms later).</p>
<p>WAIT, expired, cooldown, duplicate, invalid, error and after_end results do not become visible chat. All completed results remain below for auditing.
Unicode text is preserved in this report and the JSON logs. Browser font availability controls how it is displayed.</p>
<h2>Recorded results</h2><div class="scroll"><table><thead><tr>
<th>Request</th><th>Input cutoff (s)</th><th>Response complete (s)</th><th>Actually displayed (s)</th><th>Status</th>
<th>api_latency_ms</th><th>snapshot_age_ms</th><th>snapshot_to_display_ms</th><th>Event</th><th>Exact comment</th><th>Error</th>
</tr></thead><tbody>{''.join(rows) or '<tr><td colspan="11">No results.</td></tr>'}</tbody></table></div>
<h2>Configuration</h2><pre>{escape(json.dumps(run.get('settings', {}), ensure_ascii=False, indent=2))}</pre>
</main></body></html>"""
    output = directory / "report.html"
    temporary = directory / "report.html.tmp"
    temporary.write_text(document, encoding="utf-8")
    os.replace(temporary, output)
    return str(output)
