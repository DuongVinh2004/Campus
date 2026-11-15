"""Build/serve the actual UI in a fresh scope, retaining all earlier artifacts."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from run_public_rag import ROOT, checked

STATE = checked(ROOT / "infra/local/rag-advanced-20261013")
FRONTEND = checked(STATE / "frontend")
SOURCE = ROOT / "apps/web"
PRIOR = ROOT / "infra/local/rag-fixture/manual-20261013-76/frontend"
_WINDOWS_NODE = Path("C:/Users/Duong Vinh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe")
# The Node.js that builds and serves the UI: the bundled one on this Windows machine, otherwise CAMPUS247_NODE or `node` on PATH.
NODE = Path(os.environ.get("CAMPUS247_NODE") or (_WINDOWS_NODE if os.name == "nt" else shutil.which("node") or "node"))
# Windows only: do not open a console window for the child process.
NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def write(path, content):
    path = checked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)


def prepare():
    if FRONTEND.exists():
        raise ValueError("fresh frontend required; previous build retained")
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
    # New scope retains the original guard's deletion and boundary checks.
    # The pre-existing guard and builds are not edited.
    guard = (ROOT / "infra/local/public-rag-20261013/frontend11/preserve-build.mjs").read_text(encoding="utf-8")
    guard = guard.replace('["frontend11"]', json.dumps([FRONTEND.name]))
    write(FRONTEND / "preserve-build.mjs", guard.encode())
    for name in ("temp", "appdata", "localappdata"):
        checked(FRONTEND / name).mkdir()


def environment():
    env = {key: value for key, value in os.environ.items()
           if not any(part in key.upper() for part in ("TOKEN", "KEY", "SECRET", "PASSWORD"))}
    env.update(NODE_PATH=str(SOURCE / "node_modules"), C247_M1_FRONTEND=str(FRONTEND),
        NEXT_PUBLIC_API_URL="http://localhost:8001", NEXT_TELEMETRY_DISABLED="1", NODE_ENV="production",
        NEXT_FONT_GOOGLE_MOCKED_RESPONSES=str(FRONTEND / "font-responses.cjs"),
        TEMP=str(FRONTEND / "temp"), TMP=str(FRONTEND / "temp"), USERPROFILE=str(FRONTEND),
        APPDATA=str(FRONTEND / "appdata"), LOCALAPPDATA=str(FRONTEND / "localappdata"))
    return env


def main():
    global FRONTEND
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("build", "serve"))
    parser.add_argument("--name", choices=("frontend", "frontend2", "frontend3"), default="frontend")
    args = parser.parse_args()
    FRONTEND = checked(STATE / args.name)
    command = [str(NODE), "--import", (FRONTEND / "preserve-build.mjs").as_uri(),
        str(SOURCE / "node_modules/next/dist/bin/next")]
    if args.mode == "build":
        prepare()
        command += ["build", str(FRONTEND), "--webpack"]
        proc = subprocess.run(command, cwd=FRONTEND, env=environment(), capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=240, creationflags=NO_WINDOW, check=False)
        with checked(STATE / (FRONTEND.name + "-build.json")).open("x", encoding="utf-8") as stream:
            json.dump({"command": command, "exit_code": proc.returncode, "stdout": proc.stdout,
                       "stderr": proc.stderr}, stream, ensure_ascii=False, indent=2)
        print(proc.stdout, proc.stderr)
        raise SystemExit(proc.returncode)
    command += ["start", str(FRONTEND), "-H", "127.0.0.1", "-p", "3001"]
    raise SystemExit(subprocess.run(command, cwd=FRONTEND, env=environment(), creationflags=NO_WINDOW, check=False).returncode)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
