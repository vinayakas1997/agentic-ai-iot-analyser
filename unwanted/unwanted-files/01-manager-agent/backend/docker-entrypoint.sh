#!/usr/bin/env bash
set -e

echo "=== Running init_db (migrations + seed) ==="
python -m db.init_db
echo "=== init_db done ==="

exec "$@"
