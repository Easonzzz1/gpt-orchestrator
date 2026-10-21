#!/bin/sh
set -eu
ORCHESTRATOR_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ORCHESTRATOR_ROOT"
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . -v
python3 scripts/static-check.py
sh -n scripts/install.sh scripts/setup-browser.sh scripts/check.sh
