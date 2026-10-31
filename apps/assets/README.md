# 앱 아이콘

- `logo.svg`: 전달받은 `Frame 10.svg` 원본을 수정 없이 복사한 파일입니다.
- `app.svg`: 원본 비율을 유지하고 어두운 둥근 배경을 넣은 웹 파비콘입니다.
- `app.ico`: Windows 실행 파일·작업 표시줄·설치 프로그램·바로가기용 아이콘입니다. 16~256px 크기를 포함합니다.
- `app-*.png`: 앱 창과 설치 마법사 등에 사용하는 크기별 이미지입니다.

외부 폴더를 참조하지 않습니다. 원본 SVG와 런타임 아이콘은 설치본에도 포함됩니다.
정적 웹 데모를 따로 배포할 때는 `apps/web/legacy-demo/favicon.svg`가 함께 배포됩니다.

아이콘을 다시 생성하려면 프로젝트 루트의 Windows PowerShell에서 실행하세요.

```powershell
& .\apps\desktop\packaging\make_icons.ps1
```

변환 스크립트는 이번에 전달받은 43×18 단일 경로 SVG를 대상으로 하며 Windows WPF를 사용합니다. 추가 패키지나 원본 다운로드 경로가 필요하지 않습니다.
