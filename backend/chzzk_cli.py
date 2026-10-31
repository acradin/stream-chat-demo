"""Operator CLI: authorize once, inspect identity, explicitly send one AI chat."""

import argparse
import asyncio
import hmac
import json
import os
import secrets
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout, web

from backend.chzzk import ChzzkClient, ChzzkConfig, ChzzkError, credential
from backend.chzzk_remote import public_origin
from backend.chzzk_target import parse_channel_id
from backend.env import BACKEND_ENV, BACKEND_KEYS, load_env_file


async def create_invite(service_url, channel_url):
    origin = public_origin(service_url)
    target = parse_channel_id(channel_url)
    load_env_file(BACKEND_ENV, BACKEND_KEYS)
    token = credential(os.environ.get("CHAT_SERVICE_TOKEN", ""), "CHAT_SERVICE_TOKEN")
    try:
        async with ClientSession(timeout=ClientTimeout(total=20), trust_env=True) as session:
            async with session.post(origin + "/api/chzzk/authorize", json={"channel_url": target},
                                    headers={"Authorization": "Bearer " + token}, allow_redirects=False) as response:
                if response.status != 200:
                    raise ChzzkError("승인 링크를 발급하지 못했습니다. 서버 주소와 서비스 인증 설정을 확인해주세요.")
                try:
                    raw = await response.content.readexactly(8193)
                except asyncio.IncompleteReadError as exc:
                    raw = exc.partial
                if len(raw) > 8192:
                    raise ChzzkError("서버 응답이 너무 큽니다.")
                result = json.loads(raw)
                if not isinstance(result, dict) or not isinstance(result.get("authorization_url"), str):
                    raise ChzzkError("서버의 승인 링크 응답을 확인해주세요.")
                return result
    except (ClientError, asyncio.TimeoutError, ValueError) as exc:
        if isinstance(exc, ChzzkError):
            raise
        raise ChzzkError("승인 서버에 연결하지 못했습니다.") from None


def authorization_app(client, state, completed):
    redirect = urlsplit(client.config.redirect_uri)
    claimed = False

    async def callback(request):
        nonlocal claimed
        if request.host != redirect.netloc:
            return web.Response(status=400, text="Invalid callback host")
        supplied = request.query.get("state", "")
        if not hmac.compare_digest(supplied.encode(), state.encode()):
            return web.Response(status=400, text="Invalid authorization state")
        if claimed:
            return web.Response(status=409, text="Authorization already handled")
        claimed = True
        try:
            if request.query.get("error") or not request.query.get("code"):
                raise ChzzkError("치지직 인증이 취소되었거나 승인되지 않았습니다.")
            identity = await client.authorize(request.query["code"], state)
            completed.set_result(identity)
            return web.Response(text="치지직 연결 완료. 이 창을 닫고 앱으로 돌아가세요.",
                                content_type="text/plain", headers={"Cache-Control": "no-store"})
        except (ChzzkError, OSError) as exc:
            completed.set_exception(ChzzkError(str(exc)) if isinstance(exc, ChzzkError)
                                    else ChzzkError("치지직 인증 정보를 저장하지 못했습니다."))
            return web.Response(status=400, text="연결하지 못했습니다. 터미널의 안내를 확인해주세요.", content_type="text/plain")

    app = web.Application()
    app.router.add_get(redirect.path, callback)
    return app


async def authorize(client):
    state = secrets.token_urlsafe(32)
    redirect = urlsplit(client.config.redirect_uri)
    if redirect.scheme != "http" or redirect.hostname not in ("localhost", "127.0.0.1"):
        raise ChzzkError("공개 HTTPS 인증은 서버의 /api/chzzk/authorize에서 승인 링크를 발급해주세요.")
    completed = asyncio.get_running_loop().create_future()
    app = authorization_app(client, state, completed)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    try:
        await web.TCPSite(runner, "127.0.0.1", redirect.port).start()
        print("아래 주소에서 방송 계정으로 로그인하고 권한을 승인해주세요 (5분 안에 완료).", flush=True)
        print(client.config.authorization_url(state), flush=True)
        return await asyncio.wait_for(asyncio.shield(completed), timeout=300)
    except asyncio.TimeoutError:
        raise ChzzkError("인증 대기 시간이 끝났습니다. authorize를 다시 실행해주세요.") from None
    finally:
        await runner.cleanup()
        if completed.done() and not completed.cancelled():
            completed.exception()  # Consume an error if shutdown raced with the callback.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("authorize")
    commands.add_parser("status")
    invite = commands.add_parser("invite", help="다른 PC에서 열 수 있는 일회용 승인 링크 발급")
    invite.add_argument("--service-url", required=True)
    invite.add_argument("--channel-url", required=True)
    send = commands.add_parser("send")
    send.add_argument("--message", required=True, help="100자 이내, [AI] 표시를 포함한 채팅 한 줄")
    args = parser.parse_args()
    try:
        if args.command == "invite":
            result = asyncio.run(create_invite(args.service_url, args.channel_url))
            print(json.dumps(result, ensure_ascii=False))
            return
        client = ChzzkClient(ChzzkConfig.from_env())
        action = authorize(client) if args.command == "authorize" else client.status() if args.command == "status" else client.send(args.message)
        result = asyncio.run(action)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError) as exc:
        parser.exit(1, (str(exc) if isinstance(exc, ValueError) else "치지직 로컬 연결 또는 저장 경로를 확인해주세요.") + "\n")


if __name__ == "__main__":
    main()
