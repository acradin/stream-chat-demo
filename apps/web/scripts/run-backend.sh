#!/usr/bin/env bash
# backend/.env를 읽는 OpenAI 웹 백엔드. --provider mock으로 오프라인 테스트 가능.
set -euo pipefail
cd "$(dirname "$0")/../../.."
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -X utf8 -B -m apps.web "$@"
elif [ -x .venv/Scripts/python.exe ]; then
  exec .venv/Scripts/python.exe -X utf8 -B -m apps.web "$@"
else
  echo "Create .venv and install requirements.txt first." >&2
  exit 1
fi
