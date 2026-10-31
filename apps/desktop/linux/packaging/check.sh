#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../../../.."
unset WAYLAND_DISPLAY
export XDG_SESSION_TYPE=x11
export TIKI_X11_TEST=1
mkdir -p build
openbox >build/linux-openbox.log 2>&1 &
manager=$!
trap 'kill "$manager" 2>/dev/null || true' EXIT
sleep 1
.venv-linux/bin/python -B -m apps.desktop --self-test runs/linux_source_self_test.json
.venv-linux/bin/python -B -m unittest discover -s tests -p test_linux_desktop.py -v
if [[ "${1:-}" == --build ]]; then
  .venv-linux/bin/python -B apps/desktop/linux/packaging/build.py
fi
