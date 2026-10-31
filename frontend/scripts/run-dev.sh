#!/usr/bin/env bash
# Vite dev 서버를 node v24 로 실행한다.
set -e
NODE_BIN="$HOME/.nvm/versions/node/v24.14.1/bin"
export PATH="$NODE_BIN:$PATH"
cd "$(dirname "$0")/.."
exec npm run dev -- --host 127.0.0.1
