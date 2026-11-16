"""Build a new isolated graph candidate from retained real sources, without model calls."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "services/api/src"), str(ROOT / "packages/synthetic/src"), str(ROOT / "scripts")]
STATE = ROOT / "infra/local/policy-graph-stage5-20261014-01"


def destination(name):
    path = STATE / name
    if not name or Path(name).name != name or path.resolve() == ROOT or not path.resolve().is_relative_to(ROOT):
        raise ValueError("exact graph workspace target required")
    for parent in (path, *path.parents):
        if parent.exists() and (parent.is_symlink() or parent.is_junction()
                or getattr(parent.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("graph reparse target denied")
        if parent == ROOT:
            break
    return path.resolve()


def corpus():
    from scripts.public_rag_retrieval import load_public_hybrid_store
    from campus247.infrastructure.retrieval.public_hybrid import PublicRetrievalPolicy
    return load_public_hybrid_store(ROOT / "data/huce-public-20261013", tenant_id="huce-local-public", campus_id="HUCE",
        faq_directory=ROOT / "data/huce-faq-20261013", policy=PublicRetrievalPolicy(fusion_k=4, query_limit=1))


def review_context():
    from datetime import datetime, timezone
    from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
    # Explicit local development source review; not an independent human verdict.
    return RetrievalContext(AuthorizedScope("huce-local-public", "HUCE", "stage5-development-reviewer",
        frozenset({"KNOWLEDGE_ADMIN"}), frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})),
        "vi", datetime.now(timezone.utc), SimulationPolicy.DENY, "stage5-source-review")


async def build(*, graph_id="huce-policy-development-v1", development_source_review=False, output="build-01.json"):
    from campus247.application.policy_graph.source_mapping import authored_public_proposal
    from campus247.application.policy_graph.service import PolicyGraphService
    from campus247.domain.policy_graph import fingerprint, source_fingerprint
    from campus247.infrastructure.repositories.sqlite_policy_graph import SQLitePolicyGraphRepository
    target = destination(output)
    if target.exists():
        raise FileExistsError("retain existing build report; choose a new exact report name")
    source = corpus()  # Loads the retained index; no inference/provider/network.
    repo = SQLitePolicyGraphRepository(destination("policy-graph.sqlite3"), workspace=ROOT)
    proposal = authored_public_proposal(source, graph_id=graph_id, index_fingerprint=source.fingerprint)
    repo.add(proposal, raw=proposal.model_dump_json(indent=2))
    service = PolicyGraphService(repo, source, index_fingerprint=source.fingerprint,
        source_fingerprint=source_fingerprint(source.rows), graph_id=graph_id)
    context = review_context()
    issues = await service.validate(graph_id, context)
    if issues:
        raise ValueError("graph candidate retained with issues: " + json.dumps(issues))
    publication = None
    if development_source_review:
        revision = 0
        for record in (*proposal.nodes, *proposal.edges):
            revision = await service.review(graph_id, context, target=record.id, verdict="approved",
                note="Development Codex source review: exact retained locator/hash/span; discovery only. "
                    "Unknown legal dates and OCR layout limitations retained. Not independent human assessment.",
                expected_revision=revision)
        preview = service.publication_preview(graph_id, context, expected_revision=revision)
        publication = await service.publish(graph_id, context, expected_revision=revision, confirmation=fingerprint(preview))
    report = {"graph_id": graph_id, "candidate_sha256": fingerprint(proposal.model_dump(mode="json")),
        "node_count": len(proposal.nodes), "edge_count": len(proposal.edges), "issues": issues,
        "source_chunks": len(source.rows), "index_fingerprint": source.fingerprint,
        "source_fingerprint": proposal.source_fingerprint, "publication": publication,
        "review_origin": "development_Codex_source_review" if publication else "unreviewed_candidate",
        "provider_calls": 0, "native_inference_calls": 0, "build_provider_cost_usd": "0",
        "not_verified": ["LLM extraction quality", "fresh live graph-assisted answers", "independent human review",
            "legal effective dates", "detailed form version", "phuc-khao multi-column OCR interpretation"]}
    with target.open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2, ensure_ascii=False)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph-id", default="huce-policy-development-v1")
    parser.add_argument("--development-source-review", action="store_true")
    parser.add_argument("--output", default="build-01.json")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(asyncio.run(build(graph_id=args.graph_id, development_source_review=args.development_source_review, output=args.output)), ensure_ascii=False, indent=2))
