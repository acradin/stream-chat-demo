"""Local button-triggered chat experiment. No video/audio enters the model.

Run: python -m apps.web --provider mock
Open the printed localhost URL, optionally choose a local clip, then press the
button. A browser acknowledgement supplies button-to-DOM latency; the server
cannot infer that metric from its own clock or from a media timestamp.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
import secrets
import sys
import time
from urllib.parse import urlsplit

from aiohttp import web

from backend.manual_provider import DEFAULT_PERSONA, PERSONAS, GeminiManualProvider, MockManualProvider
from backend.providers import ProviderError, InvalidResponseError


def _number(value, name: str, *, optional: bool = False):
    if optional and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return float(value)


def _text(value, name: str, limit: int, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str) or len(value) > limit or (not allow_empty and not value.strip()):
        raise ValueError(f"Invalid {name}")
    return value.strip()


def _stats(values: list[float]) -> dict:
    ordered = sorted(values)
    def percentile(p):
        if not ordered:
            return None
        index = (len(ordered) - 1) * p
        lo = math.floor(index)
        hi = math.ceil(index)
        return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo), 3)
    return {"n": len(values), "p50": percentile(.5), "p95": percentile(.95),
            "max": round(max(values), 3) if values else None}


class ManualSession:
    def __init__(self, provider, run_dir: str | Path, *, cooldown_s: float = 1,
                 max_age_s: float = 8, timeout_s: float = 20, persist: bool = True):
        self.provider = provider
        self.cooldown_s = _number(cooldown_s, "cooldown_s")
        self.max_age_s = _number(max_age_s, "max_age_s")
        self.timeout_s = _number(timeout_s, "timeout_s")
        if not max_age_s or not timeout_s:
            raise ValueError("max_age_s and timeout_s must be positive")
        self.directory = Path(run_dir).resolve()
        self.persist = persist
        if persist and self.directory.exists() and any(self.directory.iterdir()):
            raise ValueError("Output directory is not empty; choose a new --output")
        if persist:
            self.directory.mkdir(parents=True, exist_ok=True)
        self.session_token = secrets.token_urlsafe(32)
        self.started = time.monotonic()
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.records: dict[str, dict] = {}
        self.client_requests: dict[str, str] = {}
        self.lock = asyncio.Lock()
        self.last_accepted = -math.inf
        self.rejections = {"busy": 0, "cooldown": 0}
        self._persist()

    def config(self) -> dict:
        return {"provider": self.provider.provider, "model": self.provider.model,
                "is_mock": self.provider.provider == "mock", "session_token": self.session_token,
                "cooldown_s": self.cooldown_s, "max_age_s": self.max_age_s,
                "default_persona": DEFAULT_PERSONA,
                "personas": [{"id": key, "name": value["name"], "description": value["description"]}
                             for key, value in PERSONAS.items()]}

    @staticmethod
    def _validate_trigger(payload: dict) -> dict:
        required = {"client_request_id", "persona", "channel_context",
                    "clicked_video_s", "video_session_id"}
        if not isinstance(payload, dict) or set(payload) != required:
            raise ValueError("Trigger accepts only the documented text fields and timing metadata; no media")
        client_id = _text(payload["client_request_id"], "client_request_id", 128, allow_empty=False)
        persona = payload["persona"]
        if not isinstance(persona, str) or persona not in PERSONAS:
            raise ValueError("Unknown persona")
        video_id = payload["video_session_id"]
        if video_id is not None:
            video_id = _text(video_id, "video_session_id", 128, allow_empty=False)
        video_s = _number(payload["clicked_video_s"], "clicked_video_s", optional=True)
        if (video_s is None) != (video_id is None):
            raise ValueError("Video time and video session ID must be provided together")
        return {"client_request_id": client_id, "persona": persona,
                "channel_context": _text(payload["channel_context"], "channel_context", 1000),
                "clicked_video_s": video_s, "video_session_id": video_id}

    @staticmethod
    def _response(record: dict) -> dict:
        return {key: record.get(key) for key in
                ("status", "request_id", "comment", "api_latency_ms", "error")}

    async def trigger(self, payload: dict) -> dict:
        data = self._validate_trigger(payload)
        client_id = data["client_request_id"]
        if client_id in self.client_requests:
            existing = self.records[self.client_requests[client_id]]
            if existing["status"] == "ready":
                return self._response(existing)
            return {"status": "busy" if existing["status"] == "generating" else "duplicate",
                    "request_id": existing["request_id"], "comment": ""}
        if self.lock.locked():
            self.rejections["busy"] += 1
            self._persist()
            return {"status": "busy", "request_id": None, "error": "A chat is already being generated; no request was queued"}
        since = time.monotonic() - self.last_accepted
        if since < self.cooldown_s:
            self.rejections["cooldown"] += 1
            self._persist()
            return {"status": "cooldown", "request_id": None, "retry_after_s": self.cooldown_s - since}
        async with self.lock:
            self.last_accepted = time.monotonic()
            request_id = f"m{len(self.records) + 1:06d}"
            recent = [r["comment"] for r in self.records.values() if r["status"] == "displayed"][-8:]
            # Only these human-supplied text fields enter the model. Video time,
            # filename, local URL and media bytes are NEVER forwarded.
            context = {"request_id": request_id, "persona": data["persona"],
                       "channel_context": data["channel_context"],
                       "recent_comments": recent}
            record = {"request_id": request_id, **data, "status": "generating", "comment": "",
                      "provider": self.provider.provider, "model": self.provider.model,
                      "received_session_s": self.last_accepted - self.started,
                      "response_completed_session_s": None, "api_latency_ms": None,
                      "generation_ms": None, "button_to_display_ms": None,
                      "displayed_video_s": None, "client_acknowledged": False,
                      "client_display_basis": "browser performance.now() to DOM insertion; not physical paint",
                      "model_calls": 0, "usage": {}, "error": None, "discard_reason": None}
            self.records[request_id] = record
            self.client_requests[client_id] = request_id
            self._persist()
            begin = time.monotonic()
            try:
                result = await asyncio.wait_for(self.provider.generate(context), self.timeout_s)
                comment = result.get("comment") if isinstance(result, dict) else None
                if not isinstance(comment, str) or not comment.strip() or len(comment) > 100 or "\n" in comment or "\r" in comment:
                    raise InvalidResponseError("Chat must be a nonempty single line of at most 100 characters")
                record.update(comment=comment.strip(), generation_ms=result.get("generation_ms"),
                              usage=result.get("usage", {}), model_calls=result.get("model_calls", 0))
                elapsed = time.monotonic() - self.last_accepted
                if elapsed > self.max_age_s:
                    record["status"] = "expired"
                elif any("".join(comment.split()).casefold() == "".join(old.split()).casefold() for old in recent):
                    record["status"] = "duplicate"
                else:
                    # Ready is NOT displayed. Client must confirm its DOM update.
                    record["status"] = "ready"
            except asyncio.TimeoutError:
                record.update(status="error", error="Generation timed out; no retry or fallback")
            except (ProviderError, InvalidResponseError) as exc:
                record.update(status="error", error=str(exc))
            except Exception as exc:
                record.update(status="error", error=f"Generation failed ({type(exc).__name__})")
            record["api_latency_ms"] = (time.monotonic() - begin) * 1000
            record["response_completed_session_s"] = time.monotonic() - self.started
            self._persist()
            return self._response(record)

    def acknowledge(self, payload: dict) -> dict:
        fields = {"request_id", "button_to_display_ms", "displayed_video_s", "video_session_id", "status", "reason"}
        if not isinstance(payload, dict) or set(payload) != fields:
            raise ValueError("Invalid display acknowledgement fields")
        request_id = _text(payload["request_id"], "request_id", 128, allow_empty=False)
        if request_id not in self.records:
            raise ValueError("Unknown request_id")
        record = self.records[request_id]
        status = payload["status"]
        if status not in ("displayed", "discarded"):
            raise ValueError("Display status must be displayed or discarded")
        if record["client_acknowledged"]:
            return {"status": record["status"], "request_id": request_id}
        if record["status"] != "ready":
            raise ValueError("Only a ready response can be acknowledged")
        delay = _number(payload["button_to_display_ms"], "button_to_display_ms", optional=status == "discarded")
        shown = _number(payload["displayed_video_s"], "displayed_video_s", optional=True)
        reason = _text(payload["reason"], "reason", 200)
        if status == "displayed":
            if payload["video_session_id"] != record["video_session_id"]:
                raise ValueError("Display video does not match the clicked video")
            if (shown is None) != (record["clicked_video_s"] is None):
                raise ValueError("Displayed video timestamp is inconsistent")
            # The official client measures both ends on one browser clock. We
            # record that client-reported metric, not a server-derived estimate.
            if delay > self.max_age_s * 1000:
                raise ValueError("Client should discard a stale result before displaying it")
        record.update(status=status, client_acknowledged=True, button_to_display_ms=delay if status == "displayed" else None,
                      displayed_video_s=shown if status == "displayed" else None,
                      discard_reason=reason if status == "discarded" else None)
        self._persist()
        return {"status": status, "request_id": request_id}

    def export(self) -> str:
        return "".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in self.records.values())

    def _persist(self) -> None:
        if not self.persist:
            return
        records = list(self.records.values())
        counts = {status: sum(r["status"] == status for r in records) for status in
                  ("generating", "ready", "displayed", "discarded", "expired", "duplicate", "error")}
        usage = {}
        for record in records:
            for key, value in record["usage"].items():
                if key.endswith("TokenCount") and isinstance(value, int) and not isinstance(value, bool):
                    usage[key] = usage.get(key, 0) + value
        report = {"schema_version": 3, "mode": "manual_text", "created_at": self.created_at,
                  "provider": self.provider.provider, "model": self.provider.model,
                  "is_mock": self.provider.provider == "mock", "input_media_sent_to_model": False,
                  "settings": {"cooldown_s": self.cooldown_s, "max_age_s": self.max_age_s, "timeout_s": self.timeout_s},
                  "summary": {"status_counts": counts, "rejections": self.rejections,
                              "api_latency_ms": _stats([r["api_latency_ms"] for r in records if r["api_latency_ms"] is not None]),
                              "button_to_display_ms": _stats([r["button_to_display_ms"] for r in records if r["status"] == "displayed"]),
                              "reported_model_calls": sum(r["model_calls"] for r in records), "reported_usage": usage},
                  "limitations": ["Button-to-display is client-reported, measured through browser DOM insertion; not physical paint.",
                                  "Video playback position is metadata, not elapsed wall time or an event annotation.",
                                  "No external chat platform delivery or live-model validation is implied.",
                                  "Successful reported calls only; failed upstream calls may incur usage."]}
        if report["is_mock"]:
            report["limitations"].insert(0, "MOCK / NO AI LATENCY RESULT: scripted text and artificial delay")
        content = {"run.json": json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                   "events.jsonl": self.export()}
        buf = io.StringIO(newline="")
        keys = ["request_id", "status", "persona", "channel_context", "clicked_video_s", "displayed_video_s",
                "api_latency_ms", "button_to_display_ms", "client_acknowledged", "comment", "error"]
        writer = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = {key: record.get(key) for key in keys}
            for key in ("comment", "error", "channel_context"):
                if isinstance(row[key], str) and row[key].lstrip().startswith(("=", "+", "-", "@")):
                    row[key] = "'" + row[key]
            writer.writerow(row)
        content["events.csv"] = "\ufeff" + buf.getvalue()
        for name, body in content.items():
            target = self.directory / name
            temp = target.with_suffix(target.suffix + ".tmp")
            temp.write_text(body, encoding="utf-8", newline="")
            temp.replace(target)


SESSION = web.AppKey("session", ManualSession)


@web.middleware
async def local_only(request: web.Request, handler):
    host = urlsplit("//" + request.host).hostname
    if host not in ("127.0.0.1", "localhost", "::1"):
        return web.json_response({"error": "Use the printed localhost URL"}, status=403)
    origin = request.headers.get("Origin")
    if origin is not None and origin != f"{request.scheme}://{request.host}":
        return web.json_response({"error": "Origin rejected"}, status=403)
    if request.method == "POST" and not secrets.compare_digest(request.headers.get("X-Demo-Token", ""), request.app[SESSION].session_token):
        return web.json_response({"error": "Session token required"}, status=403)
    try:
        response = await handler(request)
    except (ValueError, json.JSONDecodeError):
        return web.json_response({"status": "error", "error": "Invalid input; use the documented fields, limits and timing values"}, status=400)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; media-src 'self' blob:; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"
    return response


def create_app(provider, run_dir: str | Path, *, cooldown_s: float = 1,
               max_age_s: float = 8, timeout_s: float = 20) -> web.Application:
    session = ManualSession(provider, run_dir, cooldown_s=cooldown_s, max_age_s=max_age_s, timeout_s=timeout_s)
    app = web.Application(middlewares=[local_only], client_max_size=16 * 1024)
    app[SESSION] = session

    async def index(request):
        return web.Response(text=Path(__file__).with_name("manual_panel.html").read_text(encoding="utf-8"), content_type="text/html")
    async def config(request):
        return web.json_response(session.config())
    async def favicon(request):
        return web.FileResponse(Path(__file__).resolve().parents[1] / "assets" / "app.svg")
    async def trigger(request):
        if request.content_type != "application/json":
            raise ValueError("JSON required")
        return web.json_response(await session.trigger(await request.json()))
    async def display(request):
        if request.content_type != "application/json":
            raise ValueError("JSON required")
        return web.json_response(session.acknowledge(await request.json()))
    async def export(request):
        return web.Response(text=session.export(), content_type="application/x-ndjson",
                            headers={"Content-Disposition": 'attachment; filename="manual_events.jsonl"'})
    async def cleanup(application):
        await provider.close()
    app.add_routes([web.get("/", index), web.get("/favicon.svg", favicon), web.get("/api/config", config), web.post("/api/trigger", trigger),
                    web.post("/api/display", display), web.get("/api/export", export)])
    app.on_cleanup.append(cleanup)
    return app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["gemini", "mock"], default="gemini")
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output", default=None)
    parser.add_argument("--cooldown", type=float, default=1)
    parser.add_argument("--max-age", type=float, default=8)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--mock-delay", type=float, default=.2)
    args = parser.parse_args()
    try:
        if not 1 <= args.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        provider = MockManualProvider(args.mock_delay) if args.provider == "mock" else GeminiManualProvider(args.model, timeout_s=args.timeout)
        output = Path(args.output or ("runs/manual_" + datetime.now().strftime("%Y%m%d_%H%M%S")))
        app = create_app(provider, output, cooldown_s=args.cooldown, max_age_s=args.max_age, timeout_s=args.timeout)
        print(f"Manual text-only mode: {provider.provider}/{provider.model}")
        print(f"Open http://127.0.0.1:{args.port} in your browser. Press Ctrl+C to stop.")
        print(f"Results: {output.resolve()}")
        if provider.provider == "mock":
            print("MOCK / NO AI LATENCY RESULT — scripted comments with artificial delay")
        web.run_app(app, host="127.0.0.1", port=args.port, print=None)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
