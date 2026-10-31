# 운영자 백엔드 설정

치지직 개발자 앱 인증과 채팅 한 건 전송은 [CHZZK.md](CHZZK.md)에 있습니다. 해당 자격 증명도 `backend/.env`에만 설정합니다.

운영자의 **`OPENAI_API_KEY`는 `backend/.env`에 넣습니다.** `python -m backend.server`가 시작할 때 이 파일을 자동으로 읽습니다. 데스크톱 앱·사용자 설정·배포 클라이언트에 AI 키를 넣지 않습니다. 호스팅 환경에서는 해당 서비스의 환경변수/시크릿 설정도 사용할 수 있습니다.

기본 모델은 `gpt-6-astra`이고 운영자가 서버의 `OPENAI_MODEL`로 변경할 수 있습니다. 사용자는 모델이나 AI 키를 전송하지 않습니다. 키는 [OpenAI API 키 페이지](https://platform.openai.com/api-keys)에서 발급합니다. [공식 키 설정 안내](https://developers.openai.com/api/docs/quickstart), [GPT-6 Astra 문서](https://developers.openai.com/api/docs/models/gpt-6-astra)도 참고할 수 있습니다.

데스크톱 실시간 화면 모드는 별도의 `REALTIME_MODEL`을 사용하며 기본은 `gpt-realtime-2.1`입니다. 키는 같은 `OPENAI_API_KEY`입니다. 모델 설정은 운영자의 `backend/.env`에만 두며 설치본에는 포함하지 않습니다. `experiments/realtime_video/.env`는 개발 실험에만 적용되고 데스크톱 서비스에는 적용되지 않습니다.

## 로컬 개발 서버

프로젝트 루트에서 실행합니다. 처음 준비하는 컴퓨터는 `py -m venv .venv` 후 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`를 실행합니다.

이 작업 환경에는 `backend/.env`와 `apps/desktop/.env`를 준비했습니다. 두 파일의 개발용 서비스 토큰도 맞춰 두었으므로 **`backend/.env`의 `OPENAI_API_KEY=` 뒤에 발급받은 키만 넣고 저장**하면 됩니다.

```dotenv
OPENAI_API_KEY=여기에_실제_API_키
OPENAI_MODEL=gpt-6-astra
```

서버를 실행합니다. 키를 수정한 뒤에는 서버를 다시 시작합니다.

현재 프로젝트에서는 `start_desktop.cmd`를 더블클릭하면 로컬 서버가 없을 때 백그라운드에서 시작하고 인증 확인 후 오버레이를 엽니다. 기존 서버가 있으면 그대로 사용합니다. 앱을 닫아도 로컬 백엔드는 유지됩니다. 아래 명령은 서버를 직접 관리할 때 사용합니다.

```powershell
.\.venv\Scripts\python.exe -m backend.server
```

새로 받은 저장소에는 실제 `.env`가 포함되지 않습니다. `backend/.env.example`을 `backend/.env`로, `apps/desktop/.env.example`을 `apps/desktop/.env`로 복사합니다. 서버 파일에 AI 키를 넣고 두 파일의 `CHAT_SERVICE_TOKEN`을 같은 무작위 값으로 설정합니다. 토큰은 `.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"`로 만들 수 있습니다. 서비스 토큰은 AI 키와 별개의 계정 인증 수단이며, 단일 토큰 설정은 `development` 계정으로 집계합니다.

앱은 `apps/desktop/.env`에서 `CHAT_SERVICE_URL`과 `CHAT_SERVICE_TOKEN`만 읽습니다. 기본 주소는 `http://127.0.0.1:8766`입니다. 별도 터미널에서 실행하거나 `start_desktop.cmd`를 더블클릭합니다.

```powershell
.\.venv\Scripts\python.exe -m apps.desktop
```

실제 AI 없이 검증할 때는 서버 명령을 다음으로 바꿉니다. 서비스 인증 설정은 동일하고 OpenAI 키는 필요 없습니다.

```powershell
.\.venv\Scripts\python.exe -m backend.server --provider mock --state-dir runs/service_mock
```

`.env`는 UTF-8 형식이며 `KEY=value`, 작은따옴표/큰따옴표, 주석을 지원합니다. 여러 줄 값·변수 치환·쉘 명령 실행은 지원하지 않습니다. **이미 설정된 터미널/시스템 환경변수가 `.env`보다 우선**합니다. 이전 터미널에서 테스트 값을 설정했다면 새 터미널을 사용하거나 해당 환경변수를 제거합니다. 파일 위치는 실행 위치와 관계없이 위의 고정 경로이며, 데스크톱은 `backend/.env`를 읽지 않습니다. 실제 `.env` 두 파일은 Git에서 제외되고 `.env.example`만 공유됩니다.

서버는 기본 `127.0.0.1:8766`에서 동작합니다. 앱은 원격 주소에 HTTPS를 요구합니다. 원격 배포 시 `CHAT_SERVICE_URL`을 배포된 HTTPS 주소로 설정합니다. 실제 외부 배포는 이번 작업에 포함하지 않았습니다.

## 계정과 사용량

여러 개발 계정은 서버의 `CHAT_SERVICE_ACCOUNTS` 환경변수로 `{"account-a":"token-a...","account-b":"token-b..."}` 형태의 JSON을 제공합니다. 각 토큰은 서로 다르고 32자 이상의 무작위 값이어야 합니다. 이 설정이 있으면 서버의 단일 `CHAT_SERVICE_TOKEN`보다 우선합니다. 토큰은 서버의 인증 계정을 결정하며, 클라이언트가 요청 본문으로 계정 ID를 지정할 수 없습니다.

현재는 계정별 고정 토큰을 쓰는 개발용 인증 경계입니다. 로그인·토큰 발급/갱신·결제·요금제는 미구현입니다. 실제 사용자 배포에서는 로그인 세션의 계정 ID를 이 서버의 계정 경계에 연결해야 하며, 운영자의 공용 토큰을 앱에 내장하지 않습니다.

| 사용자에게 표시하는 항목 | 집계 기준 |
|---|---|
| 이번 달 생성 요청 | 버튼 생성 배치 1회 또는 실시간 AI 분석 1회 |
| 이번 달 생성된 채팅 | 이번 달에 성공한 채팅 1줄당 1개 |
| 누적 생성된 채팅 | 해당 계정의 전체 성공 채팅 수 |

한국 시간 월별 집계입니다. 인원 3명 중 2명 성공이면 요청 1회, 채팅 2개입니다. 실패·중단된 채팅은 생성된 채팅 수에 포함하지 않습니다. 월 경계에 걸친 요청은 시작한 달에 요청 수를, 결과가 완료된 달에 채팅 수를 기록합니다. Mock 기록은 실제 생성 기록과 분리됩니다. 기존 토큰 카운터만 있는 기록에서는 과거 월별 요청 수를 추정하지 않습니다.

실시간 모드의 WAIT·오래된 반응·중복은 요청 수에만 포함하고 생성 채팅으로 세지 않습니다. 내부 `silent` 카운터로 정상적인 무응답을 실패와 구분합니다. 기존 기록에서 이 필드가 없으면 0으로 읽습니다. 실시간 제공자 토큰은 현재 정밀 계측하지 않아 운영자용 `unmetered`에 표시하며, 사용자 화면에는 노출하지 않습니다.

`runs/service/<계정 ID의 SHA-256>/usage.json`에 저장합니다. 이 파일은 운영자 전용이며 공급자 토큰 통계도 내부 진단용으로 남깁니다. 사용자 API에는 서비스 사용량만 반환합니다. 이미지·API 키·채팅 문장은 이 파일에 저장하지 않습니다. 한 상태 디렉터리는 서버 프로세스 하나가 사용합니다. 다중 서버 배포 전에는 트랜잭션을 지원하는 공유 데이터베이스로 교체해야 합니다.

## 서비스 API

`/api/` 경로는 `Authorization: Bearer <서비스 계정 토큰>`이 필요합니다. 공개 `GET /healthz`는 상태만 반환합니다. `CHAT_PUBLIC_URL`을 설정하면 공개 `GET /oauth/chzzk/callback`이 일회용 승인 state를 검증합니다.

- `GET /api/usage`: `period`, `timezone`, `is_demo`, `generation_requests`, `generated_chats`, `total_generated_chats` 반환.
- `GET /api/chzzk/status`: `connected`, `channelId`, `channelName`, `message`를 반환합니다. 채팅은 전송하지 않으며, 인증 토큰은 반환하지 않습니다.
- `POST /api/chzzk/authorize`: 공개 주소를 설정한 서버에서 `{"channel_url":"방송 URL 또는 ID"}`를 받아 10분간 유효한 승인 URL을 발급합니다. `CHZZK_SERVICE_ACCOUNT`에만 허용하며 새 승인이 완료되면 그 계정의 연결 방송을 변경합니다. [원격 승인 안내](CHZZK.md#다른-pc에서-승인받기-배포-후)
- `POST /api/chat/generate`: `personas` (1~5개 persona ID), `context` (최대 1,000자), `screenshot` (최대 5 MB JPEG의 Base64)을 받습니다. 선택적 `destination`은 `app`(기본값) 또는 `chzzk`이며, `chzzk`이면 `channel_id`가 필요합니다. 결과는 `status`, `lines`, `usage`를 포함합니다. 전송한 줄에는 `delivery`가 추가됩니다. `model`, `api_key`, `account` 같은 필드는 거절합니다.
- `GET /api/chat/realtime`: 인증된 WebSocket. 시작 메시지는 `type: start`, `personas`, `context`, `interval` (3/5/10), `duration` (30/60/120)이며 선택적 `destination`, `channel_id`의 의미는 버튼 생성과 같습니다. 준비 응답 뒤 `type: frame`, 증가하는 `sequence`, 1280px 이하 JPEG의 Base64 `jpeg`를 초당 1장 보냅니다. 서버는 `ready`, `frame`, `decision`, `stopped`, `error`를 반환합니다. 치지직 모드에서는 로컬 채팅용 `decision` 뒤에 `delivery` 이벤트(`participant`, `persona`, `delivery`)도 반환합니다. 중지는 `{"type":"stop"}` 또는 연결 종료입니다. 음성·모델·키 필드는 거절합니다.

`delivery`는 `status` (`sent` / `failed` / `skipped`), 사용자용 `message`, 성공 시 `messageId`를 포함합니다. 전송 실패는 생성 성공·서비스 사용량을 취소하지 않습니다. 응답을 잃은 메시지를 중복 게시하지 않도록 자동 재전송하지 않으며, 첫 실패 이후 현재 배치·실시간 세션의 추가 전송을 생략합니다. 앱 표시는 유지됩니다.

치지직 전송은 운영자가 인증해 둔 방송과 `channel_id`가 일치해야 합니다. 방송 URL도 받을 수 있지만 URL 입력만으로 다른 방송의 권한을 얻지는 않습니다. 연결은 `CHZZK_SERVICE_ACCOUNT`(기본 `development`) 한 서비스 계정에만 허용합니다. `destination` 생략 또는 `app` 선택 시 치지직 API를 호출하지 않으며, Mock 서버에서는 실제 전송을 차단합니다. 자격 증명과 OAuth 설정은 [CHZZK.md](CHZZK.md)를 참조하세요.

수동 생성과 실시간 세션은 계정별 잠금을 공유합니다. 실시간에서 인원별 페르소나가 순환하며 최근 6장을 판단합니다. 실제 채팅 이후 8초 동안은 추가 분석 호출을 생략하고, 오래되거나 중복된 반응은 표시하지 않습니다. 최대 120초 뒤 종료하며 중단 시 진행 중 작업·제공자 연결을 정리합니다.

모델 오류는 사용자용 메시지로 바꿔 반환하고, 공급자 상세 오류·토큰·비용은 내보내지 않습니다. 자동 재시도는 없습니다. 생성에 성공했으나 연결이 끊겨 결과를 받지 못하면 서버 사용량에는 남을 수 있으므로 사용량을 다시 조회합니다.

서비스 연결 종료 시 진행 중 요청 취소를 지원합니다. 서버의 `handler_cancellation` 설정은 [aiohttp 연결 종료 처리 문서](https://docs.aiohttp.org/en/stable/web_advanced.html#peer-disconnection)를 따릅니다. 이미 공급자에게 전송된 호출의 비용 취소를 보장하는 기능은 아닙니다.
