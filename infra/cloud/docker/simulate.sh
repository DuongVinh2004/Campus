#!/usr/bin/env bash
# Rehearse the cloud VM on this machine (rollout steps 1.13 and 1.14): a container limited to 4 CPUs and 7.5 GB (the Docker VM here
# has 8 GB in total, so this is slightly harsher than the 8 GB VPS) that restores a backup and runs the stack with a fake provider.
#
#   infra/cloud/docker/simulate.sh <backup-folder> [extra-dir-with-student-credentials.json]
#
# Run from the repository root in Git Bash. STOP the local runtime first (it needs the same RAM). Nothing is written to the
# live state: model files, index and models state are mounted read-only; the restored state lives inside the container.
set -euo pipefail
BACKUP="${1:?backup folder}"
EXTRA="${2:-}"
ROOT="$(pwd -W)"
NAME=campus247-sim
docker rm -f "$NAME" >/dev/null 2>&1 || true
MOUNTS=(-v "$ROOT/infra/local/rag-fixture:/opt/campus247/infra/local/rag-fixture:ro"
        -v "$ROOT/data/rag_v2_index:/opt/campus247/data/rag_v2_index:ro"
        -v "$ROOT/infra/local/campus-run-20261115-02:/opt/campus247/infra/local/campus-run-20261115-02:ro"
        -v "$ROOT/$BACKUP:/backup/current:ro")
[ -n "$EXTRA" ] && MOUNTS+=(-v "$ROOT/$EXTRA:/backup/extra:ro")
docker run -d --name "$NAME" --cpus=4 --memory=7500m --memory-swap=7500m "${MOUNTS[@]}" \
  -e SIM_FAKE_PROVIDER="${SIM_FAKE_PROVIDER:-1}" "$NAME"
echo "container started; follow with: docker logs -f $NAME"
