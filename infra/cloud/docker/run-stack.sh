#!/usr/bin/env bash
# Container entrypoint for the cloud simulation (no systemd): start the stack the way the systemd units would.
#   run-stack                 restore (first start only), start Postgres, models, gateway, API; then wait
#   run-stack shell           a shell for inspection
# Environment: SIM_BACKUP (folder with a backup, default /backup/current), SIM_FAKE_PROVIDER=1 for the load test
# (the provider is answered locally, no paid call), SIM_FRONTEND=1 to also start the web frontend.
set -euo pipefail
ROOT=/opt/campus247
PY="$ROOT/.venv/bin/python"
RUN_USER=campus247
PGBIN=/usr/lib/postgresql/17/bin
cd "$ROOT"
[ "${1:-}" = shell ] && exec bash

eval "$("$PY" infra/cloud/profile_env.py --profile cloud)"
STATE=infra/local/knowledge-platform-20261023
as_app() { runuser -u "$RUN_USER" -- env "PATH=$PATH" "$@"; }

echo "== postgres"
pg_ctlcluster 17 campus247 start
for _ in $(seq 1 30); do su postgres -c "psql -p 55437 -At -c 'select 1'" >/dev/null 2>&1 && break; sleep 1; done

if [ ! -f "$ROOT/.restored" ]; then
  echo "== restore from ${SIM_BACKUP:-/backup/current}"
  "$PY" infra/cloud/backup.py restore --backup "${SIM_BACKUP:-/backup/current}" --root "$ROOT" --pg-bin "$PGBIN" \
    --admin-prefix "runuser -u postgres --" --force
  if [ -f /backup/extra/student-credentials.json ]; then cp /backup/extra/student-credentials.json "$STATE/"; fi
  # The gateway reads its provider key from .env; the simulation never contacts the provider (fake answers).
  [ -f .env ] || { printf 'DEEPSEEK_API_KEY=simulation-only-not-a-real-key\n' > .env; chmod 600 .env; }
  mkdir -p infra/local/public-rag-20261013
  chown -R "$RUN_USER:$RUN_USER" "$STATE" infra/local/public-rag-20261013 infra/local/multi-agent-integrated-20261013-01 infra/local/rag-advanced-models-20261013-18 infra/local/learning-materials-20261104-01 .env
  touch "$ROOT/.restored"
fi

COMMON_ENV=()
if [ "${SIM_FAKE_PROVIDER:-0}" = 1 ]; then
  COMMON_ENV+=(CAMPUS_LOADTEST_FAKE_PROVIDER=1 CAMPUS_LOADTEST_NO_RATE_LIMIT=1 "CAMPUS_LOADTEST_LEDGER_DIR=$ROOT/evals/results/rag-load/fake-ledger-sim"
               "PYTHONPATH=$ROOT/evals/load")
  mkdir -p "$ROOT/evals/results/rag-load" && chown -R "$RUN_USER:$RUN_USER" "$ROOT/evals/results"
fi

echo "== model server"
# A fresh state directory for every start (the model server refuses to reuse one); it continues from the newest earlier one.
PRED="$(ls -d "$ROOT"/infra/local/campus-run-*/models 2>/dev/null | sort | tail -1)"
MODELS_STATE="$ROOT/infra/local/campus-run-cloud-$(date +%s)/models"
mkdir -p "$(dirname "$MODELS_STATE")" && chown "$RUN_USER:$RUN_USER" "$(dirname "$MODELS_STATE")"
as_app "${COMMON_ENV[@]}" "$PY" -B -u scripts/serve_rag_models.py --state "$MODELS_STATE" --predecessor "$PRED" --accounting-only \
  > /var/log/models.log 2>&1 &
for _ in $(seq 1 180); do (echo > /dev/tcp/127.0.0.1/18082) 2>/dev/null && break; sleep 2; done
(echo > /dev/tcp/127.0.0.1/18082) 2>/dev/null || { echo "model server did not start"; tail -20 /var/log/models.log; exit 1; }

echo "== gateway sidecar (concurrency $PROVIDER_CONCURRENCY, daily cap $DAILY_USD_CAP USD / $DAILY_CALL_CAP calls)"
as_app "${COMMON_ENV[@]}" "$PY" -B -u scripts/gateway_sidecar.py serve --port "$GATEWAY_PORT" --concurrency "$PROVIDER_CONCURRENCY" \
  --daily-usd-cap "$DAILY_USD_CAP" --daily-call-cap "$DAILY_CALL_CAP" > /var/log/gateway.log 2>&1 &
for _ in $(seq 1 120); do curl -sf "http://127.0.0.1:$GATEWAY_PORT/health" >/dev/null && break; sleep 2; done
curl -sf "http://127.0.0.1:$GATEWAY_PORT/health" >/dev/null || { echo "gateway did not start"; tail -20 /var/log/gateway.log; exit 1; }

echo "== API ($API_WORKERS workers)"
# CAMPUS_LEARNING_ENABLED=false: the learning-materials module scans uploads with a Windows ClamAV build that is not ported yet.
as_app "${COMMON_ENV[@]}" CAMPUS_LEARNING_ENABLED=false CAMPUS247_RAG_ENGINE=v2 "CAMPUS247_RAG_V2_INDEX=$ROOT/data/rag_v2_index/embedded2" \
  "CAMPUS247_CHAT_MAX_IN_FLIGHT=$MAX_IN_FLIGHT" CAMPUS247_RATE_LIMIT_STORE=postgres \
  "CAMPUS247_GATEWAY_URL=http://127.0.0.1:$GATEWAY_PORT" "CAMPUS247_GATEWAY_TOKEN_FILE=$ROOT/infra/local/public-rag-20261013/gateway-sidecar.token" \
  "$PY" -B -u scripts/knowledge_platform.py serve --generation --port 8015 --frontend-port 3015 --workers "$API_WORKERS" \
  > /var/log/api.log 2>&1 &
for _ in $(seq 1 180); do curl -sf http://127.0.0.1:8015/health/ready >/dev/null && break; sleep 2; done
curl -sf http://127.0.0.1:8015/health/ready >/dev/null || { echo "API did not become ready"; tail -30 /var/log/api.log; exit 1; }
echo "== READY"
curl -s http://127.0.0.1:8015/health/ready | head -c 300; echo

if [ "${SIM_FRONTEND:-0}" = 1 ]; then
  echo "== frontend"
  as_app CAMPUS247_NODE=/usr/local/bin/node "$PY" -B -u scripts/knowledge_platform_frontend.py serve \
    --name "${CAMPUS247_FRONTEND_NAME:-frontend-knowledge-ui-identity-20261114-01}" --port 3015 > /var/log/frontend.log 2>&1 &
fi
exec sleep infinity
