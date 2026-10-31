"""Official CHZZK OAuth and explicit chat publishing; credentials stay server-side."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlencode, urlsplit

import aiohttp

from backend.env import BACKEND_ENV, BACKEND_KEYS, load_env_file


API_ROOT = "https://openapi.chzzk.naver.com"
AUTHORIZE_URL = "https://chzzk.naver.com/account-interlock"
DEFAULT_REDIRECT = "http://localhost:8767/oauth/chzzk/callback"
TOKEN_PATH = Path(__file__).resolve().parents[1] / "runs" / "chzzk" / "tokens.json"


class ChzzkError(ValueError):
    pass


def credential(value, name):
    if (not isinstance(value, str) or not 1 <= len(value) <= 8192 or not value.isascii()
            or any(ord(char) <= 32 or ord(char) >= 127 for char in value)):
        raise ChzzkError(f"{name} 설정을 확인해주세요.")
    return value


def channel_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{32}", value):
        raise ChzzkError("CHZZK_CHANNEL_ID에는 방송 채널 URL 끝의 32자리 ID를 넣어주세요.")
    return value.lower()


@dataclass(frozen=True, repr=False)
class ChzzkConfig:
    client_id: str
    client_secret: str
    channel_id: str
    redirect_uri: str = DEFAULT_REDIRECT

    def __post_init__(self):
        credential(self.client_id, "CHZZK_CLIENT_ID")
        credential(self.client_secret, "CHZZK_CLIENT_SECRET")
        object.__setattr__(self, "channel_id", channel_id(self.channel_id))
        try:
            parts = urlsplit(self.redirect_uri)
            port = parts.port
        except ValueError:
            raise ChzzkError("치지직 리디렉션 주소와 포트를 확인해주세요.") from None
        if (parts.scheme != "http" or parts.hostname not in ("localhost", "127.0.0.1")
                or parts.username or parts.password or parts.query or parts.fragment
                or not port or not parts.path or parts.path == "/"):
            raise ChzzkError("치지직 리디렉션 주소는 명시한 포트와 경로가 있는 로컬 HTTP 주소여야 합니다.")

    @classmethod
    def from_env(cls):
        load_env_file(BACKEND_ENV, BACKEND_KEYS)
        return cls(os.environ.get("CHZZK_CLIENT_ID", "").strip(),
                   os.environ.get("CHZZK_CLIENT_SECRET", "").strip(),
                   os.environ.get("CHZZK_CHANNEL_ID", "").strip().lower(),
                   os.environ.get("CHZZK_REDIRECT_URI", DEFAULT_REDIRECT).strip())

    def authorization_url(self, state):
        return AUTHORIZE_URL + "?" + urlencode({"clientId": self.client_id,
                                                "redirectUri": self.redirect_uri, "state": state})


class ChzzkClient:
    def __init__(self, config: ChzzkConfig, *, token_path: Path = TOKEN_PATH):
        self.config, self.token_path = config, Path(token_path)
        self._lock = asyncio.Lock()

    async def _request(self, method, path, *, data=None, access_token=None):
        headers = {"Authorization": "Bearer " + access_token} if access_token else {}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20), trust_env=True) as session:
                async with session.request(method, API_ROOT + path, json=data, headers=headers,
                                           allow_redirects=False) as response:
                    if response.status != 200:
                        hints = {401: "다시 인증해주세요.", 403: "개발자 앱 권한과 방송 계정을 확인해주세요.",
                                 429: "요청 한도를 초과했습니다. 잠시 후 확인해주세요."}
                        raise ChzzkError(f"치지직 HTTP {response.status}: " + hints.get(response.status, "요청 처리에 실패했습니다."))
                    chunks, size = [], 0
                    async for chunk in response.content.iter_chunked(8192):
                        size += len(chunk)
                        if size > 65536:
                            raise ChzzkError("치지직 응답이 너무 큽니다.")
                        chunks.append(chunk)
                    try:
                        body = json.loads(b"".join(chunks))
                    except (ValueError, UnicodeError):
                        raise ChzzkError("치지직 응답을 읽을 수 없습니다.") from None
        except (aiohttp.ClientError, asyncio.TimeoutError):
            raise ChzzkError("치지직 연결이 중단됐습니다. 전송 여부가 불확실할 수 있으므로 자동 재전송하지 않습니다.") from None
        if not isinstance(body, dict):
            raise ChzzkError("치지직 응답 형식이 올바르지 않습니다.")
        if "code" in body and body["code"] != 200:
            raise ChzzkError("치지직이 요청을 거절했습니다. 권한과 설정을 확인해주세요.")
        content = body.get("content", body)
        if not isinstance(content, dict):
            raise ChzzkError("치지직 응답 내용이 올바르지 않습니다.")
        return content

    def _token_bundle(self, body):
        access = credential(body.get("accessToken"), "치지직 accessToken")
        refresh = credential(body.get("refreshToken"), "치지직 refreshToken")
        try:
            expires = float(body["expiresIn"])
        except (KeyError, ValueError, TypeError):
            raise ChzzkError("치지직 토큰 만료 정보가 없습니다.") from None
        if not math.isfinite(expires) or expires <= 60 or body.get("tokenType") != "Bearer":
            raise ChzzkError("치지직 토큰 응답 형식이 올바르지 않습니다.")
        return {"client_id": self.config.client_id, "channel_id": self.config.channel_id,
                "access_token": access, "refresh_token": refresh, "expires_at": time.time() + expires}

    def _read_tokens(self):
        try:
            body = json.loads(self.token_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ChzzkError("치지직 인증이 필요합니다. python -m backend.chzzk_cli authorize를 실행해주세요.") from None
        if (not isinstance(body, dict) or body.get("client_id") != self.config.client_id
                or body.get("channel_id") != self.config.channel_id):
            raise ChzzkError("저장된 치지직 인증의 앱 또는 채널이 다릅니다. 다시 인증해주세요.")
        credential(body.get("access_token"), "저장된 accessToken")
        credential(body.get("refresh_token"), "저장된 refreshToken")
        expiry = body.get("expires_at")
        if type(expiry) not in (int, float) or not math.isfinite(expiry):
            raise ChzzkError("저장된 토큰 만료 정보가 잘못됐습니다. 다시 인증해주세요.")
        return body

    def _save_tokens(self, body):
        # runs/ is gitignored. Tokens never enter client settings or command output.
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.token_path.parent,
                                             prefix=".chzzk-", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(body, stream)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.token_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    async def _identity(self, access_token):
        user = await self._request("GET", "/open/v1/users/me", access_token=access_token)
        actual = channel_id(user.get("channelId"))
        if actual != self.config.channel_id:
            raise ChzzkError("인증한 계정이 지정한 방송 채널과 다릅니다. 채팅을 전송하지 않았습니다.")
        if not isinstance(user.get("channelName"), str):
            raise ChzzkError("치지직 채널 이름을 확인하지 못했습니다.")
        return {"channelId": actual, "channelName": user["channelName"]}

    async def authorize(self, code, state):
        credential(code, "치지직 인증 코드")
        credential(state, "치지직 인증 state")
        async with self._lock:
            response = await self._request("POST", "/auth/v1/token", data={
                "grantType": "authorization_code", "clientId": self.config.client_id,
                "clientSecret": self.config.client_secret, "code": code, "state": state})
            tokens = self._token_bundle(response)
            identity = await self._identity(tokens["access_token"])
            self._save_tokens(tokens)
            return identity

    async def _access_token(self):
        tokens = self._read_tokens()
        if time.time() + 60 >= tokens["expires_at"]:
            body = await self._request("POST", "/auth/v1/token", data={
                "grantType": "refresh_token", "refreshToken": tokens["refresh_token"],
                "clientId": self.config.client_id, "clientSecret": self.config.client_secret})
            tokens = self._token_bundle(body)
            # Refresh tokens rotate; persist before any subsequent API call.
            self._save_tokens(tokens)
        return tokens["access_token"]

    async def status(self):
        async with self._lock:
            return await self._identity(await self._access_token())

    async def send(self, message):
        if (not isinstance(message, str) or not message.startswith("[AI] ") or not 6 <= len(message) <= 100
                or not message[5:].strip()
                or any(ord(char) < 32 or char in "\x7f\x85\u2028\u2029" for char in message)):
            raise ChzzkError("전송할 채팅은 [AI] 표시를 포함한 100자 이내 한 줄이어야 합니다.")
        async with self._lock:
            access = await self._access_token()
            identity = await self._identity(access)
            result = await self._request("POST", "/open/v1/chats/send", data={"message": message}, access_token=access)
            if not isinstance(result.get("messageId"), str) or not result["messageId"]:
                raise ChzzkError("전송 응답에 메시지 ID가 없습니다. 방송 채팅을 확인한 뒤 재전송 여부를 판단해주세요.")
            return {**identity, "messageId": result["messageId"], "message": message}
