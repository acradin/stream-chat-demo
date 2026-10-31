"""Authenticated screenshot service. Provider secrets stay in this process."""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import os
from pathlib import Path
import re

from aiohttp import web

from backend.chat_service import DesktopService
from backend.env import BACKEND_ENV, BACKEND_KEYS, load_env_file
from backend.screenshot_provider import DEFAULT_MODEL, OpenAIScreenshotProvider, validate_model
from backend.realtime_provider import MockProvider, RealtimeProvider, credentials
from backend.realtime_service import RealtimeSession, validate_start
from backend.chat_delivery import ChatDelivery
from backend.chzzk_target import parse_channel_id
from backend.chzzk_remote import CALLBACK_PATH, RemoteAuthorization
from backend.public_page import SERVICE_PAGE


def validate_accounts(accounts):
    if not isinstance(accounts, dict) or not accounts:
        raise ValueError("서버에 CHAT_SERVICE_ACCOUNTS 또는 CHAT_SERVICE_TOKEN을 설정해주세요.")
    tokens = set()
    for account, token in accounts.items():
        if not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", account):
            raise ValueError("서비스 계정 ID 형식이 잘못됐습니다.")
        if (not isinstance(token, str) or len(token) < 32 or not token.isascii()
                or any(ord(c) <= 32 or ord(c) >= 127 for c in token) or token in tokens):
            raise ValueError("계정마다 서로 다른 32자 이상의 서비스 인증 토큰이 필요합니다.")
        tokens.add(token)
    return dict(accounts)


def create_app(state_dir, *, accounts, provider="openai", model=DEFAULT_MODEL,
               service_factory=DesktopService, realtime_factory=None, delivery_factory=None, public_url=None,
               web_dir=None):
    accounts = validate_accounts(accounts)
    if provider not in ("openai", "mock"):
        raise ValueError("잘못된 서버 생성 모드입니다.")
    model = validate_model(model)
    services = {account: service_factory(Path(state_dir) / hashlib.sha256(account.encode()).hexdigest())
                for account in accounts}
    active = set()
    deliveries = {account: (delivery_factory(account) if delivery_factory else
                            ChatDelivery(account, enabled=provider != "mock",
                                         state_dir=Path(state_dir) / hashlib.sha256(account.encode()).hexdigest()))
                  for account in accounts}
    remote_auth = RemoteAuthorization(public_url, deliveries) if public_url else None
    public_web = None
    if web_dir is not None:
        from backend.public_web import PublicWeb
        if not public_url:
            raise ValueError("The public web demo requires its HTTPS origin.")
        public_web = PublicWeb(web_dir, public_url)
    # RequestKey was added after aiohttp 3.9, our supported minimum.
    account_key = web.RequestKey("service_account", str) if hasattr(web, "RequestKey") else "service_account"

    @web.middleware
    async def authenticate(request, handler):
        if public_web and public_web.handles(request):
            return await public_web.dispatch(request)
        if request.method in ("GET", "HEAD") and request.path == "/":
            return await handler(request)
        if request.method in ("GET", "HEAD") and request.path == "/healthz":
            return web.json_response({"status": "ok"}, headers={"Cache-Control": "no-store"})
        if remote_auth and request.method == "GET" and request.path == CALLBACK_PATH:
            return await remote_auth.callback(request)
        authorization = request.headers.get("Authorization", "")
        token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
        matched = next((account for account, secret in accounts.items()
                        if hmac.compare_digest(token.encode(), secret.encode())), None)
        if matched is None:
            return web.json_response({"error": "서비스 인증을 확인해주세요."}, status=401)
        request[account_key] = matched
        try:
            response = await handler(request)
        except web.HTTPRequestEntityTooLarge:
            response = web.json_response({"error": "화면 데이터가 너무 큽니다."}, status=413)
        except web.HTTPException as exc:
            response = web.json_response({"error": "요청한 서비스 경로를 확인해주세요."}, status=exc.status)
        except (ValueError, binascii.Error):
            response = web.json_response({"error": "생성 요청 형식이 올바르지 않습니다."}, status=400)
        except Exception:
            # Never expose provider errors, secrets, model names or upstream billing to clients.
            response = web.json_response({"error": "서비스 처리에 실패했습니다. 잠시 후 다시 시도해주세요."}, status=503)
        response.headers["Cache-Control"] = "no-store"
        return response

    async def usage(request):
        return web.json_response(services[request[account_key]].service_usage(provider))

    async def chzzk_status(request):
        return web.json_response(await deliveries[request[account_key]].status())

    async def chzzk_invite(request):
        return await remote_auth.invite(request, request[account_key])

    async def health(request):
        return web.json_response({"status": "ok"})

    async def home(request):
        return web.Response(text=SERVICE_PAGE, content_type="text/html", headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        })

    async def generate(request):
        data = await request.json()
        if (not isinstance(data, dict) or not {"personas", "context", "screenshot"} <= set(data)
                or set(data) - {"personas", "context", "screenshot", "destination", "channel_id"}):
            raise ValueError("Invalid fields")
        destination = data.get("destination", "app")
        if destination not in ("app", "chzzk"):
            raise ValueError("Invalid destination")
        target = parse_channel_id(data.get("channel_id")) if destination == "chzzk" else ""
        if not isinstance(data["screenshot"], str):
            raise ValueError("Invalid screenshot")
        screenshot = base64.b64decode(data["screenshot"], validate=True)
        service = services[request[account_key]]
        result = await service.generate(data["personas"], data["context"], screenshot=screenshot,
                                        provider_name=provider, model=model)
        # Provider diagnostics are kept behind the server boundary.
        for line in result["lines"]:
            if line["status"] == "error":
                line["error"] = "채팅을 생성하지 못했습니다. 잠시 후 다시 시도해주세요."
        if destination == "chzzk":
            failed = False
            for line in result["lines"]:
                if line["status"] != "ready":
                    continue
                if failed:
                    line["delivery"] = {"status": "skipped", "message": "앞선 전송을 확인하지 못해 앱에만 표시합니다.", "messageId": ""}
                    continue
                line["delivery"] = await deliveries[request[account_key]].send(line["comment"], target)
                failed = line["delivery"]["status"] != "sent"
        return web.json_response({**result, "usage": service.service_usage(provider)})

    async def realtime(request):
        service = services[request[account_key]]
        if not service.begin_realtime():
            raise web.HTTPConflict()
        socket = web.WebSocketResponse(max_msg_size=750000, heartbeat=5, receive_timeout=10)
        try:
            await socket.prepare(request)
            active.add(socket)
            settings = validate_start(await socket.receive_json(timeout=5))
            engine = (realtime_factory() if realtime_factory else MockProvider() if provider == "mock"
                      else RealtimeProvider(*credentials()))
            await RealtimeSession(socket, engine, settings, service, provider,
                                  delivery=deliveries[request[account_key]]).run()
            if not socket.closed:
                await socket.send_json({"type": "stopped", "usage": service.service_usage(provider)})
        except asyncio.CancelledError:
            raise
        except Exception:
            # No provider errors, keys, model names or billing cross this boundary.
            if socket.prepared and not socket.closed:
                await socket.send_json({"type": "error", "message": "실시간 연결을 종료했습니다. 서비스 연결과 선택한 화면을 확인해주세요."})
        finally:
            active.discard(socket)
            try:
                await socket.close()
            finally:
                service.end_realtime()
        return socket

    async def shutdown(app):
        await asyncio.gather(*(socket.close(code=1001, message=b"Service shutdown") for socket in list(active)))

    app = web.Application(middlewares=[authenticate], client_max_size=7_000_000)
    app.router.add_get("/", home)
    app.router.add_get("/healthz", health)
    if remote_auth:
        app.router.add_get(CALLBACK_PATH, remote_auth.callback, allow_head=False)
        app.router.add_post("/api/chzzk/authorize", chzzk_invite)
    app.router.add_get("/api/usage", usage)
    app.router.add_get("/api/chzzk/status", chzzk_status)
    app.router.add_post("/api/chat/generate", generate)
    app.router.add_get("/api/chat/realtime", realtime)
    app.on_shutdown.append(shutdown)
    return app


def main():
    load_env_file(BACKEND_ENV, BACKEND_KEYS)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("CHAT_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=os.environ.get("PORT", "8766"))
    parser.add_argument("--provider", choices=("openai", "mock"), default="openai")
    parser.add_argument("--state-dir", type=Path, default=os.environ.get("CHAT_STATE_DIR") or Path(__file__).resolve().parents[1] / "runs" / "service")
    args = parser.parse_args()
    try:
        accounts = json.loads(os.environ["CHAT_SERVICE_ACCOUNTS"]) if os.environ.get("CHAT_SERVICE_ACCOUNTS") else {
            "development": os.environ.get("CHAT_SERVICE_TOKEN", "")}
        model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        if args.provider == "openai":
            OpenAIScreenshotProvider(model=model)  # Fail before serving if operator credentials are missing.
        web_dir = Path(__file__).resolve().parents[1] / "apps/web/dist"
        app = create_app(args.state_dir, accounts=accounts, provider=args.provider, model=model,
                         public_url=os.environ.get("CHAT_PUBLIC_URL") or None,
                         web_dir=web_dir if (web_dir / "index.html").is_file() and os.environ.get("CHAT_PUBLIC_URL") else None)
    except ValueError as exc:
        parser.error(str(exc))
    web.run_app(app, host=args.host, port=args.port, access_log=None, handler_cancellation=True)


if __name__ == "__main__":
    main()
