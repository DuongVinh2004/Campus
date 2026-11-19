from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import math

import pytest

from campus247.application.retrieval.rerank import StrictRerankOutputValidator
from campus247.domain.retrieval import (
    AuthorizedScope, RetrievalCandidate, RetrievalContext, RetrievalQuery, SimulationPolicy,
)
from campus247.ports.reranker import (
    RerankRequest, RerankResult, RerankScore, RerankerContractError, RerankerPort, RerankerProfile,
)


def request(count: int = 2) -> RerankRequest:
    profile = RerankerProfile(
        model_id="BAAI/bge-reranker-v2-m3",
        model_revision="953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
        max_candidates=20, timeout_ms=700,
    )
    context = RetrievalContext(
        authorized_scope=AuthorizedScope(
            tenant_id="HUCE", campus_id="HUCE", actor_id="synthetic-actor",
            roles=frozenset({"STUDENT"}), audiences=frozenset({"STUDENT"}),
            faculty_codes=frozenset({"FIT"}), program_codes=frozenset({"SOFTWARE_ENGINEERING"}),
        ),
        locale="vi", effective_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        simulation_policy=SimulationPolicy.DENY, trace_id="trace-rerank-test",
    )
    candidates = tuple(RetrievalCandidate(
        source_id="synthetic-source", document_version_id="synthetic-version",
        chunk_id=f"chunk-{i}", content_text=f"synthetic policy {i}",
        title="Synthetic policy", issuer="Synthetic", canonical_uri="urn:synthetic:policy",
        quote_span_hash="sha256:" + "a" * 64, section_path=("Section 1",),
    ) for i in range(count))
    return RerankRequest(profile, RetrievalQuery("synthetic private query"), context, candidates)


def result(req: RerankRequest, *ids: str) -> RerankResult:
    return RerankResult(tuple(RerankScore(cid, -i) for i, cid in enumerate(ids)),
                        req.profile.model_id, req.profile.model_revision, 12)


def test_preserves_provider_order_metadata_and_original_candidates():
    req = request()
    response = result(req, "chunk-1", "chunk-0")
    assert StrictRerankOutputValidator().validate(req, response) is response
    assert response.latency_ms == 12
    assert req.candidates[0].content_text == "synthetic policy 0"
    assert req.context.trace_id == "trace-rerank-test"
    with pytest.raises(FrozenInstanceError):
        response.model_revision = "mutated"  # type: ignore[misc]
    assert "synthetic private query" not in repr(req)
    assert "synthetic policy 0" not in repr(req)
    assert "synthetic-actor" not in repr(req)


@pytest.mark.parametrize("ids", [("foreign", "chunk-0"), ("chunk-0", "chunk-0"),
                                  ("chunk-0", "chunk-1", "extra"), ()])
def test_invalid_rankings_are_rejected_without_silent_filter_or_fallback(ids):
    req = request()
    with pytest.raises(RerankerContractError):
        StrictRerankOutputValidator().validate(req, result(req, *ids))


@pytest.mark.parametrize("field,value", [("model_id", "other"), ("model_revision", "main")])
def test_model_and_revision_mismatch_are_rejected(field, value):
    req = request()
    with pytest.raises(RerankerContractError, match="mismatch"):
        StrictRerankOutputValidator().validate(req, replace(result(req, "chunk-0"), **{field: value}))


@pytest.mark.parametrize("score", [math.nan, math.inf, -math.inf, "0.5", True, None, 10 ** 400])
def test_malformed_and_non_finite_scores_are_rejected(score):
    with pytest.raises(RerankerContractError, match="finite"):
        RerankScore("chunk-0", score)


@pytest.mark.parametrize("latency", [-1, math.nan, 1.5, True, "12"])
def test_invalid_latency_is_rejected(latency):
    req = request()
    with pytest.raises(RerankerContractError, match="latency"):
        replace(result(req, "chunk-0"), latency_ms=latency)


def test_profile_limits_and_typed_inputs_fail_closed():
    assert len(request(20).candidates) == 20
    with pytest.raises(RerankerContractError, match="limit"):
        request(21)
    req = request()
    with pytest.raises(RerankerContractError, match="unique"):
        replace(req, candidates=(req.candidates[0], req.candidates[0]))
    with pytest.raises(RerankerContractError, match="typed query"):
        replace(req, context={"role": "SYSTEM_ADMIN"})
    with pytest.raises(RerankerContractError, match="typed candidates"):
        replace(req, candidates=[req.candidates[0]])
    with pytest.raises(RerankerContractError, match="typed rankings"):
        replace(result(req), ranked=({"chunk_id": "chunk-0", "score": 1},))
    with pytest.raises(RerankerContractError, match="typed reranker"):
        StrictRerankOutputValidator().validate(req, {"ranked": []})


@pytest.mark.parametrize("field,value", [("model_id", ""), ("model_revision", " "),
                                        ("max_candidates", 0), ("timeout_ms", 0),
                                        ("max_candidates", True), ("timeout_ms", 1.5)])
def test_invalid_profile_is_rejected(field, value):
    with pytest.raises(RerankerContractError):
        replace(request().profile, **{field: value})


def test_empty_input_and_partial_valid_output():
    req = request(0)
    assert StrictRerankOutputValidator().validate(req, result(req)).ranked == ()
    req = request()
    assert len(StrictRerankOutputValidator().validate(req, result(req, "chunk-1")).ranked) == 1


@pytest.mark.asyncio
async def test_port_preserves_the_exact_typed_context_at_adapter_boundary():
    # Contract fake only; this is not a semantic-quality or production-model test.
    class ContractFake:
        def __init__(self, req):
            self.profile = req.profile
            self.received = None

        async def rerank(self, req):
            self.received = req
            return result(req, "chunk-1", "chunk-0")

    req = request()
    fake = ContractFake(req)
    port: RerankerPort = fake
    response = await port.rerank(req)
    assert fake.received is req
    assert fake.received.context is req.context
    assert fake.received.candidates is req.candidates
    assert StrictRerankOutputValidator().validate(req, response) is response
