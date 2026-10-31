#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Linux ]]; then
  echo 'This launcher requires Linux. For Windows use start_desktop.cmd.'
  exit 1
fi
if [[ ! -x .venv-linux/bin/python ]]; then
  echo 'Create .venv-linux with python3 -m venv .venv-linux, then install apps/desktop/linux/requirements.txt.'
  exit 1
fi
exec .venv-linux/bin/python -B -m apps.desktop.linux "$@"
