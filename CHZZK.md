# 치지직 공식 API 연결

**운영자 CLI로 방송 계정을 한 번 인증한 뒤 데스크톱에서 출력 위치를 선택**할 수 있습니다. 기본값인 **앱에만 표시 (시연)**는 치지직 로그인 없이 생성 결과를 보여줍니다. **치지직에도 전송**을 선택하면 버튼 생성·실시간 관찰의 결과를 앱에 표시하고 방송에 추가 전송합니다. 공식 API를 사용하며 로그인 쿠키나 비공식 채팅 서버 접속은 사용하지 않습니다.

치지직 모드에서 방송 링크를 붙여 넣으면 채널 ID를 자동 추출합니다. **연결 확인** 후 표시된 대상 채널과 일치할 때 시작할 수 있습니다. 전송에는 `[AI] `를 붙이며 100자 제한에 맞춰 본문을 최대 95자로 보냅니다. 전송 결과도 앱 채팅창에 표시합니다. 실패·응답 유실 시 자동 재전송하지 않고 현재 배치나 관찰의 추가 전송을 중단하지만 생성 결과는 앱에 남깁니다.

현재 운영자의 치지직 연결은 기본 서비스 계정 `development`에만 허용합니다. 다른 서비스 계정에 연결하려면 운영자가 `CHZZK_SERVICE_ACCOUNT`를 그 계정 ID로 지정해야 합니다. 하나의 방송 인증을 다른 서비스 계정에 공유하지 않습니다. Mock 서버에서는 실제 치지직 전송을 하지 않습니다.

## 처음 연결

1. [치지직 개발자 센터](https://developers.chzzk.naver.com/)에서 애플리케이션을 등록합니다.
2. **유저 정보 조회**, **채팅 메시지 쓰기** 권한을 설정합니다.
3. 로그인 리디렉션 URL을 `http://localhost:8767/oauth/chzzk/callback`으로 등록합니다. 요청 URL과 등록값이 일치해야 합니다. [공식 인증 문서](https://chzzk.gitbook.io/chzzk/chzzk-api/authorization)
4. `backend/.env`의 다음 항목을 채웁니다. 기존 OpenAI 키와 서비스 토큰은 그대로 둡니다.

```dotenv
CHZZK_CLIENT_ID=개발자_앱의_Client_ID
CHZZK_CLIENT_SECRET=개발자_앱의_Client_Secret
CHZZK_CHANNEL_ID=테스트할_방송_채널의_32자리_ID_또는_방송_URL
CHZZK_REDIRECT_URI=http://localhost:8767/oauth/chzzk/callback
```

채널 ID는 `https://chzzk.naver.com/live/<채널 ID>` 또는 채널 URL 끝에서 확인합니다. 키와 Secret은 대화창이나 데스크톱 설정에 입력하지 않습니다.

`CHZZK_CHANNEL_ID`에도 전체 방송 URL을 그대로 넣을 수 있습니다. 앱의 방송 링크 입력은 전송 대상을 선택하는 기능이며, 백엔드의 키나 OAuth 인증을 변경하지 않습니다.

다른 방송 계정도 브라우저에서 이 개발자 앱에 접근 권한을 승인해야 합니다. 승인 자체에는 데스크톱 설치가 필요하지 않습니다. 아래 로컬 인증은 인증을 시작한 PC에서 승인합니다. 다른 PC의 승인은 아래의 공개 서버 인증을 사용합니다. 방송 계정 승인과 별도 봇 계정 소유 앱의 발신자 표시는 서로 다른 검증 항목입니다.

```powershell
.\.venv\Scripts\python.exe -m backend.chzzk_cli authorize
```

표시되는 인증 URL을 열어 **해당 방송을 소유한 계정**으로 로그인하고 권한을 승인합니다. 명령은 최대 5분 동안 로컬 콜백을 기다립니다. 콜백의 state를 검사하고, [유저 정보 조회 API](https://chzzk.gitbook.io/chzzk/chzzk-api/user)로 확인한 채널 ID가 설정과 같아야 토큰을 저장합니다. 다른 계정으로 로그인했다면 다시 인증합니다.

## 다른 PC에서 승인받기 (배포 후)

공개 HTTPS 서버의 `CHAT_PUBLIC_URL`을 설정하고 치지직 개발자 센터에 `<CHAT_PUBLIC_URL>/oauth/chzzk/callback`을 로그인 리디렉션 URL로 등록합니다. `CHAT_STATE_DIR`는 서버 재시작 후에도 보존되는 디스크 경로여야 합니다. 현재 구현은 서버 프로세스 하나를 전제로 합니다. Cloud Run·Vercel처럼 인스턴스가 교체되거나 여러 개 실행되는 환경은 인증 대기 상태, 토큰, 사용량과 잠금을 외부 저장소로 옮긴 다음 배포해야 합니다.

운영자 PC의 `backend/.env`에 배포 서버와 같은 `CHAT_SERVICE_TOKEN`이 설정된 상태에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m backend.chzzk_cli invite --service-url https://your-service.example.com --channel-url https://chzzk.naver.com/live/방송채널ID
```

출력 중 `authorization_url`만 상대방에게 전달합니다. 링크는 10분간 유효하며 새 링크를 발급하면 이전 링크는 무효입니다. 상대방이 요청한 방송을 소유한 계정으로 승인하면 서버가 채널을 확인하고 토큰을 저장합니다. 승인만으로 채팅을 보내지는 않습니다. 잘못된 계정·만료·중복 요청은 기존 연결을 덮어쓰지 않습니다. 서버 재시작 중이던 승인 링크는 다시 발급합니다.

데스크톱의 `CHAT_SERVICE_URL`을 같은 공개 서버로 설정하고 연결 상태를 확인합니다. 승인된 방송 URL을 입력한 후 치지직 전송 모드를 선택하면 됩니다. 원격 토큰은 `<CHAT_STATE_DIR>/<서비스 계정 SHA-256>/chzzk/tokens.json`에 저장하며 재시작 시 복원합니다. 로컬 `status`/`send` CLI는 기존 로컬 토큰을 사용하므로 원격 상태는 앱 또는 `GET /api/chzzk/status`로 확인합니다.

## 로컬 연결 확인과 한 건 전송

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

개발자 앱을 등록한 계정과 OAuth 권한을 승인하는 방송 계정은 구분합니다. 봇 계정으로 OAuth 인증하고 다른 방송 URL을 입력하는 방식은 이 구현에서 차단됩니다. 별도 봇 계정 소유 앱을 방송 계정이 승인했을 때 발신자가 봇 이름으로 표시되는지는 아직 우리 앱에서 검증하지 않았습니다. 현재 API 요청에는 발신자나 스트리머 표시를 바꾸는 필드가 없습니다.

## 저장과 오류

- `runs/chzzk/tokens.json`에 인증 토큰을 보관합니다. 이 폴더는 Git에서 제외됩니다. 앱의 사용자 설정이나 API 응답에 토큰을 넣지 않습니다.
- 만료가 가까운 Access Token은 Refresh Token으로 갱신하고 새 토큰을 저장합니다. 갱신 토큰은 일회용이므로 인증/전송 CLI를 동시에 여러 프로세스로 실행하지 않습니다. [공식 토큰 갱신 문서](https://chzzk.gitbook.io/chzzk/chzzk-api/authorization)
- 전송을 자동 재시도하지 않습니다. 타임아웃이나 응답 유실은 이미 게시됐을 가능성이 있으므로 방송 채팅에서 확인한 뒤 재전송합니다.
- 401은 재인증, 403은 앱 권한과 계정 확인, 429는 잠시 대기 후 확인이 필요합니다. 방송이 실제로 채팅을 받을 수 있는 상태인지도 확인합니다. [공식 API 응답 규격](https://chzzk.gitbook.io/chzzk/chzzk-api/tips)

개발자 앱 자격 증명과 사용자 승인이 아직 없으면 실제 전송 검증은 완료할 수 없습니다. 자동 테스트는 로컬 모의 HTTP 서버로 요청 형식·계정 불일치 차단·토큰 갱신·오류 비노출·중복 재시도 방지를 검증합니다.
