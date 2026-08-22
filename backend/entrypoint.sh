#!/bin/sh
set -eu

mkdir -p "$DATA_DIR/uploads" "$DATA_DIR/artifacts" "$(dirname "$DB_PATH")"
chown -R appuser:appgroup "$DATA_DIR" "$(dirname "$DB_PATH")"
if [ "$#" -gt 0 ]; then
  exec runuser -u appuser -- "$@"
fi
exec runuser -u appuser -- python run.py
