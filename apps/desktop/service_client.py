"""Desktop talks only to our service; it has no AI-provider credentials."""

from __future__ import annotations

import asyncio
import base64
import copy
import json
import os
from pathlib import Path
import re
import threading
from urllib.parse import urlsplit

import aiohttp

from backend.env import DESKTOP_KEYS, load_env_file


DESKTOP_ENV = Path(__file__).resolve().parent / ".env"


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

    async def _request(self, method, path, payload=None, *, timeout=165):
        if not self._token:
            raise ValueError("서비스 연결이 준비되지 않았습니다. 운영자에게 문의해주세요.")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.request(method, self.base_url + path, json=payload,
                        headers={"Authorization": "Bearer " + self._token}, allow_redirects=False) as response:
                    if response.status != 200:
                        raise ValueError({401: "서비스 인증이 만료되었거나 유효하지 않습니다.",
                                          413: "캡처한 화면 데이터가 너무 큽니다."}.get(
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

    async def generate(self, personas, context, *, screenshot, on_line=None):
        if self.stop_requested.is_set():
            return {"status": "stopped", "lines": []}
        task = asyncio.create_task(self._request("POST", "/api/chat/generate", {
            "personas": personas, "context": context,
            "screenshot": base64.b64encode(screenshot).decode("ascii")}))
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
        self._set_usage(result.get("usage"))
        if on_line:
            for line in result["lines"]:
                on_line(line)
        return result
