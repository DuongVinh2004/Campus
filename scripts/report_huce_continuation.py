"""Versioned incremental review registry/matrices; retain all earlier audits."""
import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "services/api/src")]
from huce_source_registry import checked, save
from public_rag_retrieval import load_public_hybrid_store, public_hybrid_index_path


def main():
    output = checked(ROOT / "data/huce-discovery-20261020" / datetime.now(UTC).strftime("review-%Y%m%dT%H%M%S%fZ"))
    output.mkdir(exist_ok=False)
    evidence = checked(ROOT / ".tooling/huce-continuation-20261020-01")
    baseline = ROOT / "data/huce-discovery-20261020/audit-20261020T154933256114Z"
    directory = ROOT / "data/huce-public-20261013"
    names = ("reviewed-services-20261020-01.json", "reviewed-course-review-20261021.json", "reviewed-withdrawal-20261021.json")
    releases = [json.loads(checked(directory / name).read_text(encoding="utf-8")) for name in names]
    items = [item for release in releases for item in release["chunks"]]
    for item in items:
        assert hashlib.sha256(checked(ROOT / "data" / item["source_file"]).read_bytes()).hexdigest() == item["source_sha256"]
        assert hashlib.sha256(item["text"].encode()).hexdigest() == item["text_sha256"]
    store = load_public_hybrid_store(directory, tenant_id="HUCE", campus_id="HUCE", faq_directory=ROOT / "data/huce-faq-20261013")
    save(output / "source-registry.json", {"base_registry": str(baseline / "source-registry.json"),
        "semantics": "Incremental selected-excerpt reviews; does not certify whole documents or the inherited corpus",
        "reviews": items})
    save(output / "manifest.json", {"created_at": datetime.now(UTC).isoformat(), "originals_preserved": True,
        "releases": [str(directory / name) for name in names], "index": str(public_hybrid_index_path(store)),
        "fingerprint": store.fingerprint, "prior_audit": str(baseline), "evidence_directory": str(evidence),
        "matrix_semantics": "Inherited rows retain historical observations; appended rows describe this session only"})
    save(output / "active-rag-inventory.json", [{k: row.get(k) for k in (
        "source_id", "document_version_id", "chunk_id", "title", "canonical_uri", "version_label", "source_status",
        "section_path", "page_start", "page_end", "quote_span_hash", "provenance")} for row in store.rows])
    with checked(baseline / "coverage-matrix.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = list(reader.fieldnames), list(reader)
    fields += ["observation_version", "reviewed_facts", "e2e_partial_observations"]
    for row in rows:
        row["observation_version"] = "inherited_prior_audit_not_revalidated"
    for topic, domain, cohort, facts, gap, observations in (
        ("it_support", "ttcntt.huce.edu.vn", "UNRESOLVED", "Office steps 1–4; existing supplied account only", "account issuance/reset and broken illustrations remain unreviewed", 2),
        ("curriculum", "huce.edu.vn", "K71", "QLDA bachelor title, total/exclusions, three semester-1 cells", "remaining course grid and prerequisite arrows unreviewed", 2),
        ("registration", "huce.edu.vn", "UNRESOLVED", "Page27: withdrawal 4 steps and wishlist classes 6 steps", "specific deadlines/eligibility not fully supported; E2E is partial, not fully grounded", 0),
    ):
        rows.append(dict(topic=topic, unit_domain=domain, cohort=cohort, system="UNRESOLVED", academic_year="UNRESOLVED",
            candidate_documents=1, rag_candidate_chunks=1, scope_verified="selected_facts_only",
            e2e_grounded_observations=observations, gap=gap, observation_version="continuation-20261021",
            reviewed_facts=facts, e2e_partial_observations=1 if topic == "registration" else 0))
    with checked(output / "coverage-matrix.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    with checked(baseline / "curriculum-coverage.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream); fields, rows = list(reader.fieldnames), list(reader)
    fields += ["new_review_version", "new_total_verified", "new_selected_cells", "prerequisite_review"]
    for row in rows:
        if "1olWqgtF6y3VV1e2_DdVXxrdmZUn55d-l" in row["public_url"]:
            row.update(new_review_version="reviewed-course-review-20261021", new_total_verified=True,
                       new_selected_cells=3, prerequisite_review="not_admitted")
    with checked(output / "curriculum-coverage.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    summary = {"output": str(output), "new_downloads": 0, "new_crawl_attempts": 0, "newly_reviewed_sources": 3,
        "new_source_excerpts": 1, "corrected_existing_excerpts": 2, "selected_course_cells_reviewed": 3,
        "baseline_parent_rows": 220, "active_parent_rows": len(store.rows), "child_vectors": len(store.children),
        "new_real_embeddings_across_three_builds": 3, "complete_huce_corpus": False,
        "index": str(public_hybrid_index_path(store)), "fingerprint": store.fingerprint,
        "limits": ["Automated batch2 and title-only batch3 are not all visually reviewed",
                   "Ambiguous programme/course question still returned missing_source",
                   "Withdrawal now answers verified process steps but remains partial for specific conditions/deadlines",
                   "Leave/return run persisted an internal system_error; generic legal-content guard matched a quoted no-law-violation condition",
                   "UI effective-date label currently also displays retrieval-admission timestamps"]}
    save(output / "summary.json", summary)
    save(evidence / ("final-report-location-" + output.name + ".json"), summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
