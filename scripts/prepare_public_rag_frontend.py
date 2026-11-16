"""Build the current UI in a new directory; retain all prior source/build artifacts."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_public_rag import checked, STATE

SOURCE = ROOT / "apps/web"
FRONTEND = STATE / (sys.argv[2] if len(sys.argv) > 2 else "frontend")
if FRONTEND.name not in {"frontend", "frontend2", "frontend3", "frontend4", "frontend5", "frontend6", "frontend7", "frontend8", "frontend9", "frontend10", "frontend11"}:
    raise ValueError("unexpected frontend target")
NODE = Path("C:/Users/Duong Vinh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe")
PRIOR = ROOT / "infra/local/rag-fixture/manual-20261013-76/frontend"


def write(path, content):
    checked(path.parent).mkdir(parents=True, exist_ok=True)
    with checked(path).open("xb") as stream:
        stream.write(content)


def prepare():
    if FRONTEND.exists():
        raise FileExistsError("retain previous frontend; use a fresh namespace")
    for folder in ("src", "public"):
        for source in sorted((SOURCE / folder).rglob("*")):
            checked(source)
            if source.is_file():
                relative = source.relative_to(SOURCE)
                if relative.as_posix() == "src/app/page.tsx":
                    # The original home view has test-only optional props which
                    # are not valid Next page props. Keep the view byte-for-byte
                    # and compose it through an ordinary no-argument route.
                    write(FRONTEND / "src/app/home-view.tsx", source.read_bytes())
                    write(FRONTEND / relative, b'import HomeView from "./home-view";\nexport default function HomePage() { return <HomeView />; }\n')
                else:
                    write(FRONTEND / relative, source.read_bytes())
    for name in ("package.json", "postcss.config.mjs"):
        write(FRONTEND / name, (SOURCE / name).read_bytes())
    # Explicit existing dependencies; no package installation or source edits.
    write(FRONTEND / "tsconfig.json", (PRIOR / "tsconfig.json").read_bytes())
    write(FRONTEND / "next-env.d.ts", b'/// <reference types="next" />\n/// <reference types="next/image-types/global" />\n')
    write(FRONTEND / "next.config.js", (PRIOR / "next.config.js").read_bytes())
    write(FRONTEND / "font-responses.cjs", (PRIOR / "font-responses.cjs").read_bytes())
    # Reuse the deletion-denying build guard in a new explicitly scoped copy.
    guard = (ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs").read_text()
    guard = guard.replace('["acceptance-20261012-58-frontend-repair1", "acceptance-20261012-58-frontend-repair1-local", "acceptance-20261012-58-frontend-repair1-local-repair2"]', json.dumps([FRONTEND.name]))
    write(FRONTEND / "preserve-build.mjs", guard.encode())
    for name in ("temp", "appdata", "localappdata"):
        checked(FRONTEND / name).mkdir()


def build():
    env = {k: v for k, v in os.environ.items() if not any(part in k.upper() for part in ("TOKEN", "KEY", "SECRET", "PASSWORD"))}
    env.update(NODE_PATH=str(SOURCE / "node_modules"), C247_M1_FRONTEND=str(FRONTEND),
        NEXT_PUBLIC_API_URL="http://localhost:8000", NEXT_TELEMETRY_DISABLED="1", NODE_ENV="production",
        NEXT_FONT_GOOGLE_MOCKED_RESPONSES=str(FRONTEND / "font-responses.cjs"),
        TEMP=str(FRONTEND / "temp"), TMP=str(FRONTEND / "temp"), USERPROFILE=str(FRONTEND),
        APPDATA=str(FRONTEND / "appdata"), LOCALAPPDATA=str(FRONTEND / "localappdata"))
    command = [str(NODE), "--import", (FRONTEND / "preserve-build.mjs").as_uri(),
        str(SOURCE / "node_modules/next/dist/bin/next"), "build", str(FRONTEND), "--webpack"]
    proc = subprocess.run(command, cwd=FRONTEND, env=env, text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=240, creationflags=0x08000000)
    with checked(STATE / (FRONTEND.name + "-build.json")).open("x", encoding="utf-8") as stream:
        json.dump({"command": command, "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}, stream, ensure_ascii=False, indent=2)
    print(proc.stdout, proc.stderr)
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"prepare": prepare, "build": build}[sys.argv[1]]()
