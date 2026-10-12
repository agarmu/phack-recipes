#!/usr/bin/env bash
set -euo pipefail
# TCP is unavailable during the entrypoint's temporary initialization server.
export PGPASSWORD="$(cat /run/cms-postgres-password)"
export PGCONNECT_TIMEOUT=3
exec psql --host 127.0.0.1 --username cms --dbname cms --no-password \
  --no-psqlrc --quiet --tuples-only --command 'SELECT 1' >/dev/null
