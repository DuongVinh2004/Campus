"""Check the current runtime's parser dependencies before opening worker resources."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def resolve_parser_python(workspace: Path) -> Path:
    # A venv can omit layout dependencies already present in its base install.
    # Use that exact installation, never a PATH search or an alternate fallback.
    try:
        candidate = (Path(sys.base_prefix) / "python.exe").resolve(strict=True)
        workspace = workspace.resolve(strict=True)
        environment = {key: value for key, value in os.environ.items() if key.upper() in {
            "PATH", "SYSTEMROOT", "WINDIR", "PYTHONIOENCODING", "PYTHONDONTWRITEBYTECODE"}}
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPATH"] = os.pathsep.join(str(workspace / path) for path in (
            "services/api/src", "services/worker/src", ".tooling/knowledge-platform-20261023/site-packages"))
        probe = subprocess.run([
            str(candidate), "-B", "-c",
            "import json, sys, pypdf, pdfminer.high_level, xml.parsers.expat; "
            "from importlib.metadata import version; "
            "print(json.dumps({'python': list(sys.version_info[:3]), "
            "'packages': {name: version(name) for name in ('pypdf', 'pdfminer.six')}}))",
        ], cwd=workspace, env=environment, capture_output=True, text=True, encoding="utf-8",
            timeout=15, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if probe.returncode or len(probe.stdout) > 20000:
            raise ValueError("Parser dependency probe failed")
        identity = json.loads(probe.stdout)
        version = identity["python"]
        packages = identity["packages"]
        if (not isinstance(version, list) or len(version) != 3
                or not all(type(part) is int for part in version)
                or not (3, 12) <= tuple(version[:2]) < (3, 14)
                or not all(isinstance(packages.get(name), str) and packages[name]
                           for name in ("pypdf", "pdfminer.six"))):
            raise ValueError("Unsupported or incomplete parser")
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise RuntimeError("parser runtime unavailable: supported Python, PDF and XML dependencies are required") from error
    return candidate
