"""Correct provenance matching, without rerunning inference or changing answers."""
import hashlib
import json
import sys
from certificate_stage1_workspace import ROOT, STATE, retain
sys.path[:0] = [str(ROOT / "services/api/src")]
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore


if __name__ == "__main__":
    data = json.loads((ROOT / "evals/datasets/certificate-development-20261013.json").read_text(encoding="utf-8"))
    prior_path = STATE / "retrieval-baseline-01.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    store = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="huce-local-public", campus_id="HUCE")
    mapping = {}
    for key, page in (("catalog", 35), ("procedure", 39)):
        matches = [r for r in store.rows if r["page_start"] == page and r["canonical_uri"] == data["sources"][key]["url"]]
        if len(matches) != 1:
            raise ValueError("ambiguous source provenance")
        r = matches[0]
        mapping[key] = {"page": page, "chunk_id": r["chunk_id"], "content_sha256": r["quote_span_hash"],
            "active_source_snapshot": "data/huce-public-20261013/handbook-human-reviewed.json",
            "source_snapshot_sha256": hashlib.sha256((ROOT / "data/huce-public-20261013/handbook-human-reviewed.json").read_bytes()).hexdigest(),
            "reason": "Match visually reviewed PDF page to the current canonical excerpt; raw old paired-page corpus hash is not the model excerpt hash."}
    cases = {c["id"]: c for c in data["cases"]}
    results = []
    for previous in prior["results"]:
        row = dict(previous)
        if "skipped" not in row:
            refs = cases[row["id"]]["source_refs"]
            ids = {r["chunk_id"] for r in row.get("sources", [])}
            row["raw_corpus_hash_match_not_valid_quality_metric"] = row.pop("required_source_coverage")
            row["required_source_coverage"] = all(mapping[ref]["chunk_id"] in ids for ref in refs) if refs else None
        results.append(row)
    measured = [r for r in results if "skipped" not in r and r["required_source_coverage"] is not None]
    corrected = {**{k:v for k,v in prior.items() if k not in {"source_covered", "source_cases_measured", "results"}},
        "provenance_mapping": mapping, "prior_report_sha256": hashlib.sha256(prior_path.read_bytes()).hexdigest(),
        "source_covered": sum(r["required_source_coverage"] for r in measured), "source_cases_measured": len(measured), "results": results,
        "rescore_note": "No inference rerun, no source or expected-answer edits. Report01 raw hash metric is invalid; report02 matches fixed expected source_refs to verified page 35/39 in the actual canonical corpus."}
    retain(STATE / "retrieval-baseline-rescored-02.json", corrected)
    print(json.dumps({"source_covered": corrected["source_covered"], "source_cases_measured": corrected["source_cases_measured"]}))
