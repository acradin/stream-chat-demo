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

## 데스크톱과 공통 디자인 자산

`public/brand/app-header.svg`와 `generate-face.svg`는 데스크톱에서 사용하는 Figma
원본 경로입니다. 헤더와 생성 버튼의 말풍선 캐릭터는 SVG로 표시합니다.
`public/personas/`는 같은 마스크·crop을 적용한 데스크톱의 3배 해상도 이미지이며,
온보딩과 설정 요약에서 사진 → 이름/설명 구조로 사용합니다. favicon도 헤더의
동일한 말풍선 외곽 경로를 사용하며 밝은 브라우저 탭에서도 보이도록 민트색입니다.

이번 변경은 표시용 이름·설명·이미지만 교체합니다. 기존 localStorage의 trait ID와
`mapsTo`, 대표 페르소나 선택 규칙, API 요청/응답, 단축키와 플랜 제한은 유지합니다.
이 브랜치의 백엔드는 기존 4개 persona ID를 받으므로 새 서버 persona를 추가하지 않습니다.

`npm test`는 저장된 선택 ID/서버 매핑 호환성과 모든 이미지·favicon 자산을 검사합니다.

검증 중 기존 Vite 프록시에서 `POST /api/trigger`가 `403 Origin rejected`로 거절되는
문제를 확인했습니다. `changeOrigin`으로 Host만 바뀌고 브라우저 Origin이 유지되어
`manual.py`의 동일 출처 검사와 충돌합니다. 이번 디자인 변경에서는 Vite/API/서버
보안 로직을 수정하지 않았으며, 실제 생성 성공 검증에는 이 기존 연결 문제 해결이 필요합니다.
