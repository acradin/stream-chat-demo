# tiki 웹 프런트엔드

팀원의 `feat/demo-frontend` 브랜치(`49b0d51`)를 `frontend/`에서 이 폴더로 통합했습니다.
React 18 · TypeScript · Vite 5 · Tailwind CSS · Zustand를 사용합니다.

## 랜딩페이지와 데모

`feat/landing-page`의 `db05221`에서 랜딩 HTML·글꼴·미리보기 자산을 가져왔습니다.
`src/`의 현재 React 앱은 그대로 유지하며, 랜딩의 모든 데모 버튼은 `/demo/index.html`로 연결합니다.

- `/`: 새 서비스 소개 랜딩페이지.
- `/demo/index.html`: 현재 React 데모. 기존 페르소나 이미지·설명, 설정 뒤로가기, 요금제와 API 연결을 유지합니다.
- `/legacy-demo/index.html`: API 없이 실행하던 초기 정적 데모를 보존한 경로.

## 인터넷 접속

공개 AWS 주소: **https://tiki-chat.duckdns.org/**. 랜딩의 데모 버튼은 **https://tiki-chat.duckdns.org/demo/index.html**로 연결합니다.
데모에서는 로그인 없이 사전 영상 3개의 현재 장면으로 AI 채팅을 생성합니다.
사용자 화면 캡처·실시간 관찰·치지직 전송은 데스크톱 앱에서 사용합니다. 서버는 브라우저별 쿠키로 데이터를 분리하고,
30분 비활성 세션을 만료시킵니다. 재배포하면 웹 데모 세션이 초기화되므로 페이지를 새로고침하세요.
웹 화면 디자인은 팀원 버전을 유지하며 데스크톱 Figma 변경과 독립적입니다.

## Windows에서 실행

프로젝트 루트의 첫 번째 터미널에서 로컬 OpenAI API를 실행합니다.
`backend/.env`의 `OPENAI_API_KEY`를 자동으로 읽습니다. `OPENAI_MODEL`도 이 파일에서 지정할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m apps.web --provider openai
```

두 번째 터미널에서는 다음 명령을 실행합니다.

```powershell
cd apps/web
npm.cmd ci
npm.cmd run dev
```

브라우저에서 **http://127.0.0.1:5173**을 열고 **데모 체험하기**를 누릅니다.
체험 화면에 바로 접속하려면 **http://127.0.0.1:5173/demo/index.html**을 엽니다. 온보딩에서 페르소나와 방송 설명을
선택한 뒤 사전 영상을 재생합니다. 원하는 장면에서 생성 버튼 또는 기본 단축키 **Space**를 누르면
영상이 멈추고 그 장면을 보고 만든 AI 채팅이 나타납니다. 영상 컨트롤에 포커스가 있으면 Space는 재생/일시정지로 동작합니다.
설정에서 단축키를 바꿀 수 있으며 해당 브라우저 창에 포커스가 있을 때 동작합니다.
두 터미널에서 각각 `Ctrl+C`를 눌러 종료합니다.

AI 호출 없는 동작 확인은 `--provider mock`으로 실행합니다. Mock 채팅은 장면을 분석하지 않는 예시입니다.

## 사전 영상 체험

- 영상 파일은 `public/assets/demo-videos/`, 목록은 `src/lib/demoVideos.ts`에서 관리합니다.
  제공받은 영상 3개를 `동영상 1`, `동영상 2`, `동영상 3`으로 선택해서 체험할 수 있습니다.
- 요청에는 `demo_video_id`를 함께 보내고, 서버의 `backend/web_provider.py`에서 영상별 프롬프트를 적용합니다.
  1번은 교전·위치 선정, 2번은 조준·대기, 3번은 엄폐·회복·조준에 집중합니다.
  현재 이미지에 보이는 요소를 우선하며 기존 페르소나와 사용자 방송 설명을 유지합니다.
- 클릭할 때 현재 장면 한 장만 최대 960px JPEG로 전송합니다. 영상 재생·탐색 자체는 AI를 호출하지 않으며 음성도 전송하지 않습니다.
- AI 응답을 기다리는 동안 영상을 바꾸거나 탐색하면 이전 장면의 응답은 표시하지 않습니다.
- 원본 HEVC 영상은 브라우저 호환 H.264/AAC MP4로 변환했습니다. 배포 빌드에 영상과 포스터가 포함됩니다.
- 이미지 요청에도 기존 세션 인증·동시 요청 제한·하루 100회 웹 AI 호출 한도가 적용됩니다.
  프레임 원본이나 Base64는 실행 기록과 내보내기에 남기지 않습니다.

macOS/Linux에서는 루트의 `bash apps/web/scripts/run-backend.sh`와 별도 터미널의
`bash apps/web/scripts/run-dev.sh`를 사용할 수 있습니다. `.venv`와 Node.js가 필요합니다.
Node.js 24에서 빌드와 통합 테스트를 검증했습니다.

## 연결 범위

- 로컬 개발 웹은 `python -m apps.web`의 OpenAI 영상 장면/텍스트 API를 사용합니다.
  Mock 모드와 기존 Gemini 텍스트 모드도 유지합니다. 실시간 관찰·치지직 전송은 데스크톱 앱의 기능입니다.
- `start_desktop.cmd`의 네이티브 오버레이 실행 방식은 동일합니다. 이 React 화면은 웹 프런트입니다.
- API 키는 웹에 입력하지 않습니다. `apps/web/.env`에는 필요할 때 프록시 주소만 둡니다.
  기본값은 `API_TARGET=http://127.0.0.1:8765`이며 `.env.example`을 참고하세요.
- `/api/config`, `/api/trigger`, `/api/display`, `/api/export` 계약을 유지합니다.
  Vite는 자기 origin 요청만 백엔드 origin으로 변환하고 토큰 검증은 서버가 수행합니다.
- 사용량은 이번 웹 세션의 표시된 채팅 횟수입니다. Plus와 1,000회 한도는 팀원 시안의
  데모 UI이며 실제 구독/월간 사용량과 연결되어 있지 않습니다. 현재 API는 요청당 한 줄입니다.
- 기존 정적 `demo/`는 `legacy-demo/`로 옮겼고 `manual_panel.html`과 Python 서버는 보존했습니다.

## 검증 및 빌드

```powershell
npm.cmd run lint
npm.cmd run build
npm.cmd test
npm.cmd run preview
```

`npm test`는 임시 Mock Python 서버와 Vite를 실행하여 랜딩→React 데모 진입, origin/토큰 거절,
채팅 생성·표시 확인, 컨텍스트 변경 시 폐기를 검사합니다. 개발 서버와 충돌하지 않도록 테스트 포트를 따로 할당합니다.
AI API와 방송 채팅 전송은 사용하지 않습니다.

빌드는 `apps/web/dist/`에 생성되고 미리보기는 **http://127.0.0.1:4173**입니다.
미리보기에도 로컬 API가 필요합니다. Vite 개발/미리보기 서버는 인터넷 배포용 서버가 아닙니다.
AWS 배포 패키지는 빌드된 `apps/web/dist` 파일과 공개 웹 API를 포함합니다. 배포 전 항상
`npm.cmd --prefix apps/web run build`를 실행합니다. 서비스 인증 토큰이나 AI API 키를 Vite 환경변수에 넣지 않습니다.
공개 웹 API와 데스크톱 API의 경계는 `backend/public_web.py`, 배포 절차는 루트 `AWS.md`에서 관리합니다.

Figma의 정확한 다중 Fill/Glass 배경 수정은 Figma 원본에서 관리합니다.
이 브랜치의 CSS는 팀원이 작성한 스타일이며 네이티브 앱/Figma와의 픽셀 일치를 주장하지 않습니다.
