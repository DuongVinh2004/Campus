#!/usr/bin/env bash
# Restore a backup folder into /opt/campus247. Run as root with the campus247 services STOPPED.
#   campus247-restore --backup /var/backups/campus247/campus247-backup-<stamp> [--force]
# Without --force it refuses to overwrite existing state files or a database that already has tables.
set -euo pipefail
RUN_USER="${CAMPUS247_USER:-campus247}"
/opt/campus247/.venv/bin/python /opt/campus247/infra/cloud/backup.py restore --root /opt/campus247 \
  --pg-bin /usr/lib/postgresql/17/bin --admin-prefix "runuser -u postgres --" "$@"
chown -R "$RUN_USER:$RUN_USER" /opt/campus247/infra/local /opt/campus247/data 2>/dev/null || true
echo "restored; start the services in the order given in infra/cloud/README.md (First start)"
