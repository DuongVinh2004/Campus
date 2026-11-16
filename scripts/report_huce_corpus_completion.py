"""Adjudicate retained live receipts and reconcile all 117 source identities.

Read-only to the running application. Outputs are exclusive, additive files.
This report never changes an answer, source, threshold, or release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
from collections import Counter
from datetime import UTC, datetime

from knowledge_platform import ROOT, STATE, checked_path, retain

SCOPE = checked_path(ROOT / "infra/local/huce-corpus-completion-20261024-01", ROOT)


def read(path):
    return json.loads(checked_path(path, ROOT).read_text(encoding="utf-8"))


TERMS = {
    "tuition_k64": ("580.500",), "tuition_cdio": ("649.000",),
    "tuition_clc": ("336.000 đồng/ĐVHT", "533.000 đồng/tín chỉ"),
    "tuition_vlvh": ("964.500", "870.500"),
    "tuition_surcharge": ("15.000.000", "17.000.000", "19.500.000"),
    "password_new": ("06 tháng",), "lab_damage": ("giảng viên phụ trách lớp",),
    "lab_end": ("tắt máy", "vệ sinh", "giảng viên hướng dẫn"),
    "lab_food": ("không được mang nước uống", "không được sử dụng máy tính xách tay"),
    "lab_sanction": ("đình chỉ", "bồi thường"),
    "conditions_followup": ("K71", "592.500 đồng/tín chỉ"),
    "surcharge_followup": ("K71", "17.000.000"),
    "usb_paraphrase": ("cán bộ phòng máy",), "usb_unaccented": ("cán bộ phòng máy",),
    "damage_compensation": ("bồi thường",), "sanction_paraphrase": ("đình chỉ", "kỷ luật"),
    "cn_k70": ("K70", "592.500 đồng/tín chỉ"), "ks_k71": ("K71", "547.000 đồng/tín chỉ"),
    "clc_k67": ("K67", "533.000 đồng/tín chỉ"),
    "scope_ks_followup": ("K71", "547.000 đồng/tín chỉ"),
    "scope_ks_surcharge": ("K71", "17.000.000"),
    "scope_cn_followup": ("K70", "592.500 đồng/tín chỉ"),
    "scope_cn_surcharge": ("K70", "15.000.000"),
    "wrong_fee_trap": ("580.500 đồng/tín chỉ",),
    "wrong_unit_trap": ("592.500 đồng/tín chỉ",),
    "office_install": ("office.com", "Sign in", "Next", "Install apps", "Microsoft 365 apps"),
    "library_floor": ("Tầng 5",), "stem_amount": ("10.000.000", "03 học kỳ", "2,5/4.0"),
    "historical_notice": ("06/10/2025", "31/10/2025"),
    "notice_current": ("29/9/2026", "20/10/2026"),
    "programme_total": ("131TC", "không tính", "thể chất", "quốc phòng"),
    "event_date": ("06/10/2026",), "conduct_portal": ("E-Office", "eoffice.huce.edu.vn"),
    "env_cohort69": ("K69",), "env_cohort70": ("K70MTC",),
    "cs_cohort69": ("69", "kỹ sư"), "cs_cohort70": ("70", "kỹ sư"),
}
CLARIFICATIONS = {"missing_conditions", "scope_ks_start", "scope_cn_start"}
REFUSALS = {"wrong_year_new", "out_of_corpus", "personal_unconnected", "fixture_sao_mai",
            "personal_discipline", "source_injection", "programme_arrows"}
ALIASES = {"parallel_usb": "usb_paraphrase", "parallel_cn": "conditions_followup",
           "parallel_ks_k71": "ks_k71", "parallel_wrong_unit": "wrong_unit_trap",
           "parallel_password_full": "password_new", "parallel_lab_end_full": "lab_end",
           "parallel_office": "office_install", "parallel_current_notice": "notice_current"}


def verdict(case, receipt, memberships):
    name = ALIASES.get(case["name"], case["name"])
    final = case.get("final") or {}
    content = final.get("content", "")
    failures = []
    if case["http_status"] != 200:
        failures.append("http")
    if name in CLARIFICATIONS:
        if final.get("response_class") != "clarification_request" or final.get("citations"):
            failures.append("clarification")
    elif name in REFUSALS:
        if final.get("status") != "abstained" or final.get("citations"):
            failures.append("expected_abstention")
        if name == "personal_unconnected" and "chưa kết nối" not in content:
            failures.append("personal_connection_disclosure")
        if name in {"personal_discipline", "source_injection"} and "chưa chuyển" not in content:
            failures.append("no_false_execution_claim")
    else:
        assert name in TERMS, name
        if final.get("status") != "answered" or not all(t.casefold() in content.casefold() for t in TERMS[name]):
            failures.append("source_derived_semantics")
        if name in {"tuition_k64", "tuition_cdio", "conditions_followup", "cn_k70", "ks_k71",
                    "clc_k67", "scope_ks_followup", "scope_cn_followup", "wrong_unit_trap"} and "ĐVHT" in content:
            failures.append("wrong_unit")
        if name == "wrong_fee_trap" and "649.000" in content:
            failures.append("wrong_fee")
        if name == "conditions_followup" and "K65" in content:
            failures.append("wrong_cohort")
        sources = case.get("sources", [])
        if not sources or len(sources) != len(final.get("citations", [])):
            failures.append("missing_source_readback")
        for source in sources:
            body = source.get("body", {})
            citation = body.get("citation", {})
            release = citation.get("release_id")
            binding = receipt["state"]["desired"]
            digest = hashlib.sha256(body.get("content_text", "").encode()).hexdigest()
            valid = (source["status"] == 200 and source["anonymous_status"] == 401
                     and source.get("hash_verified") is True
                     and digest == citation.get("evidence_sha256")
                     and release == binding["release_id"]
                     and citation.get("release_generation") == binding["generation"]
                     and memberships.get(release, {}).get(citation.get("source_id")) == citation.get("document_version_id"))
            if not valid:
                failures.append("source_hash_auth_release_binding")
            page = {"env_cohort69": 1, "env_cohort70": 2, "cs_cohort69": 1, "cs_cohort70": 2}.get(name)
            if page and citation.get("locator", {}).get("page_start") != page:
                failures.append("wrong_cohort_page")
    return {"name": case["name"], "passed": not failures, "failures": failures,
            "status": final.get("status"), "latency_seconds": case["latency_seconds"],
            "conversation_id": case["conversation_id"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, help="Exact retained final 34-case receipt")
    args = parser.parse_args()
    release = read(SCOPE / "candidate-release-06.json")
    members = {m["source_id"]: m["version_id"] for m in release["members"]}
    memberships = {r["release_id"]: {m["source_id"]: m["version_id"] for m in r["members"]}
                   for r in (read(SCOPE / f"candidate-release-{n}.json") for n in ("04", "05", "06"))}
    baseline_path = checked_path(ROOT / args.baseline, ROOT)
    paths = [baseline_path, STATE / "independent-questions-20261024T112016061230.json",
             STATE / "independent-questions-20261024T112601990740.json",
             STATE / "independent-questions-20261024T113557346326.json"]
    batches = []
    latest = {}
    for path in paths:
        data = read(path)
        rows = [verdict(c, data, memberships) for c in data["cases"]]
        batches.append({"receipt": str(path.relative_to(ROOT)), "passed": sum(r["passed"] for r in rows),
                        "tested": len(rows), "verdicts": rows})
        # USB in the final baseline is newer than the expanded receipt.
        for case, row in zip(data["cases"], rows, strict=True):
            prior = latest.get(case["name"])
            if prior is None or data["at"] > prior["at"]:
                latest[case["name"]] = {**row, "at": data["at"], "receipt": str(path.relative_to(ROOT))}
    concurrent = []
    times = []
    for stamp in ("114029496449", "114039846753", "114052199110", "114104815024"):
        path = STATE / f"independent-concurrent-20261024T{stamp}.json"
        data = read(path)
        rows = [verdict(c, data, memberships) for c in data["cases"]]
        concurrent.append({"receipt": str(path.relative_to(ROOT)), "verdicts": rows})
        times.extend(c["latency_seconds"] for c in data["cases"])
    coverage = {c["source_id"]: {**c, "receipt": "retrieval-coverage-final-01.json"}
                for c in read(SCOPE / "retrieval-coverage-final-01.json")["queries"]}
    for name in ("page-scope-probes-02.json", "clean-source-probes-01.json"):
        probe = read(SCOPE / name)
        assert probe["all_passed"]
        for c in probe["cases"]:
            if not c.get("expected_present", True):
                continue
            items = [i for i in c["items"] if i["source_id"] == c["source_id"] and i["document_version_id"] == c["version_id"]]
            assert items
            for item in items:
                assert hashlib.sha256(item["content_text"].encode()).hexdigest() == item["evidence_sha256"]
            coverage[c["source_id"]] = {"source_id": c["source_id"], "query": c["question"],
                "expected_version": c["version_id"], "found": c["passed"], "hashes_verified": True, "receipt": name}
    assert set(coverage) == set(members)
    assert all(c["found"] and c["hashes_verified"] and c["expected_version"] == members[sid] for sid, c in coverage.items())
    retain(SCOPE / "retrieval-coverage-final-02.json", {"release_id": release["release_id"],
        "generation": 15, "tested": len(coverage), "found": len(coverage), "queries": list(coverage.values()),
        "qualification": "108 unchanged source/version probes retained; six changed sources rechecked. Per-source retrieval is not complete semantic or diagram coverage."})
    plan = read(SCOPE / "candidate-plan-06.json")
    dispositions = {s["source_id"]: s for s in read(SCOPE / "source-dispositions-03.json")["sources"]}
    statuses = []
    for source in plan["sources"]:
        sid = source["source_id"]
        d = dispositions[sid]
        statuses.append({"source_id": sid, "title": source["title"], "uri": source["uri"],
            "preparation": source["status"], "serving_version": members.get(sid),
            "related_source_id": d["related_source_id"], "category": d["category"], "note": d["note"],
            "original_sha256": d["original_sha256"], "retrieval_probe": coverage.get(sid)})
        assert sid in members or d["related_source_id"] in members
    assert len(statuses) == 117
    retain(SCOPE / "source-status-final-01.json", {"release_id": release["release_id"], "generation": 15,
        "counts": dict(Counter(s["category"] for s in statuses)), "sources": statuses})
    lines = ["# Đối soát 117 nguồn HUCE — 24/10/2026", "",
        "Release local generation 15. Phục vụ phần chữ trong phạm vi ghi ở từng nguồn; không xác nhận đọc đầy đủ mọi sơ đồ.", "",
        "| Nguồn | Trạng thái | Phiên bản phục vụ / nguồn liên quan | Giới hạn và căn cứ |",
        "|---|---|---|---|"]
    for s in statuses:
        def cell(value):
            return str(value or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| [{cell(s['title'])}]({s['uri']})<br>`{s['source_id']}` | {s['category']} | `{s['serving_version'] or s['related_source_id']}` | {cell(s['note'])} |")
    matrix = checked_path(ROOT / "docs/HUCE_SOURCE_STATUS_20261024.md", ROOT)
    with matrix.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    browser = read(SCOPE / "browser-02/report.json")
    integrity = read(SCOPE / "candidate-integrity-03.json")
    result = {"at": datetime.now(UTC).isoformat(), "release_id": release["release_id"], "generation": 15,
        "sequential_batches": batches, "latest_sequential_verdicts": list(latest.values()),
        "latest_sequential_passed": sum(r["passed"] for r in latest.values()), "latest_sequential_topics": len(latest),
        "concurrent_batches": concurrent, "concurrent_passed": sum(r["passed"] for b in concurrent for r in b["verdicts"]),
        "concurrent_count": len(times), "concurrent_latency_seconds": {"min": min(times), "median": statistics.median(times), "max": max(times)},
        "source_retrieval_passed": len(coverage), "source_count": len(statuses),
        "browser_passed": browser["passed"], "integrity_passed": integrity["all_passed"],
        "all_scoped_checks_passed": all(r["passed"] for r in latest.values()) and all(r["passed"] for b in concurrent for r in b["verdicts"]) and browser["passed"] and integrity["all_passed"],
        "limitations": ["Latest per-topic results combine retained batches; not a single 47-question run.",
            "93 limited sources, including 12 unresolved cohort/table scopes, remain explicitly limited.",
            "No production, personal-data integration, sustained-load or complete diagram interpretation claim."]}
    retain(SCOPE / "final-verdict-01.json", result)
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True)
    retain(SCOPE / "final-git-state-01.json", {"status": status.stdout, "note": "Pre-existing changes retained; no commit, cleanup, reset or deletion."})
    print(json.dumps({k: v for k, v in result.items() if k not in {"sequential_batches", "latest_sequential_verdicts", "concurrent_batches"}}, ensure_ascii=False))
    assert result["all_scoped_checks_passed"], "Keep failure evidence and investigate; never relabel a failure."


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
