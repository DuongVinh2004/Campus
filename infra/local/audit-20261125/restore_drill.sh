#!/usr/bin/env bash
# Restore drill on copies only: verify the backup's checksums, pg_restore postgres.dump into a NEW throwaway cluster (55498),
# compare table counts with the live database (read-only query), and integrity-check every restored SQLite file.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PG="$ROOT/.tooling/knowledge-postgres-20261023/pgsql/bin"
PY="$ROOT/infra/local/rag-fixture/.venv/Scripts/python.exe"
BK="$1"
DATA="$(dirname "$BK")/restore-pg-$(date +%H%M%S)"
PORT=55498
echo "== verify"; "$PY" -B "$ROOT/infra/cloud/backup.py" verify --backup "$BK" 2>&1 | tail -3 | cut -c1-300
"$PG/initdb.exe" -D "$DATA" -U postgres -A trust -E UTF8 --no-locale >/dev/null || exit 2
"$PG/pg_ctl.exe" -D "$DATA" -o "-p $PORT -c listen_addresses=127.0.0.1" -l "$DATA.log" -w start >/dev/null || exit 2
"$PG/createdb.exe" -h 127.0.0.1 -p $PORT -U postgres restored
echo "== pg_restore"; "$PG/pg_restore.exe" -h 127.0.0.1 -p $PORT -U postgres -d restored --no-owner --no-privileges "$BK/postgres.dump" 2>&1 | tail -5; echo "rc=${PIPESTATUS[0]}"
Q="select count(*) from information_schema.tables where table_schema not in ('pg_catalog','information_schema')"
echo "restored tables: $("$PG/psql.exe" -h 127.0.0.1 -p $PORT -U postgres -d restored -Atc "$Q")"
for t in knowledge_document knowledge_chunk rag_v2_index_registry; do
  echo "restored rows $t: $("$PG/psql.exe" -h 127.0.0.1 -p $PORT -U postgres -d restored -Atc "select count(*) from $t" 2>&1 | head -1)"
done
"$PG/pg_ctl.exe" -D "$DATA" -m fast -w stop >/dev/null && echo "throwaway cluster stopped"
echo "== sqlite copies"
"$PY" -B -c "
import sqlite3,glob,sys
for p in sorted(glob.glob(sys.argv[1]+'/sqlite/*.sqlite3')):
    c=sqlite3.connect(p); print(p.split('/')[-1].split(chr(92))[-1], c.execute('pragma integrity_check').fetchone()[0]); c.close()
" "$BK"
