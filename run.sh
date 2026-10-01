#!/usr/bin/env bash
# Lookprint launcher for macOS / Linux
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/python -m pip install -r requirements.txt
fi

exec ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8788
