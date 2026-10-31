# tiki for macOS

macOS 14 Sonoma 이상을 대상으로 합니다. Windows와 공통 UI/서비스 클라이언트를 사용하며,
버튼 캡처, 창 선택 실시간 관찰, 멤버 1~5명, 페르소나, 방송 설명, 사용량,
앱 표시/치지직 전송 전환, 방송 링크, 단축키, 항상 위 표시, 불투명도를 제공합니다.

구현과 모의 API 계약 테스트는 완료했습니다. 현재 개발 PC가 Windows이므로 실제 Mac에서의
화면 기록 권한·캡처 결과·전역 단축키·전체 화면 위 표시·설치본 실행은 아직 검증하지 못했습니다.
이 파일은 그 검증을 위한 실행 방법도 포함합니다. Mac 설치 파일이 Windows에서 만들어진 것은 아닙니다.

## GitHub에서 테스트용 설치 파일 받기

[Build Mac desktop](https://github.com/acradin/stream-chat-demo/actions/workflows/desktop-mac.yml)
워크플로는 관련 코드가 main에 push되면 Apple Silicon과 Intel용을 각각 빌드합니다.
수동으로는 **Run workflow**를 누릅니다. 해당 실행이 성공한 뒤 **Artifacts**에서 내려받습니다.

- M1/M2/M3 등 Apple Silicon: `tiki-mac-development-arm64`.
- Intel Mac: `tiki-mac-development-x86_64`.

ZIP을 풀고 DMG를 연 뒤 tiki를 Applications로 드래그합니다. 이 빌드는 아직 Apple Developer ID
서명·공증이 없는 개발용입니다. macOS가 실행을 차단하면 본인이 받은 개발 빌드인지 확인한 뒤
시스템 설정 → 개인정보 보호 및 보안에서 해당 앱의 **확인 없이 열기**를 사용합니다.
빌드 실패 시 설치 파일은 게시하지 않으며, 아래 소스 실행 방법으로도 테스트할 수 있습니다.

## 소스 실행

Tk가 포함된 [python.org macOS Python](https://www.python.org/downloads/macos/) 3.14를 사용합니다.
저장소를 처음 받는 경우 다음을 실행합니다. 기존 체크아웃이 있으면 그 폴더에서 `git pull` 후
가상환경 설치 단계부터 진행합니다. Windows의 `.venv`를 복사해서 쓰지 않습니다.

```bash
git clone https://github.com/acradin/stream-chat-demo.git
cd stream-chat-demo
python3 -m venv .venv-mac
.venv-mac/bin/python -m pip install -r apps/desktop/mac/requirements.txt
bash start_desktop_mac.command
```

Finder에서 `.command`를 더블클릭하려면 최초 한 번 `chmod +x start_desktop_mac.command build_desktop_mac.command`를 실행합니다.
앱의 **사용 방식 → 서비스 연결 설정**에 운영자가 발급한 서비스 주소와 연결 코드를 넣습니다.
배포 주소는 `https://tiki-chat.duckdns.org`입니다. 백엔드 배포와 HTTPS/인증 응답 검증을 완료했습니다.
이 런처는 데스크톱 클라이언트를 실행합니다. 백엔드는 AWS 또는 별도로 실행한 개발 서버를 사용합니다.
연결 코드는 운영자의 `backend/.env`에 있는 `CHAT_SERVICE_TOKEN` 값이며 AI API 키와 다릅니다.
이 값은 GitHub에 올리지 않으므로 Mac에서 별도로 입력해야 합니다.

## Mac 권한과 동작

- 캡처 시 **개인정보 보호 및 보안 → 화면 및 시스템 오디오 기록**에서 tiki를 허용합니다.
  실제로는 오디오를 수집하지 않습니다. 터미널에서 소스로 실행할 때는 시스템에 표시되는 Terminal/Python 실행 주체를 허용해야 할 수 있습니다.
- 전역 단축키는 **손쉬운 사용** 권한이 필요합니다. 허용 후 앱에서 **설정 적용**을 다시 누릅니다.
  권한이 없어도 생성 버튼과 앱 내부 `Ctrl+Enter`/`Cmd+Enter`는 사용할 수 있습니다.
- `Cmd`, `Command`, `⌘`, `Option`, `Alt` 표기를 인식합니다. 예: `Cmd+Shift+G`.
  Mac 전역 이벤트 모니터는 키를 독점하지 않으므로 다른 앱/OS 단축키와 겹치지 않는 조합을 선택합니다.
- ScreenCaptureKit으로 선택한 창 ID와 소유 프로세스를 확인합니다. 창이 사라지면 오류로 종료하며 다른 창이나 전체 화면으로 대체하지 않습니다.
- Pretendard Regular/Bold는 앱에 동봉하여 프로세스 내부에만 등록합니다.
- 설치본 설정: `~/Library/Application Support/tiki/desktop/`. 소스 실행 설정은 기존 `runs/desktop/`을 사용합니다.

## .app / .dmg 만들기

Mac에서 실행합니다. Apple Silicon에서는 arm64, Intel에서는 x86_64를 각각 빌드합니다.

```bash
.venv-mac/bin/python -m pip install -r apps/desktop/packaging/requirements-build.txt
bash build_desktop_mac.command
```

`dist/mac/`에 `.app`과 `.dmg`가 생성됩니다. DMG 안의 tiki를 Applications로 드래그합니다.
Python과 의존성, 이미지·폰트·라이선스가 포함되며 `.env`/사용자 설정/서버 모듈은 제외합니다.
빌드 도중 숨긴 UI 자체 검사를 통과해야 DMG 생성으로 진행합니다.

일반 사용자에게 배포할 때는 Mac 키체인에 Developer ID 인증서와 notarytool 프로필을 준비한 후:

```bash
bash build_desktop_mac.command \
  --sign-identity 'Developer ID Application: YOUR NAME (TEAMID)' \
  --notary-profile tiki-notary
```

서명 인자가 없는 결과는 개발용이며 공증된 공개 배포본이 아닙니다.
공증 프로필의 비밀번호/개인 키는 저장소에 넣지 않습니다.

## 검증

```bash
.venv-mac/bin/python -B -m unittest discover -s tests -p test_mac_desktop.py -v
.venv-mac/bin/python -B -m apps.desktop.mac --self-test runs/mac-self-test.json
```

위 검사는 실제 화면을 찍거나 AI를 호출하지 않습니다. 네이티브 캡처는 앱에서 별도로 확인합니다.

1. 메인/설정/사용 방식/채팅 화면, 모서리 투명도, Pretendard, 최소화/복원을 확인합니다.
2. 권한 거부 상태에서 캡처가 안내 메시지로 실패하는지 확인한 뒤 권한을 허용합니다.
3. 버튼 캡처 → AI 채팅, 선택한 창 실시간 시작 → 중지 → 재시작 → 버튼 모드 복귀를 확인합니다.
4. 창 제목 변경, 창 닫기/최소화, 멀티 모니터, 전체 화면 앱 위 표시를 확인합니다.
5. Cmd 단축키를 녹화·저장하고 다른 앱에서 눌러 생성/중지를 확인합니다.
6. 앱 표시와 치지직 전송은 의도한 방송 계정으로 연결한 뒤 각각 확인합니다.

공식 근거: [ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit),
[PyObjC 바인딩](https://pyobjc.readthedocs.io/en/latest/apinotes/ScreenCaptureKit.html),
[이벤트 모니터](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/EventOverview/MonitoringEvents/MonitoringEvents.html),
[서명·공증](https://pyobjc.readthedocs.io/en/latest/notes/codesigning.html).
