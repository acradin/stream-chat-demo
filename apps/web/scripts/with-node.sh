#!/usr/bin/env bash
# 전달받은 명령을 apps/web에서 실행한다. Node.js는 PATH에서 찾는다.
set -euo pipefail

if ! command -v node >/dev/null || ! command -v npm >/dev/null; then
  echo "Install Node.js and npm, or activate your nvm environment first." >&2
  exit 1
fi
cd "$(dirname "$0")/.."
echo "node $(node --version) / npm $(npm --version)"
exec "$@"
