#!/usr/bin/env bash
# Exit 0 once the ClamAV daemon answers PING on its Unix socket (used as ExecStartPost-style readiness by install checks).
SOCKET="${1:-/run/clamav/clamd.ctl}"
for _ in $(seq 1 ${2:-120}); do
  /usr/bin/python3 - "$SOCKET" <<'PY' && exit 0
import socket, sys
try:
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(2)
    s.connect(sys.argv[1])
    s.sendall(b"zPING" + bytes([0]))
    sys.exit(0 if s.recv(16).strip(bytes([0, 10, 32])) == b"PONG" else 1)
except OSError:
    sys.exit(1)
PY
  sleep 1
done
exit 1
