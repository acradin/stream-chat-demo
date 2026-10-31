# tiki 웹 프런트엔드

팀원의 `feat/demo-frontend` 브랜치(`49b0d51`)를 `frontend/`에서 이 폴더로 통합했습니다.
React 18 · TypeScript · Vite 5 · Tailwind CSS · Zustand를 사용합니다.

## 인터넷 접속

공개 AWS 주소: **https://tiki-chat.duckdns.org/**. 로그인 없이 예시 채팅을 체험하는 Mock 데모입니다.
실제 AI 호출과 치지직 전송은 데스크톱 앱에서 사용합니다. 서버는 브라우저별 쿠키로 데이터를 분리하고,
30분 비활성 세션을 만료시킵니다. 재배포하면 웹 데모 세션이 초기화되므로 페이지를 새로고침하세요.
웹 화면 디자인은 팀원 버전을 유지하며 데스크톱 Figma 변경과 독립적입니다.

## Windows에서 실행

프로젝트 루트의 첫 번째 터미널에서 로컬 Mock API를 실행합니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m apps.web --provider mock
```

두 번째 터미널에서는 다음 명령을 실행합니다.

```powershell
cd apps/web
npm.cmd ci
npm.cmd run dev
```

브라우저에서 **http://127.0.0.1:5173**을 엽니다. 온보딩에서 페르소나와 방송 설명을
선택한 뒤 생성 버튼 또는 기본 단축키 **Space**를 누르면 메인에 예시 채팅이 나타납니다.
설정에서 단축키를 바꿀 수 있으며 해당 브라우저 창에 포커스가 있을 때 동작합니다.
두 터미널에서 각각 `Ctrl+C`를 눌러 종료합니다.

macOS/Linux에서는 루트의 `bash apps/web/scripts/run-backend.sh`와 별도 터미널의
`bash apps/web/scripts/run-dev.sh`를 사용할 수 있습니다. `.venv`와 Node.js가 필요합니다.
Node.js 24에서 빌드와 통합 테스트를 검증했습니다.

## 연결 범위

- 현재 웹은 `python -m apps.web`의 텍스트 Mock/Gemini API를 사용합니다.
  OpenAI 스크린샷·실시간 관찰·치지직 전송은 기존 데스크톱 앱의 기능입니다.
- `start_desktop.cmd`의 네이티브 오버레이 실행 방식은 동일합니다. 이 React 화면은 웹 프런트입니다.
- API 키는 웹에 입력하지 않습니다. `apps/web/.env`에는 필요할 때 프록시 주소만 둡니다.
  기본값은 `API_TARGET=http://127.0.0.1:8765`이며 `.env.example`을 참고하세요.
- `/api/config`, `/api/trigger`, `/api/display`, `/api/export` 계약을 유지합니다.
  Vite는 자기 origin 요청만 백엔드 origin으로 변환하고 토큰 검증은 서버가 수행합니다.
- 사용량은 이번 웹 세션의 표시된 채팅 횟수입니다. Plus와 1,000회 한도는 팀원 시안의
  데모 UI이며 실제 구독/월간 사용량과 연결되어 있지 않습니다. 현재 API는 요청당 한 줄입니다.
- 기존 `manual_panel.html`, `demo/`, Python 서버는 보존했습니다.

## 검증 및 빌드

```powershell
npm.cmd run lint
npm.cmd run build
npm.cmd test
npm.cmd run preview
```

`npm test`는 임시 Mock Python 서버와 Vite를 실행하여 origin/토큰 거절, 채팅 생성·표시 확인,
컨텍스트 변경 시 폐기를 검사합니다. AI API와 방송 채팅 전송은 사용하지 않습니다.

빌드는 `apps/web/dist/`에 생성되고 미리보기는 **http://127.0.0.1:4173**입니다.
미리보기에도 로컬 API가 필요합니다. Vite 개발/미리보기 서버는 인터넷 배포용 서버가 아닙니다.
AWS 배포 패키지는 빌드된 `apps/web/dist` 파일과 공개 Mock API를 포함합니다. 배포 전 항상
`npm.cmd --prefix apps/web run build`를 실행합니다. 서비스 인증 토큰이나 AI API 키를 Vite 환경변수에 넣지 않습니다.
공개 웹 API와 데스크톱 API의 경계는 `backend/public_web.py`, 배포 절차는 루트 `AWS.md`에서 관리합니다.

Figma의 정확한 다중 Fill/Glass 배경 수정은 Figma 원본에서 관리합니다.
이 브랜치의 CSS는 팀원이 작성한 스타일이며 네이티브 앱/Figma와의 픽셀 일치를 주장하지 않습니다.
