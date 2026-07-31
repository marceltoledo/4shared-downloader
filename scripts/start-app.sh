#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

HOST="${DOWNLOADER_HOST:-127.0.0.1}"
PORT="${DOWNLOADER_PORT:-8000}"
PID_FILE="${DOWNLOADER_PID_FILE:-/tmp/4shared-downloader-${PORT}.pid}"
LOG_FILE="${DOWNLOADER_LOG_FILE:-/tmp/4shared-downloader-${PORT}.log}"

cd "$REPO_ROOT"

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE")"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "App already running (PID $OLD_PID)."
    echo "Stop it first with: $SCRIPT_DIR/stop-app.sh"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

if [[ -x "$REPO_ROOT/.venv/bin/uvicorn" ]]; then
  UVICORN_CMD="$REPO_ROOT/.venv/bin/uvicorn"
else
  UVICORN_CMD="uvicorn"
fi

nohup "$UVICORN_CMD" app.main:app --host "$HOST" --port "$PORT" --reload >"$LOG_FILE" 2>&1 &
PID="$!"
echo "$PID" >"$PID_FILE"

sleep 1
if kill -0 "$PID" 2>/dev/null; then
  echo "App started."
  echo "PID: $PID"
  echo "URL: http://$HOST:$PORT"
  echo "Log: $LOG_FILE"
  echo "PID file: $PID_FILE"
else
  echo "Failed to start app. Check log: $LOG_FILE"
  rm -f "$PID_FILE"
  exit 1
fi