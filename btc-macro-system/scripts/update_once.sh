#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LOG_DIR="$ROOT_DIR/logs"
LOCK_DIR="$ROOT_DIR/.update.lock"
PYTHON_BIN=${PYTHON_BIN:-python3}

mkdir -p "$LOG_DIR"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') update already running"
  exit 0
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') update start"
"$PYTHON_BIN" "$ROOT_DIR/run.py" "$@"
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') update done"
