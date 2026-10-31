#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
exec .venv-mac/bin/python -B apps/desktop/mac/packaging/build.py "$@"
