"""Operator CLI: authorize once, inspect identity, explicitly send one AI chat."""

import argparse
import asyncio
import hmac
import json
import secrets
from urllib.parse import urlsplit

from aiohttp import web

from backend.chzzk import ChzzkClient, ChzzkConfig, ChzzkError


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
    send = commands.add_parser("send")
    send.add_argument("--message", required=True, help="100자 이내, [AI] 표시를 포함한 채팅 한 줄")
    args = parser.parse_args()
    try:
        client = ChzzkClient(ChzzkConfig.from_env())
        action = authorize(client) if args.command == "authorize" else client.status() if args.command == "status" else client.send(args.message)
        result = asyncio.run(action)
        print(json.dumps(result, ensure_ascii=False))
    except (ChzzkError, OSError) as exc:
        parser.exit(1, (str(exc) if isinstance(exc, ChzzkError) else "치지직 로컬 연결 또는 저장 경로를 확인해주세요.") + "\n")


if __name__ == "__main__":
    main()
