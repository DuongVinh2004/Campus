"""Declared fake SQL rows; verify citation metadata integrity, not model quality."""
from dataclasses import replace

import pytest

from campus247.application.conversation.stream_result import ApiCitation
from campus247.application.retrieval.canonical import CanonicalRetrievalError, CanonicalRetrievalService
from campus247.application.retrieval.filters import RetrievalFilterError
from campus247.domain.retrieval import RetrievalQuery
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.retrieval.postgres_vector import authorized_rows_to_candidates
from tests.unit.retrieval.test_canonical_retrieval import fixture as canonical_fixture
from tests.unit.retrieval.test_postgres_vector_adapter import fixture as sql_fixture


@pytest.mark.parametrize("branch", ["lexical", "vector"])
def test_stored_version_and_synthetic_state_survive_public_citation_conversion(branch):
    _, _, _, _, row = sql_fixture()
    row.update(id=generate_uuid7(), document_version_id=generate_uuid7(), source_id=generate_uuid7(),
        section_path="Policy / Section 2", page_start=3, page_end=4)
    candidate, = authorized_rows_to_candidates([row], lambda _: "Declared synthetic issuer", branch=branch)
    citation = ApiCitation(citation_id=generate_uuid7(), source_id=candidate.source_id,
        document_version_id=candidate.document_version_id, chunk_id=candidate.chunk_id,
        source_title=candidate.title, canonical_uri=candidate.canonical_uri,
        version_label=candidate.version_label, source_status=candidate.source_status,
        locator={"section_path": " / ".join(candidate.section_path),
            "page_start": candidate.page_start, "page_end": candidate.page_end}, quote=candidate.content_text)
    assert citation.version_label == row["version_label"] == "synthetic-v1"
    assert citation.source_status == "SYNTHETIC" and candidate.simulation_label
    assert citation.locator.model_dump(exclude_none=True) == {
        "section_path": row["section_path"], "page_start": 3, "page_end": 4}
    assert citation.canonical_uri == row["canonical_uri"]
    assert candidate.issuer == "Declared synthetic issuer"


@pytest.mark.parametrize("field,value", [
    ("version_label", ""), ("version_label", None), ("document_status", "DRAFT"),
    ("approval_status", "PENDING"), ("is_synthetic", "true"),
])
def test_incomplete_or_ineligible_row_does_not_receive_a_current_citation(field, value):
    _, _, _, _, row = sql_fixture()
    row[field] = value
    with pytest.raises(RetrievalFilterError, match="provenance"):
        authorized_rows_to_candidates([row], lambda _: "Declared synthetic issuer", branch="lexical")


@pytest.mark.asyncio
async def test_version_provenance_disagreement_between_branches_never_reaches_reranker():
    config, context, candidates, requests, _ = canonical_fixture()
    async def lexical(*_, **__):
        return [replace(candidates[0], version_label="synthetic-v1", source_status="SYNTHETIC")]
    async def vector(*_, **__):
        return [replace(candidates[0], version_label="synthetic-v2", source_status="SYNTHETIC")]
    config.update(lexical=lexical, vector=vector)
    with pytest.raises(CanonicalRetrievalError, match="drift"):
        await CanonicalRetrievalService(**config).retrieve(RetrievalQuery("synthetic question"), context)
    assert not requests
