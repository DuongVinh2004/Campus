"""C backend runner: fresh fixtures, captured commands, stable-source evidence."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
from unified_parallel_c_preserve import BATCH, ROOT, STATE, checked, git_status, manifest, retain


def selected_files(stage):
    if stage == "independent":
        return ["tests/unified_final"]
    if stage == "rehearsal":
        return ["tests/integration/test_unified_actor_features.py::test_legacy_import_unknown_owner_rejected_and_original_export_preserved",
                "tests/integration/test_unified_actor_features.py::test_legacy_http_preview_confirm_has_provenance_and_receipt",
                "tests/integration/test_unified_consumers09.py::test_catalog_confirm_readback_replay_restart_preserves_held_history",
                "tests/integration/test_unified_storage_completion.py::test_staff_draft_commit_restart_cas_and_private_readback",
                "tests/integration/test_unified_staff12.py::test_native_missing_consumer_is_explicitly_unavailable"]
    if stage == "affected":
        return ["tests/unified_workflow13a/test_certificate.py"]
    if stage == "contracts":
        return ["tests/unified_final/test_case_contracts_c.py"]
    script = checked(ROOT / "scripts/verify_unified_ai_session06.py")
    value = ast.parse(script.read_text(encoding="utf-8"))
    files = next(ast.literal_eval(node.value) for node in value.body
                 if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TEST_FILES" for t in node.targets))
    files += ["tests/integration/test_unified_actor_features.py", "tests/integration/test_unified_storage_completion.py",
              "tests/integration/test_unified_consumers09.py", "tests/unit/assistance/test_consumer_contracts09.py",
              "tests/api/test_privacy_requests.py", "tests/api/test_answer_feedback.py", "tests/api/test_session_revocation.py",
              "tests/api/test_identity_boundary.py", "tests/api/test_identity_middleware.py", "tests/unit/conversation/test_context.py",
              "tests/integration/test_unified_coordination10.py", "tests/integration/test_unified_student11.py",
              "tests/integration/test_unified_staff12.py", "tests/unified_final"]
    for relative in ["tests/unified_workflow13a", "tests/unified_personal13b"]:
        if not checked(ROOT / relative).is_dir():
            raise FileNotFoundError("final owner suite unavailable: " + relative)
        files.append(relative)
    return list(dict.fromkeys(files))


def outcomes(paths):
    latest = {}
    for path in paths:
        for case in ET.parse(path).getroot().iter("testcase"):
            state = next((tag for tag in ["failure", "error", "skipped"] if case.find(tag) is not None), "passed")
            latest[(case.get("classname"), case.get("name"))] = {"state": state, "xml": str(path)}
    return {"unique": len(latest), "passed": sum(v["state"] == "passed" for v in latest.values()),
            "nonpassing": [{"classname": k[0], "name": k[1], **v} for k, v in latest.items() if v["state"] != "passed"],
            "deduplication": "latest (classname,name), only XMLs explicitly passed to this check"}


def run(stage, number):
    status = git_status()
    if stage == "combined":
        for stream in ["stream-a", "stream-b"]:
            final = list(checked(BATCH / stream / "handoffs").glob("final-*.json"))
            if not final:
                raise RuntimeError("final integration pending " + stream + " immutable final handoff")
        snapshot = checked(STATE / "snapshots" / ("manifest-" + number + ".json"))
        record = json.loads(snapshot.read_text(encoding="utf-8"))
        if not record["stable_during_capture"] or record["hashes"] != manifest():
            raise RuntimeError("fresh stable source snapshot required")
    target = checked(STATE / "checks" / (stage + "-" + number))
    if target.exists():
        raise FileExistsError("retain old attempt")
    target.mkdir(exist_ok=False)
    paths = {key: checked(target / name) for key, name in {"tmp": "basetemp", "db": "idempotency.sqlite3",
             "xml": "backend.xml", "log": "backend.log", "command": "command.json"}.items()}
    selected = selected_files(stage)
    command = [sys.executable, "-B", "-u", "-m", "pytest", *selected, "-q", "--tb=short", "-p", "no:cacheprovider",
               "-p", "pytest_asyncio.plugin", "-o", "faulthandler_timeout=30",
               "--basetemp=" + str(paths["tmp"]), "--junitxml=" + str(paths["xml"])]
    environment = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1",
                   "PYTHONIOENCODING": "utf-8", "CAMPUS247_IDEMPOTENCY_DB": str(paths["db"]),
                   "PYTHONPATH": os.pathsep.join(str(ROOT / p) for p in [".", "services/worker/src", "services/api/src", "packages/synthetic/src"])}
    before = manifest()
    captured_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    with paths["log"].open("xb") as output:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT)
    after = manifest()
    summary = outcomes([paths["xml"]]) if paths["xml"].exists() else {"collection_failed": True}
    retain(paths["command"], {"captured_at": captured_at, "command": command, "exit_code": result.returncode, "duration_seconds": time.monotonic() - started,
           "selected_files": selected, "git_before": status, "source_hashes_before": before, "source_hashes_after": after,
           "stable_during_checks": before == after, "outcomes": summary, "ui_tests_run": False,
           "scope": "local synthetic fixture backend only", "provider_calls": 0,
           "final_integration_evidence": stage == "combined" and before == after})
    print(json.dumps({"exit_code": result.returncode, "stable": before == after, "outcomes": summary}, ensure_ascii=False))
    print(paths["log"].read_text(encoding="utf-8", errors="replace")[-12000:])
    return result.returncode if stage == "independent" or before == after else 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["independent", "rehearsal", "affected", "contracts", "scoped", "combined"])
    parser.add_argument("number")
    args = parser.parse_args()
    if re.fullmatch(r"[0-9]{2}", args.number) is None:
        raise ValueError("exact two digit attempt required")
    raise SystemExit(run(args.stage, args.number))
