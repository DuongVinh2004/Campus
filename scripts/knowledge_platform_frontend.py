"""Snapshot/build the current UI without changing any source/build already present."""
import argparse
import json
import os
import subprocess
import sys

import advanced_rag_frontend as frontend
from knowledge_platform import ROOT, STATE, checked_path, retain

# Portable templates for a server that does not have the development machine's retained frontend files.
CLOUD_TEMPLATES = ROOT / "infra/cloud/frontend"


def prepare():
    scope = frontend.FRONTEND
    if scope.exists():
        raise ValueError("Fresh snapshot required; failed builds remain retained")
    # Current homepage takes searchParams; preserve the actual component signature.
    for folder in ("src", "public"):
        for source in sorted((frontend.SOURCE / folder).rglob("*")):
            checked_path(source, ROOT)
            if source.is_file():
                relative=source.relative_to(frontend.SOURCE)
                # Only real operational pages enter this new serving snapshot.
                # Source files and all older snapshots remain untouched.
                if relative.parts[:2]==("src","app") and len(relative.parts)>3:
                    if relative.parts[2] not in {"chat","knowledge","login","services","tickets","schedule","rooms","privacy","learning","staff","notifications","admin"}:
                        continue
                    if relative.parts[2]=="knowledge" and len(relative.parts)>4 and relative.parts[3]!="sources":
                        continue
                if relative.as_posix()=="src/app/page.tsx":
                    frontend.write(scope / relative,b'import { redirect } from "next/navigation";\nexport default function Page() { redirect("/chat"); }\n')
                elif relative.as_posix()=="src/app/knowledge/page.tsx":
                    frontend.write(scope / relative,b'import { redirect } from "next/navigation";\nexport default function Page() { redirect("/knowledge/sources"); }\n')
                else:
                    frontend.write(scope / relative, source.read_bytes())
    for name in ("package.json", "postcss.config.mjs"):
        frontend.write(scope / name, (frontend.SOURCE / name).read_bytes())
    portable = os.name != "nt" or not frontend.PRIOR.exists()   # the retained templates hold Windows paths: never use them on Linux
    for name in ("tsconfig.json", "next.config.js", "font-responses.cjs"):
        data = ((CLOUD_TEMPLATES if portable else frontend.PRIOR) / name).read_bytes()
        if portable and name == "tsconfig.json":
            data = data.replace(b"__ROOT__", ROOT.as_posix().encode())
        frontend.write(scope / name, data)
    frontend.write(scope / "next-env.d.ts", b'/// <reference types="next" />\n/// <reference types="next/image-types/global" />\n')
    template_path = ROOT / "infra/local/public-rag-20261013/frontend11/preserve-build.mjs"
    template = (template_path if os.name == "nt" and template_path.exists() else CLOUD_TEMPLATES / "preserve-build.mjs").read_text(encoding="utf-8")
    # Bind a new copy to exactly this new artifact; never edit an existing protection.
    template = template.replace('["frontend11"]', json.dumps([scope.name]))
    frontend.write(scope / "preserve-build.mjs", template.encode())
    for name in ("temp", "appdata", "localappdata"):
        checked_path(scope / name, ROOT).mkdir()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["build", "serve"])
    parser.add_argument("--name", default="frontend-knowledge-v1")
    parser.add_argument("--port",type=int,default=3015)
    args = parser.parse_args()
    if not args.name.startswith("frontend-knowledge-") or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in args.name):
        raise ValueError("Explicit fresh frontend name required")
    frontend.FRONTEND = checked_path(STATE / args.name, ROOT)
    frontend.STATE = STATE
    if args.mode == "build":
        prepare()
    scope = frontend.FRONTEND
    command = [str(frontend.NODE), "--import", (scope / "preserve-build.mjs").as_uri(),
               str(frontend.SOURCE / "node_modules/next/dist/bin/next")]
    command += ["build", str(scope), "--webpack"] if args.mode == "build" else ["start", str(scope), "-H", "127.0.0.1", "-p", str(args.port)]
    environment = frontend.environment()
    environment["NEXT_PUBLIC_API_URL"] = ""  # API proxy on 8015 is the single browser origin.
    environment["NEXT_PUBLIC_KNOWLEDGE_PLATFORM"] = "true"
    environment["NEXT_PUBLIC_CAMPUS_OPERATIONS"] = "true"  # durable rooms/timetable/tickets/staff pages on 8015
    result = subprocess.run(command, cwd=scope, env=environment, capture_output=args.mode == "build",
        text=True, encoding="utf-8", errors="replace", creationflags=frontend.NO_WINDOW, check=False)
    if args.mode == "build":
        retain(STATE / (args.name + "-build.json"), {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        print(result.stdout, result.stderr)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
