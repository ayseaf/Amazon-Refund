#!/bin/sh
# Start the local API and the interface. Both stay on 127.0.0.1.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
export APT_HOST="${APT_HOST:-127.0.0.1}"
export APT_PORT="${APT_PORT:-8787}"
export APT_DATA_DIR="${APT_DATA_DIR:-$HOME/.local/share/amazon-price-tracker}"
"$ROOT/backend/.venv/bin/python" -m apt &
API_PID=$!
trap 'kill "$API_PID"' EXIT INT TERM
cd "$ROOT/frontend"
npm run dev
