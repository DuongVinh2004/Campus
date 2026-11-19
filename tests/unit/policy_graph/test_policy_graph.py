"""Synthetic security/topology/fault tests; no claim of model quality."""
import hashlib
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from campus247.application.policy_graph.service import PolicyGraphService, PolicyGraphError, structural_issues
from campus247.domain.policy_graph import GraphProposal, GraphScope, PolicyNode, PolicyEdge, SourceRef, EffectiveInterval, TraversalBounds, fingerprint
from campus247.domain.retrieval import AuthorizedScope, RetrievalContext, SimulationPolicy
from campus247.infrastructure.repositories.sqlite_policy_graph import SQLitePolicyGraphRepository, GraphConflict
from campus247.ports.citation_source import CitationSourceExcerpt

TEXT = "Thủ tục thử nghiệm. Tất cả điều kiện:\na) Có hồ sơ đầy đủ.\nb) Đạt điểm từ 2.0 trở lên.\nMột trong các ngoại lệ. Hiệu lực 01/01/2026 đến 01/01/2027."


def context(*, actor="reviewer", roles=("KNOWLEDGE_ADMIN",), tenant="tenant", faculty="PUBLIC", at=None):
    return RetrievalContext(AuthorizedScope(tenant, "HUCE", actor, frozenset(roles), frozenset({"STUDENT"}),
        frozenset({faculty}), frozenset({"PUBLIC"})), "vi", at or datetime(2026, 10, 14, tzinfo=timezone.utc), SimulationPolicy.DENY, "trace")


def proposal(graph_id="synthetic-v1"):
    scope = GraphScope(tenant_id="tenant", campus_id="HUCE", audiences=("STUDENT",), faculties=("PUBLIC",), programs=("PUBLIC",))
    ref = SourceRef(source_id="source", document_version_id="version", chunk_id="chunk", locator={"section_path": "Clause 1"},
        content_sha256=hashlib.sha256(TEXT.encode()).hexdigest(), quote=TEXT)
    nodes = (PolicyNode(id="procedure", kind="Procedure", label="Thủ tục thử nghiệm", aliases=("thử nghiệm",), scope=scope, source=ref),
        PolicyNode(id="group", kind="ConditionGroup", label="Điều kiện toàn bộ", scope=scope, source=ref,
            operator="ALL", members=("a", "b")),
        PolicyNode(id="a", kind="Condition", label="Đầy đủ hồ sơ", scope=scope, source=ref.model_copy(update={"quote": "a) Có hồ sơ đầy đủ."})),
        PolicyNode(id="b", kind="Condition", label="Điểm tối thiểu", scope=scope, source=ref.model_copy(update={"quote": "b) Đạt điểm từ 2.0 trở lên."})))
    edges = tuple(PolicyEdge(id=f"e{i}", from_id=left, to_id=right, relation="requires", source=ref, scope=scope)
        for i, (left, right) in enumerate((("procedure", "group"), ("group", "a"), ("group", "b"))))
    return GraphProposal(id=graph_id, author="candidate-author", origin="llm_candidate", acquired_at=context().effective_at,
        index_fingerprint="1"*64, source_fingerprint="2"*64, nodes=nodes, edges=edges)


class Reader:
    def __init__(self):
        self.calls, self.denied, self.drift, self.expired, self.unavailable = [], False, False, False, False
    async def read(self, source_id, version_id, chunk_id, *, context):
        self.calls.append((source_id, version_id, chunk_id))
        if self.unavailable:
            raise RuntimeError("secret payload should never escape")
        if self.denied:
            return None
        return CitationSourceExcerpt(source_id, version_id, chunk_id, "Synthetic", "https://synthetic.example",
            "v1", "EXPIRED" if self.expired else "CURRENT", {"section_path": "Clause 1"}, "Test",
            datetime(2026, 1, 1, tzinfo=timezone.utc), None, TEXT + ("changed" if self.drift else ""), hashlib.sha256(TEXT.encode()).hexdigest())


def service(tmp_path, p=None):
    p = p or proposal()
    repo = SQLitePolicyGraphRepository(tmp_path / "graph.sqlite3", workspace=tmp_path)
    repo.add(p, raw=p.model_dump_json())
    reader = Reader()
    return PolicyGraphService(repo, reader, index_fingerprint="1"*64, source_fingerprint="2"*64, graph_id=p.id), p


async def publish(service, p, ctx=None):
    ctx = ctx or context()
    revision = 0
    for record in (*p.nodes, *p.edges):
        revision = await service.review(p.id, ctx, target=record.id, verdict="approved", note="Synthetic source review", expected_revision=revision)
    preview = service.publication_preview(p.id, ctx, expected_revision=revision)
    return await service.publish(p.id, ctx, expected_revision=revision, confirmation=fingerprint(preview))


@pytest.mark.asyncio
async def test_candidates_cannot_be_traversed_or_self_approved(tmp_path):
    s, p = service(tmp_path)
    assert (await s.traverse(context=context(), query="thử nghiệm"))["status"] == "unavailable"
    with pytest.raises(GraphConflict, match="AUTHOR_CANNOT_REVIEW"):
        await s.review(p.id, context(actor=p.author), target="e0", verdict="approved", note="Self review prohibited", expected_revision=0)
    assert s.repository.raw(p.id) == p.model_dump_json()
    assert not s.repository.publication(p.id)


@pytest.mark.asyncio
async def test_publication_preserves_raw_verdicts_and_original_evidence(tmp_path):
    s, p = service(tmp_path)
    manifest = await publish(s, p)
    result = await s.traverse(context=context(), query="thử nghiệm", bounds=TraversalBounds(depth=2))
    assert len(result["edges"]) == 3 and len(result["nodes"]) == 4
    assert result["sources"][0]["content_text"] == TEXT
    assert result["sources"][0]["quote_span_hash"] == hashlib.sha256(TEXT.encode()).hexdigest()
    assert manifest["legal_effective_dates_unknown"] is True
    assert manifest["use"] == "source_discovery_only_not_business_rules"
    reopened = SQLitePolicyGraphRepository(s.repository.path, workspace=tmp_path)
    assert reopened.publication(p.id) == manifest and len(reopened.reviews(p.id)) == 7
    with pytest.raises(GraphConflict):
        reopened.add(p, raw=p.model_dump_json())
    with pytest.raises(GraphConflict, match="PUBLISHED"):
        await s.review(p.id, context(), target="e0", verdict="rejected", note="Published remains immutable", expected_revision=7)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["wrong_tenant", "wrong_faculty", "reader_denied", "expired"])
async def test_authorization_precedes_counts_aliases_and_payloads(tmp_path, kind):
    s, p = service(tmp_path)
    await publish(s, p)
    s.reader.calls.clear()
    ctx = context(tenant="other") if kind == "wrong_tenant" else context(faculty="private") if kind == "wrong_faculty" else context()
    s.reader.denied = kind == "reader_denied"
    s.reader.expired = kind == "expired"
    result = await s.traverse(context=ctx, query="thử nghiệm")
    assert result["nodes"] == result["edges"] == result["sources"] == []
    if kind.startswith("wrong"):
        assert s.reader.calls == [] and "graph_id" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["index_fingerprint", "source_fingerprint"])
async def test_snapshot_mismatch_rejected_before_source_reads(tmp_path, field):
    s, p = service(tmp_path)
    await publish(s, p)
    s.reader.calls.clear()
    setattr(s, field, "f"*64)
    with pytest.raises(PolicyGraphError, match="SNAPSHOT_MISMATCH"):
        await s.traverse(context=context(), query="thử nghiệm")
    assert s.reader.calls == []


@pytest.mark.asyncio
async def test_source_drift_denial_and_graph_outage_are_distinct(tmp_path):
    s, p = service(tmp_path)
    await publish(s, p)
    s.reader.drift = True
    with pytest.raises(PolicyGraphError, match="SOURCE_MISMATCH"):
        await s.traverse(context=context(), query="thử nghiệm")
    s.reader.drift, s.reader.unavailable = False, True
    with pytest.raises(PolicyGraphError, match="SOURCE_UNAVAILABLE") as exc:
        await s.traverse(context=context(), query="thử nghiệm")
    assert "secret" not in str(exc.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("depth,nodes,edge_count", [(0, 4, 0), (1, 4, 1), (2, 4, 3), (4, 1, 0), (4, 2, 1)])
async def test_depth_node_and_cycle_bounds(tmp_path, depth, nodes, edge_count):
    s, p = service(tmp_path)
    await publish(s, p)
    result = await s.traverse(context=context(), query="thử nghiệm", bounds=TraversalBounds(depth=depth, nodes=nodes, edges=3))
    assert len(result["nodes"]) <= nodes and len(result["edges"]) == edge_count


def test_all_any_missing_members_dangling_cycle_alias_and_scope_checks():
    p = proposal()
    assert structural_issues(p) == []
    mutations = [
        (p.model_copy(update={"nodes": (p.nodes[0], p.nodes[1].model_copy(update={"operator": "ANY", "source": p.nodes[1].source.model_copy(update={"quote": TEXT.split("Một trong")[0]})}), *p.nodes[2:])}), "QUANTIFIER_SOURCE_MISMATCH"),
        (p.model_copy(update={"edges": p.edges[:2]}), "INCOMPLETE_CONDITION_GROUP"),
        (p.model_copy(update={"edges": (p.edges[0].model_copy(update={"to_id": "missing"}), *p.edges[1:])}), "DANGLING_EDGE"),
        (p.model_copy(update={"edges": (*p.edges, p.edges[0].model_copy(update={"id": "cycle", "from_id": "a", "to_id": "procedure"}))}), "DIRECTED_CYCLE"),
        (p.model_copy(update={"nodes": (*p.nodes, p.nodes[0].model_copy(update={"id": "ambiguous"}))}), "DUPLICATE_ALIAS"),
        (p.model_copy(update={"edges": (p.edges[0].model_copy(update={"scope": p.nodes[0].scope.model_copy(update={"campus_id": "other"})}), *p.edges[1:])}), "EDGE_SCOPE_MISMATCH"),
        (p.model_copy(update={"edges": (*p.edges, p.edges[0].model_copy(update={"id": "duplicate"}))}), "DUPLICATE_EDGE"),
    ]
    for changed, code in mutations:
        assert code in {issue["code"] for issue in structural_issues(changed)}
    # Same aliases in separately sourced audiences/campuses remain distinct.
    separate = p.nodes[0].model_copy(update={"id": "other-audience", "scope": p.nodes[0].scope.model_copy(update={"audiences": ("ALUMNI",)})})
    assert "DUPLICATE_ALIAS" not in {i["code"] for i in structural_issues(p.model_copy(update={"nodes": (*p.nodes, separate)}))}


def test_temporal_intervals_overlap_and_limited_supersession():
    p = proposal()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2027, 1, 1, tzinfo=timezone.utc)
    interval = EffectiveInterval(start=start, end=end, basis=p.nodes[0].source, status="reviewed")
    assert interval.contains(start) and not interval.contains(end)
    with pytest.raises(ValueError):
        EffectiveInterval(start=start.replace(tzinfo=None), status="reviewed", basis=p.nodes[0].source)
    with pytest.raises(ValueError):
        p.edges[0].model_validate({**p.edges[0].model_dump(), "relation": "supersedes"})
    e1 = p.edges[0].model_copy(update={"interval": interval, "conflict_key": "exclusive"})
    e2 = e1.model_copy(update={"id": "conflict", "to_id": "a"})
    assert "TEMPORAL_CONFLICT" in {i["code"] for i in structural_issues(p.model_copy(update={"edges": (e1, e2, *p.edges[1:])}))}


@pytest.mark.asyncio
async def test_review_cas_incomplete_and_confirmation_are_enforced(tmp_path):
    s, p = service(tmp_path)
    with pytest.raises(PolicyGraphError, match="REVIEW_DENIED"):
        await s.review(p.id, context(roles=("STUDENT",)), target="e0", verdict="approved", note="No review rights", expected_revision=0)
    await s.review(p.id, context(), target="e0", verdict="rejected", note="Keep this rejection", expected_revision=0)
    with pytest.raises(GraphConflict, match="REVISION_CHANGED"):
        await s.review(p.id, context(), target="e0", verdict="approved", note="Stale tab cannot win", expected_revision=0)
    preview = s.publication_preview(p.id, context(), expected_revision=1)
    with pytest.raises(PolicyGraphError, match="REVIEW_INCOMPLETE"):
        await s.publish(p.id, context(), expected_revision=1, confirmation=fingerprint(preview))
    with pytest.raises(PolicyGraphError, match="CONFIRMATION_CHANGED"):
        await s.publish(p.id, context(), expected_revision=1, confirmation="f"*64)
    assert s.repository.reviews(p.id)[0][1].verdict == "rejected"


def test_path_outside_workspace_is_refused(tmp_path):
    with pytest.raises(ValueError, match="outside workspace"):
        SQLitePolicyGraphRepository(tmp_path.parent / "unauthorized.sqlite3", workspace=tmp_path)


def test_numeric_predicate_cannot_change_value_unit_or_strict_comparator():
    from campus247.domain.policy_graph import ConditionPredicate
    p = proposal()
    node = p.nodes[3].model_copy(update={"predicate": ConditionPredicate(comparator=">=", value="2.0", unit="điểm")})
    changed = p.model_copy(update={"nodes": (*p.nodes[:3], node)})
    assert "PREDICATE_SOURCE_MISMATCH" not in {i["code"] for i in structural_issues(changed)}
    wrong = node.model_copy(update={"predicate": ConditionPredicate(comparator=">", value="2.1", unit="điểm")})
    assert "PREDICATE_SOURCE_MISMATCH" in {i["code"] for i in structural_issues(p.model_copy(update={"nodes": (*p.nodes[:3], wrong)}))}


@pytest.mark.asyncio
async def test_publish_preview_binds_session_scope_and_review_revision(tmp_path):
    s, p = service(tmp_path)
    for i, record in enumerate((*p.nodes, *p.edges)):
        await s.review(p.id, context(), target=record.id, verdict="approved", note="Synthetic source review", expected_revision=i)
    preview = s.publication_preview(p.id, context(), expected_revision=7, session_binding="session-one")
    with pytest.raises(PolicyGraphError, match="CONFIRMATION_CHANGED"):
        await s.publish(p.id, context(), expected_revision=7, confirmation=fingerprint(preview), session_binding="session-two")
    assert s.repository.publication(p.id) is None
