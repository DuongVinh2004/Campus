"""Build a fresh scoped UI copy using the existing guard byte-for-byte."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from certificate_stage1_workspace import ROOT, STATE, checked, retain

SOURCE = ROOT / "apps/web"
# The retained guard already permits this basename. Its contents and rules are unchanged.
ATTEMPT = sys.argv[2] if len(sys.argv) > 2 else "01"
if ATTEMPT not in {"01", "02", "03"}:
    raise ValueError("explicit build attempt required")
FRONTEND = STATE / ("frontend" if ATTEMPT == "01" else "frontend" + ATTEMPT) / "acceptance-20261012-58-frontend-repair1-local-repair2"
PRIOR = ROOT / "infra/local/rag-fixture/manual-20261013-76/frontend"
NODE = Path("C:/Users/Duong Vinh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe")


def write(path, data):
    checked(path, FRONTEND)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def prepare():
    checked(FRONTEND, STATE).mkdir(parents=True, exist_ok=False)
    for folder in ("src", "public"):
        for source in sorted((SOURCE / folder).rglob("*")):
            checked(source)
            if source.is_file():
                relative = source.relative_to(SOURCE)
                if relative.as_posix() == "src/app/page.tsx":
                    write(FRONTEND / "src/app/home-view.tsx", source.read_bytes())
                    write(FRONTEND / relative, b'import HomeView from "./home-view";\nexport default function HomePage() { return <HomeView />; }\n')
                else:
                    write(FRONTEND / relative, source.read_bytes())
    for name in ("package.json", "postcss.config.mjs"):
        write(FRONTEND / name, (SOURCE / name).read_bytes())
    for name in ("tsconfig.json", "next.config.js", "font-responses.cjs"):
        write(FRONTEND / name, (PRIOR / name).read_bytes())
    write(FRONTEND / "next-env.d.ts", b'/// <reference types="next" />\n/// <reference types="next/image-types/global" />\n')
    write(FRONTEND / "preserve-build.mjs", (ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs").read_bytes())
    for name in ("temp", "appdata", "localappdata"):
        checked(FRONTEND / name, FRONTEND).mkdir()


def runtime_environment():
    env = {k: v for k, v in os.environ.items() if not any(p in k.upper() for p in ("TOKEN", "KEY", "SECRET", "PASSWORD"))}
    env.update(NODE_PATH=str(SOURCE / "node_modules"), C247_M1_FRONTEND=str(FRONTEND),
        NEXT_PUBLIC_API_URL="http://localhost:8002", NEXT_PUBLIC_CERTIFICATE_DEMO="true",
        NEXT_TELEMETRY_DISABLED="1", NODE_ENV="production", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
        NEXT_FONT_GOOGLE_MOCKED_RESPONSES=str(FRONTEND / "font-responses.cjs"),
        TEMP=str(FRONTEND / "temp"), TMP=str(FRONTEND / "temp"), USERPROFILE=str(FRONTEND),
        APPDATA=str(FRONTEND / "appdata"), LOCALAPPDATA=str(FRONTEND / "localappdata"))
    return env


def build():
    output = checked(STATE / f"frontend-build-{ATTEMPT}.json", STATE)
    if output.exists() or (FRONTEND / ".next").exists():
        raise FileExistsError("retain this attempt; prepare a new explicitly scoped copy for another build")
    command = [str(NODE), "--import", (FRONTEND / "preserve-build.mjs").as_uri(),
               str(SOURCE / "node_modules/next/dist/bin/next"), "build", str(FRONTEND), "--webpack"]
    proc = subprocess.run(command, cwd=FRONTEND, env=runtime_environment(), text=True, encoding="utf-8",
                          errors="replace", capture_output=True, timeout=240, creationflags=0x08000000)
    retain(output, {"command": command, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
    print(proc.stdout, proc.stderr)
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"prepare": prepare, "build": build}[sys.argv[1]]()
