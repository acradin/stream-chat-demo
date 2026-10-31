#!/usr/bin/env bash
# PowerShell -> WSL 중첩 인용 문제를 피하기 위한 헬퍼.
# nvm 의 node v24 를 PATH 에 올린 뒤, 전달받은 명령을 frontend/ 에서 실행한다.
set -euo pipefail

NODE_BIN="$HOME/.nvm/versions/node/v24.14.1/bin"
if [ ! -x "$NODE_BIN/node" ]; then
  echo "node v24.14.1 not found under nvm" >&2
  exit 1
fi
export PATH="$NODE_BIN:$PATH"

cd "$(dirname "$0")/.."
echo "node $(node --version) / npm $(npm --version)"
exec "$@"
