"""Public, browser-isolated demo alongside the private desktop service."""

import json
from pathlib import Path
import secrets
import time

from aiohttp import web

from apps.web.server import ManualSession, MAX_WEB_REQUEST
from backend.web_provider import MockWebProvider


COOKIE = "__Host-tiki-demo"
API_PATHS = {"/api/config", "/api/trigger", "/api/display", "/api/export"}
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
}


class PublicWeb:
    def __init__(self, directory, origin, *, clock=time.monotonic, capacity=128, ttl=1800, max_records=100, provider=None):
        self.directory = Path(directory).resolve()
        self.origin, self.clock = origin, clock
        self.capacity, self.ttl, self.max_records = capacity, ttl, max_records
        self.provider = provider or MockWebProvider(.2)
        self.is_live = self.provider.provider != "mock"
        if self.is_live:
            self.max_records = min(max_records,10)
        self.sessions = {}
        self.files = {}
        for path in self.directory.rglob("*"):
            if (path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(self.directory)
                    and path.suffix in {".html", ".js", ".css", ".svg", ".png", ".jpg", ".webp", ".woff2", ".ttf", ".mp4"}
                    and not any(part.startswith(".") for part in path.relative_to(self.directory).parts)):
                self.files["/" + path.relative_to(self.directory).as_posix()] = path
        if "/index.html" not in self.files:
            raise ValueError("Build the web frontend before enabling its public routes.")
        self.files["/"] = self.files["/index.html"]

    def handles(self, request):
        return request.path in API_PATHS or (request.method in {"GET", "HEAD"} and request.path in self.files)

    async def dispatch(self, request):
        try:
            response = await self._dispatch(request)
        except web.HTTPRequestEntityTooLarge:
            response = web.json_response({"error": "요청이 너무 큽니다."}, status=413)
        except (ValueError, json.JSONDecodeError):
            response = web.json_response({"status": "error", "error": "입력 내용과 요청 형식을 확인해주세요."}, status=400)
        response.headers.update(HEADERS)
        return response

    async def _dispatch(self, request):
        if request.path in self.files:
            return web.FileResponse(self.files[request.path])
        expected_method = "POST" if request.path in {"/api/trigger", "/api/display"} else "GET"
        if request.method not in ({"GET", "HEAD"} if expected_method == "GET" else {"POST"}):
            return web.json_response({"error": "허용되지 않는 요청입니다."}, status=405)
        # Use the configured HTTPS origin; the reverse proxy talks HTTP internally.
        origin = request.headers.get("Origin")
        if ((origin is not None and origin != self.origin)
                or request.headers.get("Sec-Fetch-Site") == "cross-site"
                or (request.method == "POST" and origin != self.origin)):
            return web.json_response({"error": "웹 페이지에서 다시 요청해주세요."}, status=403)
        now = self.clock()
        for key, (session, touched) in list(self.sessions.items()):
            if now - touched >= self.ttl and not session.lock.locked():
                del self.sessions[key]
        cookie = request.cookies.get(COOKIE)
        entry = self.sessions.get(cookie)
        if request.path == "/api/config":
            if entry is None:
                if len(self.sessions) >= self.capacity:
                    return web.json_response({"error": "접속이 많습니다. 잠시 후 다시 시도해주세요."}, status=503)
                cookie = secrets.token_urlsafe(32)
                session = ManualSession(self.provider, self.directory, persist=False,
                                        cooldown_s=3 if self.is_live else 1,
                                        max_age_s=40 if self.is_live else 8, timeout_s=35 if self.is_live else 20)
            else:
                session = entry[0]
            self.sessions[cookie] = (session, now)
            config = session.config()
            config.update(provider="tiki",model="",session_limit=self.max_records,
                          remaining_requests=max(0,self.max_records-len(session.records)))
            response = web.json_response(config)
            response.set_cookie(COOKIE, cookie, max_age=self.ttl, secure=True, httponly=True, samesite="Lax", path="/")
            return response
        if entry is None:
            return web.json_response({"error": "데모 세션이 끝났습니다. 페이지를 새로고침해주세요."}, status=403)
        session = entry[0]
        self.sessions[cookie] = (session, now)
        if request.path == "/api/export":
            fields = {"request_id","status","persona","channel_context","comment","api_latency_ms","button_to_display_ms","model_calls"}
            exported = "".join(json.dumps({key:value for key,value in record.items() if key in fields},ensure_ascii=False)+"\n" for record in session.records.values())
            return web.Response(text=exported, content_type="application/x-ndjson",
                                headers={"Content-Disposition": 'attachment; filename="tiki-demo.jsonl"'})
        supplied = request.headers.get("X-Demo-Token", "")
        if not secrets.compare_digest(supplied.encode(), session.session_token.encode()):
            return web.json_response({"error": "데모 세션을 확인해주세요."}, status=403)
        if request.content_type != "application/json":
            raise ValueError("JSON required")
        limit = MAX_WEB_REQUEST if request.path == "/api/trigger" else 16 * 1024
        body = await request.clone(client_max_size=limit).read()
        payload = json.loads(body)
        if isinstance(payload, dict) and "frame_jpeg" not in payload and len(body) > 16 * 1024:
            raise web.HTTPRequestEntityTooLarge(max_size=16 * 1024, actual_size=len(body))
        if request.path == "/api/trigger":
            data = session._validate_trigger(payload)
            repeated = data["client_request_id"] in session.client_requests
            if not repeated and len(session.records) >= self.max_records:
                return web.json_response({"status": "error", "error": "이번 데모 세션의 체험 횟수를 모두 사용했습니다. 잠시 후 다시 방문해주세요."}, status=429)
            result = await session.trigger(payload)
            return web.json_response(result)
        return web.json_response(session.acknowledge(payload))

    async def close(self):
        await self.provider.close()
