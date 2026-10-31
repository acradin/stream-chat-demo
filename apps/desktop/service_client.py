"""Desktop talks only to our service; it has no AI-provider credentials."""

from __future__ import annotations

import asyncio
import base64
import copy
import json
import os
import re
import threading
from urllib.parse import parse_qs, urlsplit

import aiohttp

from backend.env import DESKTOP_KEYS, load_env_file
from apps.desktop.paths import connection_file
from backend.chzzk_target import parse_channel_id


DESKTOP_ENV = connection_file()


class ServiceClient:
    def __init__(self, *, base_url=None, token=None):
        load_env_file(DESKTOP_ENV, DESKTOP_KEYS)
        self.base_url = (base_url or os.environ.get("CHAT_SERVICE_URL", "http://127.0.0.1:8766")).rstrip("/")
        parts = urlsplit(self.base_url)
        if (parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password
                or parts.query or parts.fragment or parts.path
                or (parts.scheme == "http" and parts.hostname not in ("127.0.0.1", "localhost", "::1"))):
            raise ValueError("서비스 주소는 HTTPS여야 합니다. 로컬 개발 주소만 HTTP를 지원합니다.")
        self._token = token if token is not None else os.environ.get("CHAT_SERVICE_TOKEN", "")
        if self._token and (not self._token.isascii() or any(ord(c) <= 32 or ord(c) >= 127 for c in self._token)):
            raise ValueError("서비스 인증 설정을 확인해주세요.")
        self._usage = None
        self.stop_requested = threading.Event()

    @property
    def configured(self):
        return bool(self._token)

    def usage(self):
        return copy.deepcopy(self._usage)

    def _set_usage(self, usage):
        fields = {"period", "timezone", "is_demo", "generation_requests", "generated_chats", "total_generated_chats"}
        if (not isinstance(usage, dict) or set(usage) != fields or not isinstance(usage["period"], str)
                or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", usage["period"])
                or usage["timezone"] != "Asia/Seoul" or type(usage["is_demo"]) is not bool
                or any(type(usage[key]) is not int or usage[key] < 0
                       for key in ("generation_requests", "generated_chats", "total_generated_chats"))):
            raise ValueError("서비스 사용량 응답을 확인할 수 없습니다.")
        candidate = copy.deepcopy(usage)
        previous = self._usage
        if previous and previous["is_demo"] == candidate["is_demo"]:
            if candidate["period"] < previous["period"] or candidate["total_generated_chats"] < previous["total_generated_chats"]:
                return
            if candidate["period"] == previous["period"]:
                for key in ("generation_requests", "generated_chats"):
                    candidate[key] = max(candidate[key], previous[key])
        self._usage = candidate

    async def _request(self, method, path, payload=None, *, timeout=165, errors=None):
        if not self._token:
            raise ValueError("서비스 연결이 준비되지 않았습니다. 운영자에게 문의해주세요.")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.request(method, self.base_url + path, json=payload,
                        headers={"Authorization": "Bearer " + self._token}, allow_redirects=False) as response:
                    if response.status != 200:
                        raise ValueError({400: "앱의 요청을 처리하지 못했습니다. 앱과 서버를 최신 버전으로 다시 실행해주세요.",
                                          401: "서비스 인증이 만료되었거나 유효하지 않습니다.",
                                          413: "캡처한 화면 데이터가 너무 큽니다.", **(errors or {})}.get(
                                              response.status, "서비스 연결에 실패했습니다. 잠시 후 다시 시도해주세요."))
                    chunks, size = [], 0
                    async for chunk in response.content.iter_chunked(65536):
                        size += len(chunk)
                        if size > 100_000:
                            raise ValueError("서비스 응답이 너무 큽니다.")
                        chunks.append(chunk)
                    try:
                        return json.loads(b"".join(chunks))
                    except (ValueError, UnicodeDecodeError):
                        raise ValueError("서비스 응답을 읽지 못했습니다.") from None
        except (aiohttp.ClientError, asyncio.TimeoutError):
            raise ValueError("서비스에 연결할 수 없습니다. 연결 상태를 확인해주세요.") from None

    async def refresh_usage(self):
        self._set_usage(await self._request("GET", "/api/usage", timeout=5))
        return self.usage()

    async def chzzk_status(self):
        value = await self._request("GET", "/api/chzzk/status", timeout=30)
        if (not isinstance(value, dict) or type(value.get("connected")) is not bool
                or any(not isinstance(value.get(key), str) for key in ("channelId", "channelName", "message"))):
            raise ValueError("치지직 연결 상태를 확인할 수 없습니다.")
        if value["connected"]:
            parse_channel_id(value["channelId"])
        return value

    async def authorize_chzzk(self, channel_url):
        target = parse_channel_id(channel_url)
        value = await self._request("POST", "/api/chzzk/authorize", {"channel_url": channel_url}, timeout=30,
                                    errors={400: "방송 링크와 서비스의 치지직 인증 설정을 확인해주세요.",
                                            404: "이 서버는 앱 인증을 지원하지 않습니다. 서비스 연결에서 배포된 서버 주소를 설정해주세요."})
        if (not isinstance(value, dict) or value.get("channel_id") != target
                or type(value.get("expires_in")) is not int or not 1 <= value["expires_in"] <= 600
                or not isinstance(value.get("authorization_url"), str)):
            raise ValueError("치지직 인증 안내를 확인할 수 없습니다.")
        try:
            parts = urlsplit(value["authorization_url"])
            query = parse_qs(parts.query)
            valid = (parts.scheme == "https" and parts.netloc == "chzzk.naver.com"
                     and parts.path == "/account-interlock" and not parts.fragment
                     and len(query.get("state", [])) == 1 and bool(query["state"][0]))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("안전한 치지직 인증 주소를 확인할 수 없습니다.")
        return value

    @staticmethod
    def _destination(destination, channel_id):
        if destination not in ("app", "chzzk"):
            raise ValueError("채팅 표시 위치를 확인해주세요.")
        return ({"destination": "chzzk", "channel_id": parse_channel_id(channel_id)}
                if destination == "chzzk" else {})

    @staticmethod
    def _validate_delivery(value):
        if (not isinstance(value, dict) or value.get("status") not in ("sent", "failed", "skipped")
                or not isinstance(value.get("message"), str) or len(value["message"]) > 300
                or not isinstance(value.get("messageId"), str) or len(value["messageId"]) > 300):
            raise ValueError("치지직 전송 결과를 확인할 수 없습니다.")

    async def realtime(self, personas, context, *, capture, stop_event, on_event, interval=5, duration=60,
                       destination="app", channel_id=""):
        """Stream selected-window JPEGs to our authenticated service until stopped."""
        if not self.configured:
            raise ValueError("설정에서 서비스 연결을 먼저 등록해주세요.")
        output = self._destination(destination, channel_id)
        async def reject_redirect(session, trace_context, params):
            raise ValueError("서비스 주소가 변경되었습니다. 연결 설정을 확인해주세요.")
        trace = aiohttp.TraceConfig()
        trace.on_request_redirect.append(reject_redirect)

        async def exchange():
            timeout = aiohttp.ClientTimeout(total=None, sock_connect=5, sock_read=20)
            async with aiohttp.ClientSession(timeout=timeout, trace_configs=[trace]) as session:
                async with session.ws_connect(self.base_url + "/api/chat/realtime",
                        headers={"Authorization": "Bearer " + self._token}, max_msg_size=100000,
                        heartbeat=5) as socket:
                    await socket.send_json({"type": "start", "personas": personas, "context": context,
                                            "interval": interval, "duration": duration, **output})
                    ready = await socket.receive_json(timeout=20)
                    if ready != {"type": "ready"}:
                        raise ValueError("실시간 모드를 시작하지 못했습니다. 서비스 연결을 확인해주세요.")
                    on_event(ready)

                    async def send_frames():
                        sequence = 0
                        while not stop_event.is_set() and not self.stop_requested.is_set():
                            jpeg = await asyncio.to_thread(capture)
                            if stop_event.is_set() or self.stop_requested.is_set():
                                return
                            if not isinstance(jpeg, bytes) or len(jpeg) > 525000:
                                raise ValueError("캡처한 창 데이터가 너무 큽니다.")
                            sequence += 1
                            await socket.send_json({"type": "frame", "sequence": sequence,
                                                    "jpeg": base64.b64encode(jpeg).decode("ascii")})
                            await asyncio.sleep(1)

                    async def receive():
                        async for message in socket:
                            if message.type != aiohttp.WSMsgType.TEXT:
                                break
                            event = json.loads(message.data)
                            if not isinstance(event, dict):
                                raise ValueError("실시간 서비스 응답을 확인할 수 없습니다.")
                            kind = event.get("type")
                            if kind == "error":
                                raise ValueError("실시간 연결이 종료되었습니다. 서비스와 선택한 창을 확인해주세요.")
                            if kind == "decision":
                                participant = event.get("participant")
                                if (type(participant) is not int or not 1 <= participant <= len(personas)
                                        or event.get("persona") != personas[participant - 1]
                                        or event.get("result") not in ("chat", "wait", "stale", "cooldown", "duplicate")
                                        or not isinstance(event.get("comment"), str)
                                        or len(event["comment"]) > 100
                                        or (event["result"] == "chat" and not event["comment"].strip())):
                                    raise ValueError("실시간 채팅 응답 형식이 올바르지 않습니다.")
                                self._set_usage(event.get("usage"))
                            elif kind == "delivery":
                                if (destination != "chzzk" or type(event.get("participant")) is not int
                                        or not 1 <= event["participant"] <= len(personas)
                                        or event.get("persona") != personas[event["participant"] - 1]):
                                    raise ValueError("치지직 전송 결과를 확인할 수 없습니다.")
                                self._validate_delivery(event.get("delivery"))
                            elif kind == "stopped":
                                self._set_usage(event.get("usage"))
                                on_event(event)
                                return
                            elif kind != "frame":
                                raise ValueError("실시간 서비스 응답을 확인할 수 없습니다.")
                            on_event(event)
                        raise ValueError("실시간 연결이 끊어졌습니다. 시작 버튼으로 다시 연결해주세요.")

                    tasks = [asyncio.create_task(send_frames()), asyncio.create_task(receive())]
                    try:
                        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                        for task in done:
                            task.result()
                    finally:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)

        task = asyncio.create_task(exchange())
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=.1)
                if stop_event.is_set() or self.stop_requested.is_set():
                    return
            await task
        except (aiohttp.ClientError, asyncio.TimeoutError):
            raise ValueError("실시간 서비스에 연결할 수 없습니다. 서비스 연결 설정을 확인해주세요.") from None
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def generate(self, personas, context, *, screenshot, on_line=None, destination="app", channel_id=""):
        if self.stop_requested.is_set():
            return {"status": "stopped", "lines": []}
        task = asyncio.create_task(self._request("POST", "/api/chat/generate", {
            "personas": personas, "context": context,
            "screenshot": base64.b64encode(screenshot).decode("ascii"),
            **self._destination(destination, channel_id)}, timeout=300 if destination == "chzzk" else 165))
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=.1)
                if self.stop_requested.is_set():
                    return {"status": "stopped", "lines": []}
            result = await task
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if (not isinstance(result, dict) or result.get("status") not in ("complete", "partial", "busy", "cooldown", "stopped")
                or not isinstance(result.get("lines"), list) or len(result["lines"]) > len(personas)):
            raise ValueError("채팅 응답 형식이 올바르지 않습니다.")
        for index, line in enumerate(result["lines"], 1):
            if (not isinstance(line, dict) or line.get("participant") != index or line.get("persona") != personas[index - 1]
                    or line.get("status") not in ("ready", "error")
                    or not isinstance(line.get("comment"), str) or not isinstance(line.get("error"), str)
                    or (line["status"] == "ready" and not 1 <= len(line["comment"]) <= 100)):
                raise ValueError("채팅 응답 형식이 올바르지 않습니다.")
            if "delivery" in line:
                self._validate_delivery(line["delivery"])
        self._set_usage(result.get("usage"))
        if on_line:
            for line in result["lines"]:
                on_line(line)
        return result
