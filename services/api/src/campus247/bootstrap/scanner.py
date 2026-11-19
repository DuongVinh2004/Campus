"""Build the shared malware scanner from the process environment (one place for every file-accepting flow)."""
from __future__ import annotations

import os
from datetime import timedelta


def scanner_from_environment(environ=None):
    """A ClamdScanner when CAMPUS247_SCANNER_PORT (loopback) or CAMPUS247_SCANNER_SOCKET is set, otherwise None.

    The cloud profile must have one: a production host never accepts files without a real scanner.
    """
    environ = os.environ if environ is None else environ
    port, socket_path = environ.get("CAMPUS247_SCANNER_PORT"), environ.get("CAMPUS247_SCANNER_SOCKET")
    if not port and not socket_path:
        if environ.get("CAMPUS247_PROFILE") == "cloud":
            raise ValueError("The cloud profile requires CAMPUS247_SCANNER_PORT or CAMPUS247_SCANNER_SOCKET")
        return None
    if port and socket_path:
        raise ValueError("Set exactly one of CAMPUS247_SCANNER_PORT and CAMPUS247_SCANNER_SOCKET")
    hours_text = environ.get("CAMPUS247_SCANNER_MAX_DATABASE_AGE_HOURS", "72")
    if not hours_text.isdigit() or not 1 <= int(hours_text) <= 720:
        raise ValueError("CAMPUS247_SCANNER_MAX_DATABASE_AGE_HOURS must be 1-720")
    if port is not None and port and (not port.isdigit() or not 1 <= int(port) <= 65535):
        raise ValueError("CAMPUS247_SCANNER_PORT must be a TCP port")
    if socket_path and not socket_path.startswith("/"):
        raise ValueError("CAMPUS247_SCANNER_SOCKET must be an absolute Unix socket path")
    retry_text = environ.get("CAMPUS247_SCANNER_RETRY_SECONDS", "75")
    if not retry_text.isdigit() or int(retry_text) > 600:
        raise ValueError("CAMPUS247_SCANNER_RETRY_SECONDS must be 0-600")
    from campus247.infrastructure.scanning.clamd import ClamdScanner

    return ClamdScanner(retry_window=float(retry_text), host="127.0.0.1" if port else None, port=int(port) if port else None,
                        socket_path=socket_path or None, max_database_age=timedelta(hours=int(hours_text)))
