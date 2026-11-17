"""Read-only final scope/runtime audit; every evidence output is exclusive."""
import difflib
import hashlib
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime

from handoff_unified_ai_session04 import windows_read
from multi_agent_live_resources import native_view, paid_view
from unified_ai_runtime_probe import ROOT, checked, http, retain
from verify_unified_ai_candidate import database_digest
from verify_unified_ai_session07 import STATE, test_results

NEW = [
    "services/api/src/campus247/application/assistance/staff_drafts.py",
    "services/api/src/campus247/infrastructure/repositories/sqlite_auxiliary.py",
    "services/api/src/campus247/infrastructure/repositories/held_history.py",
    "services/api/src/campus247/bootstrap/actor_storage.py",
    "services/api/src/campus247/bootstrap/run_storage.py",
    "services/api/src/campus247/presentation/staff_drafts.py",
    "services/api/src/campus247/presentation/held_history.py",
    "apps/web/src/features/assistance/StaffDraftEditor.tsx",
    "apps/web/src/features/assistance/StaffDraftEditor.test.tsx",
    "apps/web/vitest.unified07.config.ts",
    "tests/integration/test_unified_storage_completion.py",
    "scripts/prepare_unified_ai_session07.py", "scripts/prepare_unified_ai_frontend07.py",
    "scripts/verify_unified_ai_session07.py", "scripts/probe_unified_storage_process07.py",
    "scripts/finalize_unified_ai_session07.py", "docs/UNIFIED_AI_SESSION07_20261014.md",
]


def lint(path, before=None):
    command = [str(checked(ROOT / ".venv/Scripts/ruff.exe")), "check", "--no-cache", "--output-format=json"]
    command += [str(path)] if before is None else ["--stdin-filename",str(path),"-"]
    result = subprocess.run(command,cwd=ROOT,input=before,capture_output=True,text=True,encoding="utf-8",check=False)
    if result.returncode not in {0,1}:raise RuntimeError("lint execution unavailable")
    return json.loads(result.stdout)


def main():
    preflight = json.loads(checked(STATE / "preflight.json").read_text(encoding="utf-8"))
    sources = [*preflight["sources"],*json.loads(checked(STATE / "extra-preflight-01.json").read_text())["sources"]]
    changes, patches, diagnostics = [], [], []
    for entry in sources:
        path,backup = checked(ROOT / entry["path"]),checked(STATE / entry["backup"])
        before,after = backup.read_bytes(),path.read_bytes()
        assert hashlib.sha256(before).hexdigest() == entry["sha256"]
        if before == after:continue
        relative = path.relative_to(ROOT).as_posix()
        changes.append({"path":relative,"preimage":entry["backup"],"sha256":hashlib.sha256(after).hexdigest()})
        patches.extend(difflib.unified_diff(before.decode("utf-8").splitlines(True),after.decode("utf-8").splitlines(True),
                                           fromfile="before/"+relative,tofile="after/"+relative))
        if path.suffix == ".py":
            old,new = lint(path,before.decode("utf-8")),lint(path)
            baseline = Counter((d["code"],d["message"]) for d in old)
            introduced = Counter((d["code"],d["message"]) for d in new)-baseline
            assert not introduced,relative
            diagnostics.append({"path":relative,"before":len(old),"after":len(new),
                                "introduced":[{"code":c,"message":m,"count":n} for (c,m),n in introduced.items()]})
    for relative in NEW:
        path = checked(ROOT / relative);data = path.read_bytes()
        changes.append({"path":relative,"new_file":True,"sha256":hashlib.sha256(data).hexdigest()})
        patches.extend(difflib.unified_diff([],data.decode("utf-8").splitlines(True),fromfile="/dev/null",tofile="after/"+relative))
        if path.suffix == ".py":assert lint(path) == [],relative
    target = checked(STATE / "source-changes-02.patch")
    with target.open("x",encoding="utf-8",newline="") as stream:stream.writelines(patches)
    status = subprocess.run(["git","status","--porcelain=v1"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",check=True)
    assert set(preflight["git_status"].splitlines()) <= set(status.stdout.splitlines())
    diff = subprocess.run(["git","diff","--check"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",check=False)
    build = json.loads(checked(STATE / "frontend-build-01.json").read_text());assert build["exit_code"] == 0
    frontend = checked(STATE / "frontend01/acceptance-20261012-58-frontend-repair1-local-repair2")
    frontend_paths = [p for p in NEW if p.endswith(".tsx")] + ["apps/web/src/features/documents/ServiceWorkspace.tsx","apps/web/src/features/documents/CertificateWorkspace.tsx"]
    for name in frontend_paths:
        assert checked(ROOT / name).read_bytes() == checked(frontend / name.removeprefix("apps/web/")).read_bytes()
    assert checked(frontend / "preserve-build.mjs").read_bytes() == checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs").read_bytes()
    ownership = windows_read();code,runtime = http(8006,"/v1/assistant/runtime")
    assert ownership == preflight["ownership"] and code == 200 and runtime == preflight["runtime"]
    held = []
    for snapshot in preflight["snapshots"]:
        assert database_digest(checked(ROOT / snapshot["source"])) == snapshot["tables"]
        held.append({"path":snapshot["source"],"all_rows_unchanged":True})
    assert paid_view() == preflight["paid_before"] and native_view() == preflight["native_before"]
    result = {"captured_at":datetime.now(UTC).isoformat(),"tests":test_results(),"source_candidate":"unified-local-v7",
        "live_runtime":runtime,"ownership":ownership,"runtime_handoff":False,"browser_testing":"deferred_by_user",
        "held_databases":held,"paid_native_counters_unchanged":True,"model_dispatches":0,"human_measurements_started":0,
        "frontend_build_id":checked(frontend / ".next/BUILD_ID").read_text().strip(),"build_matches_current_changed_ui":True,
        "preservation_guard_unchanged":True,"changes":changes,"scoped_patch":target.name,"preexisting_git_entries_preserved":True,
        "git_status":status.stdout,"git_warnings":status.stderr,"git_diff_check":{"exit_code":diff.returncode,"output":diff.stdout+diff.stderr},
        "new_python_files_full_lint_passed":True,"changed_existing_file_lint":diagnostics,"no_new_lint_diagnostics":True,
        "compatibility_evidence":"migration-compatibility-02.json","production_changes":False}
    retain(STATE / "session-verification-02.json",result)
    print(json.dumps({"tests":result["tests"],"source_candidate":result["source_candidate"],"live_runtime":runtime["runtime"],
        "changed_paths":len(changes),"new_python_lint_passed":True,"originals_unchanged":True,"browser_testing":"deferred_by_user"}))


if __name__ == "__main__":main()
