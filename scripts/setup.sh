#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  python3.12 -m venv .venv
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3, 12), "This setup was validated with Python 3.12"'
.venv/bin/python -m pip install --cache-dir .venv/pip-cache -r requirements.txt
.venv/bin/python -m pip install --cache-dir .venv/pip-cache -e . --no-deps
.venv/bin/python -m pip check
