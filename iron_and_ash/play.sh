#!/usr/bin/env bash
# ============================================================
#  Iron & Ash - one-click launcher for Linux and macOS
#  Run `./play.sh` (or double-click where your file manager
#  allows). Sets up a private environment on first run.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" >/dev/null 2>&1 &&
           "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            echo "$cmd"
            return 0
        fi
    done
    return 1
}

PY="$(find_python)" || {
    echo
    echo "  Python 3.11+ was not found."
    echo "  Install it with your package manager (e.g. 'sudo apt install python3')"
    echo "  or from https://www.python.org/downloads/ and run this again."
    echo
    exit 1
}

if [ ! -x ".venv/bin/python" ]; then
    echo "First run: preparing the game..."
    "$PY" -m venv .venv
    # These are optional niceties; the game runs on the standard library alone,
    # so never let a failed install (e.g. offline) stop you from playing.
    ./.venv/bin/python -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
    ./.venv/bin/python -m pip install --quiet rich pydantic >/dev/null 2>&1 || \
        echo "(optional extras not installed - playing in plain-text mode)"
fi

exec ./.venv/bin/python -m iron_and_ash
