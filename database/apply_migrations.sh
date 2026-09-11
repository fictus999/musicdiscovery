#!/usr/bin/env bash
# Applies every migration in database/migrations/ in order against
# DATABASE_URL (defaults to the local docker-compose Postgres). Each file
# is idempotent (`create table if not exists`, `create extension if not
# exists`) so re-running this against an already-migrated database is safe.
set -euo pipefail

DATABASE_URL="${DATABASE_URL:-postgresql://musicdiscovery:musicdiscovery@localhost:5432/musicdiscovery}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for migration in "$SCRIPT_DIR"/migrations/*.sql; do
    echo "applying $(basename "$migration")"
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$migration"
done

echo "all migrations applied"
