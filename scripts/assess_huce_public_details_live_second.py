"""Assess one complete generation27 run, including exact source bindings."""
import argparse
import re
from datetime import UTC, datetime

from assess_huce_completion_second import assess
from continue_huce_completion_20261025 import CORPUS, OUT, ROOT, checked, read, save, sha
from knowledge_platform import STATE
from report_huce_evidence_20261025 import source_checks
from campus247.application.conversation.followup import normalized_question


def contains_material(body, term):
    normalized = normalized_question(term)
    if normalized in body:
        return True
    date = re.fullmatch(r"(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})", normalized)
    slash = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", normalized)
    if date or slash:
        day, month, year = map(int, (date or slash).groups())
        # Date formatting may vary; the day, month and year must all agree.
        return bool(re.search(rf"\b0?{day}\s*/\s*0?{month}\s*/\s*{year}\b", body)
            or re.search(rf"\b0?{day}\s+thang\s+0?{month}\s+nam\s+{year}\b", body))
    return False


def main(args):
    assert re.fullmatch(r"independent-questions-\d{8}T\d{12}\.json", args.receipt)
    file = checked(STATE / args.receipt)
    receipt = read(file)
    release = read(CORPUS / ("candidate-release-32.json" if args.it_common else "candidate-release-31.json"))
    expectation = read(OUT / ("it-common-live-expectations-224-01.json" if args.it_common else "public-details-live-expectations-399-01.json"))
    expected = {r["name"]: r for r in expectation["cases"]}
    smoke = set(expectation["prior_smoke_names"])
    if args.focus:
        names = {r["name"] for r in read(OUT / ("it-common-focus-live-cases-7-01.json" if args.it_common else "public-details-focus-live-cases-08-01.json"))}
        expected = {k: v for k, v in expected.items() if k in names}
        smoke = set()
    else:
        names = set(expected) | smoke
    binding = receipt["state"]["desired"]
    assert binding["generation"] == 27 and binding["release_id"] == release["release_id"]
    assert len(receipt["cases"]) == ((7 if args.focus else 224) if args.it_common else (8 if args.focus else 399))
    assert {r["name"] for r in receipt["cases"]} == names
    members = {r["source_id"]: r["version_id"] for r in release["members"]}
    rows = []
    for case in receipt["cases"]:
        name = case["name"]
        if name in smoke:
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
            missing = [t for t in requirement["expected_terms"] if not contains_material(body, t)]
            if missing:
                failures.append({"missing_material_terms": missing})
            if not source_checks(case, receipt, members):
                failures.append("source_hash_auth_release_binding")
            if any(s["body"]["citation"]["source_id"] != requirement["source_id"] for s in case.get("sources", [])):
                failures.append("wrong_source")
            page = {"stem_application_prompts": 3, "stem_obligations": 3, "stem_activities": 4, "stem_ai_notice": 4,
                "stem_cv": 5, "stem_family": 6, "stem_notice_heading": 1, "stem_notice_recitals": 1,
                "stem_notice_contact": 2, "stem_notice_recipients": 2, "stem_notice_signatory": 2}.get(name)
            if page and not any(s["body"]["citation"]["locator"]["page_start"] == page for s in case.get("sources", [])):
                failures.append("wrong_original_page")
        elif final.get("status") != "abstained" or final.get("citations"):
            failures.append("expected_abstention_without_citations")
        rows.append({"name": name, "passed": not failures, "failures": failures, "status": final.get("status"),
            "conversation_id": case["conversation_id"], "latency_seconds": case["latency_seconds"]})
    result = {"at": datetime.now(UTC), "receipt": str(file.relative_to(ROOT)), "receipt_sha256": sha(file.read_bytes()),
        "binding": binding, "count": len(rows), "passed": sum(r["passed"] for r in rows),
        "all_passed": all(r["passed"] for r in rows), "verdicts": rows,
        "method": "One complete immutable API run; no case substitution. Equivalent numeric/written dates permitted only when day/month/year all agree.",
        "entire_corpus_or_integration_complete": False}
    save(checked(OUT / f"live-verdict-{len(rows)}-{args.attempt}.json"), result)
    print({k: result[k] for k in ("count", "passed", "all_passed")})
    for row in rows:
        if not row["passed"]:
            print(row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--attempt", choices=("01", "02", "03"), required=True)
    parser.add_argument("--focus", action="store_true")
    parser.add_argument("--it-common", action="store_true")
    main(parser.parse_args())
