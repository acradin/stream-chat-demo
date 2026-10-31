"""Operator-owned CHZZK delivery. App-only generation never enters this module's API calls."""

import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path

from backend.chzzk import ChzzkClient, ChzzkConfig, ChzzkError
from backend.chzzk_target import parse_channel_id


class ChatDelivery:
    def __init__(self, account, *, enabled=True, client_factory=ChzzkClient, state_dir=None):
        self.account, self.enabled = account, enabled
        self.client_factory = client_factory
        self.client = None
        self.lock = asyncio.Lock()
        self.connection_path = Path(state_dir) / "chzzk" / "tokens.json" if state_dir is not None else None

    def _check_enabled(self):
        if not self.enabled or self.account != os.environ.get("CHZZK_SERVICE_ACCOUNT", "development"):
            raise ChzzkError("이 서비스 계정에는 치지직 전송이 연결되지 않았습니다.")

    def _client(self):
        self._check_enabled()
        if self.client is None:
            config = ChzzkConfig.from_env()
            if self.connection_path is not None and self.connection_path.exists():
                saved = json.loads(self.connection_path.read_text(encoding="utf-8"))
                config = replace(config, channel_id=saved["channel_id"])
                self.client = self.client_factory(config, token_path=self.connection_path)
            else:
                self.client = self.client_factory(config)
        return self.client

    def authorization_client(self, target, redirect_uri):
        self._check_enabled()
        if self.connection_path is None:
            raise ChzzkError("원격 인증 저장 경로가 설정되지 않았습니다.")
        config = replace(ChzzkConfig.from_env(), channel_id=parse_channel_id(target), redirect_uri=redirect_uri)
        return self.client_factory(config, token_path=self.connection_path)

    async def status(self):
        try:
            async with asyncio.timeout(25), self.lock:
                identity = await self._client().status()
            return {"connected": True, **identity, "message": "치지직 연결 완료"}
        except Exception:
            return {"connected": False, "channelId": "", "channelName": "",
                    "message": "치지직 연결이 필요합니다. 앱에만 표시는 로그인 없이 사용할 수 있습니다."}

    async def send(self, comment, target):
        # A failed/uncertain send is never retried. The caller retains the local chat.
        try:
            message = "[AI] " + comment.strip()[:95]
            async with asyncio.timeout(25), self.lock:
                client = self._client()
                if parse_channel_id(target) != client.config.channel_id:
                    raise ChzzkError("선택한 방송과 연결된 치지직 채널이 다릅니다.")
                result = await client.send(message)
            return {"status": "sent", "message": "치지직 전송 완료", "messageId": result["messageId"]}
        except Exception:
            return {"status": "failed", "message": "치지직 전송 확인 필요 · 방송 채팅을 확인해주세요. 자동 재전송하지 않습니다.",
                    "messageId": ""}
