"""The actual FAQ collection selects original evidence with immutable bindings."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.infrastructure.retrieval.public_faq_index import PublicFaqIndex
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore
from campus247.agent.nodes.intent import IntentRouterNode
from campus247.agent.state import AgentState, NormalizedTurn, Route

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "data/huce-public-20261013"
FAQ = ROOT / "data/huce-faq-20261013"


def context():
    return RetrievalContext(AuthorizedScope("HUCE", "HUCE", "actor", frozenset({"STUDENT"}),
        frozenset({"STUDENT"}), frozenset({"PUBLIC"}), frozenset({"PUBLIC"})), "vi",
        datetime.now(timezone.utc), SimulationPolicy.DENY, "1" * 32)


@pytest.mark.asyncio
async def test_all_330_real_questions_retrieve_all_bound_source_pages():
    store = PublicKnowledgeStore(SOURCE, tenant_id="HUCE", campus_id="HUCE", faq_directory=FAQ)
    assert len(store.faq_index.entries) == 330
    for entry in store.faq_index.entries:
        state = AgentState(request=NormalizedTurn("session", "turn", "actor", entry["question"]))
        assert IntentRouterNode().route(state).route == Route.GROUNDED_FAQ, entry["question"]
        rows = await store.search(entry["question"], context())
        for binding in entry["sources"]:
            assert any(binding["url"] == row["canonical_uri"] and
                ((binding["pdf_page"] is None and row["page_start"] is None) or
                 binding["pdf_page"] is not None and row["page_start"] is not None
                 and row["page_start"] <= binding["pdf_page"] <= row["page_end"])
                for row in rows), entry["question"]
        for row in rows:
            assert row["source_status"] == "CURRENT" and not row["simulation_label"]
            source = await store.read(row["source_id"], row["document_version_id"], row["chunk_id"], context=context())
            assert hashlib.sha256(source.content_text.encode()).hexdigest() == source.content_sha256


def test_tampered_faq_source_binding_is_rejected(tmp_path):
    document = json.loads((FAQ / "faq.json").read_text(encoding="utf-8"))
    evidence = json.loads((FAQ / "evidence.json").read_text(encoding="utf-8"))
    for item in evidence.values():
        item["source_manifest"] = str((FAQ / item["source_manifest"]).resolve())
    document["faqs"][0]["sources"][0]["source_text_sha256"] = "0" * 64
    (tmp_path / "faq.json").write_text(json.dumps(document), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError, match="evidence mismatch"):
        PublicFaqIndex(tmp_path, SOURCE)


@pytest.mark.parametrize("question,reference", [
    ("Thủ tục xin cấp bảng điểm", "H113"),
    ("Tra cứu phòng tự học thư viện", "L"),
    ("hoc bong can dieu kien gi vay", "H111"),
])
def test_screen_and_unaccented_aliases_select_the_relevant_official_service(question, reference):
    index = PublicFaqIndex(FAQ, SOURCE)
    matches = index.source_matches(question)
    assert any(source["evidence_ref"] == reference for source, _ in matches)
    if reference == "H113":
        assert all(source["evidence_ref"] not in {"R13", "R23"} for source, _ in matches)
