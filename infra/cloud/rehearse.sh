#!/usr/bin/env bash
# Monthly restore drill (systemd timer): restores the newest backup into a throw-away database and root, compares, deletes
# them, and writes /var/backups/campus247/REHEARSAL.json. Never touches the live database or files.
set -euo pipefail
exec /opt/campus247/.venv/bin/python /opt/campus247/infra/cloud/rehearse_restore.py --root /opt/campus247 \
  --backups /var/backups/campus247 --pg-bin /usr/lib/postgresql/17/bin --admin-prefix "runuser -u postgres --"
