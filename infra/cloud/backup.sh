#!/usr/bin/env bash
# Daily backup (systemd timer). Keeps the 14 newest backups.
set -euo pipefail
exec runuser -u "${CAMPUS247_USER:-campus247}" -- /opt/campus247/.venv/bin/python /opt/campus247/infra/cloud/backup.py backup \
  --root /opt/campus247 --out /var/backups/campus247 --pg-bin /usr/lib/postgresql/17/bin --keep 14
