"""Probe one sealed curriculum candidate; this helper never activates it."""
import argparse
import asyncio
import re
from datetime import UTC, datetime

from complete_huce_corpus import actors
from continue_huce_completion_20261025 import CORPUS, OUT, ROOT, read, save, sha
from knowledge_platform import TENANT, components
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy


async def main(args):
    review = read(ROOT / args.review)
    release = read(CORPUS / f"candidate-release-{args.release}.json")
    source_id = review["source_id"]
    version = next(m["version_id"] for m in release["members"] if m["source_id"] == source_id)
    rows = []
    semesters = review.get("semesters_admitted")
    if semesters is None:
        assert review.get("full_source_review_complete") is True
        semesters = sorted({c["semester"] for c in review["cells"]})
    for semester in semesters:
        cells = [c for c in review["cells"] if c["semester"] == semester]
        terms = [code for c in cells for code in c["course_codes"]] + [c["text"] for c in cells if not c["course_codes"]]
        rows.append({"name": f"semester_{semester}", "question": f"Theo kế hoạch {review['programme_printed']} {review['cohort']}, học kỳ {semester} có những học phần nào?",
            "expected_terms": terms, "expected_present": True})
    cells = {c["id"]: c for c in review["cells"]}
    for edge in review["edges"]:
        a, b = cells[edge["from_cell"]]["course_codes"][0], cells[edge["to_cell"]]["course_codes"][0]
        relation, symbol = ("tiên quyết", "→") if edge["kind"] == "PREREQUISITE" else ("song hành", "↔")
        body = f"{a} là tiên quyết của {b} không?" if edge["kind"] == "PREREQUISITE" else f"{a} và {b} có quan hệ {relation} không?"
        rows.append({"name": "edge_" + edge["id"], "question": f"Theo sơ đồ {review['programme_printed']} {review['cohort']}, {body}",
            "expected_terms": [a, b, symbol], "expected_present": True})
    rows.extend(read(OUT / f"{args.label}-extra-probes-01.json"))
    pool, _, _, runtime = await components(); _, owner = actors()
    roles = frozenset(r.value for r in owner.roles)
    context = RetrievalContext(AuthorizedScope(TENANT, "HUCE", owner.subject_id, roles, roles,
        frozenset({"FIT"}), frozenset({"PUBLIC"})), "vi", datetime.now(UTC), SimulationPolicy.DENY, "b"*32)
    results = []
    try:
        for row in rows:
            items = await runtime.preview_search(owner, row["question"], context, release["release_id"])
            own = [r for r in items if r["document_version_id"] == version]
            passed = (any(all(t in r["content_text"] for t in row["expected_terms"]) for r in own)
                if row["expected_present"] else not own)
            passed &= all(sha(r["content_text"].encode()) == r["evidence_sha256"] for r in items)
            results.append({**row, "passed": bool(passed), "expected_version": version, "items": items})
            print({"name": row["name"], "passed": bool(passed)}, flush=True)
        save(OUT / f"{args.label}-candidate-probes-{args.attempt}.json", {"release_id": release["release_id"],
            "source_id": source_id, "review": args.review, "review_sha256": sha((ROOT / args.review).read_bytes()),
            "cases": results, "count": len(results), "passed": sum(r["passed"] for r in results),
            "all_passed": all(r["passed"] for r in results), "activation_claimed": False})
    finally:
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", required=True); parser.add_argument("--release", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--attempt", choices=["01", "02", "03", "04", "05", "06"], default="01")
    args = parser.parse_args()
    assert re.fullmatch(r"\d{2}", args.release) and re.fullmatch(r"[a-z][a-z0-9-]{1,50}", args.label)
    asyncio.run(main(args))
