# Pretendard 1.3.9

공식 [Pretendard v1.3.9](https://github.com/orioncactus/pretendard/releases/tag/v1.3.9)의 정적 TTF 원본입니다.
앱에서 사용하는 Regular(400), SemiBold(600), Bold(700)를 포함합니다. 글리프 변경이나 서브셋 처리를 하지 않았습니다.

- 다운로드: https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip
- 압축 내 경로: `public/static/alternative/Pretendard-Regular.ttf`, `Pretendard-Bold.ttf`
- 라이선스: 동봉한 `LICENSE.txt` (SIL Open Font License 1.1, 원본 저작권 표시 포함)
- Regular SHA-256: `6d0af5258997aec7354a6e340fc2325ba321c410ca48b3af858c8c3d6e92a324`
- Bold SHA-256: `c16b88c670d23e83fa1170c954cbc4822d3b8dad3c3cde15d798a94b43d97985`
- SemiBold SHA-256: `5e1c548732af70873103066c16e1369b9a8a871f0b38c321a1d5bc73e43cea2d` (동일 ZIP의 `public/static/alternative/Pretendard-SemiBold.ttf`)

Windows는 GDI의 FR_PRIVATE, Mac은 CoreText의 process scope로 앱 프로세스에만 등록합니다.
Linux는 Fontconfig에 앱 글꼴로 등록합니다. 별도 설치 없이 Windows/Mac/Linux 배포본에 TTF 세 파일과 라이선스를 포함합니다.
