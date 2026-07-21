#!/usr/bin/env bash
set -e

echo "=== Running init_db (create tables + seed data) ==="
python -m db.init_db
echo "=== init_db done ==="

exec "$@"
