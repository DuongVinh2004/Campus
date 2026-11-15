#!/usr/bin/env bash
# Campus 24/7: install the runtime on a clean Ubuntu 24.04 LTS server (4 vCPU / 8 GB). Run as root. Idempotent.
#
#   CAMPUS247_ROOT=/opt/campus247 CAMPUS247_DOMAIN=chat.example.edu.vn ./infra/cloud/install.sh
#
# Expects the repository (or the release subset described in infra/cloud/README.md) already at $CAMPUS247_ROOT.
# Installs system packages, a dedicated Postgres cluster on port 55437 (the port the code expects), the Python
# environment from uv.lock, Node.js for the web frontend, the systemd units rendered from infra/profiles/cloud.toml
# and the Caddy HTTPS proxy. It creates no accounts, writes no secret into the repository and starts nothing that
# talks to the paid provider until the owner puts the provider key into /etc/campus247/campus247.env.
set -euo pipefail

ROOT="${CAMPUS247_ROOT:-/opt/campus247}"
RUN_USER="${CAMPUS247_USER:-campus247}"
DOMAIN="${CAMPUS247_DOMAIN:-}"
PROFILE="${CAMPUS247_PROFILE:-cloud}"
PG_VERSION="${CAMPUS247_PG_VERSION:-17}"   # the development database is PostgreSQL 17.x: pg_restore needs the same or a newer major
NODE_VERSION="${CAMPUS247_NODE_VERSION:-22.11.0}"
DB_NAME="campus247_knowledge_local_20261023"
DB_PORT=55437
ENV_FILE=/etc/campus247/campus247.env
SKIP_SERVICES="${CAMPUS247_SKIP_SERVICES:-0}"   # 1 in a container without systemd: install everything, enable nothing

log() { printf '\n== %s\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
[ -f "$ROOT/uv.lock" ] || { echo "no repository at $ROOT (uv.lock missing)" >&2; exit 1; }

log "system packages (PostgreSQL from the official PGDG repository: Ubuntu 24.04 itself ships 16)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl rsync tar xz-utils gnupg ufw logrotate python3-venv caddy
if [ ! -f /etc/apt/sources.list.d/pgdg.list ]; then
  . /etc/os-release
  install -d /usr/share/postgresql-common/pgdg
  curl -fsSL --retry 5 --retry-delay 3 --retry-connrefused -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" > /etc/apt/sources.list.d/pgdg.list
  apt-get update -qq
fi
apt-get install -y -qq postgresql-"$PG_VERSION" postgresql-"$PG_VERSION"-pgvector

log "service user and directories"
id "$RUN_USER" >/dev/null 2>&1 || useradd --system --create-home --home-dir "/var/lib/$RUN_USER" --shell /usr/sbin/nologin "$RUN_USER"
mkdir -p /etc/campus247 /var/backups/campus247
mkdir -p "$ROOT/infra/local" "$ROOT/data" "$ROOT/.tooling"
chown -R "$RUN_USER:$RUN_USER" "$ROOT/infra/local" "$ROOT/data" "$ROOT/.tooling" /var/backups/campus247

log "Node.js $NODE_VERSION (official tarball, checksum verified)"
if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node')" != "$NODE_VERSION" ]; then
  tmp="$(mktemp -d)"
  base="https://nodejs.org/dist/v${NODE_VERSION}"
  curl -fsSL --retry 5 --retry-delay 3 --retry-connrefused -o "$tmp/node.tar.xz" "$base/node-v${NODE_VERSION}-linux-x64.tar.xz"
  curl -fsSL --retry 5 --retry-delay 3 --retry-connrefused -o "$tmp/SHASUMS256.txt" "$base/SHASUMS256.txt"
  (cd "$tmp" && grep " node-v${NODE_VERSION}-linux-x64.tar.xz\$" SHASUMS256.txt | sed 's/ .*/  node.tar.xz/' | sha256sum -c -)
  tar -xJf "$tmp/node.tar.xz" -C /usr/local --strip-components=1
  rm -rf "$tmp"
fi

log "Python environment from uv.lock"
if [ ! -x /opt/uv/bin/uv ]; then python3 -m venv /opt/uv && /opt/uv/bin/pip install -q uv; fi
export UV_PROJECT_ENVIRONMENT="$ROOT/.venv" UV_PYTHON_INSTALL_DIR=/opt/uv-python
(cd "$ROOT" && /opt/uv/bin/uv python install 3.12 && /opt/uv/bin/uv sync --frozen --no-dev)
chown -R "$RUN_USER:$RUN_USER" "$ROOT/.venv" 2>/dev/null || true

log "pinned runtime components (ONNX Runtime, tokenizers), hash verified"
if [ "${CAMPUS247_SKIP_FETCH:-0}" != 1 ]; then CAMPUS247_ROOT="$ROOT" bash "$ROOT/infra/cloud/fetch_runtime_deps.sh"; fi

log "Postgres cluster campus247 on port $DB_PORT"
RAM_MB="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
SHARED="$(python3 - <<PY
import tomllib
print(tomllib.load(open("$ROOT/infra/profiles/$PROFILE.toml", "rb"))["postgres"]["shared_buffers"])
PY
)"
MAXCONN="$(python3 - <<PY
import tomllib
print(tomllib.load(open("$ROOT/infra/profiles/$PROFILE.toml", "rb"))["postgres"]["max_connections"])
PY
)"
if ! pg_lsclusters | awk '{print $2}' | grep -qx campus247; then
  pg_createcluster "$PG_VERSION" campus247 --port "$DB_PORT" -- --encoding=UTF8 --auth-local=peer --auth-host=scram-sha-256
fi
cat > "/etc/postgresql/$PG_VERSION/campus247/conf.d/campus247.conf" <<CONF
listen_addresses = '127.0.0.1'
shared_buffers = $SHARED
max_connections = $MAXCONN
log_min_error_statement = panic
CONF
pg_ctlcluster "$PG_VERSION" campus247 start 2>/dev/null || pg_ctlcluster "$PG_VERSION" campus247 reload
CONN_FILE="$ROOT/infra/local/knowledge-platform-20261023/local-connection.json"
mkdir -p "$(dirname "$CONN_FILE")"
if [ ! -f "$CONN_FILE" ]; then
  PW="$(head -c 24 /dev/urandom | base64 | tr -d '=+/' | head -c 32)"
  su postgres -c "psql -p $DB_PORT -v ON_ERROR_STOP=1" <<SQL
CREATE ROLE knowledge_owner LOGIN PASSWORD '$PW';
CREATE DATABASE $DB_NAME OWNER knowledge_owner;
SQL
  su postgres -c "psql -p $DB_PORT -d $DB_NAME -v ON_ERROR_STOP=1" <<SQL
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gist;
SQL
  umask 077
  printf '{"host":"127.0.0.1","port":%s,"database":"%s","user":"knowledge_owner","password":"%s"}' "$DB_PORT" "$DB_NAME" "$PW" > "$CONN_FILE"
  chown "$RUN_USER:$RUN_USER" "$CONN_FILE"
fi

log "environment file (no secrets in the repository)"
if [ ! -f "$ENV_FILE" ]; then
  install -m 0640 -o root -g "$RUN_USER" "$ROOT/infra/cloud/campus247.env.example" "$ENV_FILE"
  echo "created $ENV_FILE: fill in the provider key and the model state paths before starting"
fi

log "swap file 2 GB (safety net only)"
if [ "$SKIP_SERVICES" != 1 ] && ! swapon --show | grep -q /swapfile; then
  [ -f /swapfile ] || { fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null; }
  swapon /swapfile || true
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=10 >/dev/null
fi

log "systemd units from profile $PROFILE"
"$ROOT/.venv/bin/python" "$ROOT/infra/cloud/render_units.py" --profile "$PROFILE" --root "$ROOT" --user "$RUN_USER" \
  --python "$ROOT/.venv/bin/python" --node /usr/local/bin/node --out /etc/systemd/system
install -m 0644 "$ROOT/infra/cloud/logrotate.conf" /etc/logrotate.d/campus247
install -m 0755 "$ROOT/infra/cloud/backup.sh" /usr/local/sbin/campus247-backup
install -m 0755 "$ROOT/infra/cloud/restore.sh" /usr/local/sbin/campus247-restore
if [ "$SKIP_SERVICES" != 1 ]; then
  systemctl daemon-reload
  systemctl enable campus247-models campus247-gateway campus247-api campus247-frontend >/dev/null
  install -m 0644 "$ROOT/infra/cloud/campus247-backup.service" /etc/systemd/system/
  install -m 0644 "$ROOT/infra/cloud/campus247-backup.timer" /etc/systemd/system/
  systemctl enable --now campus247-backup.timer >/dev/null
fi

log "HTTPS proxy and firewall (only 22 and 443 are reachable)"
if [ -n "$DOMAIN" ]; then
  sed "s/{\$CAMPUS247_DOMAIN}/$DOMAIN/g" "$ROOT/infra/cloud/Caddyfile.example" > /etc/caddy/Caddyfile
  [ "$SKIP_SERVICES" = 1 ] || systemctl restart caddy
else
  echo "CAMPUS247_DOMAIN not set: Caddy left unconfigured"
fi
if [ "$SKIP_SERVICES" != 1 ]; then
  ufw --force reset >/dev/null; ufw default deny incoming >/dev/null; ufw default allow outgoing >/dev/null
  ufw allow 22/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw --force enable >/dev/null
fi

log "done. Next: infra/cloud/README.md section 'First start'"
