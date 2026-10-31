#!/usr/bin/env bash
# Mock 백엔드를 저장소 루트의 .venv로 실행한다.
set -euo pipefail
cd "$(dirname "$0")/../../.."
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -X utf8 -B -m apps.web --provider mock "$@"
elif [ -x .venv/Scripts/python.exe ]; then
  exec .venv/Scripts/python.exe -X utf8 -B -m apps.web --provider mock "$@"
else
  echo "Create .venv and install requirements.txt first." >&2
  exit 1
fi
