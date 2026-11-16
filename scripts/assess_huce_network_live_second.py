"""Assess one complete network API run, retaining every failure."""
import argparse
import re
from datetime import UTC, datetime

from assess_huce_completion_second import assess
from continue_huce_completion_20261025 import CORPUS, OUT, ROOT, read, save, sha
from knowledge_platform import STATE
from report_huce_evidence_20261025 import source_checks
from review_huce_network_geometry_second import NETWORK
from review_huce_data_science_second import DATA_SCIENCE
from prepare_huce_stem_full_second import STEM
from review_huce_building_services_second import BUILDING_SERVICES
from prepare_huce_environment_geometry_second import ENVIRONMENT
from campus247.application.conversation.followup import normalized_question


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--attempt", required=True, choices=["01", "02", "03"])
    parser.add_argument("--dataset", choices=["network", "data-science", "stem-combined", "stem-focus", "building-combined", "boundary-combined", "boundary-focus"], default="network")
    args = parser.parse_args()
    assert re.fullmatch(r"independent-questions-\d{8}T\d{12}\.json", args.receipt)
    path = STATE / args.receipt
    receipt = read(path)
    science = args.dataset == "data-science"
    focus = args.dataset == "stem-focus"
    building = args.dataset == "building-combined"
    boundary = args.dataset in {"boundary-combined", "boundary-focus"}
    boundary_focus = args.dataset == "boundary-focus"
    combined = args.dataset in {"stem-combined", "stem-focus", "building-combined"}
    number, generation, count = ("25", 26, 12 if boundary_focus else 294) if boundary else ("23", 26, 249) if building else ("22", 25, 10 if focus else 199) if combined else ("21", 24, 40) if science else ("20", 23, 44)
    release = read(CORPUS / f"candidate-release-{number}.json")
    expectation = read(OUT / ("combined-live-expectations-294-01.json" if boundary else "combined-live-expectations-249-01.json" if building else "combined-live-expectations-199-01.json" if combined else "data-science-live-expectations-01.json" if science else "network-live-expectations-02.json"))
    if focus:
        names = {r["name"] for r in read(OUT / "stem-focus-live-cases-02.json")}
        expectation = {"cases": [r for r in expectation["cases"] if r["name"] in names], "prior_smoke_names": []}
    if boundary_focus:
        names = {r["name"] for r in read(OUT / "boundary-focus-live-cases-01.json")}
        expectation = {"cases": [r for r in expectation["cases"] if r["name"] in names], "prior_smoke_names": []}
    expected = {r["name"]: r for r in expectation["cases"]}
    members = {r["source_id"]: r["version_id"] for r in release["members"]}
    binding = receipt["state"]["desired"]
    assert binding["release_id"] == release["release_id"] and binding["generation"] == generation
    assert len(receipt["cases"]) == count
    assert {r["name"] for r in receipt["cases"]} == set(expected) | set(expectation["prior_smoke_names"])
    rows = []
    for case in receipt["cases"]:
        name = case["name"]
        if name not in expected:
            rows.append(assess(case, receipt, release))
            continue
        requirement = expected[name]
        final = case.get("final") or {}
        body = normalized_question(final.get("content", ""))
        failures = []
        if case["http_status"] != 200:
            failures.append("http")
        if requirement["expected_present"]:
            if final.get("status") != "answered":
                failures.append("required_answer_missing")
            missing = [t for t in requirement["expected_terms"] if normalized_question(t) not in body]
            if missing:
                failures.append({"missing_material_terms": missing})
            if not source_checks(case, receipt, members):
                failures.append("source_hash_auth_release_binding")
            source_id = ENVIRONMENT if name.startswith("envb_") else BUILDING_SERVICES if name.startswith("hk_") else STEM if name.startswith("stem_") else DATA_SCIENCE if name.startswith("ds_") else NETWORK
            if any(s["body"]["citation"]["source_id"] != source_id for s in case.get("sources", [])):
                failures.append("wrong_source")
            if name == "net_semester_8":
                for term in ["Chuyên đề tổng hợp", "Bảo vệ bản quyền số2", "467713", "467703", "467708"]:
                    if normalized_question(term) not in body:
                        failures.append({"missing_semester8_literal": term})
            expected_page = {"stem_application_prompts": 3, "stem_obligations": 3,
                "stem_activities": 4, "stem_cv": 5, "stem_family": 6, "stem_ai_notice": 4}.get(name)
            if expected_page and not any(s["body"]["citation"]["locator"]["page_start"] == expected_page for s in case.get("sources", [])):
                failures.append("missing_original_form_page")
        elif final.get("status") != "abstained" or final.get("citations"):
            failures.append("expected_abstention_without_citations")
        rows.append({"name": name, "passed": not failures, "failures": failures,
            "status": final.get("status"), "conversation_id": case["conversation_id"]})
    result = {"at": datetime.now(UTC), "receipt": str(path.relative_to(ROOT)),
        "receipt_sha256": sha(path.read_bytes()), "binding": binding, "count": len(rows),
        "passed": sum(r["passed"] for r in rows), "all_passed": all(r["passed"] for r in rows),
        "verdicts": rows, "method": "One complete immutable API run; no case substitution",
        "entire_corpus_or_integration_complete": False}
    save(OUT / f"live-verdict-{count}-{args.attempt}.json", result)
    print({k: result[k] for k in ("count", "passed", "all_passed")})
    for row in rows:
        if not row["passed"]:
            print(row)


if __name__ == "__main__":
    main()
