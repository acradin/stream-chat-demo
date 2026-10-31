"""One-use, account-bound browser authorization for a single persistent server."""

import asyncio
import hashlib
import json
import secrets
import time
from urllib.parse import urlsplit

from aiohttp import web

from backend.chzzk import ChzzkError


CALLBACK_PATH = "/oauth/chzzk/callback"
INVITE_TTL = 600


def public_origin(value):
    value = value.rstrip("/")
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.path or parts.query or parts.fragment
            or parts.username or parts.password or parts.hostname in ("localhost", "127.0.0.1", "::1")
            or parts.port not in (None, 443)):
        raise ValueError("CHAT_PUBLIC_URL에는 경로 없는 공개 HTTPS 주소를 설정해주세요.")
    return value


def browser_response(text, status=200):
    return web.Response(text=text, status=status, content_type="text/plain", headers={
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    })


class RemoteAuthorization:
    def __init__(self, origin, deliveries, *, clock=time.monotonic):
        self.origin = public_origin(origin)
        self.deliveries = deliveries
        self.clock = clock
        self.pending = {}

    async def invite(self, request, account):
        # These links are issued only behind the service's Bearer authentication.
        try:
            raw = await request.content.readexactly(4097)
        except asyncio.IncompleteReadError as exc:
            raw = exc.partial
        if len(raw) > 4096:
            raise web.HTTPRequestEntityTooLarge(max_size=4096, actual_size=len(raw))
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"channel_url"}:
            raise ValueError("Invalid invitation fields")
        delivery = self.deliveries[account]
        try:
            client = delivery.authorization_client(data["channel_url"], self.origin + CALLBACK_PATH)
        except ChzzkError:
            return web.json_response({"error": "이 계정의 치지직 연결 설정과 방송 링크를 확인해주세요."}, status=400)
        state = secrets.token_urlsafe(32)
        # One pending link per service account; issuing another invalidates its predecessor.
        self.pending = {key: entry for key, entry in self.pending.items()
                        if entry[0] != account and entry[2] > self.clock()}
        self.pending[hashlib.sha256(state.encode()).digest()] = (account, client, self.clock() + INVITE_TTL)
        return web.json_response({"authorization_url": client.config.authorization_url(state),
                                  "channel_id": client.config.channel_id, "expires_in": INVITE_TTL})

    async def callback(self, request):
        if request.host != urlsplit(self.origin).netloc:
            return browser_response("승인 주소가 일치하지 않습니다.", 400)
        state = request.query.getall("state", [])
        codes = request.query.getall("code", [])
        if len(state) != 1 or not 1 <= len(state[0]) <= 128:
            return browser_response("승인 링크가 올바르지 않습니다.", 400)
        key = hashlib.sha256(state[0].encode()).digest()
        entry = self.pending.pop(key, None)  # Consume before any network await or token exchange.
        if entry is None or entry[2] <= self.clock():
            return browser_response("승인 링크가 만료되었거나 이미 사용되었습니다. 새 링크를 요청해주세요.", 400)
        if request.query.get("error") or len(codes) != 1 or not codes[0] or len(codes[0]) > 8192:
            return browser_response("치지직 승인이 취소되었습니다. 연결하려면 새 링크를 요청해주세요.", 400)
        account, client, _ = entry
        delivery = self.deliveries[account]
        try:
            async with asyncio.timeout(50), delivery.lock:
                await client.authorize(codes[0], state[0])
                delivery.client = client
        except Exception:
            return browser_response("연결하지 못했습니다. 요청받은 방송 계정으로 로그인했는지 확인하고 새 링크를 요청해주세요.", 400)
        return browser_response("치지직 연결이 완료되었습니다. 이 창을 닫아도 됩니다. 승인만으로 채팅이 전송되지는 않습니다.")
