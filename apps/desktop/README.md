# Desktop

Windows와 Mac이 같은 오버레이 UI·페르소나·사용량·채팅·서비스 연결 코드를 사용합니다.
운영체제에 따라 캡처·단축키·글꼴·창 처리를 선택합니다.
Linux 데스크톱은 아직 지원하지 않습니다. AWS의 Linux 백엔드 실행과는 별개입니다.

```text
apps/desktop/
  window/          Windows 캡처·단축키·창·아이콘·글꼴
    packaging/     Windows EXE/설치 프로그램
  mac/             macOS 14+ 캡처·단축키·창·아이콘·글꼴
    packaging/     Mac .app/.dmg 빌드
  overlay.py       공통 동작·설정·채팅
  figma_ui.py      공통 화면 구성
  panel.py         공통 배경·색상·폰트 테마
  service_client.py 공통 백엔드 연결
  connection.py    공통 서비스 연결 창
  capture.py, hotkey.py, branding.py, shell.py  OS 선택 인터페이스
  packaging/       공통 검증·진입점 및 기존 Windows 명령 호환 래퍼
```

Windows 실행: 프로젝트 루트의 `start_desktop.cmd`.
Mac 실행·배포: [mac/README.md](mac/README.md).
설치본에는 API 키를 포함하지 않습니다. 두 OS에서 같은 배포된 백엔드 주소를 사용합니다.

디자인 값: [추출 명세](../../design/desktop/README.md).
글꼴: [Pretendard 원본·라이선스](../assets/fonts/pretendard/README.md).
