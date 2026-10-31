"""Loopback-only experiment UI. Browser video -> server -> Realtime -> local chat."""

import argparse
import asyncio
import contextlib
import hmac
import json
import secrets
import time
from urllib.parse import urlsplit

import aiohttp
from aiohttp import web

from backend.personas import PERSONAS
from experiments.realtime_video.provider import (
    DIRECTORY, MockProvider, RealtimeError, RealtimeProvider, credentials, decode_frame)


def validate_start(value, token):
    if (not isinstance(value, dict) or set(value) != {"type", "token", "persona", "context", "interval", "duration"}
            or value["type"] != "start" or not isinstance(value["token"], str)
            or not hmac.compare_digest(value["token"].encode(), token.encode())
            or not isinstance(value["persona"], str) or value["persona"] not in PERSONAS
            or not isinstance(value["context"], str) or len(value["context"]) > 1000
            or type(value["interval"]) is not int or value["interval"] not in (3, 5, 10)
            or type(value["duration"]) is not int or value["duration"] not in (30, 60, 120)):
        raise RealtimeError("실험 시작 설정을 확인해주세요.")
    return value


class Experiment:
    def __init__(self, browser, provider, settings):
        self.browser, self.provider, self.settings = browser, provider, settings
        self.last_sequence, self.frame_count, self.decisions, self.chats = 0, 0, 0, 0
        self.last_frame_at = self.last_reply_at = float("-inf")
        self.recent = []

    async def receive(self):
        async for message in self.browser:
            if message.type != aiohttp.WSMsgType.TEXT:
                break
            try:
                value = json.loads(message.data)
            except ValueError:
                raise RealtimeError("화면 전송 메시지를 읽을 수 없습니다.") from None
            if value == {"type": "stop"}:
                return
            frame = decode_frame(value, self.last_sequence)
            if frame.received_at - self.last_frame_at < .8:
                continue
            await self.provider.push_frame(frame)
            self.last_sequence, self.last_frame_at = frame.sequence, frame.received_at
            self.frame_count += 1
            await self.browser.send_json({"type": "frame", "frames": self.frame_count})

    def accept(self, decision, frames, now):
        reason = "wait"
        if decision["action"] == "REACT":
            evidence = next(frame for frame in frames if frame.id == decision["evidence_frame_id"])
            compact = "".join(decision["comment"].split())
            if now - evidence.received_at > 8:
                reason = "stale"
            elif now - self.last_reply_at < 8:
                reason = "cooldown"
            elif compact in {"".join(comment.split()) for comment in self.recent}:
                reason = "duplicate"
            else:
                reason = "chat"
                self.last_reply_at = now
                self.recent = [*self.recent, decision["comment"]][-8:]
                self.chats += 1
        return reason

    async def judge(self):
        previous = 0
        while True:
            await asyncio.sleep(self.settings["interval"])
            if self.last_sequence <= previous or time.monotonic() - self.last_frame_at > 3:
                continue
            decision, frames, elapsed = await self.provider.analyze(
                self.settings["persona"], self.settings["context"], list(self.recent))
            previous = frames[-1].sequence
            self.decisions += 1
            reason = self.accept(decision, frames, time.monotonic())
            await self.browser.send_json({"type": "decision", "result": reason,
                "comment": decision["comment"] if reason == "chat" else "", "generation_ms": elapsed,
                "frame_sequence": previous, "decisions": self.decisions, "chats": self.chats})

    async def run(self):
        tasks = []
        try:
            await self.provider.open()
            await self.browser.send_json({"type": "ready"})
            tasks = [asyncio.create_task(self.receive()), asyncio.create_task(self.judge()),
                     asyncio.create_task(asyncio.sleep(self.settings["duration"]))]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.provider.close()


def create_app(*, provider="mock", factory=None):
    if provider not in ("mock", "openai"):
        raise ValueError("Unknown provider")
    token = secrets.token_urlsafe(32)
    active = set()

    @web.middleware
    async def local_only(request, handler):
        host = urlsplit("//" + request.host)
        port = request.transport.get_extra_info("sockname")[1]
        try:
            valid = host.hostname in ("127.0.0.1", "localhost") and host.port == port and not host.username
        except ValueError:
            valid = False
        if not valid:
            raise web.HTTPForbidden()
        origin = request.headers.get("Origin")
        if origin and origin != "http://" + request.host:
            raise web.HTTPForbidden()
        response = await handler(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
            "media-src 'self' blob:; connect-src 'self' ws://127.0.0.1:* ws://localhost:*; frame-ancestors 'none'")
        return response

    async def config(request):
        return web.json_response({"token": token, "provider": provider,
            "personas": [{"id": key, "name": value["name"]} for key, value in PERSONAS.items()]})

    async def asset(request):
        name = request.match_info.get("name", "index.html")
        if name not in ("index.html", "app.js", "style.css"):
            raise web.HTTPNotFound()
        return web.FileResponse(DIRECTORY / name)

    async def websocket(request):
        if request.headers.get("Origin") != "http://" + request.host:
            raise web.HTTPForbidden()
        if active:
            raise web.HTTPConflict(text="이미 실험 중입니다.")
        browser = web.WebSocketResponse(max_msg_size=750000, heartbeat=10, receive_timeout=10)
        active.add(browser)
        try:
            await browser.prepare(request)
            settings = validate_start(await browser.receive_json(timeout=5), token)
            engine = factory() if factory else MockProvider() if provider == "mock" else RealtimeProvider(*credentials())
            await Experiment(browser, engine, settings).run()
            if not browser.closed:
                await browser.send_json({"type": "stopped", "message": "실험을 종료했습니다."})
        except RealtimeError as exc:
            if not browser.closed:
                await browser.send_json({"type": "error", "message": str(exc)})
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError):
            if not browser.closed:
                await browser.send_json({"type": "error", "message": "실시간 연결에 실패했습니다. 자동으로 재시도하지 않습니다."})
        finally:
            active.discard(browser)
            await browser.close()
        return browser

    async def shutdown(app):
        for browser in list(active):
            with contextlib.suppress(Exception):
                await browser.close(code=1001, message=b"Experiment shutdown")

    app = web.Application(middlewares=[local_only], client_max_size=750000)
    app.router.add_get("/", asset)
    app.router.add_get("/config", config)
    app.router.add_get("/ws", websocket)
    app.router.add_get("/{name}", asset)
    app.on_shutdown.append(shutdown)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("mock", "openai"), default="mock")
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("포트는 1024~65535 사이여야 합니다.")
    if args.provider == "openai":
        try:
            credentials()
        except RealtimeError as exc:
            parser.error(str(exc))
    print(f"화면 전용 실험 ({args.provider}): http://127.0.0.1:{args.port}")
    web.run_app(create_app(provider=args.provider), host="127.0.0.1", port=args.port,
                access_log=None, handler_cancellation=True)
