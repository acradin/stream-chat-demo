# 검증 기록

## 2026-11-01 · Windows 배율/이미지/글자 겹침 및 치지직 승인

- Windows 프로세스가 DPI 비인식 상태에서 전체 비트맵을 확대하던 경로를 수정했습니다. 소스 실행은 Tk 창 생성 전에 시스템 DPI 인식을 설정하고 설치본은 EXE 매니페스트에도 선언합니다. 레이아웃·픽셀 글꼴·이미지를 같은 배율로 변환하며 SVG에서 생성한 3배 PNG를 포함합니다.
- 100/125/150% 배율에서 배경 크기, 인원 슬라이더 좌표, 설정 페르소나 설명과 버튼 간격, 시작 안내의 6개 페르소나 카드 글자 경계를 검사했습니다. 전체 Python 테스트 137개: 133개 통과, Linux 전용 4개 건너뜀. 실제 AI 호출 없이 검증했습니다.
- Windows 설치본 재빌드 및 비밀/백엔드 제외 검사 통과. `runs/installer_smoke_20261101-040820-917/report.json`: 임시 설치, frozen 실행, 업그레이드와 설정 유지, 제거와 설정 보존 통과. 서로 다른 DPI 모니터 간 이동 시 자동 재배치는 미지원입니다.
- 치지직 실패 콜백의 state가 발급한 원문과 달랐습니다. 원문 URL을 TXT로 제공한 뒤 승인에 성공했고, 사용자 요청에 따라 테스트 채팅 1건을 전송했습니다. API 성공 응답과 사용자의 방송 채팅창 수신 확인을 모두 확보했습니다. 추가 채팅은 보내지 않았습니다.
- 알 수 없는/처리된 state와 실제 10분 만료의 오류 문구를 분리했습니다. state 비교는 계속 대소문자를 구분하며, 변형된 state가 원래 요청을 소모하지 않는 검사와 만료 검사를 포함한 원격 승인 테스트 9개를 통과했습니다.

## 2026-11-01 · OS 분리, Pretendard, 디자인 추출, AWS 배포

- Windows 코드를 `apps/desktop/window`, macOS 코드를 `apps/desktop/mac`으로 분리하고 UI·서비스 통신은 공통으로 유지했습니다. 전체 Python 테스트 **123개 통과**. 이후 AWS 배포·설치 경로·Mac 계약 검사 **23개 재검증 통과**.
- Mac 캡처 권한, 창 식별, 콜백 오류·시간 초과, 이미지 크기, 주 모니터 선택, 단축키와 저장 경로는 모의 네이티브 API로 검사했습니다. 실제 Mac 실행·권한 대화상자·DMG 빌드·서명은 아직 검증하지 않았습니다. 관련 코드 push 및 수동 실행용 GitHub Actions 워크플로로 Apple Silicon/Intel 빌드를 구성했습니다. 실행 결과는 해당 커밋의 Actions 기록으로 확인합니다.
- 공식 Pretendard 1.3.9 Regular/Bold TTF와 OFL 라이선스를 자산에 포함했습니다. Windows 소스와 설치본에서 프로세스 전용 글꼴 로딩 및 실제 Tk 글꼴 패밀리·굵기를 확인했습니다. `runs/platform_font_self_test.json` 통과.
- Windows 설치본 `dist/StreamChat-Setup-0.4.0-x64.exe` 재빌드 및 비밀/백엔드 제외 검사 통과. `runs/installer_smoke_20261101-013025-348/report.json`: 격리 설치, frozen 실행, 업그레이드 설정 유지, 제거와 설정 보존 모두 통과. 실제 AI 호출·방송 채팅 전송·화면 캡처는 하지 않았습니다.
- `design/desktop/`에 디자인 설명, JSON 전체 값, 참조 CSS를 생성했습니다. 12개 화면 상태와 26개 자산을 포함한 `dist/tiki-desktop-design.zip`의 ZIP 무결성 및 허용 파일 목록을 확인했습니다. Tk의 실제 굴절·외부 그림자 미지원 차이는 문서에 명시했습니다.
- AWS `stream-chat-demo` 스택 생성 완료, EC2 `i-0639cfc3ff95be510`, 고정 IP `52.200.103.213`. 초기 APT의 AWS CLI 패키지 부재를 공식 설치 파일로 수정한 뒤 SSM 초기 설정과 백엔드 설치·내부 상태 검사가 통과했습니다. 관련 Bash 스크립트 구문 검사도 통과했습니다.
- 사용자의 DuckDNS 수정 후 A 레코드 `52.200.103.213`과 공개 `/healthz` HTTP 200을 확인했습니다. 배포 도구 `check`의 신뢰 가능한 HTTPS 및 인증된 `/api/usage` 검사도 통과했습니다. 사용자 확인상 치지직 redirect URL 수정은 완료됐으며, 배포 서버의 실제 AI 생성·치지직 승인/전송은 미검증입니다. 현재 상태는 `AWS.md`에 기록했습니다.

## 타이틀바 로고 0.3.2 — 2026-10-31

- Tkinter의 `iconbitmap(bitmap, default=...)` 호출은 `default`가 있으면 현재 창에 대한 `bitmap` 인수를 사용하지 않았습니다. 현재 창의 ICO와 자식 창 기본 ICO를 별도 호출로 지정했습니다.
- 수정 전 숨긴 창에서 `WM_GETICON`의 작은/큰 아이콘이 모두 0이었고, 수정 후에는 두 핸들이 모두 존재합니다. 기존 작업 표시줄 속성 검사에 타이틀바·Alt+Tab 아이콘의 네이티브 검사도 추가했습니다.
- 소스 검사 `runs/native_overlay_titlebar_self_test.json`과 최종 설치본 검사 `runs/installer_smoke_20261031-221931-756/report.json` 통과. 실제 열린 앱도 정상 재실행 후 타이틀바/Alt+Tab 아이콘 및 작업 표시줄 로고 속성을 확인했습니다: `runs/desktop_titlebar_live_check.json`. 화면 촬영이나 AI/치지직 전송은 하지 않았습니다.
- 설치본 `dist/StreamChat-Setup-0.3.2-x64.exe` SHA-256: `929590069210d26116527adf70849cae22fde6e9412c2c4995f248779c83d4eb`. 임시 설치·업데이트·제거와 설정 보존 검증 및 `git diff --check` 통과.

## 작업 표시줄 로고 / 화면 정리 / 사용자 지정 단축키 0.3.1 — 2026-10-31

- Tk 아이콘 외에 Windows 창의 AppUserModelID·재실행 명령·이름·아이콘을 지정합니다. 소스/설치본의 숨긴 검사에서 실제 Windows 속성 저장소를 읽어 로고 경로와 이름을 확인했습니다. 실행 중인 소스 오버레이에서도 동일한 속성을 확인했습니다: `runs/desktop_branding_live_check.json`. 화면 촬영 없이 확인했으며 픽셀 단위 시각 검사는 하지 않았습니다.
- 상단의 중복 설정 버튼을 없애고 설정 탭을 유지했습니다. 방송 링크 입력은 앱 표시 모드에서도 보이며, 링크를 넣어도 해당 모드에서는 전송하지 않는다는 안내를 표시합니다.
- 사용자 지정 단축키 직접 입력·키 녹화·정규화·저장을 지원합니다. 실제 Windows 전역 키 등록/충돌 테스트에서 새 조합이 충돌하면 기존 조합이 계속 등록되어 있음을 확인했습니다. 한글 입력 상태에서도 물리 키 코드를 사용하는 경로, 잘못된 조합과 F12 거절도 검사했습니다.
- 전체 **96개 테스트 통과**. 실시간 검사가 마지막 이벤트를 전송 결과로 가정하던 간헐적 오류를 고쳐, 이후 프레임 이벤트가 들어와도 실제 전송 결과 이벤트를 확인합니다. 마지막 키 입력 포커스 수정 후 소스/설치본의 숨긴 UI 검사도 통과했습니다. Python 소스 62개 구문 검사와 `git diff --check` 통과.
- 최종 설치·업데이트·제거 및 사용자 설정 보존 검사: `runs/installer_smoke_20261031-221146-394/report.json`. 설치본 `dist/StreamChat-Setup-0.3.1-x64.exe`의 SHA-256은 `8d52c8a97294d2475f86dc3e80d64d6ff2eb4a3029ffdce95fce58ccb2f3b694`입니다. 설치 검사에서 네트워크 호출과 화면 촬영은 각각 0회입니다.
- 다른 계정의 브라우저 OAuth 테스트는 대상 계정의 채널 링크를 기다리고 있습니다. 기존 인증을 덮어쓰지 않는 별도 실행기를 `runs/chzzk/authorize_alternate.py`에 준비했으며, 아직 인증·채팅 전송을 실행하지 않았습니다. 현재 localhost 콜백은 같은 PC의 브라우저용이며 외부 PC의 승인을 받는 공개 콜백은 미구현입니다.

## 데스크톱 출력 전환 / 방송 링크 / 설치본 0.3.0 — 2026-10-31

- 버튼 생성과 실시간 관찰 모두 `앱에만 표시 (시연)` / `치지직에도 전송`을 선택합니다. 방송 URL에서 채널 ID를 추출하고 연결된 채널과 일치해야 전송합니다. 앱 표시 모드의 생성에는 치지직 인증이나 호출이 필요 없습니다.
- 전체 자동 테스트 **92개 통과**. 최종 전송 시간 제한 조정 후 관련 **8개 재검사 통과**. 로컬 HTTP·WebSocket으로 계정/채널 격리, 기본 앱 표시, 양쪽 생성 모드의 전송 결과, 실패 시 로컬 결과 보존·추가 전송 중지·자동 재전송 방지를 확인했습니다. 샌드박스 임시 폴더 접근 오류가 발생한 재검사는 정상 권한에서 같은 명령으로 통과했습니다.
- 소스와 설치된 EXE의 숨긴 오버레이 검사에서 출력 전환, 방송 링크 추출, 버튼 생성, 실시간 시작·중지·재시작, 아이콘·설정 저장을 확인했습니다. 화면 촬영과 네트워크 호출은 각각 0회입니다. 실제 사용자 화면 배치는 수동 확인 대상입니다.
- 설치본 `dist/StreamChat-Setup-0.3.0-x64.exe` 빌드 및 별도 폴더 설치·업데이트·제거, 사용자 설정 보존 검사 통과. 보고서: `runs/installer_smoke_20261031-213859-882/report.json`. SHA-256: `66d0a64412e0f6f62bf23c9a303e5b5ee597d846b9601236b766ce4e899b3e3d`.
- 기존 로컬 백엔드에 새 API를 적용하고 실제 데스크톱 서비스 클라이언트로 사용량과 치지직 연결 성공을 확인했습니다. 보고서: `runs/chzzk/desktop_connection_check.json`. 이 확인에서 AI 호출·채팅 전송은 각각 0회입니다. 기존 CLI 실제 전송은 아래 기록과 사용자의 표시 확인을 근거로 합니다.
- Python 소스 **61개 구문 검사**, `git diff --check` 통과. 별도 린터·타입 검사 설정은 없습니다. 별도 봇 계정 소유 앱의 발신자 표시 변경은 아직 검증하지 않았습니다.

## 치지직 실제 채팅 전송 — 2026-10-31

- 사용자 계정의 OAuth 연결을 완료하고 인증 계정의 채널 ID와 `backend/.env` 설정이 일치하는 것을 확인했습니다. 토큰은 Git에서 제외된 `runs/chzzk/tokens.json`에 저장하며 이 문서에는 포함하지 않습니다.
- 운영자 CLI로 `[AI] 채팅 연동 테스트입니다.`를 한 번 전송했습니다. 공식 채팅 API가 `messageId`를 반환했고 CLI는 종료 코드 0으로 완료됐습니다. 재전송은 하지 않았습니다. 응답과 대상 채널은 `runs/chzzk/live_send_*.json`에 기록했습니다.
- API의 전송 성공 응답에 더해 사용자가 방송 채팅창에서 실제 표시를 확인했습니다. 이후 연결한 데스크톱 AI 생성 결과의 자동 전송 경로는 별도의 모의 테스트로 검증했으며, 이 경로로 실제 방송에 추가 게시하지는 않았습니다.

## SVG 앱 아이콘 / 설치본 0.2.1 — 2026-10-31

- 전달받은 SVG를 `apps/assets/logo.svg`로 복사했고 원본과 SHA-256이 일치합니다. 프로젝트 내부 파일만으로 ICO·PNG·웹 파비콘을 재생성할 수 있습니다. 설치본에 포함된 원본 SVG와 런타임 이미지도 프로젝트 파일과 바이트 단위로 일치합니다.
- `StreamChat.exe`와 `dist/StreamChat-Setup-0.2.1-x64.exe`의 PE 리소스에서 16~256px 아이콘 9종이 실제로 포함된 것을 확인했습니다. 설치 파일 크기는 15,949,894바이트이며 SHA-256은 옆 `.sha256` 파일에 있습니다.
- 기존 자동 테스트 **84개 통과**. 소스 앱 및 설치된 EXE의 숨긴 UI 검사에서 아이콘 로딩, 원본 SVG 포함, 버튼 생성·실시간 모드 전환을 확인했습니다. 설치·업데이트·제거와 사용자 설정 유지 검사도 통과했습니다. 보고서: `runs/installer_smoke_20261031-203000-479/report.json`.
- 로컬 모의 HTTP 서버에서 웹 패널·실시간 실험의 파비콘 200 응답, SVG MIME 타입과 내용 일치를 확인했습니다. 정적 데모에도 동일한 파비콘 파일을 포함했습니다. Python 및 아이콘 생성 PowerShell 구문 검사 통과. 화면 촬영이나 외부 AI 호출은 수행하지 않았습니다. 실제 Windows 작업 표시줄·바로가기의 시각적 표시는 수동 확인 대상입니다.

## Windows 데스크톱 설치본 — 2026-10-31

- `dist/StreamChat-Setup-0.1.0-x64.exe`를 실제 빌드했습니다. 크기는 15,969,718바이트이며 SHA-256은 옆의 `.sha256` 파일에 있습니다. Python 3.14.4 / PyInstaller 6.22.3 / Inno Setup 7.1.1을 사용했습니다.
- 전체 **74개 자동 테스트 통과**. 설치본과 소스 실행의 설정 경로 분리, 연결 정보의 허용 목록·원자적 저장·잘못된 입력 시 기존 파일 보존, 서버 모듈·개인 설정의 배포 차단 검사를 추가했습니다.
- 임시 폴더에 설치 → Python이 없는 PATH와 소스 외부 작업 폴더에서 EXE 실행 → 재설치 업데이트 → 제거를 실제 수행했습니다. 모두 성공했고 사용자 설정이 유지됐습니다. 테스트 설치의 실행 파일과 제거 등록도 없어졌음을 확인했습니다.
- EXE 검사는 숨겨진 Tk 오버레이 구성, JPEG 인코딩, TLS 런타임, 임시 설정 저장을 확인했습니다. 화면 촬영과 네트워크 호출은 각각 0회입니다. 사용자 환경의 설치 마법사 클릭·바로가기 실행·첫 연결 창 입력은 자동 조작하지 않았습니다.
- 상세 보고서: `runs/installer_smoke_20261031-183020-089/report.json`. 같은 폴더에 설치·업데이트·제거 로그가 있습니다.
- Python 소스 41개와 PowerShell 빌드·검증 스크립트의 구문 검사, `git diff --check`가 통과했습니다. 별도 린터·타입 검사 설정은 없습니다. `.env`, 빌드 도구, 설치 결과물은 Git 제외 대상입니다.
- 설치본은 코드 서명 전 개발용이며, 데스크톱 클라이언트만 포함합니다. 실제 AI 사용에는 별도로 실행 중인 백엔드와 서비스 연결 정보가 필요합니다.

## 페르소나 말투 / 치지직 연결 — 2026-10-31

- 전체 **68개 자동 테스트 통과**. 선택한 페르소나만 서버 지침에 들어가는지, 사용자 맥락이 데이터로 유지되는지, 치지직 OAuth state·계정 일치·토큰 갱신·한 건 전송·오류 비노출·리디렉트 차단을 검사했습니다.
- 실제 `gpt-6-astra`에 합성 점수판(BLUE 3, RED 1)을 전달해 페르소나 4종을 한 번씩 호출했고 모두 성공했습니다. 총 11.768초, 각 생성은 약 2.04~3.93초였습니다. 격리된 테스트 사용량은 요청 1회, 채팅 4건입니다.
- 실제 응답 예: 장난꾸러기 친구 `파랑이 좀 여유 있겠는데`, 다정한 응원단 `두 점 차네, 빨강도 궁금하다`, 과몰입 해설러 `3대1이면 격차 꽤 있네`, 덤덤한 드립러 `칸 크기는 무승부인데`. 한 장면에서 얻은 표본이며 다양한 실제 방송에서의 품질 검증은 남아 있습니다.
- 로컬 결과는 Git에서 제외된 `runs/persona_live_20261031T090739216048Z/report.json`에 있습니다. 앞선 단일 실제 호출도 성공했으며 기록은 `runs/live_ai_20261031T085732202448Z/report.json`에 있습니다.
- 치지직 개발자 앱 자격 증명과 방송 계정 승인이 없어 실제 방송 전송은 아직 실행하지 않았습니다. 치지직 자동 검사는 로컬 모의 HTTP 서버를 사용했습니다.
- 화면 조작 검증은 사용자 요청에 따라 수행하지 않았습니다. 아래 기록들은 이전 단계의 검증 결과입니다.

## .env 자동 로딩

- 전체 **58개 자동 테스트 통과**. 새 7개 검사는 서버 시작 시 로딩, 기존 환경변수 우선, UTF-8/BOM·따옴표·주석, 빈 값, 파일 부재, 오류 메시지의 키 비노출, 데스크톱에서 AI 키 로딩 제외를 확인합니다.
- 운영자용 `backend/.env`와 서비스 연결용 `apps/desktop/.env`를 분리했습니다. 실제 파일은 Git 제외 대상이며 공유 템플릿은 `.env.example`입니다.
- 사용자가 서비스 사용량 화면의 정상 동작을 확인했습니다. 이번 변경에서는 사용자 요청에 따라 추가 화면 조작 검증을 하지 않았습니다.

## 서비스 서버 분리 / 사용자 사용량

- 전체 **51개 자동 테스트 통과**. 서비스 인증, 계정별 격리, 데스크톱→서비스 HTTP 요청, 클라이언트의 AI 키·모델·계정 덮어쓰기 거절, 공급자 오류 비노출, 월 변경, 성공한 채팅만 집계, 취소·리다이렉트 차단을 검사했습니다.
- 데스크톱 설정에서 API 키·모델·공급자 선택을 제거했습니다. 실행 화면에서 단축키·항상 위·불투명도만 있는 설정 페이지를 확인했습니다.
- Python 소스 29개의 구문 검사와 새 CLI `--help`, `git diff --check`가 통과했습니다. 이 프로젝트에는 별도 린터·타입 검사 설정이 없습니다.
- 새 서버와 앱을 로컬 Mock 모드로 실행했고 초기 서비스 연결·테스트 모드 표시를 확인했습니다. 이후 사용자 요청에 따라 화면 조작 검증을 중단했습니다. 새 사용량 화면의 수동 생성→표시 확인은 사용자가 이어서 진행합니다.
- 실제 OpenAI 모델 호출·외부 서버 배포·로그인·결제는 검증하지 않았습니다. 로컬 HTTP 테스트는 실제 AI 품질이나 응답 지연의 증거가 아닙니다.

## GPT-6 스크린샷 오버레이 / 폴더 분리

- 데스크톱·웹·공통 백엔드·기존 영상 실험을 각각 `apps/desktop`, `apps/web`, `backend`, `experiments`로 분리했습니다.
- 전체 **42개 테스트**가 폴더 이동 전후 통과했습니다. 새 검사 15개는 JPEG 입력, 로컬 HTTP 서버에 보내는 실제 Responses 요청, GPT-6 기본값, 오류·미완성·거절 응답, 인원수·동시 입력·부분 실패·사용량 저장·API 키 비저장을 포함합니다.
- 새 데스크톱·웹·영상 실험 CLI의 `--help`가 정상 실행됩니다.
- 기존 CSV 저장의 Windows 줄바꿈 중복 변환을 수정했습니다. 원래 상황 설명의 개행과 CSV 레코드 구분을 보존하는 기존 회귀 검사가 통과합니다.
- 실제 OpenAI API 키를 사용한 GPT-6 모델 호출·화면 이해 품질·지연은 아직 검증하지 않았습니다. 로컬 HTTP 서버 검증과 Mock 수치는 실제 AI 검증이 아닙니다.

## 현재 버전: 프리셋 페르소나 + 방송 정보 + 수동 버튼

수동 모드를 페르소나 중심으로 변경했습니다. 장난꾸러기 친구·다정한 응원단·과몰입 해설러·덤덤한 드립러 중 하나를 고르고, 필요한 방송 정보를 최대 1,000자의 여러 줄 텍스트로 입력합니다. 매번 반응 종류를 정하지 않고 버튼만 눌러 생성합니다.

- 생성 요청은 선택한 페르소나와 방송 정보를 사용합니다. 영상·음성·자동 반응 판단 모델은 사용하지 않습니다.
- 실제 Gemini 모드는 방송 정보를 텍스트 맥락으로 전달합니다. 정적 데모와 Mock 모드는 페르소나별 예시 문장을 사용하며 방송 정보의 의미를 해석하지 않습니다.
- 변경 후 전체 자동 검사 **27개(기존 15개 + 수동 모드 12개)**를 통과했습니다. 페르소나별 서버 지침과 방송 정보의 텍스트 전달, 선택값 스냅샷, 빈 방송 정보, 잘못된 페르소나·이전 입력 필드·미디어 거부, 단일 요청·중복·만료·표시 확인 동작을 확인했습니다. 검사는 실제 모델을 호출하지 않습니다.
- 서버 패널과 정적 데모의 JavaScript 구문 검사를 통과했습니다.
- 정적 데모를 실제 브라우저에서 확인했습니다. 방송 정보를 입력한 뒤 다정한 응원단과 덤덤한 드립러로 각각 버튼을 눌렀고, 해당 페르소나 이름과 서로 다른 예시 문장이 표시됐습니다. 입력한 방송 정보가 두 번의 클릭 후에도 유지되고, 텍스트 입력 중 Space가 채팅을 생성하지 않는 것을 확인했습니다.
- 정적 데모의 두 번의 버튼 → DOM 삽입 시간은 각각 약 651ms였으며, 설정한 650ms 모의 대기를 포함합니다. AI 응답 시간이나 실제 방송 전송 지연을 측정한 값이 아닙니다.
- 정적 데모의 기록 내보내기 버튼은 눌렀지만 이 환경의 다운로드 완료 이벤트가 시간 초과되어 파일 내용까지 검증하지 못했습니다. 서버 패널의 실제 브라우저 → HTTP API → 화면 표시 전체 흐름은 이번 검증에 포함하지 않았습니다. 수동 API는 자동 HTTP 검사로 확인했습니다.
- 실제 모델 API 인증이 연결되지 않아 Gemini 호출·드립 품질·실제 AI 지연은 미검증입니다. 모의 지연을 AI 성능으로 해석하면 안 됩니다.

수동 모드는 테스트 패널에 채팅을 표시합니다. 방송 플랫폼 전송이나 운영체제 전역 단축키는 포함하지 않습니다.

## 이전 수동 버튼 버전의 검증 기록

페르소나 도입 전 `apps/web/server.py`, `backend/manual_provider.py`, `apps/web/manual_panel.html`에서 확인한 결과입니다.

- 기존 검사 15개와 수동 모드 검사 10개를 합쳐 총 **25개**를 통과했습니다.
- 수동 HTTP 검사는 대기 중 호출 0회, 버튼 요청 1회당 생성 1회, 동시·중복 입력의 추가 호출 차단, 영상·오디오 필드 거부, 표시 확인 전 지연값 `null`, 만료·시간 초과 처리 등을 확인했습니다.
- 실제 로컬 서버를 켜서 패널 HTML 제공, 명시적인 요청 후 한국어 `[MOCK]` 문장 반환, 표시 확인이 없을 때 `button_to_display_ms=null` 보존을 확인했습니다. 이 기록은 `runs/manual_button_verified/`에 있습니다.
- 서버 패널의 JavaScript 구문 검사를 통과했습니다. 당시 서버 패널의 실제 브라우저 클릭·DOM 삽입까지의 검증은 완료하지 못했습니다. HTTP 검사에 사용한 표시 확인 값은 테스트 입력이며 실제 브라우저 측정치가 아닙니다.
- 별도의 정적 데모는 브라우저에서 두 번의 버튼 클릭 후 예시 채팅이 표시되는 것을 확인했습니다. 약 651ms는 설정한 650ms 모의 대기를 포함한 값입니다. 이 결과도 페르소나 입력창 도입 전 화면에서 얻었습니다.
- 실제 모델 API 인증이 연결되지 않아 Gemini 호출·드립 품질·실제 AI 지연은 여전히 미검증입니다. 모의 지연을 AI 성능으로 해석하면 안 됩니다.

사용자 컴퓨터에서 README의 실행 명령으로 켠 뒤 실제 브라우저와 API를 연결해 확인할 수 있습니다.

---

## 이전 버전: 자동 영상 분석 실행 흐름 — 2026-10-31

### 실제로 실행한 것

- 직접 생성한 18초 합성 애니메이션과 전자음 파일을 1배속으로 재생했습니다.
- `MockProvider`에 인위적인 0.2초 대기를 넣었습니다. 이 응답기는 색 변화에 맞춰 미리 정한 영어 문장을 반환하며 AI를 호출하지 않습니다.
- 총 9개 판단 기록 중 `WAIT` 7개, 표시된 모의 채팅 2개가 나왔습니다. 오류와 만료는 없었고, 모델 API 호출 수는 0입니다.
- 결과 영상은 18초이며 영상·오디오의 시작 시점은 0초입니다. 채팅 두 개는 기록된 실제 표시 시점 이후에만 나타납니다.
- 전체 15개 단위 검사를 통과했습니다. 미래 프레임·음성 차단, 느린 응답 중 재생 진행, 최신 대기 입력 교체, 만료·종료 후 표시 억제, 실제 표시 시점 유지, 사람 확인이 없는 사건 지연 계산 차단을 포함합니다.
- 실제 FFmpeg 추출에서 5.999초까지의 입력에는 빨간색 전환 장면이 없고, 해당 장면은 원본 시점 6.0초부터 들어가는 것을 픽셀로 확인했습니다.
- API 인증이 없으면 실행이 명시적으로 중단되며 mock으로 자동 전환하지 않는 것을 확인했습니다.

정확한 수치는 `runs/pipeline_check/run.json`과 `events.jsonl`에 있습니다. `report.html`에서 결과 영상과 기록을 함께 볼 수 있습니다. 합성 클립 정답 시점 파일은 모델 입력으로 사용하지 않았습니다.

### 아직 검증하지 않은 것

실제 Gemini 인증 호출, 실제 방송 영상에서의 한국어 드립 품질, 사건부터 드립까지의 실제 AI 지연, 실제 화면 캡처·방송 플랫폼 전달 지연은 측정하지 않았습니다. 현재 영상과 로그의 약 0.2초 값은 설정한 모의 대기를 반영하므로 AI 성능 수치로 사용하면 안 됩니다.

다음 실험에는 실제 데모 영상과 로컬 환경변수에 설정한 API 키가 필요합니다. README의 `joint` / `split` 명령으로 같은 영상을 실행한 뒤, 사람이 사건과 채팅을 매칭해 품질과 타이밍을 함께 평가합니다.
# 2026-10-31 네이티브 오버레이 0.2.0

- `python -B -m unittest discover -s tests -v`: **84개 통과**. 인증·리다이렉트 차단·계정별 사용량·동시 생성 잠금·실시간 WAIT/REACT·페르소나 순환·중지 후 버튼 생성·닫힌 창 캡처 차단·운영자 키의 자식 프로세스 전달 차단 포함.
- `python -B -m unittest experiments.realtime_video.test_realtime experiments.realtime_video.test_cost_benchmark -v`: **21개 통과**. 실제 AI·개인 화면 없이 합성 이미지와 루프백 mock만 사용.
- 숨긴 소스 UI 검사: `runs/native_overlay_self_test.json`. 버튼 생성 → 실시간 시작/중지 → 재시작 → 버튼 모드 복귀, 항상 위 표시·설정 저장 통과. 네트워크 호출/스크린샷 각각 0.
- `apps/desktop/packaging/build.ps1`: **StreamChat-Setup-0.2.0-x64.exe 빌드 성공**. 비밀 설정·백엔드/provider 미포함 게이트 통과.
- `apps/desktop/packaging/smoke.ps1`: `runs/installer_smoke_20261031-194354-553/report.json`. 별도 폴더 설치, Python 없는 PATH에서 frozen UI 검사, 재설치, 제거, 사용자 설정 보존 **모두 통과**. 기존 사용자 설치는 건드리지 않음.
- 개발용 로컬 백엔드 자동 시작과 계정 인증 조회 확인. 이 확인에는 AI 호출 없음.
- 실제 Realtime API의 함수 응답 검증: 수정 후 진단 2회·비교 21회 모두 형식 유효. 장면 판단 품질/비용 수치는 `experiments/realtime_video/EXPERIMENT_RESULTS.md`에 별도 기록. 실제 게임/OBS 창 캡처와 사용자가 보는 오버레이 배치는 사용자 수동 테스트 대상.
## 2026-11-01 · 데스크톱 Figma 포팅, 웹 병합, 0.4.0

- Figma 원본의 메인·설정 두 화면을 MCP로 조회하고 기본 배경 검정 NORMAL 20%, 별도 Glass SCREEN 20%를 확인했습니다. 네이티브 `figma_ui.py`·`panel.py`와 로컬 자산으로 실행하며 웹에는 Figma 스타일을 추가하지 않았습니다.
- `python -X utf8 -B -m unittest discover -s tests -v`: **113개 통과**. 단일 Fill 합성·콘텐츠 alpha 보존 검사 추가. 기존 생성, 실시간 관찰, 계정 사용량, 치지직 출력·원격 승인, AWS 패키지 경계 포함.
- 소스 앱 self-test 통과: 화면 이동, 인원 1→5→1, 캡처/실시간 재시작, 앱/치지직 출력 전환, 단축키 저장, 제목/작업 표시줄 로고. 실제 AI·치지직 전송 0회.
- 오프라인 실제 창 검수: 메인 278×448, 설정 420×666, 사용 방식 420×690. 로컬 스크린샷으로 자산 배치·투명도 확인. 최소화 후 normal 복원 및 frameless 유지 확인. 결과는 Git에서 제외되는 `build/figma-*.png`와 `build/figma-preview.json`에 있습니다.
- Windows 0.4.0 설치본 빌드 및 비밀/서버 코드 제외 검사 통과. `packaging/smoke.ps1`: 격리 폴더 설치, Python 없는 PATH의 frozen self-test, 재설치 설정 유지, 제거와 설정 보존 통과. 로그: `runs/installer_smoke_20261101-004332-300/`.
- 웹 팀원 브랜치 병합 `6b90e8e`: `npm run lint`, `npm run build`, `npm test` **5개 통과**. 실제 로컬 Python Mock API, Origin/인증, 결과 표시 확인, 오래된 컨텍스트 폐기, preview 프록시 포함.
- AWS: `package` 성공, 기본 리전 `us-east-1`. AWS 리소스 생성·서버 부팅·DNS/TLS·실제 원격 승인은 미검증입니다. 계정 로그인과 도메인이 필요합니다.
- 남은 디자인 차이: Tk에는 Figma의 실시간 배경 굴절/GLASS 광학 효과와 외부 그림자가 없습니다. 다중 Fill과 별도 Glass 레이어는 유지하되 중립 어두운 배경 위의 합성·가장자리 빛으로 근사합니다. 폰트는 Pretendard가 없으면 맑은 고딕을 사용하며 일부 입력 컨트롤은 네이티브 위젯입니다.
# 2026-11-01 public service entry and Mac startup follow-up

- Public `GET /` and `HEAD /` now show a static Tiki service guide without credentials. API routes remain authenticated.
- Service API tests: 8 passed; AWS deployment tests: 7 passed. Deployed to the existing AWS instance. Public `/` returned HTTP 200 HTML; unauthenticated `/api/usage` returned 401; authenticated usage and HTTPS health checks passed. No AI generation or broadcast chat was sent.
- Mac CI baseline run `41222180932`: Intel bundle built, but startup aborted because branding created `NSApplication` before Tk initialized its subclass. Dock branding now runs after the Tk root exists; a regression test covers the ordering contract (11 Mac tests passed locally).
- The ARM job was cancelled by the scheduled macOS 14 runner brownout. Updated it to `macos-15`; native builds must pass before release claims.

## 2026-11-01 · Figma v2, Linux X11, public web deployment

- Figma v2 Main/Settings and all five onboarding screens are implemented in the shared desktop UI. Local assets and Pretendard Regular/SemiBold/Bold are bundled. Existing settings skip first-run onboarding; a regression test verifies the migration.
- Full Windows-hosted suite: 134 tests ran successfully, with 4 Linux-only skips. After adding onboarding migration coverage, all 12 `test_desktop_service.py` tests passed. Tests use Mock/local fixtures, with no paid AI or broadcast sends.
- Windows 0.4.0 installer build and bundle secret/provider exclusion passed. Isolated install, upgrade, frozen UI checks (23), uninstall, and settings preservation passed: `runs/installer_smoke_20261101-025147-764/report.json`.
- Linux WSL Ubuntu 26.04/glibc 2.43: Xvfb/Openbox source UI and packaged UI checks (21 each) passed. All 4 Linux tests passed, including native passive-key conflict/replacement/repeat handling and selected-window capture under an occluding window; stale PID and closed windows are rejected. Latest local archive: `dist/linux/tiki-0.4.0-x86_64-20261101-031128-624128.tar.gz`. This local binary does not guarantee compatibility with older glibc; Ubuntu 24.04 CI is configured separately.
- Figma v2 commit `67a38e7`: [Mac run 41229612463](https://github.com/acradin/stream-chat-demo/actions/runs/41229612463) succeeded for Apple Silicon and Intel, including 11 adapter tests, frozen UI checks, DMG generation and artifact upload. [Linux run 41229612374](https://github.com/acradin/stream-chat-demo/actions/runs/41229612374) also succeeded on Ubuntu 24.04 with native X11 checks and packaged UI verification. Real user Mac permission, capture, and global-hotkey behavior still need manual checks.
- Web `npm test`: 5 passed; `npm run build` and `npm run lint` passed. Public-web tests: 4 passed; AWS package tests: 8 passed. Live HTTPS verified React HTML/assets, per-visitor Mock generation/display acknowledgement/export with `model_calls=0`, and unauthenticated private usage rejection (401). Authenticated health/usage passed during deploy. Public web is already deployed at `https://tiki-chat.duckdns.org/`.
- Design export includes 17 synthetic UI states and 60 bundled assets. `design/desktop/README.md` documents dimensions and implementation differences. Tk has no native Figma optical refraction or external drop shadow; Linux Wayland capture/hotkeys and real game/OBS permission checks remain outside validation.
