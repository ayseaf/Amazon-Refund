#!/usr/bin/env bash
# Start the local API, then the Vite UI. The API is stopped when this script exits.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="$ROOT/backend/.venv/bin/tracker-api"

if [[ ! -x "$API" ]]; then
  echo "Backend virtualenv is missing. Create it with the steps in README.md." >&2
  exit 1
fi

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

"$API" &
API_PID=$!

cleanup() {
  if kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

ready=0
for _ in $(seq 1 25); do
  if curl -sf "http://127.0.0.1:${TRACKER_PORT:-8787}/health" >/dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "The API exited before it became ready." >&2
    exit 1
  fi
  sleep 0.2
done

if [[ "$ready" -ne 1 ]]; then
  echo "The API did not become ready on 127.0.0.1:${TRACKER_PORT:-8787}." >&2
  exit 1
fi

cd "$ROOT/frontend"
pnpm dev
