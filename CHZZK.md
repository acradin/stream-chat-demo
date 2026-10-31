# 치지직 공식 API 연결

현재는 **운영자 CLI로 방송 계정을 인증하고 채팅 한 건을 명시적으로 전송**하는 단계입니다. 오버레이의 생성 버튼을 눌렀다고 방송에 자동 게시하지 않습니다. 공식 API를 사용하며, 로그인 쿠키나 비공식 채팅 서버 접속은 사용하지 않습니다.

## 처음 연결

1. [치지직 개발자 센터](https://developers.chzzk.naver.com/)에서 애플리케이션을 등록합니다.
2. **유저 정보 조회**, **채팅 메시지 쓰기** 권한을 설정합니다.
3. 로그인 리디렉션 URL을 `http://localhost:8767/oauth/chzzk/callback`으로 등록합니다. 요청 URL과 등록값이 일치해야 합니다. [공식 인증 문서](https://chzzk.gitbook.io/chzzk/chzzk-api/authorization)
4. `backend/.env`의 다음 항목을 채웁니다. 기존 OpenAI 키와 서비스 토큰은 그대로 둡니다.

```dotenv
CHZZK_CLIENT_ID=개발자_앱의_Client_ID
CHZZK_CLIENT_SECRET=개발자_앱의_Client_Secret
CHZZK_CHANNEL_ID=테스트할_방송_채널의_32자리_ID
CHZZK_REDIRECT_URI=http://localhost:8767/oauth/chzzk/callback
```

채널 ID는 `https://chzzk.naver.com/live/<채널 ID>` 또는 채널 URL 끝에서 확인합니다. 키와 Secret은 대화창이나 데스크톱 설정에 입력하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m backend.chzzk_cli authorize
```

표시되는 인증 URL을 열어 **해당 방송을 소유한 계정**으로 로그인하고 권한을 승인합니다. 명령은 최대 5분 동안 로컬 콜백을 기다립니다. 콜백의 state를 검사하고, [유저 정보 조회 API](https://chzzk.gitbook.io/chzzk/chzzk-api/user)로 확인한 채널 ID가 설정과 같아야 토큰을 저장합니다. 다른 계정으로 로그인했다면 다시 인증합니다.

## 확인과 한 건 전송

인증 상태와 채널을 확인합니다. 이 명령은 채팅을 보내지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m backend.chzzk_cli status
```

아래 명령은 실제 방송 채팅에 메시지를 한 건 보냅니다.

```powershell
.\.venv\Scripts\python.exe -m backend.chzzk_cli send --message "[AI] 채팅 연동 테스트입니다."
```

`POST /open/v1/chats/send`에 메시지를 전달하고 반환된 `messageId`를 성공 증거로 출력합니다. 공식 전송 API의 메시지 길이는 최대 100자이며, 이 프로젝트는 `[AI] ` 표시를 포함한 한 줄만 허용합니다. [공식 채팅 문서](https://chzzk.gitbook.io/chzzk/chzzk-api/chat)

전송 전에 매번 인증 계정의 채널을 확인합니다. 공식 전송 요청에는 임의의 대상 채널 ID를 넣는 필드가 없으므로 이 구현은 인증한 방송 계정과 설정된 채널이 일치하는 경우에만 사용합니다. 페르소나는 생성 말투를 바꾸며 치지직 계정을 여러 개 만들거나 다른 사람으로 로그인하는 기능은 아닙니다.

## 저장과 오류

- `runs/chzzk/tokens.json`에 인증 토큰을 보관합니다. 이 폴더는 Git에서 제외됩니다. 앱의 사용자 설정이나 API 응답에 토큰을 넣지 않습니다.
- 만료가 가까운 Access Token은 Refresh Token으로 갱신하고 새 토큰을 저장합니다. 갱신 토큰은 일회용이므로 인증/전송 CLI를 동시에 여러 프로세스로 실행하지 않습니다. [공식 토큰 갱신 문서](https://chzzk.gitbook.io/chzzk/chzzk-api/authorization)
- 전송을 자동 재시도하지 않습니다. 타임아웃이나 응답 유실은 이미 게시됐을 가능성이 있으므로 방송 채팅에서 확인한 뒤 재전송합니다.
- 401은 재인증, 403은 앱 권한과 계정 확인, 429는 잠시 대기 후 확인이 필요합니다. 방송이 실제로 채팅을 받을 수 있는 상태인지도 확인합니다. [공식 API 응답 규격](https://chzzk.gitbook.io/chzzk/chzzk-api/tips)

개발자 앱 자격 증명과 사용자 승인이 아직 없으면 실제 전송 검증은 완료할 수 없습니다. 자동 테스트는 로컬 모의 HTTP 서버로 요청 형식·계정 불일치 차단·토큰 갱신·오류 비노출·중복 재시도 방지를 검증합니다.
