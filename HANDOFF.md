# 개발 인수인계: 웹사이트와 데스크톱 앱

## 최신 변경: 폴더 분리와 스크린샷 오버레이

- Windows 설치본은 `build_desktop.cmd`로 빌드합니다. `apps/desktop/packaging/`에 PyInstaller·Inno Setup 설정이 있고 결과는 `dist/`입니다. 설치본은 사용자 폴더에 설정을 저장하며, 첫 실행의 서비스 연결 창에서 기존 데스크톱 `.env`를 가져올 수 있습니다. 백엔드·AI 키는 포함하지 않습니다. [INSTALLER.md](INSTALLER.md) 참조.
- 페르소나의 단일 정의는 `backend/personas.py`입니다. 4종의 말투·예문과 공통 자연스러운 채팅 지침을 OpenAI/Gemini 양쪽에 적용합니다. 데스크톱에 선택한 성격 설명을 추가했습니다.
- 치지직 공식 API의 인증·토큰 갱신·계정 채널 확인·채팅 한 건 전송은 `backend/chzzk.py`, 운영자 CLI는 `backend/chzzk_cli.py`입니다. [CHZZK.md](CHZZK.md) 참조. 오버레이 자동 게시는 아직 연결하지 않았으며, 실제 치지직 전송은 앱 등록과 방송 계정 승인이 필요합니다.

- 데스크톱은 `apps/desktop/`입니다. `python -m apps.desktop` 또는 `start_desktop.cmd`로 실행합니다. 버튼·전역 단축키로 주 모니터를 촬영하고 **OpenAI `gpt-6-astra`**로 생성합니다.
- 웹은 `apps/web/`입니다. 기존 텍스트 Gemini/Mock 서버는 `python -m apps.web`, 정적 UI는 `apps/web/demo/`입니다. 웹에 스크린샷 업로드 API를 새로 노출하지 않았습니다.
- 공통 생성·검증 코드는 `backend/`입니다. `server.py`는 인증·계정별 API, `chat_service.py`는 생성·서버 집계, `screenshot_provider.py`는 OpenAI 이미지 요청을 담당합니다. `OPENAI_API_KEY`와 `OPENAI_MODEL`은 `backend/.env` 또는 서버 환경변수에만 설정합니다. 앱은 별도의 `apps/desktop/.env`에서 서비스 연결 정보만 읽습니다. 사용자 화면에는 AI 키·모델·공급자 토큰 수를 표시하지 않습니다.
- 데스크톱의 `service_client.py`는 우리 서버만 호출합니다. 사용량은 월별 생성 요청·생성된 채팅·누적 채팅 수이며 서버 기록을 조회합니다. 현재 개발 인증은 계정별 서비스 토큰이고 로그인·요금제는 미구현입니다. [BACKEND.md](BACKEND.md)에 연결 방법과 API 계약이 있습니다.
- 자동 영상 실험은 `experiments/`로 분리했습니다. `python -m experiments.replay`로 실행하며 합성 샘플도 해당 폴더 안에 있습니다.
- 디자이너는 `apps/desktop/overlay.py`, 웹 담당자는 `apps/web/`, AI 생성 담당자는 `backend/`를 우선 작업합니다. 공유 페르소나·입력 계약 변경은 함께 검토합니다.
- 상세 실행·키 설정·저장 경계는 [DESKTOP.md](DESKTOP.md)를 확인하세요. 아래 내용은 기존 **웹 텍스트 데모 계약과 당시 인수인계 기록**입니다. 데스크톱 미구현이라는 아래의 과거 설명은 새 오버레이에 적용되지 않습니다.

현재 제품 흐름은 **페르소나 선택 → 방송 정보 입력(선택) → 원하는 순간에 버튼 클릭 → 한국어 채팅 한 줄 표시**입니다. 방송자가 매번 반응 종류를 지정하지 않습니다. 팀원은 웹사이트를, 제품 개발자는 데스크톱 앱을 이어서 개발하는 방향입니다. 이 저장소는 그 출발점인 데모와 생성 코드를 담고 있습니다.

## 1. 먼저 확인할 것

- [README](README.md): 실행 방법과 사용법.
- [검증 기록](VALIDATION.md): 실제로 확인한 범위와 미검증 항목. 실제 Gemini API 지연이나 드립 품질이 검증됐다고 간주하지 마세요.
- `apps/web/demo/index.html`: API 없이 화면 흐름을 확인하는 정적 데모.
- `apps/web/server.py` + `apps/web/manual_panel.html`: 로컬 HTTP 서버에 연결되는 패널. Mock 또는 Gemini를 선택해 실행합니다.

GitHub 저장소는 비공개이며, 협업자 초대나 웹사이트 외부 배포는 완료하지 않았습니다. 현재 제공되는 것은 저장소 소스와 로컬 실행 경로입니다.

## 2. 파일 지도와 재사용 경계

| 파일 | 역할 | 이어서 작업할 때 |
|---|---|---|
| `apps/web/demo/index.html`, `apps/web/demo/sample.mp4` | 브라우저 안에서만 동작하는 체험 화면과 합성 영상 | 웹 UI 참고용. 예시 문장·650ms 대기를 실제 생성 로직으로 오해하지 않기 |
| `apps/web/manual_panel.html` | 실제 로컬 API를 호출하는 웹 패널 | 페르소나·방송 정보 입력, 생성 버튼, 결과 표시와 표시 확인 요청을 참고 |
| `backend/manual_provider.py` | 페르소나 정의, 텍스트 입력·출력 검증, Gemini/Mock 생성 | 웹 서비스와 데스크톱에서 공유할 생성 기능의 시작점 |
| `apps/web/server.py` | `aiohttp` 로컬 어댑터, 단일 세션, 동시 입력 제어, 표시 확인, 로그 | 로컬 API 계약과 요청 생명주기 참고. 운영용 다중 사용자 서버는 아님 |
| `backend/providers.py` | Gemini REST 전송 및 기존 영상 실험의 provider | 수동 provider도 이 파일의 전송 코드를 재사용하므로 함께 확인 |
| `tests/test_manual*.py` | 수동 생성·HTTP 흐름 검사 | 공통 계약을 바꿀 때 함께 수정 |
| `experiments/replay.py`, `experiments/media.py`, `experiments/artifacts.py`, `experiments/make_fixture.py`, `experiments/samples/` | 이전 자동 영상 분석·합성 샘플 실험 | 현재 버튼 제품의 필수 실행 경로가 아님 |

아직 공통 코드를 별도 패키지로 추출하지 않았습니다. 데스크톱은 Python 생성 모듈을 직접 재사용하거나 로컬 HTTP 어댑터를 호출할 수 있지만, 프레임워크·패키징 방식은 선택하지 않았습니다. 우선 아래의 입력 계약을 웹과 데스크톱에서 함께 유지하면 됩니다.

## 3. 빠른 실행

저장소를 받은 폴더에서 실행합니다. Python 3.10 이상이 필요합니다.

**화면만 확인:**

```bash
python -m http.server 8000 --directory apps/web/demo
```

같은 컴퓨터에서 `http://127.0.0.1:8000`을 엽니다. 페르소나별 준비된 문장을 표시합니다. 입력한 방송 정보는 체험 기록에 보관하지만 의미를 해석하지 않습니다.

**API와 표시 흐름 확인:**

```bash
python -m pip install -r requirements.txt
python -m apps.web --provider mock
```

같은 컴퓨터에서 `http://127.0.0.1:8765`를 엽니다. Mock의 기본 0.2초 대기도 인위적인 값입니다. 실제 생성은 서버 환경변수에 `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY`를 설정한 뒤 `python -m apps.web --provider gemini`로 실행합니다. 키 설정 방법은 README에 있습니다. 브라우저 입력창에 API 키를 넣지 않습니다.

```bash
python -m unittest discover -s tests -v
```

## 4. 웹·데스크톱 공통 생성 계약

### 페르소나와 방송 정보

| ID | 표시 이름 |
|---|---|
| `witty_friend` | 장난꾸러기 친구 — 기본값 |
| `warm_supporter` | 다정한 응원단 |
| `hype_commentator` | 과몰입 해설러 |
| `dry_comic` | 덤덤한 드립러 |

정식 정의는 `backend/manual_provider.py`의 `PERSONAS`입니다. `channel_context`는 최대 1,000자의 텍스트이며 빈 문자열도 허용합니다. 방송 주제·별명·배경·목표 등을 적어두고 여러 번의 버튼 입력에 재사용합니다. 버튼을 누른 순간의 선택값과 텍스트를 한 요청으로 고정합니다.

생성 모듈이 받는 키는 정확히 `request_id`, `persona`, `channel_context`, `recent_comments`입니다. `recent_comments`는 최대 8개의 이미 표시된 채팅이고, 각 문장은 100자 이하입니다. HTTP 어댑터가 이를 조립하므로 브라우저는 최근 채팅을 직접 보낼 필요가 없습니다. 영상·오디오·재생 시점은 모델에 전달하지 않습니다.

### 로컬 HTTP API

기본 주소는 `http://127.0.0.1:8765`입니다. 현재 서버는 loopback 호스트와 같은 origin만 허용합니다. 모든 POST에는 `Content-Type: application/json`과 `/api/config`에서 받은 `X-Demo-Token` 헤더가 필요합니다. 이 토큰은 로컬 세션 보호용이며 사용자 로그인 기능이 아닙니다.

| 메서드·경로 | 응답·동작 |
|---|---|
| `GET /` | `apps/web/manual_panel.html` 제공 |
| `GET /api/config` | `provider`, `model`, `is_mock`, `session_token`, `cooldown_s`, `max_age_s`, `default_persona`, `personas` 반환. `personas` 항목은 `{id, name, description}` |
| `POST /api/trigger` | 아래 입력을 받아 생성 결과 또는 거절 상태 반환 |
| `POST /api/display` | 클라이언트의 표시·폐기 결과를 기록 |
| `GET /api/export` | 현재 세션 기록을 `application/x-ndjson`으로 다운로드. 파일명 `manual_events.jsonl` |

`POST /api/trigger`에는 다음 **5개 키만** 보냅니다. 예시의 방송 정보는 합성 입력입니다.

```json
{
  "client_request_id": "example-click-1",
  "persona": "witty_friend",
  "channel_context": "별명은 민트. 오늘은 공포 게임 첫 플레이. 편하게 이야기하는 방송.",
  "clicked_video_s": null,
  "video_session_id": null
}
```

`client_request_id`는 클릭마다 새로 만드는 128자 이하의 비어 있지 않은 ID입니다. 영상이 없으면 마지막 두 필드는 모두 `null`입니다. 영상이 있으면 0 이상 유한수인 재생 위치와 128자 이하의 영상 세션 ID를 함께 보냅니다. 상황·반응 종류·별도 말투 필드는 없습니다. 알 수 없는 필드도 거부합니다.

생성 완료 응답의 공통 필드는 `status`, `request_id`, `comment`, `api_latency_ms`, `error`입니다. `status`가 `ready`일 때만 표시 후보로 처리합니다. `busy`, `cooldown`, `expired`, `duplicate`, `error` 상태도 처리해야 하며, `cooldown`에는 `retry_after_s`가 포함됩니다. 거절 응답은 필드가 일부 생략될 수 있습니다. 이 업무 상태들은 HTTP 200으로도 반환되므로 `response.ok`만 확인해서는 안 됩니다. 입력 오류는 HTTP 400, origin·토큰 등 로컬 접근 거절은 HTTP 403입니다.

현재 한 세션에서 생성은 한 번에 하나만 수행합니다. 동시 요청은 대기열에 넣지 않습니다. 기본 간격은 1초, 결과 유효 시간은 8초, 생성 타임아웃은 20초입니다. 같은 `client_request_id`로 재요청해도 추가 생성하지 않으며, 준비된 결과는 같은 ID로 반환합니다. 자동 재시도나 실제 모델 실패 시 Mock 전환은 없습니다.

`POST /api/display`에는 다음 **6개 키만** 보냅니다. 아래 시간은 형식 설명용 예시이며 측정 결과가 아닙니다.

```json
{
  "request_id": "m000001",
  "button_to_display_ms": 725.4,
  "displayed_video_s": null,
  "video_session_id": null,
  "status": "displayed",
  "reason": ""
}
```

표시 전 결과가 만료됐거나 영상 위치가 바뀌었거나 페이지가 숨겨졌다면 `status: "discarded"`, 두 시간 필드는 `null`, `reason`은 폐기 사유로 보냅니다. 영상 세션 ID는 해당 요청의 값을 유지합니다. 실제 표시한 경우 재생 위치·세션 ID는 클릭한 영상과 일치해야 합니다. 응답은 `{status, request_id}`이며, 중복 표시 확인은 기존 상태를 반환합니다.

`ready`는 서버가 문장을 준비했다는 뜻입니다. 표시 확인 전에는 `button_to_display_ms`가 `null`입니다. 웹 클라이언트는 버튼 입력부터 DOM 삽입까지 동일한 브라우저 시계로 측정합니다. 이는 물리적인 화면 표시나 방송 플랫폼 전송까지의 시간이 아닙니다. 네이티브 화면을 만들면 측정 기준을 명시하고, 방송 플랫폼 전송 확인은 별도 수치로 추가해야 합니다.

`--output` 폴더에는 `run.json`(요약·설정, 현재 `schema_version: 3`), `events.jsonl`(전체 요청·표시 기록), `events.csv`가 저장됩니다. 버전 3은 기존 상황·말투 입력을 `persona`와 `channel_context`로 바꾼 기록입니다. 이전 실행 결과를 읽는 도구는 이 차이를 구분해야 합니다. 방송 정보도 기록에 포함됩니다. 세션·기록은 현재 단일 프로세스와 파일에 기반하며 사용자별 영구 저장 서비스는 아직 없습니다.

## 5. 구현된 범위와 남은 범위

**구현됨:** 네 페르소나, 선택형 방송 정보 입력, 버튼·페이지 안 Space 단축키, 텍스트 생성 provider, 중복·동시 입력 제어, 늦거나 유효하지 않은 응답 억제, AI/Mock 표시, 로컬 영상 재생, 지연·결과 기록.

**미구현:** 데스크톱 창·트레이·전역 단축키·설치 파일·자동 업데이트, 운영용 사용자 인증·요금제·API 서비스, 설정의 계정별 저장, 방송 플랫폼 채팅 전송, 영상·음성 인식, 배포된 웹사이트. 실제 모델 인증을 사용한 품질·지연 검증도 별도로 필요합니다.

## 6. 다음 개발 순서

| 담당 | 첫 작업 | 완료 기준 |
|---|---|---|
| 웹사이트 | 정적 체험 화면을 기반으로 실제 생성 API 연결 | 선택한 페르소나·방송 정보로 요청하고 성공·거절·오류·폐기를 구분해 표시 |
| 웹 서비스 | 운영용 인증, 사용자별 세션·설정, 서버 측 모델 호출과 사용량 제한 설계 | 로컬 단일 세션 어댑터를 그대로 공개하지 않고 사용자별 접근·기록을 분리 |
| 데스크톱 앱 | 대상 OS와 프레임워크 선택 후 버튼·전역 단축키·트레이·로컬 설정·결과 미리보기 구현 | 다른 프로그램을 사용하면서도 명시적인 입력으로 한 번만 생성하고 상태를 확인 |
| 공통 | 페르소나·입력 계약 유지, 실제 모델 품질·지연 평가, 방송 플랫폼 전송 대상 결정 | 웹과 데스크톱의 결과가 같은 계약을 따르고 생성 지연과 전송 지연을 구분 |

데스크톱 개발의 첫 단계에서는 현재 수동 생성 흐름을 제품 UI에 연결하면 됩니다. 화면 캡처나 자동 영상 판단을 다시 도입할 필요는 없습니다. 제품용 패키징과 외부 배포는 이 인수인계 범위에서 진행하지 않았습니다.
# 2026-10-31 데스크톱 모드 통합

현재 사용자 진입점은 설치형 네이티브 오버레이다. `start_desktop.cmd`는 개발 PC의 백엔드를 필요할 때 숨겨 시작하고 앱을 연다. 브라우저 localhost 안내를 주 사용법으로 제시하지 않는다. 설치본은 `dist/StreamChat-Setup-0.2.0-x64.exe`; 두 모드 선택·설치·실행 안내는 `DESKTOP.md`, `INSTALLER.md`에 있다.

- 버튼 캡처: 주 모니터 1장 → 기존 GPT-6 서비스.
- 실시간 화면: 명시적으로 선택한 창을 초당 1장 → 인증된 `/api/chat/realtime` → OpenAI Realtime. 기본 5초 분석 / 60초 종료, 최대 120초. 음성 없음, 인원별 페르소나 순환, 중지·재시작·버튼 모드 복귀 지원.
- API 키는 `backend/.env` 전용. 데스크톱 모델 지정·키 입력 없음. 패키징은 서버/provider와 운영자 실행기를 제외한다.
- 공통 provider는 `backend/realtime_provider.py`. 함수 호출 결과만 파싱한다. 실험 폴더의 provider는 재사용 어댑터이며 비교 코드는 그대로 남긴다.
- 실제 비용 실험과 출력 오류 수정 결과는 `experiments/realtime_video/EXPERIMENT_RESULTS.md` 참고. Mini·프레임 축소는 누락이 있어 기본으로 강제하지 않았다.
- 로그인·치지직 실전 발송·서버 배포·음성 추가는 보류. 사용자 직접 UI 테스트 예정이며 실제 개인 화면을 자동으로 촬영하지 않았다.
