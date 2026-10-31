# tiki for Linux X11

Windows/Mac과 공통 Figma UI, 시작 안내, 페르소나, 서비스 사용량, 버튼 생성·실시간 관찰, 앱/치지직 출력 전환을 사용합니다.
Linux는 X11 데스크톱을 대상으로 합니다. Wayland/WSLg 전체 화면 캡처와 전역 단축키는 아직 지원하지 않습니다.
WSL에서는 Linux 앱을 빌드하고 가상 X11 화면에서 검증할 수 있지만 macOS `.app/.dmg`는 만들 수 없습니다.
WSL 앱이 Windows 게임/OBS 창을 캡처하는 기능도 제공하지 않습니다. Windows 방송은 Windows 앱을 사용합니다.

## 소스 실행

Ubuntu/Debian의 X11 데스크톱에서:

```bash
sudo apt-get install python3-tk python3-venv libx11-6 libxcomposite1 libxext6 libfontconfig1
python3 -m venv .venv-linux
.venv-linux/bin/python -m pip install -r apps/desktop/linux/requirements.txt
bash start_desktop_linux.sh
```

왼쪽 위 로고 → 사용 방식 → 서비스 연결에서 `https://tiki-chat.duckdns.org`와 운영자가 발급한 연결 코드를 입력합니다.
AI API 키는 서버에서 관리합니다. 기본 단축키는 `Ctrl+Alt+Space`, 입력창 안 단축키는 `Ctrl+Enter`입니다.
전역 단축키가 다른 앱과 충돌하면 기존 단축키를 유지하고 오류를 표시합니다. 키보드 배열을 바꾼 뒤에는 앱을 재시작합니다.

선택 창 캡처는 XComposite pixmap을 사용하며 창 ID·소유 프로세스를 재확인합니다. 닫힌/최소화된 창 대신 전체 화면을 보내지 않습니다.
EWMH 창 목록/PID를 제공하는 X11 앱을 선택할 수 있습니다. Compositor와 창 관리자가 기능을 제한할 수 있습니다.
항상 위·최소화·불투명도는 창 관리자를 사용하고 모서리는 X Shape로 잘라냅니다. Pretendard 3개 굵기를 프로세스에 등록합니다.

## 배포 파일 만들기

```bash
.venv-linux/bin/python -m pip install -r apps/desktop/packaging/requirements-build.txt
bash build_desktop_linux.sh
```

`dist/linux/tiki-0.4.0-x86_64-*.tar.gz`를 풀고 내부 `tiki/tiki`를 실행합니다. Python과 자산이 포함됩니다.
빌드에는 실행 가능한 X11 화면이 필요하며 UI 자체 검사·서버 모듈/비밀 설정 제외 검사를 통과해야 압축파일을 생성합니다.
설정은 설치본에서 `$XDG_DATA_HOME/tiki/desktop` 또는 `~/.local/share/tiki/desktop`에 저장합니다.

현재 로컬 빌드는 WSL Ubuntu 26.04/glibc 2.43 x86_64 환경입니다. 오래된 배포판과의 바이너리 호환성을 보장하지 않습니다.
배포 대상 중 가장 오래된 Linux에서 다시 빌드하세요. Windows EXE와 Mac DMG는 해당 OS에서 각각 빌드합니다.

[Build Linux desktop](https://github.com/acradin/stream-chat-demo/actions/workflows/desktop-linux.yml)은 Ubuntu 24.04에서 빌드합니다.
성공한 실행의 `tiki-linux-development-x86_64` artifact에서 압축 파일과 자체 검사 결과를 받습니다.

## 검증

`--self-test`는 실제 화면/AI 호출 없이 UI·설정·모드 전환을 검사합니다. 네이티브 입력/캡처 테스트는
격리된 Xvfb에서만 `TIKI_X11_TEST=1`로 실행합니다. 실제 사용자 화면에 가상 키를 전송하는 테스트가 아닙니다.
Xvfb + Openbox에서 전역 단축키 충돌/반복 방지, 선택 창 색상, 닫힌 창/PID 변경 거절을 검사합니다.
실제 게임/OBS·Wayland 포털과 오디오 입력은 이 검증 범위에 포함되지 않습니다.
