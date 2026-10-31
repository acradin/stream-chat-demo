# 개발 인수인계: 웹사이트와 데스크톱 앱

## 최신 변경 · 2026-11-01 데스크톱 디자인 / 랜딩과 영상 데모

- 공통 데스크톱 UI: 메인 상하 28px 여백, 로고와 생성 Canvas 겹침 제거, 채팅 뒤로가기 Figma `2088:1511` SVG(21px 버튼), 설정 설명란 8px 간격·카운터 우측 정렬을 반영했습니다. 설정 페르소나는 51×48 사진·이름·설명 행을 8px 간격으로 추가하며 창도 늘어납니다. 수정 화면은 진행 표시가 없고 **저장**으로 돌아옵니다. 선택 테두리는 카드와 동일한 8px 곡률을 사용합니다.
- 단축키 표시는 읽기 전용입니다. **변경** 후 실제 키를 누르는 녹화 경로만 지원하며 기존 등록·충돌 복구·저장을 유지합니다. Mac은 focusable document 스타일을 유지하면서 네이티브 제목 영역을 투명하게 하고 콘텐츠를 확장합니다. 실제 Mac 창 검수는 별도입니다.
- `feat/landing-page`의 `db05221`에서 랜딩을 선택 반영했습니다. `/`는 랜딩, `/demo/index.html`은 기존 React 앱, `/legacy-demo/index.html`은 초기 정적 데모입니다. 기존 웹의 페르소나 이미지·설명·설정 뒤로가기·API 동작을 유지합니다.
- 웹은 `public/assets/demo-videos/`의 H.264/AAC 영상 3개를 **동영상 1/2/3**으로 제공합니다. 명시적인 생성 동작 때 재생을 멈추고 현재 JPEG 한 장과 `demo_video_id`를 전송합니다. 서버는 영상별 상황 프롬프트와 기존 페르소나를 적용하고, 프레임을 실행 기록에 남기지 않습니다. 원본 영상은 변경하지 않았으며 배포 패키지도 MP4를 포함합니다.
- 웹 공개 API는 브라우저별 쿠키·Origin·CSRF, 30분 TTL, 세션별 한도와 서버 전체 UTC 하루 100회 AI 한도를 유지합니다. 실제 화면 캡처·실시간 관찰·치지직 전송은 데스크톱 전용입니다. AWS 자동 배포는 연결하지 않았고 이번 사용자 요청에 따라 수동 재배포합니다.
- 새 검증 증거와 배포 완료 여부는 `VALIDATION.md`의 최신 절을 기준으로 확인합니다. 아래 절은 이전 상태입니다.

## 이전 상태 · 2026-11-01 Figma v2 / Linux / 공개 웹

- 웹에는 `64e0c2b`의 페르소나 이미지 6종과 설명만 선택 반영했습니다. 이름·API 매핑·로고·생성 버튼은 기존 값을 유지합니다. 설정의 페르소나 수정 화면에서 `이전`은 첫 단계일 때 설정으로 돌아갑니다. 이 웹 변경과 아래 별도 채팅 창 변경은 로컬 개발 서버에서 확인했으며 AWS 재배포는 하지 않았습니다.
- 생성 버튼·단축키와 실시간 관찰 시작 시 별도 채팅 창을 자동으로 엽니다. 설정창을 닫거나 입력 내용을 초기화하지 않습니다. 캡처는 메인·설정·채팅 창 상태를 먼저 기록한 뒤 잠깐 숨기고 복원하며, 실패 시에도 복원합니다. 채팅 창 닫기는 앱 종료와 분리됩니다.
- 메인 하단의 **채팅 보기**와 **치지직 전송**이 별도 화면입니다. 후자에서 방송 링크 → 인증(브라우저 승인/앱 상태 확인) → 전송 스위치를 켭니다. 인증 시작 및 서비스 연결 변경 시 전송을 끄며 자동으로 다시 켜지 않습니다. 수동/실시간 전송 내역은 `delivery_log`, 생성 결과는 `chat_log`에 분리합니다. 현재 개발 PC의 무시된 `apps/desktop/.env`는 AWS 주소로 변경했고 기존 서비스 토큰을 유지했습니다.
- 아래 과거 배포 준비 기록보다 이 절이 우선합니다. AWS `us-east-1` 배포와 DuckDNS HTTPS 연결을 완료했습니다. `https://tiki-chat.duckdns.org/`는 최신 `feat/demo-frontend`를 통합한 React 웹이며 실제 OpenAI 텍스트 채팅을 생성합니다. 영상 분석·치지직 전송은 하지 않습니다. 데스크톱 API는 계속 서비스 토큰 인증을 요구합니다.
- 공개 웹은 `backend/public_web.py`: 메모리 세션, 30분 TTL, 최대 128개 세션/세션당 10회, 쿠키·Origin·CSRF 확인. `backend/web_provider.py`는 전체 방문자 UTC 하루 100회 한도를 디스크에 유지하며 실패 호출도 계산합니다. 키와 공급자 상세 오류는 브라우저에 노출하지 않습니다. `npm run build`를 `apps/web`에서 실행한 다음 AWS 패키지/배포를 진행합니다. GitHub에서 AWS로 자동 배포하는 워크플로는 없습니다.
- `prompt.zip`과 Figma v2의 메인 277×347, 설정 420×540(저장 버튼 추가), 시작 안내 5개 화면을 공통 Tk UI에 적용했습니다. 원본 SVG/PNG와 Pretendard 3개 굵기를 저장소에 포함합니다. 페르소나 다중 선택 시 인원·미리보기를 함께 갱신하며 메인 하단에 **채팅 보기** 버튼이 있습니다. 방송 링크는 설정의 **저장**으로 적용합니다. 단축키 녹화는 즉시 적용하고 Mac 기본값은 `Cmd+Shift+Space`입니다.
- Windows/Mac/Linux 공통 UI는 `figma_ui.py`, `onboarding.py`, `design_widgets.py`; OS 구현은 `window/`, `mac/`, `linux/`입니다. Linux는 X11 대상이며 WSL에서 빌드·가상 화면 검증을 완료했습니다. Wayland/WSLg 캡처·전역 단축키는 지원하지 않습니다. Mac 빌드는 GitHub의 macOS 러너를 사용합니다.
- 페르소나 6종을 Figma 선택창에 연결했고 기존 `dry_comic`도 유지합니다. 서버의 `backend/personas.py`가 기준입니다. 실제 GLASS 굴절과 외부 그림자는 Tk에서 근사하므로 픽셀 단위 동일성을 주장하지 않습니다.
- Windows 설치본과 Linux 묶음은 `dist/`, 디자인 값/자산 ZIP은 `dist/tiki-desktop-design.zip`입니다. 플랫폼별 검사·빌드 증거와 남은 수동 확인은 `VALIDATION.md`를 참고하세요.
- 다른 방송의 치지직 승인과 테스트 채팅 1건 전송을 완료했고 사용자가 실제 방송 채팅창에서 수신을 확인했습니다. 링크를 TXT 파일로 전달한 뒤 인증에 성공했습니다. 앞선 실패는 발급 URL과 콜백의 state 불일치였으며, 원문을 그대로 전달해야 합니다. 로컬 코드에서 알 수 없는 state와 실제 10분 만료의 안내를 구분했습니다. 서비스 재배포/재시작은 진행 중인 승인 state를 무효화하므로 인증 중 재배포하지 않습니다.
- Windows 배율 처리는 `display.py`와 실행 전 DPI 설정/EXE 매니페스트에 있습니다. 좌표·픽셀 글꼴·이미지를 함께 확대하며 고해상도 `@3x` PNG를 포함합니다. 100/125/150% 레이아웃 검사와 Windows 설치본 검사를 통과했습니다. 서로 다른 DPI 모니터 사이의 자동 재배치는 지원하지 않습니다.

## 과거 기록 · 2026-11-01 초기 Figma 적용 / 웹 병합 / AWS 준비

- Figma MCP 연결·편집 확인 완료. Screen/Main과 Settings 내부 Fill + Shadow의 검정 NORMAL Fill을 20%로 맞췄으며 별도 Glass SCREEN Fill도 20%입니다.
- 사용자 지정 적용 대상은 **데스크톱 앱**입니다. `apps/desktop/figma_ui.py`가 메인 원형 생성 버튼, 인원 슬라이더, 설정 화면을 제공합니다. 기능 제어는 `overlay.py`, 배경 레이어는 `panel.py`, 원본 자산은 `apps/assets/figma/`입니다. Tk의 실제 배경 굴절/그림자 제약은 자산 README에 명시했습니다.
- `start_desktop.cmd`로 새 UI를 실행합니다. 메인 톱니 → 설정, 사용 방식 → 캡처/실시간·출력 위치·페르소나·연결, 채팅 보기 → 생성 결과. 기본 단축키는 기존 Ctrl+Alt+Space이며 저장된 사용자 조합을 유지합니다.
- 팀원의 `origin/feat/demo-frontend`를 실제 merge commit `6b90e8e`로 병합하고 `frontend/` 대신 `apps/web/`로 옮겼습니다. 이번 Figma 포팅은 웹 스타일을 수정하지 않습니다.
- AWS는 배포 준비와 비밀 없는 로컬 패키지 생성까지만 완료했습니다. 기본 리전은 사용자가 선택한 북미 `us-east-1`. CLI 로그인·도메인 선택/DNS·실제 리소스 생성·TLS 검증은 아직 진행하지 않았습니다. 기존 .env 값은 유지했습니다.

## 2026-10-31 AWS 배포 준비 / 세션 재시작 메모

- 사용자는 새 AWS 계정에서 배포하기로 결정했고, 현재 요청 범위는 배포 준비입니다. 리소스 생성·키 업로드·실제 채팅 전송은 하지 않았습니다.
- `deploy/aws/`, `prepare_aws.cmd`, `AWS.md`: EC2 단일 서버 + Caddy HTTPS + SSM 관리 + 암호화된 EBS/SSM 설정. `package`는 로컬 전용, `deploy`는 명시적 계정 ID와 도메인이 필요합니다. 기존 .env와 데스크톱 연결 주소는 수정하지 않았습니다.
- 원격 승인: `backend/chzzk_remote.py`, `POST /api/chzzk/authorize`, 공개 HTTPS 콜백. 승인 state는 단일 프로세스 메모리, 토큰은 서비스 계정별 디스크에 저장합니다. Cloud Run/Vercel용 분산 저장 구조가 아닙니다.
- 당시에는 Figma 도구가 없었으나 2026-11-01 연결·편집·디자인 조회까지 확인했습니다. 위 최신 상태를 따릅니다.
- AWS 실제 실행 전 계정/도메인/CLI 로그인, CloudFormation·Linux 설치·TLS 검증이 남아 있습니다. 배포 도구 검증 결과는 VALIDATION.md에 기록합니다.

## 최신 변경: 폴더 분리와 스크린샷 오버레이

- 0.3.2 타이틀바 수정: Tkinter `iconbitmap`의 `bitmap`/`default`를 한 호출에 같이 넣지 않습니다. 기본 아이콘과 현재 창 아이콘을 각각 지정하며, 소스·설치본 검사에서 `WM_GETICON`으로 실제 작은/큰 아이콘 등록을 확인합니다.

- 0.3.2: `branding.py`가 Tk 창 아이콘 외에 Windows 창의 AppUserModelID·재실행 아이콘/이름/명령도 지정합니다. 소스 실행의 고정 바로가기는 절대 경로 `backend/desktop_demo.py`로 다시 실행됩니다. 설정 진입은 탭 하나로 통합했고 방송 링크 입력을 항상 표시합니다. `hotkey.py`는 사용자 지정 조합을 정규화하며, 새 조합 등록 성공 후 기존 조합을 해제하여 충돌 시 기존 설정을 보존합니다.

- 데스크톱 출력은 `app`(기본 시연) / `chzzk`로 전환합니다. 방송 URL 추출은 `backend/chzzk_target.py`, 서버 전송은 `backend/chat_delivery.py`에 있습니다. `/api/chzzk/status`로 연결 채널을 확인하고 생성·실시간 시작 요청에 선택적 `destination`, `channel_id`를 전달합니다. 기존 요청은 앱 표시로 동작합니다. 전송 오류는 생성 결과와 분리하며 자동 재전송하지 않습니다. 치지직 연결은 `CHZZK_SERVICE_ACCOUNT`(기본 `development`) 하나에만 허용하고 토큰은 계속 서버에 둡니다.

- 앱 브랜드 원본은 `apps/assets/logo.svg`이며 전달받은 SVG를 수정 없이 보관합니다. 같은 폴더의 ICO·PNG·파비콘을 데스크톱과 웹에서 사용하고, 설치본 0.3.2에도 원본과 런타임 이미지를 포함합니다. 재생성: `apps/desktop/packaging/make_icons.ps1`. 개인 다운로드 경로를 참조하지 않습니다.

- Windows 설치본은 `build_desktop.cmd`로 빌드합니다. `apps/desktop/packaging/`에 PyInstaller·Inno Setup 설정이 있고 결과는 `dist/`입니다. 설치본은 사용자 폴더에 설정을 저장하며, 첫 실행의 서비스 연결 창에서 기존 데스크톱 `.env`를 가져올 수 있습니다. 백엔드·AI 키는 포함하지 않습니다. [INSTALLER.md](INSTALLER.md) 참조.
- 페르소나의 단일 정의는 `backend/personas.py`입니다. 4종의 말투·예문과 공통 자연스러운 채팅 지침을 OpenAI/Gemini 양쪽에 적용합니다. 데스크톱에 선택한 성격 설명을 추가했습니다.
- 치지직 공식 API의 인증·토큰 갱신·계정 채널 확인·채팅 한 건 전송은 `backend/chzzk.py`, 운영자 CLI는 `backend/chzzk_cli.py`입니다. [CHZZK.md](CHZZK.md) 참조. 오버레이의 버튼 생성과 실시간 반응을 연결했으며, 실제 치지직 전송에는 앱 등록과 방송 계정 승인이 필요합니다. 기존 계정의 CLI 전송은 사용자가 방송 채팅창에서도 확인했습니다. 별도 봇 계정 소유 앱의 발신자 표시는 아직 실험하지 않았습니다.

- 데스크톱은 `apps/desktop/`입니다. `python -m apps.desktop` 또는 `start_desktop.cmd`로 실행합니다. 버튼·전역 단축키로 주 모니터를 촬영하고 **OpenAI `gpt-6-astra`**로 생성합니다.
- 웹은 `apps/web/`입니다. 기존 텍스트 Gemini/Mock 서버는 `python -m apps.web`, 정적 UI는 `apps/web/legacy-demo/`입니다. 웹에 스크린샷 업로드 API를 새로 노출하지 않았습니다.
- 공통 생성·검증 코드는 `backend/`입니다. `server.py`는 인증·계정별 API, `chat_service.py`는 생성·서버 집계, `screenshot_provider.py`는 OpenAI 이미지 요청을 담당합니다. `OPENAI_API_KEY`와 `OPENAI_MODEL`은 `backend/.env` 또는 서버 환경변수에만 설정합니다. 앱은 별도의 `apps/desktop/.env`에서 서비스 연결 정보만 읽습니다. 사용자 화면에는 AI 키·모델·공급자 토큰 수를 표시하지 않습니다.
- 데스크톱의 `service_client.py`는 우리 서버만 호출합니다. 사용량은 월별 생성 요청·생성된 채팅·누적 채팅 수이며 서버 기록을 조회합니다. 현재 개발 인증은 계정별 서비스 토큰이고 로그인·요금제는 미구현입니다. [BACKEND.md](BACKEND.md)에 연결 방법과 API 계약이 있습니다.
- 자동 영상 실험은 `experiments/`로 분리했습니다. `python -m experiments.replay`로 실행하며 합성 샘플도 해당 폴더 안에 있습니다.
- 디자이너는 `apps/desktop/overlay.py`, 웹 담당자는 `apps/web/`, AI 생성 담당자는 `backend/`를 우선 작업합니다. 공유 페르소나·입력 계약 변경은 함께 검토합니다.
- 상세 실행·키 설정·저장 경계는 [DESKTOP.md](DESKTOP.md)를 확인하세요. 아래 내용은 기존 **웹 텍스트 데모 계약과 당시 인수인계 기록**입니다. 데스크톱 미구현이라는 아래의 과거 설명은 새 오버레이에 적용되지 않습니다.

현재 제품 흐름은 **페르소나 선택 → 방송 정보 입력(선택) → 원하는 순간에 버튼 클릭 → 한국어 채팅 한 줄 표시**입니다. 방송자가 매번 반응 종류를 지정하지 않습니다. 팀원은 웹사이트를, 제품 개발자는 데스크톱 앱을 이어서 개발하는 방향입니다. 이 저장소는 그 출발점인 데모와 생성 코드를 담고 있습니다.

## 1. 먼저 확인할 것

- [README](README.md): 실행 방법과 사용법.
- [검증 기록](VALIDATION.md): 실제로 확인한 범위와 미검증 항목. 실제 Gemini API 지연이나 드립 품질이 검증됐다고 간주하지 마세요.
- `apps/web/legacy-demo/index.html`: API 없이 화면 흐름을 확인하는 정적 데모.
- `apps/web/server.py` + `apps/web/manual_panel.html`: 로컬 HTTP 서버에 연결되는 패널. Mock 또는 Gemini를 선택해 실행합니다.

GitHub 저장소는 비공개이며, 협업자 초대나 웹사이트 외부 배포는 완료하지 않았습니다. 현재 제공되는 것은 저장소 소스와 로컬 실행 경로입니다.

## 2. 파일 지도와 재사용 경계

| 파일 | 역할 | 이어서 작업할 때 |
|---|---|---|
| `apps/web/legacy-demo/index.html`, `apps/web/legacy-demo/sample.mp4` | 브라우저 안에서만 동작하는 체험 화면과 합성 영상 | 웹 UI 참고용. 예시 문장·650ms 대기를 실제 생성 로직으로 오해하지 않기 |
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
python -m http.server 8000 --directory apps/web/legacy-demo
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
