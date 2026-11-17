#!/usr/bin/env bash
# Build the web frontend on the server (Linux): installs the locked npm dependencies with pnpm and builds a fresh snapshot
# that the campus247-frontend unit serves. Run as root; it does the work as the service user. Prints the snapshot name,
# which must be set as CAMPUS247_FRONTEND_NAME in /etc/campus247/campus247.env (the script does that unless
# CAMPUS247_NO_ENV_EDIT=1).
#
#   sudo CAMPUS247_ROOT=/opt/campus247 infra/cloud/build_frontend.sh [name]
#
# Needs network access to the npm registry. The Next.js build is not given any secret.
set -euo pipefail
ROOT="${CAMPUS247_ROOT:-/opt/campus247}"
RUN_USER="${CAMPUS247_USER:-campus247}"
PNPM_VERSION="${CAMPUS247_PNPM_VERSION:-9.12.0}"        # the version pinned by packageManager in package.json
NAME="${1:-frontend-knowledge-cloud-$(date +%Y%m%d-%H%M%S)}"
ENV_FILE=/etc/campus247/campus247.env
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
[ -f "$ROOT/pnpm-lock.yaml" ] || { echo "pnpm-lock.yaml missing under $ROOT" >&2; exit 1; }
case "$NAME" in frontend-knowledge-*) ;; *) echo "name must start with frontend-knowledge-" >&2; exit 1;; esac

HOME_DIR="$(getent passwd "$RUN_USER" | cut -d: -f6)"
as_app() { runuser -u "$RUN_USER" -- env HOME="$HOME_DIR" PATH="/usr/local/bin:/usr/bin:/bin" CAMPUS247_ROOT="$ROOT" "$@"; }

echo "== pnpm $PNPM_VERSION"
npm install -g "pnpm@$PNPM_VERSION" --no-audit --no-fund >/dev/null

# The dependencies are installed by root and stay read-only for the service user (it cannot change its own code).
# Install scripts are disabled: nothing from the npm packages runs during the install.
echo "== locked dependencies (pnpm install --frozen-lockfile, web only)"
(cd "$ROOT" && pnpm install --frozen-lockfile --filter 'web...' --ignore-scripts)

echo "== build snapshot $NAME"
(cd "$ROOT" && as_app "$ROOT/.venv/bin/python" -B scripts/knowledge_platform_frontend.py build --name "$NAME")

if [ "${CAMPUS247_NO_ENV_EDIT:-0}" != 1 ] && [ -f "$ENV_FILE" ]; then
  if grep -q '^CAMPUS247_FRONTEND_NAME=' "$ENV_FILE"; then sed -i "s|^CAMPUS247_FRONTEND_NAME=.*|CAMPUS247_FRONTEND_NAME=$NAME|" "$ENV_FILE"
  else echo "CAMPUS247_FRONTEND_NAME=$NAME" >> "$ENV_FILE"; fi
fi
echo "== done: $NAME"
