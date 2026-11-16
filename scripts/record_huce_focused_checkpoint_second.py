"""Verify the focused scope and retain a checkpoint after the complete API batch."""
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime

from audit_huce_rag_20261023 import API, client, request
from continue_huce_completion_20261025 import CORPUS, OUT, ROOT, checked, read, save, sha


def main():
    manifest = read(OUT / "source-execution-priorities-01.json")
    priority = {r["source_id"]: r for r in manifest["sources"]}
    assert len(priority) == len(manifest["sources"]) == 117
    assert Counter(r["group"] for r in priority.values()) == {"CNTT": 24, "DUNG_CHUNG": 22, "DE_SAU": 71}
    status = read(OUT / "source-status-07.json")
    assert {r["source_id"] for r in status["sources"]} == set(priority)
    for row in status["sources"]:
        assigned = priority[row["source_id"]]
        assert row["execution_priority"] == assigned["execution_priority"] and row["workstream"] == assigned["group"]
        assert row["original_sha256"] == assigned["original_sha256"]
    document = checked(ROOT / "docs/HUCE_ACTIVE_DOCUMENT_SCOPE_20261025.md")
    rows = dict(re.findall(r"(?m)^\| `([0-9a-f]{8})` \| .* \| (Đang tập trung|Để sau) \|$", document.read_text(encoding="utf-8")))
    assert len(rows) == len(priority)
    assert all(rows[sid[:8]] == ("Để sau" if row["group"] == "DE_SAU" else "Đang tập trung") for sid, row in priority.items())
    release = read(CORPUS / "candidate-release-32.json")
    previous = read(CORPUS / "candidate-release-25.json")
    members = {r["source_id"]: r["version_id"] for r in release["members"]}
    old = {r["source_id"]: r["version_id"] for r in previous["members"]}
    assert set(members) == set(old) and len(members) == 114
    changed = [sid for sid in members if members[sid] != old[sid]]
    assert set(changed) == {"ba2795dc-ce32-7325-8b2c-c2bb61eaff1a", "9f9bf571-a71e-707e-8c1b-3bca8cfe089a", "129ba0a6-652e-70b8-8532-8e63661262ce"}
    assert all(priority[sid]["group"] != "DE_SAU" for sid in changed)
    fingerprint = read(OUT / "api-code-fingerprint-20.json")
    assert len(fingerprint["sha256"]) == 16
    assert all(sha(checked(ROOT / name).read_bytes()) == value for name, value in fingerprint["sha256"].items())
    factual = read(OUT / "live-verdict-224-01.json")
    contact = read(OUT / "contact-safe-stream-verdict-01.json")
    assert factual["count"] == 224 and contact["all_checks_passed"]
    assert factual["binding"]["release_id"] == release["release_id"] and factual["binding"]["generation"] == 27
    assert contact["factual_pass_count_unchanged"] == factual["passed"]
    report_file = checked(ROOT / factual["receipt"])
    assert sha(report_file.read_bytes()) == factual["receipt_sha256"]
    input_cases = read(OUT / "it-common-live-cases-224-01.json")
    assert {r["name"] for r in read(report_file)["cases"]} == {r["name"] for r in input_cases}
    tests = ET.parse(checked(OUT / "regression-tests-28.xml")).getroot()
    suites = list(tests.iter("testsuite"))
    totals = {key: sum(int(s.get(key, "0")) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    assert totals == {"tests": 407, "failures": 0, "errors": 0, "skipped": 4}
    backup_file = checked(CORPUS / "backups/post-it-common-20261025-06/receipt.json")
    backup = read(backup_file)
    assert len(backup["copies"]) == 4 and backup["restore_not_run"]
    assert all(sha(checked(backup_file.parent / row["file"]).read_bytes()) == row["sha256"] for row in backup["copies"])
    before = read(OUT / "preflight-01.json")
    git = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, encoding="utf-8", check=True)
    original_deletions = [line for line in before["status"].splitlines() if line[:2].strip() == "D"]
    current_deletions = [line for line in git.stdout.splitlines() if line[:2].strip() == "D"]
    assert len(original_deletions) == 5 and current_deletions == original_deletions
    with closing(client()) as c:
        state = request(c, "GET", API + "/state").json()["desired"]
        availability = request(c, "GET", API + "/availability").json()
    assert state["release_id"] == release["release_id"] and state["generation"] == 27 and state["policy_generation"] == 3
    assert availability["ready"] and availability["serving_documents"] == 114
    failures = [row for row in factual["verdicts"] if not row["passed"]]
    audit = {"at": datetime.now(UTC), "original_deletions": original_deletions,
        "current_deletions": current_deletions, "unchanged_deleted_targets": True,
        "status": git.stdout, "warnings": git.stderr, "no_cleanup_performed": True,
        "scope_document_sha256": sha(document.read_bytes()), "production_code_matches_boot20": True}
    checkpoint = {"at": datetime.now(UTC), "binding": state, "availability": availability,
        "focused_counts": manifest["counts"], "focused_sources": 46, "deferred_sources": 71,
        "all117_sources_classified_once": True, "deferred_versions_unchanged": True,
        "changed_sources": changed, "factual_qa_count": 224, "factual_qa_passed": factual["passed"],
        "factual_failures": failures, "safe_contact_alternative_verified_separately": True,
        "regression_tests": totals, "production_code_matches_boot20": True,
        "backup_receipt": str(backup_file.relative_to(ROOT)), "backup_receipt_sha256": sha(backup_file.read_bytes()),
        "scope_request_completed": True, "all_focused_content_complete": False,
        "limited_focused_sources": 22, "unknown_it_cohorts": 6, "SSO_and_real_API_connected": False,
        "new_offline_reviews_not_admitted": ["71PM", "71IS", "71TH", "CS69/70"],
        "scope": "User-requested prioritization is complete. Offline source findings and a completed safe alternative do not substitute for missing source evidence or passing inline factual QA. Existing documents, versions, data and protections are preserved."}
    save(OUT / "scope-audit-06.json", audit)
    save(OUT / "it-common-checkpoint-01.json", checkpoint)
    print({key: checkpoint[key] for key in ("focused_sources", "deferred_sources", "factual_qa_count", "factual_qa_passed", "scope_request_completed", "all_focused_content_complete")})


if __name__ == "__main__":
    main()
