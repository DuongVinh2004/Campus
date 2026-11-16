"""Record exact scoped review and observed evidence; preserve all old outputs."""
import ast
from collections import Counter
from datetime import datetime, timezone
import difflib
import hashlib
import json
import subprocess

from unified_ai_runtime_probe import ROOT, checked, retain
from verify_unified_ai_session06 import STATE, test_results

NEW_FILES = [
    "services/api/src/campus247/application/assistance/durable_services.py",
    "services/api/src/campus247/bootstrap/consent_storage.py",
    "tests/integration/test_unified_durable_services.py",
    "scripts/prepare_unified_ai_session06.py", "scripts/verify_unified_ai_session06.py",
    "scripts/finalize_unified_ai_session06.py", "docs/UNIFIED_AI_SESSION06_20261014.md",
]


def main():
    preflight = json.loads(checked(STATE / "preflight.json").read_text(encoding="utf-8"))
    runtime = json.loads(checked(STATE / "runtime-verification-01.json").read_text(encoding="utf-8"))
    migration = json.loads(checked(STATE / "migration-compatibility-01.json").read_text(encoding="utf-8"))
    backlog_path = checked(ROOT / "docs/UNIFIED_AI_IMPLEMENTATION_BACKLOG_20261014.json")
    backlog = json.loads(backlog_path.read_text(encoding="utf-8"))
    previous = json.loads(checked(STATE / "source-before-07.snapshot").read_text(encoding="utf-8"))
    assert backlog["next_task"] == "UNI-006" and len(backlog["tasks"]) == 50
    assert [(t["id"],t["status"]) for t in backlog["tasks"]] == [(t["id"],t["status"]) for t in previous["tasks"]]
    assert all(s["state"] == "finished" for s in runtime["baseline"]["sessions"])
    scoped = []
    for item in preflight["sources"]:
        before = checked(STATE / item["backup"]).read_bytes()
        assert hashlib.sha256(before).hexdigest() == item["sha256"]
        after = checked(ROOT / item["path"]).read_bytes()
        delta = "".join(difflib.unified_diff(before.decode("utf-8").splitlines(keepends=True),
            after.decode("utf-8").splitlines(keepends=True), fromfile=item["backup"],tofile=item["path"]))
        scoped.append({"path":item["path"],"backup":item["backup"],"sha256":hashlib.sha256(after).hexdigest(),"diff":delta})
    fresh = []
    for name in NEW_FILES:
        path = checked(ROOT / name); data = path.read_bytes()
        if path.suffix == ".py": ast.parse(data.decode("utf-8"),filename=name)
        fresh.append({"path":name,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)})
    status = subprocess.run(["git","status","--porcelain=v1"],cwd=ROOT,capture_output=True,text=True,check=True)
    original_entries = set(preflight["git_status"].splitlines())
    current_entries = set(status.stdout.splitlines())
    assert original_entries <= current_entries, "pre-existing Git entry changed; inspect without restoring"
    allowed = set(NEW_FILES) | {item["path"].replace("\\","/") for item in preflight["sources"]} | {"infra/local/unified-ai-20261014-06/"}
    unexpected = sorted(line for line in current_entries-original_entries if line[3:].replace("\\","/") not in allowed)
    assert not unexpected, unexpected
    diff = subprocess.run(["git","diff","--check","--","services/api/src/campus247/bootstrap/app.py",
        "services/api/src/campus247/bootstrap/settings.py"],cwd=ROOT,capture_output=True,text=True)
    assert diff.returncode == 0
    source_lint = [n for n in NEW_FILES if n.endswith(".py")]
    lint_command = [str(checked(ROOT / ".venv/Scripts/ruff.exe")),"check","--no-cache","--select","F,E9",*source_lint]
    lint = subprocess.run(lint_command,cwd=ROOT,capture_output=True,text=True)
    assert lint.returncode == 0, lint.stdout
    retain(STATE / "scoped-review-01.json", {"preimages":scoped,"new_files":fresh,
        "git_status":status.stdout,"git_warnings":status.stderr,"preexisting_git_entries_preserved":True,
        "unexpected_new_git_entries":unexpected,"scoped_diff_check_exit":diff.returncode,
        "scoped_diff_warnings":diff.stderr,"new_python_ast":"pass","lint_command":lint_command,
        "lint_exit":lint.returncode,"lint_output":lint.stdout,
        "initial_lint":{"exit_code":1,"diagnostics":"Two unused imports in the new verification runner; removed by scoped patch, no automatic --fix"},
        "initial_finalize":{"exit_codes":[1,1],"diagnostics":"Read-only scope check first omitted backed-up clean source targets, then compared Windows separators against Git forward slashes. Included exact preflight paths with separator normalization; neither failed attempt wrote a report"},
        "known_unrelated_global_diff_check":"Earlier global git diff --check returned1 for pre-existing apps/web/src/app/globals.css:945 blank EOF; left unchanged",
        "review_notes":["preview is bound to actor/tenant/session and exact internal-state payload",
            "no grant activation or business mutation/receipt authority",
            "bundle is an immutable resource-version observation, not a cross-database execution transaction",
            "schema/revision/receipt failure closes reads/commit without repair or fallback",
            "no live handoff; v6 composition is fixture/clone evidence only"]})
    report = {"captured_at":datetime.now(timezone.utc).isoformat(),"tests":test_results(),
        "backlog_status_counts":dict(Counter(t["status"] for t in backlog["tasks"])),"next_task":"UNI-006",
        "UNI_006_status":"in_progress","full_UNI_006_acceptance":False,"pending_verification":backlog["pending_verification"],
        "source_candidate_version":"unified-local-v6","source_services_wired_on_fixtures":True,
        "product_settings_grants_enabled":False,"grants_are_requests_only":True,"receipts":"internal_state_commit_only",
        "proposal_bundle_scope":"own student DRAFT; immutable candidate plus evidence; use revalidates business/source versions",
        "main_consent_composition":"explicit ephemeral/sqlite/injected; configured SQLite requires initialized file",
        "candidate_consent_composition":"disabled/sqlite; SQLite verified on fixtures/clones, not live",
        "runtime":runtime["runtime"],"ownership":runtime["ownership"],"runtime_handoff":False,
        "runtime_handoff_reason":runtime["handoff_reason"],"live_consent_adapter_enabled":False,
        "held_sources":runtime["held_sources"],"migration":migration,"frontend_unchanged":True,
        "preexisting_git_entries_preserved":True,"all_source_preimages_retained":True,"scoped_review":"scoped-review-01.json",
        "model_dispatches":0,"human_measurements_started":0,"human_usability_verified":False,
        "paid_call_delta":0,"native_deltas":runtime["native_deltas"],"caps_and_uncertain_reservations_retained":True,
        "production_changes":False,"cleanup_delete_discard_commit_push_deploy":False,"coding_subagents_spawned":False,
        "commands":{"tests":"test-command-01/02/03.json","clone_rehearsal_exit":0,"runtime_readback_exit":0,"scoped_lint_exit":0},
        "remaining_scope_tasks":["UNI-006","UNI-007","UNI-009","UNI-010","UNI-015","UNI-028","UNI-030","UNI-031"]}
    retain(STATE / "session-verification-01.json",report)
    task = next(t for t in backlog["tasks"] if t["id"] == "UNI-006")
    assert all(checked(ROOT / path).exists() for path in task["evidence"])
    print(json.dumps({"tests":report["tests"]["unique"],"runtime":runtime["runtime"]["runtime"],
        "next_task":report["next_task"],"scoped_review":"passed","preexisting_git_entries_preserved":True}))


if __name__ == "__main__":
    main()
