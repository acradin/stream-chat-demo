"""Public landing page for the desktop service; no credentials or account data."""

SERVICE_PAGE = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>tiki · 데스크톱 채팅 서비스</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; }
    body { margin: 0; min-height: 100svh; display: grid; place-items: center;
           background: #151619; color: #fff; }
    main { max-width: 32rem; padding: 3rem 1.5rem; }
    .brand { color: #03ffd5; font-size: 3rem; font-weight: 800; margin: 0; }
    h1 { font-size: 1.5rem; line-height: 1.5; margin-top: 2rem; }
    p { color: #d6d6d6; line-height: 1.8; }
    a { color: #03ffd5; text-underline-offset: .25em; }
    a:focus-visible { outline: 2px solid currentColor; outline-offset: 6px; }
    footer { margin-top: 2rem; font-size: .9rem; }
  </style>
</head>
<body>
  <main>
    <p class="brand">tiki</p>
    <h1>데스크톱 앱에서 만나요.</h1>
    <p>이 주소는 tiki 데스크톱 앱이 연결하는 서비스 주소입니다.
       채팅 생성과 방송 화면 관찰은 데스크톱 앱에서 이용해주세요.</p>
    <p>치지직 방송 연결을 승인하려면 전달받은 전용 승인 링크를 열어주세요.</p>
    <footer><a href="/healthz">서비스 연결 상태 확인</a></footer>
  </main>
</body>
</html>
"""
