#!/usr/bin/env bash
# Start the model server with a FRESH state directory (the server refuses to reuse one, so a plain restart of the unit with a fixed
# --state path fails with "fresh owned model namespace required"). The new directory continues from the newest earlier one.
#   start_models.sh <python> [root]
set -euo pipefail
PY="${1:?python}"
ROOT="${2:-/opt/campus247}"
cd "$ROOT"
PREDECESSOR="$(ls -d "$ROOT"/infra/local/campus-run-*/models 2>/dev/null | sort | tail -1 || true)"
PREDECESSOR="${PREDECESSOR:-${CAMPUS247_MODELS_PREDECESSOR:?no earlier model state found and CAMPUS247_MODELS_PREDECESSOR is not set}}"
STATE="$ROOT/infra/local/campus-run-cloud-$(date +%Y%m%d%H%M%S)/models"
mkdir -p "$(dirname "$STATE")"
exec "$PY" -B -u scripts/serve_rag_models.py --state "$STATE" --predecessor "$PREDECESSOR" --accounting-only
