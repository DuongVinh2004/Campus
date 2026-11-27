#!/usr/bin/env bash
# Alembic up -> down -> up on a brand-new throwaway Postgres cluster (port 55499). Never touches 55437 or 5433.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PG="$ROOT/.tooling/knowledge-postgres-20261023/pgsql/bin"
DATA="$ROOT/infra/local/audit-20261125/pgtmp-$(date +%H%M%S)"
PORT=55499
URL="postgresql+asyncpg://postgres@127.0.0.1:$PORT/campus_mig"
cd "$ROOT/services/api"
"$PG/initdb.exe" -D "$DATA" -U postgres -A trust -E UTF8 --no-locale >/dev/null || { echo "initdb failed"; exit 2; }
"$PG/pg_ctl.exe" -D "$DATA" -o "-p $PORT -c listen_addresses=127.0.0.1" -l "$DATA.log" -w start >/dev/null || { echo "pg start failed"; exit 2; }
"$PG/createdb.exe" -h 127.0.0.1 -p $PORT -U postgres campus_mig
[ "${PRECREATE_VECTOR:-0}" = 1 ] && "$PG/psql.exe" -h 127.0.0.1 -p $PORT -U postgres -d campus_mig -qc "CREATE EXTENSION IF NOT EXISTS vector" && echo "vector extension pre-created (as the runtime bootstrap does)"
step() { echo "== alembic $*"; DATABASE_URL="$URL" "$ROOT/.venv/Scripts/python.exe" -B -m alembic -c alembic.ini "$@" 2>&1 | grep -vE "^INFO  \[alembic.runtime.migration\] (Context|Will assume)" | tail -6; echo "rc=${PIPESTATUS[0]}"; }
step upgrade head
step current
"$PG/psql.exe" -h 127.0.0.1 -p $PORT -U postgres -d campus_mig -Atc "select count(*) from information_schema.tables where table_schema not in ('pg_catalog','information_schema')" | sed 's/^/tables after upgrade: /'
step downgrade base
"$PG/psql.exe" -h 127.0.0.1 -p $PORT -U postgres -d campus_mig -Atc "select count(*) from information_schema.tables where table_schema not in ('pg_catalog','information_schema') and table_name <> 'alembic_version'" | sed 's/^/tables after downgrade: /'
step upgrade head
"$PG/pg_ctl.exe" -D "$DATA" -m fast -w stop >/dev/null && echo "temp cluster stopped: $DATA"
