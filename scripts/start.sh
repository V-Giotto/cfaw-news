#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
(cd frontend && npm ci --no-audit --no-fund && npm run build)
exec .venv/bin/python -m uvicorn cfaw_news.main:create_app --factory --host 127.0.0.1 --port "${PORT:-8000}"
