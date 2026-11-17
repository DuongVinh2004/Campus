"""Fresh final-source frontend checks with the inherited guard byte-identical."""
import argparse
import json
import re
import subprocess
import sys

sys.dont_write_bytecode = True
from unified_parallel_c_preserve import BATCH, GUARD, ROOT, STATE, checked, manifest, retain, sha


def run(stage, number):
    for stream in ["stream-a", "stream-b"]:
        if not list(checked(BATCH / stream / "handoffs").glob("final-*.json")):
            raise RuntimeError("final frontend verification pending " + stream + " final handoff")
    snapshot = json.loads(checked(STATE / "snapshots" / ("manifest-" + number + ".json")).read_text(encoding="utf-8"))
    before = manifest()
    if not snapshot["stable_during_capture"] or snapshot["hashes"] != before:
        raise RuntimeError("stable final source snapshot required")
    saved_arguments = sys.argv
    sys.argv = [sys.argv[0], stage, "01"]
    import prepare_unified_ai_frontend08 as wrapper
    sys.argv = saved_arguments
    build = wrapper.build_tools
    build.STATE = checked(STATE / "checks" / ("frontend-" + number))
    build.ATTEMPT = number
    build.FRONTEND = checked(build.STATE / "frontend" / "acceptance-20261012-58-frontend-repair1-local-repair2")
    build.retain = retain
    if stage == "prepare":
        build.STATE.mkdir(exist_ok=False)
        build.prepare()
        retain(build.STATE / "prepared.json", {"source_hashes": before, "guard_sha256": sha(checked(ROOT / GUARD).read_bytes()),
            "guard_copy_identical": checked(ROOT / GUARD).read_bytes() == (build.FRONTEND / "preserve-build.mjs").read_bytes(),
            "source_stable": before == manifest(), "ui_tests_run": False})
    elif stage == "build":
        try:
            build.build()
        finally:
            retain(build.STATE / "source-after-build.json", {"source_stable": before == manifest(), "hashes": manifest(),
                "guard_copy_identical": checked(ROOT / GUARD).read_bytes() == (build.FRONTEND / "preserve-build.mjs").read_bytes()})
    else:
        command = [str(build.NODE), str(ROOT / "apps/web/node_modules/typescript/bin/tsc"),
                   "--project", str(build.FRONTEND / "tsconfig.json"), "--noEmit", "--incremental", "false"]
        output = checked(build.STATE / "typescript.json")
        if output.exists():
            raise FileExistsError("retain previous typecheck")
        result = subprocess.run(command, cwd=build.FRONTEND, env=build.runtime_environment(),
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, creationflags=0x08000000)
        retain(output, {"command": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
                       "source_stable": before == manifest(), "ui_tests_run": False})
        print(result.stdout, result.stderr)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "build", "typecheck"])
    parser.add_argument("number")
    args = parser.parse_args()
    if re.fullmatch(r"[0-9]{2}", args.number) is None:
        raise ValueError("fresh exact attempt required")
    run(args.stage, args.number)
