# StreamCast AI — Frontend (React + Vite)

해커톤 발표용 데스크톱 프론트엔드입니다. 기존 Python 백엔드(`manual.py`)와 API 계약을
그대로 사용하며, 백엔드 코드는 수정하지 않습니다.

## 스택

React 18 · TypeScript · Vite 5 · Tailwind CSS v3 · Zustand · Framer Motion · Lucide React

## 사전 준비: 백엔드 실행

프로젝트 루트에서 Mock(또는 Gemini) 서버를 먼저 띄웁니다.

```bash
# 루트에서
source .venv/bin/activate
python manual.py --provider mock --output runs/manual_mock
# -> http://127.0.0.1:8765
```

## 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
# -> http://localhost:5173
```

브라우저에서 **http://localhost:5173** 접속. Vite dev 서버가 `/api/*` 요청을
`127.0.0.1:8765`(백엔드)로 프록시하므로, 브라우저에는 same-origin 으로 보여
백엔드의 loopback/토큰 제약을 그대로 만족합니다.

백엔드 포트/주소가 다르면 `.env` 에 지정합니다.

```
VITE_API_TARGET=http://127.0.0.1:8765
```

## 빌드

```bash
npm run build     # 타입체크(tsc -b) + vite build -> dist/
npm run preview   # 빌드 결과 미리보기
```

## 설계 메모

- API 계약: `GET /api/config`, `POST /api/trigger`(5키), `POST /api/display`(6키),
  `GET /api/export`. 응답의 업무 상태(busy/cooldown/expired/duplicate/error)는
  HTTP 200 으로도 오므로 `response.ok` 가 아니라 본문 `status` 로 분기합니다.
- 영상은 브라우저에서만 재생되며 업로드되지 않습니다. 모델에는 영상/프레임/오디오를
  전달하지 않습니다. 영상 시점/세션 ID 는 로깅 목적입니다.
- 자동 생성·자동 재시도·Mock 자동 전환은 없습니다. 버튼/Space 로만 생성합니다.
