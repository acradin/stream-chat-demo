#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
exec .venv-linux/bin/python -B apps/desktop/linux/packaging/build.py "$@"
