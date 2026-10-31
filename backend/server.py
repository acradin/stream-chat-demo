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
               service_factory=DesktopService, realtime_factory=None):
    accounts = validate_accounts(accounts)
    if provider not in ("openai", "mock"):
        raise ValueError("잘못된 서버 생성 모드입니다.")
    model = validate_model(model)
    services = {account: service_factory(Path(state_dir) / hashlib.sha256(account.encode()).hexdigest())
                for account in accounts}
    active = set()
    # RequestKey was added after aiohttp 3.9, our supported minimum.
    account_key = web.RequestKey("service_account", str) if hasattr(web, "RequestKey") else "service_account"

    @web.middleware
    async def authenticate(request, handler):
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

    async def generate(request):
        data = await request.json()
        if not isinstance(data, dict) or set(data) != {"personas", "context", "screenshot"}:
            raise ValueError("Invalid fields")
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
            await RealtimeSession(socket, engine, settings, service, provider).run()
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
    app.router.add_get("/api/usage", usage)
    app.router.add_post("/api/chat/generate", generate)
    app.router.add_get("/api/chat/realtime", realtime)
    app.on_shutdown.append(shutdown)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--provider", choices=("openai", "mock"), default="openai")
    parser.add_argument("--state-dir", type=Path, default=Path(__file__).resolve().parents[1] / "runs" / "service")
    args = parser.parse_args()
    try:
        load_env_file(BACKEND_ENV, BACKEND_KEYS)
        accounts = json.loads(os.environ["CHAT_SERVICE_ACCOUNTS"]) if os.environ.get("CHAT_SERVICE_ACCOUNTS") else {
            "development": os.environ.get("CHAT_SERVICE_TOKEN", "")}
        model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        if args.provider == "openai":
            OpenAIScreenshotProvider(model=model)  # Fail before serving if operator credentials are missing.
        app = create_app(args.state_dir, accounts=accounts, provider=args.provider, model=model)
    except ValueError as exc:
        parser.error(str(exc))
    web.run_app(app, host=args.host, port=args.port, access_log=None, handler_cancellation=True)


if __name__ == "__main__":
    main()
