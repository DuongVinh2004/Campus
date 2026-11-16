"""Retain each verification output without cleanup or model campaigns."""
import json
import os
import subprocess
from datetime import UTC, datetime

from knowledge_platform import ROOT, checked_path, retain


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-ocr",action="store_true",help="One retained installed local OCR smoke; no paid model calls")
    parser.add_argument("--without-database", action="store_true", help="Explicitly report database tests as skipped when the local database cannot run")
    args = parser.parse_args()
    if args.without_database and args.local_ocr:
        parser.error("The local OCR integration smoke requires PostgreSQL; do not imply it ran offline")
    scope = checked_path(ROOT / "infra/local/knowledge-automation-20261026" /
        ("verify-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")), ROOT)
    scope.mkdir()
    python = str(checked_path(ROOT / "infra/local/rag-fixture/.venv/Scripts/python.exe", ROOT))
    # Existing bundled executable is read-only. All generated outputs stay in
    # the workspace's existing test/build namespaces and this fresh receipt.
    from advanced_rag_frontend import NODE
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    environment.pop("KNOWLEDGE_PLATFORM_LIVE_TESTS", None)
    environment.pop("KNOWLEDGE_AUTOMATION_BGE_TESTS", None)
    environment.pop("KNOWLEDGE_AUTOMATION_LOCAL_OCR_TESTS",None)
    if args.local_ocr:
        environment["KNOWLEDGE_AUTOMATION_LOCAL_OCR_TESTS"]="1"
    environment["KNOWLEDGE_AUTOMATION_REHEARSAL"] = str(ROOT / "infra/local/knowledge-automation-20261026/schema-rehearsal-20261026T090926324751.json")
    environment["KNOWLEDGE_AUTOMATION_RESTORED"] = str(ROOT / "infra/local/knowledge-automation-20261026/schema-rehearsal-restored-20261026T101117685822.json")
    environment["KNOWLEDGE_AUTOMATION_RELATIONS"] = "infra/local/knowledge-automation-20261026/schema-rehearsal-20261026T124825291097.json"
    environment["KNOWLEDGE_AUTOMATION_BUNDLE"] = "infra/local/knowledge-automation-20261026/schema-rehearsal-bundle-20261026T125636532306.json"
    environment["KNOWLEDGE_AUTOMATION_CORRECTIONS"] = "infra/local/knowledge-automation-20261026/schema-rehearsal-20261026T133349385686.json"
    if args.without_database:
        for name in ("REHEARSAL", "RESTORED", "RELATIONS", "BUNDLE", "CORRECTIONS"):
            environment.pop("KNOWLEDGE_AUTOMATION_"+name, None)
    commands = [
        ("backend", ROOT, [python, "-B", "-m", "pytest", "tests/knowledge_platform", "-q", "-p", "no:cacheprovider"]),
        ("ui", ROOT / "apps/web", [str(NODE), "node_modules/vitest/vitest.mjs", "run", "--config", "vitest.policy-graph.config.ts",
            "src/features/knowledge/KnowledgeIntake.test.tsx", "src/features/knowledge/KnowledgePlatform.test.tsx", "src/features/knowledge/RenditionCorrection.test.tsx",
            "src/features/knowledge/EditionWorkspace.test.tsx", "src/features/knowledge/KnowledgeSchedules.test.tsx"]),
        ("typescript", ROOT / "apps/web", [str(NODE), "node_modules/typescript/bin/tsc", "--noEmit", "--incremental", "false"]),
    ]
    report = {"started_at": datetime.now(UTC).isoformat(), "new_model_campaign": False, "local_ocr_smoke":args.local_ocr,
        "database_tests_enabled": not args.without_database, "commands": []}
    for name, cwd, arguments in commands:
        started = datetime.now(UTC)
        with (scope / (name + ".stdout.log")).open("xb") as out, (scope / (name + ".stderr.log")).open("xb") as err:
            child = subprocess.run(arguments, cwd=ROOT if cwd == ROOT else checked_path(cwd, ROOT), env=environment, stdout=out, stderr=err,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
        item = {"name": name, "cwd": str(cwd), "arguments": arguments, "exit_code": child.returncode,
            "started_at": started.isoformat(), "finished_at": datetime.now(UTC).isoformat()}
        report["commands"].append(item)
        print(json.dumps(item), flush=True)
    report["finished_at"] = datetime.now(UTC).isoformat()
    retain(scope / "receipt.json", report)
    print(json.dumps({"receipt": str(scope / "receipt.json")}))
    raise SystemExit(int(any(item["exit_code"] for item in report["commands"])))


if __name__ == "__main__":
    main()
