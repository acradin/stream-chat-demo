#!/usr/bin/env bash
# 현재 PATH의 Node.js로 Vite 서버를 실행한다.
set -euo pipefail
exec bash "$(dirname "$0")/with-node.sh" npm run dev -- "$@"
