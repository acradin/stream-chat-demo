# 데스크톱 디자인 추출 — Figma v2

`prompt.zip`와 지정된 Figma Component/Main/Settings/Start 5개 화면을 기준으로 공통 데스크톱 UI를 수정했습니다.
Windows, Mac, Linux X11은 같은 `figma_ui.py`, `onboarding.py`, `design_widgets.py`, `panel.py`를 사용합니다.
웹 프론트 디자인은 변경하지 않았습니다. 실행 중 읽는 CSS는 없으며 Tk/ttk와 Pillow로 그립니다.

## 전달 파일

- `desktop-design.json`: 토큰, 실제 위젯 좌표·폰트·Canvas 항목, 17개 화면/상태, 원본 자산 해시, 소스 위치.
- `reference-tokens.css`: 다른 구현으로 이식하기 위한 참고 변수이며 앱이 읽는 CSS가 아닙니다.
- `../../dist/tiki-desktop-design.zip`: 위 문서와 UI 소스, SVG/PNG/ICO/TTF 및 라이선스를 포함하는 전달용 파일.

`runtime.screens`와 `source_inventory`가 상세 값의 기준입니다. 초기화 후 덮어쓴 값은 runtime 값을 사용합니다.
추출은 임시 설정·가짜 서비스로 실행하므로 사용자 설정, 인증 정보, 화면 캡처, 네트워크 요청을 포함하지 않습니다.

## 화면과 글꼴

| Figma 화면 | 크기(px) |
|---|---|
| Screen/Main | 277×347 |
| Screen/Settings | 420×491 |
| Screen/Start, Screen/StartEnd | 277×347 |
| Screen/Start1 | 339×430 |
| Screen/Start2 | 339×775 |
| Screen/Start3 | 339×286 |
| 추가 사용 방식, 채팅 보기 | 420×690, 420×530 |

Pretendard 1.3.9 Regular(400), SemiBold(600), Bold(700)를 동봉합니다. 새 Figma 화면은 음수 Tk 폰트 크기로
픽셀 단위(8/12/14/16/24px)를 지정합니다. JSON에는 실제 선택된 family, weight, metrics가 있습니다.
측정 환경의 DPI와 Tk scaling도 기록합니다. 다른 OS/DPI에서 기본 입력 컨트롤의 크기는 달라질 수 있습니다.

## 배경과 자산

- Main 루트와 Settings 내부 `Fill + Shadow`는 RGB(.15,.15,.15)/COLOR_DODGE + 검정 20%/NORMAL을 순서대로 합성합니다.
- 별도 Glass 레이어는 검정 20%/SCREEN, radius 26입니다. 콘텐츠와 전체 창의 기본 opacity는 1입니다.
- Start1–3은 수정 시안의 검정 40% 배경, Start/StartEnd는 80% 그라데이션을 사용합니다.
- Glass 메타데이터: radius12, refraction1, depth16, lightAngle315, lightIntensity .67, dispersion0, splay .06.
- Drop shadow 메타데이터: 검정 alpha .12, x0/y8, blur40, spread0, NORMAL, showShadowBehindNode=false.
- Tk는 실제 광학 굴절이나 바탕화면을 투과하는 Figma GLASS를 구현하지 않습니다. 고정 어두운 기준색과 가장자리 빛으로 근사하며 캔버스 밖 그림자도 제한됩니다.
- macOS에서는 `systemTransparent` Canvas가 바디·로고·문구를 누락시키는 현상이 있어 불투명 배경을 사용하고, 네이티브 content view의 26px corner radius로 모서리를 자릅니다. 그림자·바디·가장자리 레이어는 Pillow에서 먼저 합성합니다. 이 처리는 공통 창 opacity 설정과 별개입니다.
- 모서리 밖의 macOS NSWindow 배경도 clear로 지정합니다. content view의 contents/rasterization scale은 모니터 backing scale을 따릅니다. Windows는 DPI 배율을 적용한 네이티브 둥근 window region으로 외곽을 자릅니다.
- 로고·아이콘·슬라이더는 SVG 원본을 유지합니다. Mac은 AppKit NSImage로 SVG를 직접 표시하고, Windows/Linux는 원본에서 생성한 `@4x.png`를 실제 DPI 크기로 리샘플링합니다. 새 자산 생성은 `python -B apps/desktop/packaging/render_vector_assets.py`이며 빌드 도구 `resvg-py==0.5.0`만 필요합니다.
- `Main/ChatbotCountSlider` 원본은 `v2-source-count-slider.svg`(Figma `2011:207`)입니다. 숫자·손잡이·그라데이션을 벡터로 유지한 5개 상태를 생성하며, 데모에서 제공하는 1–5명 선택에 맞춰 Plus 잠금 그림만 런타임 상태에서 제거합니다. 원본 SVG는 그대로 보존합니다.
- 원본 SVG/PNG와 정확한 crop/mask를 적용한 런타임 PNG는 `apps/assets/figma/v2-*`입니다. 화면 전체 이미지를 UI로 붙이지 않았습니다.
- PNG 재생성: `python -B apps/desktop/packaging/rasterize_figma_v2.py` (Windows Edge 필요). 배포본은 생성된 PNG를 사용하므로 Edge가 필요 없습니다.

## 기능과 시안의 차이

시안에 표시된 Plus 잠금이나 가상의 월간 사용량을 실제 기능으로 표시하지 않습니다. 데모 인원은 기존대로 1–5명이며,
사용량은 서버의 실제 요청 수와 `한도 미설정`을 표시합니다. 자세한 세 가지 사용량 지표는 사용 방식 화면에 있습니다.
방송 설명은 기존 데이터와 API 계약을 보존해 최대 1,000자입니다. 시작 안내의 방송 링크는 앱 표시 모드에서 비워둘 수 있으며,
링크 입력을 치지직 OAuth 승인으로 처리하지 않습니다. 기존 사용자는 설정을 유지하고, 새 사용자는 안내 5단계를 거칩니다.

메인 로고 또는 우클릭 메뉴로 사용 방식·채팅 보기·설정 적용·치지직 연결 확인·안내 다시 보기에 접근합니다.
Settings는 Main을 교체하지 않는 별도 창입니다. Main 옆에 열리고, Main의 transient 자식으로 연결해 겹칠 때 Settings가 앞에 표시됩니다. Settings를 닫아도 Main은 유지합니다.
설정은 Esc로 나가거나 다른 화면으로 이동할 때 저장합니다. 페르소나 편집은 설정의 수정 아이콘으로 엽니다.

## 다시 추출

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m apps.desktop.export_design
```

Git revision은 기준 커밋입니다. 미커밋 UI 변경은 각 소스 SHA-256으로 구분합니다. 추출용 창의 alpha=0은 측정 전용이며
앱 기본값을 바꾸지 않습니다. OS 파일 선택창·메시지창·네이티브 창 관리 효과는 이 문서의 고정 디자인 범위 밖입니다.
