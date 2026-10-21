#!/bin/sh
set -eu
ORCHESTRATOR_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 -m venv "$ORCHESTRATOR_ROOT/.venv"
"$ORCHESTRATOR_ROOT/.venv/bin/python" -m pip install --disable-pip-version-check -r "$ORCHESTRATOR_ROOT/requirements-browser.txt"
printf '%s\n' 'Browser dependency ready. Installed Google Chrome is used by default.' 'To login: .venv/bin/python -m gpt_orchestrator browser-login --allow-web' 'For Chromium instead: PLAYWRIGHT_BROWSERS_PATH="$PWD/.state/pw-browsers" .venv/bin/python -m playwright install chromium'
