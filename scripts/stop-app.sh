#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PORT="${DOWNLOADER_PORT:-8000}"
PID_FILE="${DOWNLOADER_PID_FILE:-/tmp/4shared-downloader-${PORT}.pid}"

cd "$REPO_ROOT"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No PID file found at $PID_FILE."
  echo "If needed, stop manually with: pkill -f 'uvicorn app.main:app --host 127.0.0.1 --port $PORT'"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if [[ -z "$PID" ]]; then
  echo "PID file is empty, removing it."
  rm -f "$PID_FILE"
  exit 0
fi

if ! kill -0 "$PID" 2>/dev/null; then
  echo "Process $PID is not running, removing stale PID file."
  rm -f "$PID_FILE"
  exit 0
fi

kill "$PID"

for _ in {1..20}; do
  if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "App stopped (PID $PID)."
    exit 0
  fi
  sleep 0.2
done

echo "Process $PID did not stop in time, sending SIGKILL."
kill -9 "$PID" 2>/dev/null || true
rm -f "$PID_FILE"
echo "App force-stopped (PID $PID)."