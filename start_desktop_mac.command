#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'This launcher requires macOS 14 or newer.'
  exit 1
fi
if [[ ! -x .venv-mac/bin/python ]]; then
  echo 'First install Python with Tk, then run:'
  echo 'python3 -m venv .venv-mac'
  echo '.venv-mac/bin/python -m pip install -r apps/desktop/mac/requirements.txt'
  exit 1
fi
exec .venv-mac/bin/python -B -m apps.desktop.mac "$@"
