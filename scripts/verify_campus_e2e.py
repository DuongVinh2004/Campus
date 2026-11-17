"""Run real browser tests once in a fresh evidence directory; never clean it."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

from campus_backend import ROOT, checked

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt")
    parser.add_argument("--grep")
    parser.add_argument("--exclude-model", action="store_true")
    parser.add_argument("--readback-conversation")
    parser.add_argument("--campaign", choices=("e2e", "rag-recovery"), default="e2e")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]{2}", args.attempt):
        raise ValueError("Exact two digit attempt required")
    campaign = {"e2e": ".tooling/campus-e2e-20261016-01", "rag-recovery": ".tooling/campus-rag-recovery-20261016-01"}[args.campaign]
    target = checked(ROOT / campaign / ("browser-" + args.attempt))
    if target.exists():
        raise FileExistsError("Keep existing evidence; choose a fresh attempt")
    target.mkdir()
    checked(target / "temp").mkdir()
    node = Path("C:/Users/Duong Vinh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe")
    cli = ROOT / "apps/web/node_modules/@playwright/test/cli.js"
    command = [str(node), str(cli), "test", "--config=playwright.live.config.ts",
        "--output=" + str(checked(target / "artifacts")), "--reporter=line,json"]
    if args.grep:
        command += ["--grep", args.grep]
    if args.exclude_model:
        command += ["--grep-invert", "@model"]
    env = {**os.environ, "TEMP": str(target / "temp"), "TMP": str(target / "temp"),
        "PYTHONDONTWRITEBYTECODE": "1", "PLAYWRIGHT_JSON_OUTPUT_NAME": str(checked(target / "report.json"))}
    if args.readback_conversation:
        if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", args.readback_conversation):
            raise ValueError("Exact UUID7 conversation required")
        env["CAMPUS_READBACK_CONVERSATION"] = args.readback_conversation
    with checked(target / "stdout.log").open("xb") as output, checked(target / "stderr.log").open("xb") as error:
        result = subprocess.run(command, cwd=ROOT / "apps/web", env=env, stdout=output, stderr=error)
    print(str(target), "exit", result.returncode, flush=True)
    sys.exit(result.returncode)
