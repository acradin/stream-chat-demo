#!/usr/bin/env bash
# Mock 백엔드(manual.py)를 .venv 로 실행한다. 매 실행마다 새 출력 폴더.
set -e
cd "$(dirname "$0")/../.."
exec .venv/bin/python manual.py --provider mock --output "runs/manual_fe_$(date +%s)"
