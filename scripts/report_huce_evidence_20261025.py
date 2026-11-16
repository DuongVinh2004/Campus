"""Reconcile current source status and adjudicate exact immutable audit receipts."""
import argparse
import asyncio
import json
import re
import subprocess
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime
from xml.etree import ElementTree

from audit_huce_rag_20261023 import API, client
from complete_huce_corpus import SCOPE, actors, read
from knowledge_platform import ROOT, STATE, TENANT, checked_path, components, retain
from prepare_huce_evidence_20261025 import OUT
from report_huce_corpus_completion import verdict
from campus247.application.conversation.followup import normalized_question
from campus247.application.knowledge.platform_models import digest
from campus247.domain.shared.values import generate_uuid7

MATERIALS = "dc43e7f5-466f-7ce3-8fe2-a10a0c809d9b"
TERMS = {
    "evidence_arch_k71": ("651601", "1"), "evidence_civil_k71": ("428801", "3"),
    "evidence_economics_k71": ("361455", "360401"),
    "evidence_materials_k71": ("x", "y", "so tiet ly thuyet", "so tiet huong dan thuc hanh", "thi nghiem", "chuyen de do an"),
    "evidence_calendar_k68": ("28/09/2026", "thi het hp"),
    "evidence_calendar_k71_planned": ("03/05/2027", "gdqp", "du kien"),
    "evidence_credit_hours": ("50 gio", "15 gio", "30 gio", "50 phut"),
    "evidence_prerequisite_prior": ("hoc va dat hoc phan a", "da phai hoc hoc phan a"),
    "evidence_corequisite_cancel": ("cung hoc ky", "lan hoc dau", "huy hoc phan b"),
}
REFUSALS = {"evidence_arch_k70_unproven", "evidence_calendar_wrong_year", "evidence_personal_sso"}


async def final_dispositions():
    value = read(OUT / "source-dispositions-01.json")
    row = next(r for r in value["sources"] if r["source_id"] == MATERIALS)
    entry = next(r for r in read(SCOPE / "candidate-plan-08.json")["sources"] if r["source_id"] == MATERIALS)
    row["evidence"] = {**row["evidence"], "plan": "candidate-plan-08.json",
        "candidate_sha256": entry["candidate_sha256"], "applicability": read(ROOT / entry["candidate"])["applicability"],
        "legend_repair_probes": str((OUT / "legend-repair-probes-01.json").relative_to(ROOT))}
    pool, _, platform, _ = await components(); _, owner = actors()
    try:
        async with platform.repo.transaction() as conn:
            key = "evidence-20261025-legend-disposition:" + MATERIALS
            fingerprint = digest(row)
            if not await platform.repo.replay(conn, owner.subject_id, key, fingerprint):
                identifier = generate_uuid7()
                await conn.execute("""INSERT INTO knowledge_source_disposition(id,tenant_id,source_id,original_sha256,category,
                    related_source_id,note,evidence,created_by) VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9)""",
                    identifier, TENANT, MATERIALS, row["original_sha256"], row["category"], row["related_source_id"],
                    row["note"], json.dumps(row["evidence"]), owner.subject_id)
                await platform.repo.audit(conn, owner.subject_id, "knowledge.source.classified", MATERIALS,
                    {"disposition_id": identifier, "category": row["category"]})
                await platform.repo.remember(conn, owner.subject_id, key, fingerprint, {"id": identifier})
        target = OUT / "source-dispositions-final-01.json"
        if target.exists():
            assert read(target) == value
        else:
            retain(target, value)
        return value
    finally:
        await pool.close()


def source_checks(case, receipt, members):
    final = case.get("final") or {}; binding = receipt["state"]["desired"]
    sources = case.get("sources", [])
    return bool(sources) and len(sources) == len(final.get("citations", [])) and all(
        s["status"] == 200 and s["anonymous_status"] == 401 and s["hash_verified"]
        and digest(s["body"]["content_text"].encode()) == s["body"]["citation"]["evidence_sha256"]
        and s["body"]["citation"]["release_id"] == binding["release_id"]
        and s["body"]["citation"]["release_generation"] == binding["generation"]
        and members[s["body"]["citation"]["source_id"]] == s["body"]["citation"]["document_version_id"] for s in sources)


def assess_extra(case, receipt, members):
    name = case["name"]; result = case.get("final") or {}; body = normalized_question(result.get("content", ""))
    if name in REFUSALS:
        passed = result.get("status") == "abstained" and not result.get("citations")
        if name == "evidence_personal_sso": passed &= "chua ket noi" in body
    else:
        passed = result.get("status") == "answered" and all(normalized_question(term) in body for term in TERMS[name]) and source_checks(case, receipt, members)
        if name == "evidence_civil_k71":
            passed &= not bool(re.search(r"\bma(?: hoc phan| mon)?\s+428801\s*[-–−]\s*3\b", body))
    return {"name": name, "passed": bool(passed), "status": result.get("status"), "latency_seconds": case["latency_seconds"]}


def main(args):
    paths = []
    for value in (args.extra, args.regression):
        if not re.fullmatch(r"independent-questions-\d{8}T\d{12}\.json", value):
            raise ValueError("Exact retained audit receipt filename required")
        paths.append(checked_path(STATE / value, ROOT))
    extra, regression = map(read, paths)
    release = read(SCOPE / "candidate-release-08.json")
    memberships = {release["release_id"]: {r["source_id"]: r["version_id"] for r in release["members"]}}
    for receipt in (extra, regression):
        assert receipt["state"]["desired"]["release_id"] == release["release_id"]
        assert receipt["state"]["desired"]["generation"] == 17
    extra_verdicts = [assess_extra(c, extra, memberships[release["release_id"]]) for c in extra["cases"]]
    old_verdicts = [verdict(c, regression, memberships) for c in regression["cases"]]
    assert len(extra_verdicts) == 12 and len(old_verdicts) == 34
    dispositions = asyncio.run(final_dispositions())
    mapping = {r["source_id"]: r for r in dispositions["sources"]}
    current_probes = {}
    for case in extra["cases"]:
        for source in case.get("sources", []):
            citation = source["body"]["citation"]
            current_probes[citation["source_id"]] = {"query": case["question"], "expected_version": citation["document_version_id"],
                "receipt": str(paths[0].relative_to(ROOT)), "generation": 17, "hashes_verified": source["hash_verified"],
                "source_http": source["status"], "anonymous_http": source["anonymous_status"]}
    status = read(SCOPE / "source-status-final-01.json")
    status.update(release_id=release["release_id"], generation=17, counts=dict(Counter(r["category"] for r in dispositions["sources"])))
    for row in status["sources"]:
        current = mapping[row["source_id"]]
        row.update(category=current["category"], note=current["note"],
            serving_version=memberships[release["release_id"]].get(row["source_id"], row.get("serving_version")))
        if row["source_id"] in current_probes:
            row["historical_retrieval_probe"] = row.get("retrieval_probe")
            row["retrieval_probe"] = current_probes[row["source_id"]]
        elif row.get("retrieval_probe"):
            row["retrieval_probe"]["scope_note"] = "Historical generation-15 probe, retained; not a new live probe for this batch."
    if (OUT / "source-status-final-01.json").exists():
        assert read(OUT / "source-status-final-01.json") == status
    else:
        retain(OUT / "source-status-final-01.json", status)
    work = [{"source_id": r["source_id"], "title": r["title"], "uri": r["uri"], "category": r["category"],
        "verified_limit": r["note"], "next_step": "Obtain exact cohort authority" if r["category"] == "SOURCE_SCOPE_UNRESOLVED"
            else "Reconcile omitted original page/cell/condition and preserve its locator before expanding answers"}
        for r in status["sources"] if r["category"] in {"PARTIAL_SOURCE_TEXT", "SOURCE_SCOPE_UNRESOLVED"}]
    assert len(work) == 93
    worklist = {"sources": work, "count": len(work), "unresolved_specific_cohort_count": 7, "all_content_complete": False}
    if (OUT / "remaining-evidence-worklist-01.json").exists():
        assert read(OUT / "remaining-evidence-worklist-01.json") == worklist
    else:
        retain(OUT / "remaining-evidence-worklist-01.json", worklist)
    with closing(client()) as c:
        availability = c.get(API + "/availability").json()
        state = c.get(API + "/state").json()
    tests = ElementTree.parse(OUT / "regression-tests-07.xml").getroot().find("testsuite").attrib
    result = {"at": datetime.now(UTC).isoformat(), "client_date": "2026-10-25", "release_id": release["release_id"],
        "generation": 17, "policy_generation": state["desired"]["policy_generation"], "availability": availability,
        "extra_receipt": str(paths[0].relative_to(ROOT)), "extra_verdicts": extra_verdicts,
        "extra_passed": sum(r["passed"] for r in extra_verdicts), "extra_count": 12,
        "regression_receipt": str(paths[1].relative_to(ROOT)), "regression_verdicts": old_verdicts,
        "regression_passed": sum(r["passed"] for r in old_verdicts), "regression_count": 34,
        "test_suite": tests, "postgres_suite": ElementTree.parse(OUT / "postgres-tests-01.xml").getroot().find("testsuite").attrib,
        "integrity": read(SCOPE / "candidate-integrity-05.json"), "source_counts": status["counts"],
        "this_six_source_batch_checks_passed": all(r["passed"] for r in extra_verdicts + old_verdicts),
        "entire_93_source_completion": False, "sso_and_personal_academic_api": "not_connected",
        "browser_recheck": "not_performed_in_this_batch; source HTTP/auth/hash verified through live API"}
    retain(OUT / f"final-verdict-{args.attempt}.json", result)
    before = read(OUT / "preflight-01.json")["status"].splitlines()
    after = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    deleted_before = {r[3:] for r in before if r[:2] == " D"}
    deleted_after = {r[3:] for r in after.splitlines() if r[:2] == " D"}
    assert deleted_before == deleted_after
    retain(OUT / f"final-scope-check-{args.attempt}.json", {"at": datetime.now(UTC).isoformat(), "git_status": after,
        "preexisting_deleted_paths_unchanged": sorted(deleted_after), "destructive_operations": False,
        "note": "No commit/push/deploy/reset/cleanup. Existing dirty state retained; scoped patches and additive receipts only."})
    print(json.dumps({"release_id": result["release_id"], "generation": 17, "extra_passed": result["extra_passed"],
        "regression_passed": result["regression_passed"], "unresolved_cohort": 7, "remaining_limited_sources": 93,
        "entire_corpus_complete": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--extra", required=True)
    parser.add_argument("--regression", required=True)
    parser.add_argument("--attempt", choices=("01", "02"), default="01")
    main(parser.parse_args())
