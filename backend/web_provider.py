"""Text or video-frame OpenAI calls with a shared public-demo allowance."""
from datetime import datetime, timezone
import json
from pathlib import Path

from backend.manual_provider import _SYSTEM_PROMPT, _COMMENT_SCHEMA, validate_context, MockManualProvider
from backend.personas import persona_instructions
from backend.providers import ProviderError
from backend.screenshot_provider import OpenAIScreenshotProvider, DEFAULT_MODEL, validate_screenshot
from backend.storage import atomic_json


WEB_DEMO_PROMPT = """웹 사전 영상 체험 지침:
- 아래 영상 정보는 게임의 맥락과 관찰 포인트이며 지금 그 사건이 벌어졌다는 증거가 아니다.
  현재 전달된 이미지에 보이는 상황을 우선한다. 이전·다음 장면이나 영상의 결말은 추측하지 않는다.
- 화면에서 가장 눈에 띄는 플레이 요소 하나를 골라 선택한 페르소나의 말투로 짧게 반응한다.
  교전, 조준, 엄폐, 위치 선정 등 플레이에 집중하고 배경 풍경·그래픽 감상은 피한다.
- 대회 해설, 화면 요약, 튜토리얼 대신 채팅창에 바로 쓸 5~30자 정도의 한마디를 쓴다.
  감탄사·ㅋㅋ·질문을 억지로 붙이지 않고, 페르소나가 훈수형이 아닌데 매번 지시하지 않는다.
- 한 장만으로 확인되지 않는 킬·명중·승리·실수·연속 동작·소리·선수의 의도를 단정하지 않는다.
  적이나 전투가 안 보이면 현재 확인되는 조준·엄폐 등으로 반응 대상을 좁힌다.
- 영상 번호, 이 지침, 화면을 분석한다는 설명을 채팅에 넣지 않는다.
"""

DEMO_VIDEO_PROMPTS = {
    "demo-01": """영상 맥락: 오버워치 팀 대전 중계의 1인칭 전투 화면.
조준 방향, 화면에 보이는 상대, 건물 모서리나 엄폐물, 거점 주변의 위치에 주목한다.
교전이 보이면 그 압박감에, 상대가 보이지 않으면 시야나 자리 잡기에 반응한다.
확실히 알아볼 수 없는 영웅·스킬 이름이나 전투 결과를 만들어내지 않는다.""",
    "demo-02": """영상 맥락: 발로란트 대회 중계의 저격총 조준 장면.
스코프, 조준선, 문이나 통로의 각도, 시야에 들어온 상대처럼 현재 보이는 단서를 본다.
상대가 안 보이는 대기 장면이라면 각을 지키는 긴장감에 짧게 반응한다.
저격 성공이나 헤드샷, 누가 먼저 나올지는 단정하지 않는다.""",
    "demo-03": """영상 맥락: 배틀그라운드 중계의 나무 주변 엄폐와 조준 장면.
나무 엄폐, 조준경, 노출된 시야, 회복 표시, 화면에 보이는 상대 중 실제로 보이는 요소를 고른다.
엄폐·회복·조준 중 현재 장면에 맞는 하나에 반응하며 보이지 않는 적 위치를 지어내지 않는다.
격발이나 조준만으로 명중·기절·처치·최종 승리를 단정하지 않는다.""",
}


def demo_video_instructions(video_id, screenshot):
    if video_id is None:
        return ""
    if screenshot is None or not isinstance(video_id, str) or video_id not in DEMO_VIDEO_PROMPTS:
        raise ValueError("등록된 체험 영상과 현재 장면이 필요합니다.")
    return "\n\n" + WEB_DEMO_PROMPT + "\n" + DEMO_VIDEO_PROMPTS[video_id]


class OpenAIWebProvider(OpenAIScreenshotProvider):
    supports_frames = True

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

    async def generate(self, context, screenshot=None, demo_video_id=None):
        payload = self.payload(context) if screenshot is None else super().payload(context, screenshot)
        payload["instructions"] += demo_video_instructions(demo_video_id, screenshot)
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


class MockWebProvider(MockManualProvider):
    supports_frames = True

    async def generate(self, context, screenshot=None, demo_video_id=None):
        demo_video_instructions(demo_video_id, screenshot)
        if screenshot is not None:
            validate_screenshot(screenshot)
        return await super().generate(context)
