# Windows 데스크톱 앱 설치

Windows 설치 구현은 `apps/desktop/window/packaging/`에 있습니다.
이전 `apps/desktop/packaging/build.ps1`·`smoke.ps1` 명령도 호환 래퍼로 유지합니다.
Mac용 `.app`/`.dmg`는 [Mac 안내](apps/desktop/mac/README.md)에 따라 Mac에서 빌드합니다.
Pretendard 1.3.9 Regular/Bold와 OFL 라이선스를 설치본에 포함합니다.

## 사용자 설치

`dist/StreamChat-Setup-0.4.0-x64.exe`를 실행합니다. Windows 10/11의 64비트 앱이며 Python을 따로 설치하지 않아도 됩니다. 한국어 설치 마법사에서 설치 위치와 바탕화면 바로가기를 선택할 수 있습니다. 설치 완료 화면의 실행을 선택하거나 시작 메뉴의 **Stream Chat**을 열면 네이티브 오버레이가 바로 뜹니다.

- 기본 설치 위치: `%LOCALAPPDATA%\Programs\StreamChat`
- 실행: 시작 메뉴 또는 바탕화면의 **Stream Chat**
- 제거: Windows **설정 → 앱 → 설치된 앱 → Stream Chat → 제거**
- 설정: `%LOCALAPPDATA%\StreamChat\desktop`에 보관하며 업데이트와 제거 시 유지합니다.

현재 설치본은 코드 서명 인증서를 적용하지 않은 개발용 빌드입니다. 서명이 필요한 외부 배포는 별도로 준비해야 합니다.

## 처음 서비스 연결

앱은 연결 설정 여부와 관계없이 오버레이부터 엽니다. 첫 연결은 오버레이의 **사용 방식 → 서비스 연결 설정 → 연결 설정 파일 불러오기**에서 이 프로젝트의 `apps/desktop/.env`를 선택하세요. 서비스 주소와 계정용 연결 코드를 직접 입력해도 됩니다. 연결 설정 파일은 개인 인증 정보이므로 설치 EXE와 함께 배포하지 않습니다.

오버레이의 **사용 방식**에서 **버튼 캡처 모드 / 실시간 화면 모드**를 선택합니다. 실시간 모드는 캡처할 창을 선택하고 메인으로 돌아와 원형 버튼을 누릅니다. 기본 60초 뒤 자동 종료되며 원형 버튼을 다시 누르거나 **실시간 중지**로 바로 멈출 수 있습니다. 자세한 테스트 순서는 [DESKTOP.md](DESKTOP.md)에 있습니다.

채팅 표시 위치는 **앱에만 표시 (시연) / 치지직에도 전송**으로 전환합니다. 치지직 전송은 방송 링크를 붙여 넣고 **연결 확인** 후 사용할 수 있습니다. 치지직 키와 로그인 토큰은 백엔드에 보관하며 설치본에는 포함하지 않습니다.

**방송 링크**는 메인의 **톱니 → 설정**에서 입력합니다. 단축키를 직접 입력하거나 **키로 지정**으로 녹화한 뒤 적용할 수 있습니다. 캡처/실시간·앱/치지직 전환과 서비스 연결은 **사용 방식**에서 설정합니다. 창·작업 표시줄·설치 바로가기에는 프로젝트의 tiki 로고를 사용합니다.

운영자가 발급한 계정용 연결 코드이며 OpenAI API 키가 아닙니다. OpenAI 키는 계속 백엔드에서 관리합니다. 가져오기와 저장은 `CHAT_SERVICE_URL`, `CHAT_SERVICE_TOKEN`만 허용합니다. 나중에는 앱의 **사용 방식 → 서비스 연결 설정**에서 바꿀 수 있습니다.

설치본의 연결 정보는 `%LOCALAPPDATA%\StreamChat\desktop\.env`, 창·페르소나 설정은 같은 폴더의 `settings.json`에 저장됩니다. 소스 코드로 실행할 때는 기존 `apps/desktop/.env`, `runs/desktop/settings.json` 경로를 유지합니다. 프로세스 환경변수를 직접 설정했다면 파일보다 우선합니다.

이 설치 프로그램은 데스크톱 클라이언트를 설치합니다. AI 생성과 사용량 조회에는 운영 중인 백엔드가 필요합니다. 현재 로컬 개발 PC에서는 프로젝트의 `start_desktop.cmd`를 한 번 실행하면 로컬 백엔드도 함께 시작됩니다. 소스 오버레이를 닫은 뒤 설치본을 열어 테스트할 수 있습니다. 운영자용 직접 서버 실행은 [BACKEND.md](BACKEND.md)를 참고하세요. 계정 로그인·서버 배포는 아직 별도입니다.

## 개발자: 설치 파일 다시 만들기

빌드 도구는 사용자 설치 파일에 들어가지 않습니다. Windows x64, Python 3.14와 프로젝트 `.venv`를 사용했습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r apps/desktop/packaging/requirements-build.txt
```

[Inno Setup 7 공식 배포본](https://jrsoftware.org/isdl.php)을 설치한 뒤 `build_desktop.cmd`를 더블클릭합니다. 현재 작업 환경에는 서명을 검증한 Inno Setup 7.1.1을 `build/tools/inno`에 준비했습니다. 다른 경로의 컴파일러도 지정할 수 있습니다.

```powershell
& .\apps\desktop\packaging\build.ps1 -Compiler 'C:\Program Files\Inno Setup 7\ISCC.exe'
```

[PyInstaller](https://pyinstaller.org/en/stable/usage.html)가 Python·Tk·앱 의존성을 묶고, [Inno Setup](https://jrsoftware.org/ishelp/topic_compilercmdline.htm)이 설치 마법사·바로가기·제거 프로그램을 만듭니다. 설치는 현재 사용자 권한으로 동작합니다.

아이콘 원본은 프로젝트 안의 `apps/assets/logo.svg`입니다. 원본 SVG와 앱에서 사용하는 ICO·PNG를 설치본에 함께 포함하므로 외부 다운로드 폴더가 필요하지 않습니다. 창·작업 표시줄·실행 파일·설치 및 제거 프로그램·바로가기에 같은 로고를 사용합니다. 이미지 재생성 방법은 [아이콘 안내](apps/assets/README.md)를 참고하세요.

빌드 중 `.env`, 사용자 설정, AI provider·서버 모듈이 포함되지 않았는지 검사합니다. 루트 폴더나 개인 설정을 통째로 추가하지 마세요. 빌드 파일은 `build/desktop/<빌드 시각>/`, 설치 파일과 SHA-256 체크섬은 `dist/`에 생성합니다. 두 폴더는 Git 제외 대상입니다. 앱 버전은 `packaging/version.txt`와 `setup.iss`, 빌드 스크립트의 결과 파일 이름을 함께 변경합니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

설치된 `StreamChat.exe --self-test <결과 JSON 경로>`는 창을 숨긴 상태로 Tk UI 구성, TLS 런타임, JPEG 처리, 임시 설정 저장을 확인하고 종료합니다. 화면 촬영이나 네트워크 호출을 하지 않습니다. 일반적인 설치 마법사·UI 수동 확인과는 별개의 검사입니다.

`apps/desktop/packaging/smoke.ps1`은 새 임시 폴더에 설치·실행·재설치·제거를 검사합니다. 기존 Stream Chat 설치가 있으면 손대지 않고 중단합니다. 숨긴 UI 검사에는 버튼 생성, 실시간 시작·중지·재시작, 두 모드 전환, 항상 위 표시가 포함됩니다. 결과는 [VALIDATION.md](VALIDATION.md)에 기록합니다.
