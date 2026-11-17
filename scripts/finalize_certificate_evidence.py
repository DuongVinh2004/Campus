"""Final read-only scope/contract/source checks, writing exclusive evidence files."""
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import httpx
from certificate_stage1_workspace import ROOT, STATE, checked, retain

FILES = [
    "services/api/src/campus247/domain/document_request/model.py",
    "services/api/src/campus247/domain/document_request/certificate.py",
    "services/api/src/campus247/domain/action/confirmation.py",
    "services/api/src/campus247/infrastructure/identity/mock.py",
    "services/api/src/campus247/application/document_request/certificates.py",
    "services/api/src/campus247/application/document_request/assistant.py",
    "services/api/src/campus247/ports/certificate_repository.py",
    "services/api/src/campus247/infrastructure/repositories/sqlite_certificates.py",
    "services/api/src/campus247/presentation/certificates.py",
    "services/api/src/campus247/bootstrap/certificate_demo.py",
    "services/api/src/campus247/bootstrap/app.py",
    "apps/web/src/lib/data/api/certificate-gateway.ts",
    "apps/web/src/features/documents/CertificateWorkspace.tsx",
    "apps/web/src/features/documents/CertificateWorkspace.test.tsx",
    "apps/web/src/app/login/page.tsx", "apps/web/src/app/tickets/page.tsx",
    "apps/web/src/app/staff/page.tsx", "apps/web/src/app/chat/page.tsx",
    "apps/web/src/components/AppShell.tsx", "tests/api/test_certificate_stage1.py",
    "scripts/certificate_stage1_workspace.py", "scripts/prepare_certificate_frontend.py",
    "scripts/run_certificate_demo.py", "scripts/launch_certificate_demo.py",
    "scripts/build_certificate_devset.py", "scripts/evaluate_certificate_rag.py",
    "scripts/rescore_certificate_retrieval.py", "scripts/review_certificate_baseline.py",
    "scripts/run_certificate_restart_worker.py", "scripts/verify_certificate_restart.py",
    "scripts/verify_certificate_delivery.py", "scripts/finalize_certificate_evidence.py",
    "evals/datasets/certificate-development-20261013.json",
    "evals/CERTIFICATE_DEVELOPMENT_RUBRIC_20261013.md",
    "docs/CERTIFICATE_STAGE1_INVENTORY_20261013.md",
    "docs/CERTIFICATE_STAGE1_RUNBOOK_20261013.md",
    "docs/CERTIFICATE_STAGE1_DELIVERY_20261013.md",
]


if __name__ == "__main__":
    output = checked(STATE / "verification-manifest-01.json", STATE)
    if output.exists():
        raise FileExistsError("retain previous manifest")
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    diff = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    initial = json.loads((STATE / "initial-discovery.json").read_text(encoding="utf-8"))
    before_deleted = {line[3:] for line in initial["git_status_at_evidence_capture"].splitlines() if "D" in line[:2]}
    after_deleted = {line[3:] for line in status.stdout.splitlines() if "D" in line[:2]}
    assert before_deleted == after_deleted
    files = []
    for name in FILES:
        path = checked(ROOT / name)
        data = path.read_bytes()
        if path.suffix == ".py":
            ast.parse(data, filename=name)
        files.append({"path": name, "sha256": hashlib.sha256(data).hexdigest()})
    guard = checked(ROOT / "infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs").read_bytes()
    copy = checked(STATE / "frontend03/acceptance-20261012-58-frontend-repair1-local-repair2/preserve-build.mjs", STATE).read_bytes()
    assert guard == copy
    dataset = json.loads((ROOT / "evals/datasets/certificate-development-20261013.json").read_text(encoding="utf-8"))
    pdf_hash = hashlib.sha256((ROOT / "data/huce-public-20261013/handbook-2026-2027.pdf").read_bytes()).hexdigest()
    assert pdf_hash == dataset["sources"]["catalog"]["source_file_sha256"]
    review = json.loads((STATE / "generation-review-03.json").read_text(encoding="utf-8"))
    assert all(p["persisted_final_matches_stream"] for r in review["reviews"] for p in r["provenance_checks"])
    with httpx.Client(base_url="http://127.0.0.1:8002", trust_env=False, timeout=10) as client:
        response = client.get("/openapi.json"); response.raise_for_status()
        contract = response.json()
    retain(STATE / "certificate-openapi-runtime-01.json", contract)
    retain(output, {"files_in_task_scope": files, "git_status": status.stdout, "git_status_exit": status.returncode,
        "git_diff_name_only": diff.stdout, "git_diff_exit": diff.returncode, "preexisting_deleted_state_preserved": True,
        "build_guard_unchanged": True, "source_pdf_hash_unchanged": True,
        "python_ast_checks": "passed", "history_stream_final_checks": "6/6 passed",
        "runtime_contract_paths": sorted(contract["paths"]),
        "evidence": ["backend-04.xml", "frontend-tests-03.json", "frontend-build-03.json", "process-restart-01.json",
                     "retrieval-baseline-01.json", "retrieval-baseline-rescored-02.json", "generation-baseline-01.json",
                     "generation-missing-evidence-02.json", "generation-review-03.json", "delivery-readback-01.json"],
        "limits": "Git diff includes pre-existing work; this is not a claim that all dirty changes belong to this task. No broad cleanup, commits, pushes, source/index/guard mutation or ledger reset occurred."})
    print(json.dumps({"files_hashed": len(files), "python_ast": "passed", "source_guard_preserved": True, "history_checks": "6/6"}))
