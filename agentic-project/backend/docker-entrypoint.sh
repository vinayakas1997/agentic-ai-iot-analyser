#!/usr/bin/env bash
set -e

# Wait for PostgreSQL to be ready
echo "=== Waiting for PostgreSQL ==="
python -c "
import asyncio, asyncpg, os, sys
async def wait():
    url = os.environ.get('DB_URL', 'postgresql+asyncpg://manager_agent:manager_agent_pass@db:5432/manager_agent_db')
    dsn = url.replace('+asyncpg', '')
    for i in range(30):
        try:
            conn = await asyncpg.connect(dsn)
            await conn.close()
            print('PostgreSQL is ready')
            return
        except Exception:
            pass
        await asyncio.sleep(1)
    print('PostgreSQL not ready after 30s', file=sys.stderr)
    sys.exit(1)
asyncio.run(wait())
"

echo "=== Running init_db (create tables + seed data) ==="
python -m db.init_db
echo "=== init_db done ==="

exec "$@"
