#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
"$ROOT/backend/.venv/bin/python" -m pytest "$ROOT/backend/tests" -q
npm --prefix "$ROOT/frontend" test
npm --prefix "$ROOT/frontend" run build
