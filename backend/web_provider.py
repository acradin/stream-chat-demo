"""Text-only OpenAI calls with a persistent, shared public-demo allowance."""
from datetime import datetime, timezone
import json
from pathlib import Path

from backend.manual_provider import _SYSTEM_PROMPT, _COMMENT_SCHEMA, validate_context
from backend.personas import persona_instructions
from backend.providers import ProviderError
from backend.screenshot_provider import OpenAIScreenshotProvider, DEFAULT_MODEL
from backend.storage import atomic_json


class OpenAIWebProvider(OpenAIScreenshotProvider):
    def __init__(self, usage_path, model=DEFAULT_MODEL, api_key=None, *, daily_limit=100,
                 today=lambda: datetime.now(timezone.utc).date().isoformat()):
        super().__init__(model, api_key)
        self.usage_path, self.daily_limit, self.today = Path(usage_path), daily_limit, today
        self.usage = json.loads(self.usage_path.read_text(encoding="utf-8")) if self.usage_path.exists() else {}
        self.active = 0

    def remaining(self):
        used = self.usage.get("requests", 0) if self.usage.get("date") == self.today() else 0
        return max(0, self.daily_limit-used)

    def payload(self, context):
        cleaned = validate_context(context)
        return {
            "model": self.model, "store": False, "max_output_tokens": 2048,
            "reasoning": {"effort": "low"},
            "instructions": _SYSTEM_PROMPT+"\n\n"+persona_instructions(cleaned["persona"]),
            "input": [{"role": "user", "content": [{"type": "input_text", "text": json.dumps(cleaned,ensure_ascii=False)}]}],
            "text": {"format": {"type": "json_schema", "name": "livestream_comment", "strict": True,
                                "schema": _COMMENT_SCHEMA}},
        }

    async def generate(self, context):
        payload = self.payload(context)
        if self.remaining() <= 0:
            raise ProviderError("오늘의 웹 AI 체험 한도를 모두 사용했습니다. 내일 다시 이용해주세요.")
        if self.active >= 2:
            raise ProviderError("현재 AI가 응답 중입니다. 잠시 후 다시 눌러주세요.")
        # Reserve before awaiting the provider; failures can incur usage too.
        usage = {"date": self.today(), "requests": self.daily_limit-self.remaining()+1}
        atomic_json(self.usage_path,usage)
        self.usage = usage
        self.active += 1
        try:
            return await self._generate_payload(payload)
        except Exception:
            raise ProviderError("채팅을 생성하지 못했습니다. 잠시 후 다시 눌러주세요.") from None
        finally:
            self.active -= 1
