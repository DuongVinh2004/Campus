#!/usr/bin/env bash
# Acceptance check for the malware scanner on the VM. Run as root AFTER install.sh and with the whole stack up:
#
#   sudo infra/cloud/verify_scanner.sh [/opt/campus247] [soak-minutes]
#
# It prints every measurement it takes (clamd memory, memory left for the rest, soak result) so the numbers can be put
# into docs/04-architecture/MALWARE_SCANNING_DESIGN_20261117.md. Exit status 0 only when every check passed.
set -uo pipefail
ROOT="${1:-/opt/campus247}"
SOAK_MINUTES="${2:-5}"
SOCKET=/run/clamav/clamd.ctl
PYTHON="$ROOT/.venv/bin/python"
MIN_AVAILABLE_MB="${MIN_AVAILABLE_MB:-1000}"   # memory that must remain available with the whole stack and clamd up
failures=0

ok()   { printf 'PASS  %s\n' "$*"; }
bad()  { printf 'FAIL  %s\n' "$*"; failures=$((failures + 1)); }
note() { printf 'info  %s\n' "$*"; }

[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 2; }
[ -x "$PYTHON" ] || { echo "no Python environment at $PYTHON" >&2; exit 2; }

for unit in clamav-daemon clamav-freshclam campus247-api; do
  if systemctl is-active --quiet "$unit"; then ok "$unit is active"; else bad "$unit is not active"; fi
done

if [ -S "$SOCKET" ] && [ "$(stat -c '%a %U:%G' "$SOCKET")" = "660 clamav:clamav" ]; then ok "socket $SOCKET is 660 clamav:clamav"; else bad "socket missing or wrong mode: $(stat -c '%a %U:%G' "$SOCKET" 2>&1)"; fi
if "$ROOT/infra/cloud/wait_scanner.sh" "$SOCKET" 30; then ok "clamd answers PING"; else bad "clamd does not answer PING"; fi
if ss -ltnp 2>/dev/null | grep -qi clam; then bad "clamd listens on a TCP port"; else ok "clamd has no TCP listener"; fi

# Scan through the same client the API uses, as the API user (member of the clamav group), including a real EICAR file.
PROBE="$(mktemp -d)"
trap 'rm -rf "$PROBE"' EXIT
chmod 1777 "$PROBE"   # the probe runs as the API user and writes its test files here
cat > "$PROBE/probe.py" <<'PY'
import asyncio, sys
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, sys.argv[1] + "/services/api/src")
from campus247.infrastructure.scanning.clamd import ClamdScanner
from campus247.ports.file_scanner import ScanRejected

async def main():
    scanner = ClamdScanner(socket_path="/run/clamav/clamd.ctl", max_database_age=timedelta(hours=72), retry_window=30)
    health = await scanner.health()
    print("health", health)
    if not health.get("up") or health.get("stale"):
        sys.exit(3)
    clean = Path(sys.argv[2]) / "clean.pdf"
    clean.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n")
    print("clean", (await scanner.scan(clean)).as_dict())
    eicar = Path(sys.argv[2]) / "eicar.com"
    eicar.write_bytes(b"X5O!P%@AP[4" + bytes([92]) + b"PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")
    try:
        await scanner.scan(eicar)
    except ScanRejected as failure:
        print("eicar rejected", failure.code, failure.signature)
        return
    sys.exit(4)

asyncio.run(main())
PY
RUN_USER="$(systemctl show campus247-api -p User --value)"
if runuser -u "${RUN_USER:-campus247}" -g "${RUN_USER:-campus247}" -G clamav -- "$PYTHON" "$PROBE/probe.py" "$ROOT" "$PROBE"; then ok "clean file passes and EICAR is rejected, database fresh"; else bad "probe failed (database stale, EICAR not detected or no socket access)"; fi

# Memory: clamd resident set and what is left for the rest of the stack.
CLAMD_RSS_MB="$(ps -o rss= -C clamd | awk '{s+=$1} END {printf "%d", s/1024}')"
AVAILABLE_MB="$(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo)"
TOTAL_MB="$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)"
note "clamd resident ${CLAMD_RSS_MB} MB; total ${TOTAL_MB} MB; available ${AVAILABLE_MB} MB with the stack up"
note "services: $(systemctl show campus247-api campus247-models campus247-gateway postgresql@17-campus247 -p MemoryCurrent --value 2>/dev/null | tr '\n' ' ')"
if [ "$AVAILABLE_MB" -ge "$MIN_AVAILABLE_MB" ]; then ok "at least ${MIN_AVAILABLE_MB} MB stays available"; else bad "only ${AVAILABLE_MB} MB available (need ${MIN_AVAILABLE_MB})"; fi
if [ "${CLAMD_RSS_MB:-0}" -le 1500 ]; then ok "clamd is within its 1500 MB limit"; else bad "clamd resident ${CLAMD_RSS_MB} MB exceeds 1500 MB"; fi

# Soak with signature reloads under load (re-reads the database already on disk; the memory limit must hold across them).
SOAK_OUT="$PROBE/soak.jsonl"
if "$PYTHON" "$ROOT/scripts/scanner_soak.py" --socket "$SOCKET" --minutes "$SOAK_MINUTES" --reload-every 1 --interval 15 --out "$SOAK_OUT"; then ok "soak with reloads under load passed"; else bad "soak failed (see summary above)"; fi
note "memory after the soak: available $(awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo) MB; oom kills of clamd: $(journalctl -k --no-pager 2>/dev/null | grep -ci 'killed process.*clamd')"

# The API sees the scanner (the cloud runs knowledge uploads only; learning stays off).
if curl -sf http://127.0.0.1:8015/health/ready | grep -q '"upload-scanner"'; then ok "/health/ready lists upload-scanner"; else bad "/health/ready does not list upload-scanner"; fi

echo
if [ "$failures" = 0 ]; then echo "ALL CHECKS PASSED"; else echo "$failures CHECK(S) FAILED"; fi
exit $(( failures > 0 ))
