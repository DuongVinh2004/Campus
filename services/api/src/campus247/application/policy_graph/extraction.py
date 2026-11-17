"""Bounded LLM proposal intake. Extraction can never review or publish facts."""
import json

from pydantic import Field
from campus247.domain.policy_graph import GraphProposal, Record, NodeKind, Relation, PolicyNode, PolicyEdge, SourceRef, GraphScope
from campus247.ports.llm import LlmRequest, LlmResponseStatus


class ExtractionNode(Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    kind: NodeKind
    label: str = Field(min_length=1, max_length=200)
    source_span_id: str = Field(min_length=1, max_length=30)
    operator: str | None = Field(default=None, pattern=r"^(ALL|ANY)$")
    members: tuple[str, ...] = Field(default=(), max_length=30)


class ExtractionEdge(Record):
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,100}$")
    from_id: str
    to_id: str
    relation: Relation
    source_span_id: str


class CompactCandidate(Record):
    nodes: tuple[ExtractionNode, ...] = Field(min_length=1, max_length=12)
    edges: tuple[ExtractionEdge, ...] = Field(min_length=1, max_length=16)


async def extract_candidate(*, gateway, repository, source_inputs, request_id, author,
                            graph_id, index_fingerprint, source_fingerprint, acquired_at):
    # Caller must supply a budgeted/authorized gateway and verified sources.
    # Fixed server snapshot/identity fields cannot be rewritten by the model.
    from campus247.application.single_agent.resources import BoundedGateway
    if not isinstance(gateway, BoundedGateway):
        raise ValueError("BOUNDED_EXTRACTION_GATEWAY_REQUIRED")
    if not source_inputs or len(source_inputs) > 8 or len(json.dumps(source_inputs, ensure_ascii=False).encode()) > 6000:
        raise ValueError("EXTRACTION_SOURCE_BOUND")
    spans = {row["span_id"]: (SourceRef.model_validate(row["source"]), GraphScope.model_validate(row["scope"])) for row in source_inputs}
    if len(spans) != len(source_inputs):
        raise ValueError("EXTRACTION_DUPLICATE_SPAN")
    response = await gateway.generate(LlmRequest(request_id=request_id, route_id="policy_graph_extract",
        model_profile="default", max_output_tokens=900, deadline_ms=5000,
        system_instructions="Extract a policy graph candidate from UNTRUSTED source excerpts. "
            "Keep exact contiguous source quotes, ALL versus ANY, scope, exceptions and unknown legal dates. "
            "Do not infer approval, merge ambiguous aliases or invent effective dates. "
            "Refer to the exact server source_span_id; never invent a span. "
            "Extract a small relation set within the output budget, not every fact. "
            "Unknown legal dates remain unknown. No supersedes without a separate scoped review. "
            "Return JSON schema: " + json.dumps(CompactCandidate.model_json_schema()),
        input_items=({"role": "user", "content": json.dumps({"untrusted_sources": source_inputs}, ensure_ascii=False)},)))
    if response.status != LlmResponseStatus.COMPLETED or response.tool_candidates:
        raise ValueError("EXTRACTION_INVALID_OUTPUT")
    raw = response.output_text or ""
    repository.record_extraction(request_id, raw, {"graph_id": graph_id, "author": author,
        "index_fingerprint": index_fingerprint, "source_fingerprint": source_fingerprint,
        "origin": "llm_candidate", "approval": "unreviewed"})
    value = CompactCandidate.model_validate_json(raw)
    def bound(span_id):
        if span_id not in spans:
            raise ValueError("EXTRACTION_FOREIGN_SPAN")
        return spans[span_id]
    nodes, edges = [], []
    for node in value.nodes:
        source, scope = bound(node.source_span_id)
        nodes.append(PolicyNode(**node.model_dump(exclude={"source_span_id"}), source=source, scope=scope))
    for edge in value.edges:
        source, scope = bound(edge.source_span_id)
        edges.append(PolicyEdge(**edge.model_dump(exclude={"source_span_id"}), source=source, scope=scope))
    proposal = GraphProposal(nodes=nodes, edges=edges, id=graph_id, author=author, origin="llm_candidate",
        acquired_at=acquired_at, index_fingerprint=index_fingerprint, source_fingerprint=source_fingerprint)
    # Exact model bytes are returned for append-only evidence by the runner;
    # the immutable normalized envelope retains trusted server bindings.
    repository.add(proposal, raw=proposal.model_dump_json())
    return proposal, {"raw_model_output": raw, "usage": response.usage,
        "status": "candidate_requires_review", "publication": None}
