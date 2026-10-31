"""Authenticated desktop video sessions. No audio, screen files or browser UI."""

import asyncio
import json
import time

import aiohttp

from backend.personas import PERSONAS
from backend.realtime_provider import RealtimeError, decode_frame
from backend.chzzk_target import parse_channel_id


def validate_start(value):
    if (not isinstance(value, dict)
            or not {"type", "personas", "context", "interval", "duration"} <= set(value)
            or set(value) - {"type", "personas", "context", "interval", "duration", "destination", "channel_id"}
            or value["type"] != "start"
            or not isinstance(value["personas"], list) or not 1 <= len(value["personas"]) <= 5
            or any(not isinstance(p, str) or p not in PERSONAS for p in value["personas"])
            or not isinstance(value["context"], str) or len(value["context"]) > 1000
            or type(value["interval"]) is not int or value["interval"] not in (3, 5, 10)
            or type(value["duration"]) is not int or value["duration"] not in (30, 60, 120)):
        raise ValueError("Invalid realtime settings")
    if value.get("destination", "app") not in ("app", "chzzk"):
        raise ValueError("Invalid destination")
    if value.get("destination") == "chzzk":
        parse_channel_id(value.get("channel_id"))
    return value


class RealtimeSession:
    def __init__(self, socket, provider, settings, service, provider_name, *, delivery=None):
        self.socket, self.provider, self.settings = socket, provider, settings
        self.service, self.provider_name = service, provider_name
        self.last_sequence = self.frames = self.decisions = self.chats = 0
        self.last_frame_at = self.last_reply_at = float("-inf")
        self.recent = []
        self.delivery = delivery
        self.delivery_failed = False

    async def receive(self):
        async for message in self.socket:
            if message.type != aiohttp.WSMsgType.TEXT:
                return
            value = json.loads(message.data)
            if value == {"type": "stop"}:
                return
            frame = decode_frame(value, self.last_sequence)
            if frame.received_at - self.last_frame_at < .8:
                continue
            await self.provider.push_frame(frame)
            self.last_sequence, self.last_frame_at = frame.sequence, frame.received_at
            self.frames += 1
            await self.socket.send_json({"type": "frame", "frames": self.frames})

    def accept(self, decision, frames, now):
        if decision["action"] == "WAIT":
            return "wait"
        evidence = next(frame for frame in frames if frame.id == decision["evidence_frame_id"])
        if now - evidence.received_at > 8:
            return "stale"
        if now - self.last_reply_at < 8:
            return "cooldown"
        if "".join(decision["comment"].split()) in {"".join(c.split()) for c in self.recent}:
            return "duplicate"
        self.last_reply_at = now
        self.recent = [*self.recent, decision["comment"]][-8:]
        self.chats += 1
        return "chat"

    async def judge(self):
        previous = 0
        while True:
            await asyncio.sleep(self.settings["interval"])
            now = time.monotonic()
            # Apply the chat cooldown BEFORE a paid call.
            if (self.last_sequence <= previous or now - self.last_frame_at > 3
                    or now - self.last_reply_at < 8):
                continue
            index = self.decisions % len(self.settings["personas"])
            persona = self.settings["personas"][index]
            self.service.realtime_attempt(self.provider_name)
            try:
                decision, frames, elapsed = await self.provider.analyze(persona, self.settings["context"], list(self.recent))
                previous = frames[-1].sequence
                reason = self.accept(decision, frames, time.monotonic())
            except BaseException:
                self.service.realtime_result(self.provider_name, failed=True)
                raise
            self.service.realtime_result(self.provider_name, chat=reason == "chat")
            self.decisions += 1
            await self.socket.send_json({"type": "decision", "result": reason,
                "participant": index + 1, "persona": persona,
                "comment": decision["comment"] if reason == "chat" else "", "generation_ms": elapsed,
                "decisions": self.decisions, "chats": self.chats,
                "usage": self.service.service_usage(self.provider_name)})
            if reason == "chat" and self.settings.get("destination") == "chzzk":
                if self.delivery_failed:
                    receipt = {"status": "skipped", "message": "전송 중단 상태 · 앱에만 표시합니다.", "messageId": ""}
                else:
                    receipt = await self.delivery.send(decision["comment"], self.settings["channel_id"])
                    self.delivery_failed = receipt["status"] != "sent"
                await self.socket.send_json({"type": "delivery", "participant": index + 1,
                                             "persona": persona, "delivery": receipt})

    async def run(self):
        tasks = []
        try:
            await self.provider.open()
            await self.socket.send_json({"type": "ready"})
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
