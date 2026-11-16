"""Typed final response conversion for the approved chat SSE binding.

This consumes the graph outcome; it never runs retrieval, repairs a draft,
executes a tool or changes the graph's domain decision.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, replace
from typing import Any

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    field_validator,
)

from campus247.agent.state import AgentState, Route, Terminal, ToolPhase
from campus247.agent.streaming import StreamValidationResult
from campus247.application.conversation.guidance_block import render_guidance
from campus247.application.retrieval.simulation import label_grounded_answer
from campus247.domain.shared.values import generate_uuid7

UUID7_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
SAFE_ABSTENTION = (
    "Tôi chưa thể xác minh câu trả lời từ nguồn có đủ thông tin kiểm chứng. "
    "Bạn có thể làm rõ câu hỏi hoặc gửi yêu cầu hỗ trợ."
)


class CitationLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    section_path: StrictStr | None = Field(default=None, min_length=1, max_length=500)
    page_start: StrictInt | None = Field(default=None, ge=1)
    page_end: StrictInt | None = Field(default=None, ge=1)
    paragraph_id: StrictStr | None = Field(default=None, min_length=1, max_length=100)


class ApiCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    citation_id: StrictStr = Field(pattern=UUID7_PATTERN)
    source_id: StrictStr = Field(pattern=UUID7_PATTERN)
    document_version_id: StrictStr = Field(pattern=UUID7_PATTERN)
    chunk_id: StrictStr = Field(pattern=UUID7_PATTERN)
    source_title: StrictStr = Field(min_length=1, max_length=300)
    canonical_uri: StrictStr = Field(min_length=1, max_length=2000)
    version_label: StrictStr = Field(min_length=1, max_length=64)
    source_status: StrictStr = Field(pattern=r"^(CURRENT|SUPERSEDED|EXPIRED|SYNTHETIC)$")
    locator: CitationLocator
    quote: StrictStr = Field(max_length=500)
    release_id: StrictStr | None = Field(default=None, pattern=UUID7_PATTERN)
    release_generation: StrictInt | None = Field(default=None, ge=0)
    evidence_sha256: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    unit_id: StrictStr | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")

    @field_validator("canonical_uri")
    @classmethod
    def validate_canonical_uri(cls, value: str) -> str:
        AnyUrl(value)
        # Validation must not rewrite the server's canonical evidence URI.
        return value


@dataclass(frozen=True)
class StreamCitation:
    turn_citation_id: str
    citation_json: str

    def to_dict(self) -> dict[str, Any]:
        return {"turn_citation_id": self.turn_citation_id, "citation": json.loads(self.citation_json)}


@dataclass(frozen=True)
class FinalChatResult:
    status: str
    response_class: str
    content: str
    citations: tuple[StreamCitation, ...] = ()
    agent_run_id: str | None = None


class StreamFailure(Exception):
    """Only allowlisted codes cross the transport boundary, never exception text."""

    def __init__(self, code: str = "INTERNAL_ERROR") -> None:
        self.code = code
        super().__init__(code)


def _grounded_citations(state: AgentState) -> tuple[StreamCitation, ...]:
    assert state.draft is not None
    refs = set(re.findall(r"\[(CIT-[0-9]{3,})\]", state.draft.text))
    candidates = state.tool_flow.candidates if state.tool_flow else None
    if not refs or not candidates or len(refs) > 20:
        raise ValueError("unresolvable citation mapping")
    resolved: list[StreamCitation] = []
    for index, candidate in enumerate(candidates, start=1):
        local_id = f"CIT-{index:03d}"
        if local_id not in refs:
            continue
        if not isinstance(candidate, dict):
            raise ValueError("missing server citation metadata")
        # Required metadata comes from the server evidence, never from model text.
        citation = ApiCitation(
            citation_id=generate_uuid7(), source_id=candidate["source_id"],
            document_version_id=candidate["document_version_id"], chunk_id=candidate["chunk_id"],
            source_title=candidate["title"], canonical_uri=candidate["canonical_uri"],
            version_label=candidate["version_label"], source_status=candidate["source_status"],
            locator=candidate["locator"], quote=(candidate["quote"] if candidate.get("unit_id")
                                               else candidate["content_text"][:500]),
            release_id=candidate.get("release_id"), release_generation=candidate.get("release_generation"),
            evidence_sha256=candidate.get("evidence_sha256"),
            unit_id=candidate.get("unit_id"),
        )
        locator = citation.locator.model_dump(exclude_none=True)
        if (not locator or (citation.locator.page_end is not None and
                            (citation.locator.page_start is None or citation.locator.page_end < citation.locator.page_start))):
            raise ValueError("invalid citation locator")
        if citation.source_status not in {"CURRENT", "SYNTHETIC"}:
            raise ValueError("citation is not current")
        resolved.append(StreamCitation(local_id, citation.model_dump_json(exclude_none=True)))
    if {citation.turn_citation_id for citation in resolved} != refs:
        raise ValueError("unknown citation reference")
    return tuple(resolved)


def prepare_chat_result(state: AgentState) -> FinalChatResult:
    result = _prepare_chat_result(state)
    if isinstance(state, AgentState) and state.agent_run_id is not None:
        from campus247.domain.shared.values import is_valid_uuid7
        if not is_valid_uuid7(state.agent_run_id):
            raise StreamFailure()
        return replace(result, agent_run_id=state.agent_run_id)
    return result


def _prepare_chat_result(state: AgentState) -> FinalChatResult:
    if isinstance(state, AgentState) and "AI_AGENT_UNNECESSARY_TASK" in state.errors:
        return FinalChatResult("abstained", "system_error",
            "Kế hoạch tìm bổ sung chưa khớp phần cần tra cứu. Bạn có thể hỏi một phần cụ thể hơn.")
    if isinstance(state, AgentState) and any(code.startswith("AI_AGENT_") for code in state.errors):
        failures = {"MODEL_TIMEOUT", "MODEL_FAILURE", "MODEL_INVALID_OUTPUT", "MODEL_INVALID_USAGE",
            "MODEL_OUTCOME_UNKNOWN", "RETRIEVAL_TIMEOUT", "RETRIEVAL_UNAVAILABLE", "SOURCE_TIMEOUT",
            "SOURCE_UNAVAILABLE", "DEADLINE_EXCEEDED", "WORKFLOW_FAILURE", "TASK_FAILURE",
            "AUTHORIZATION_UNAVAILABLE", "SOURCE_DENIED", "SOURCE_HASH_MISMATCH", "SOURCE_INELIGIBLE",
            "RETRIEVAL_DENIED", "RETRIEVAL_INVALID_OUTPUT", "PLAN_INVALID_OUTPUT", "TASK_INVALID_OUTPUT",
            "COVERAGE_INVALID_OUTPUT", "COVERAGE_INVALID_PROVENANCE", "DECISION_INVALID_OUTPUT",
            "TASK_DEPENDENCY_FAILED", "MODEL_BUDGET_EXHAUSTED", "TOOL_BUDGET_EXHAUSTED", "EVIDENCE_BUDGET_EXHAUSTED"}
        if any("AI_AGENT_" + code in state.errors for code in failures):
            return FinalChatResult("abstained", "system_error",
                state.draft.text if state.draft and state.draft.text else "Dịch vụ xử lý yêu cầu chưa hoàn tất.")
    if isinstance(state, AgentState) and "AI_GENERATION_UNAVAILABLE" in state.errors:
        if "AI_GENERATION_TIMEOUT" in state.errors:
            text = "Dịch vụ tạo câu trả lời phản hồi quá chậm. Bạn có thể thử lại câu hỏi."
        elif "AI_GENERATION_EMPTY_CLAIMS" in state.errors:
            text = "Tôi chưa có nội dung đủ căn cứ để trả lời từ nguồn đã tìm. Bạn có thể làm rõ câu hỏi hoặc phạm vi cần tra cứu."
        elif any(code in state.errors for code in ("AI_GENERATION_INVALID_SCHEMA", "AI_GENERATION_EMPTY_OUTPUT")):
            text = "Kết quả tạo câu trả lời chưa đúng định dạng kiểm chứng. Bạn có thể thử lại câu hỏi."
        else:
            text = "Dịch vụ tạo câu trả lời chưa hoàn tất yêu cầu. Bạn có thể thử lại sau."
        return FinalChatResult("abstained", "safe_refusal", text)
    if not isinstance(state, AgentState) or state.terminal == Terminal.SAFE_FAILURE:
        codes = [code for code in getattr(state, "errors", ())[-8:] if isinstance(code, str) and len(code) <= 64
                 and all(ch.isupper() or ch.isdigit() or ch == "_" for ch in code)]   # finite codes only, never text
        logging.getLogger("campus247.chat").warning("stream_prepare_failure site=1 errors=%s", ",".join(codes) or "-")
        raise StreamFailure()
    if "AI_RETRIEVAL_UNAVAILABLE" in state.errors:
        raise StreamFailure("DEPENDENCY_UNAVAILABLE")
    if state.terminal is None or state.draft is None or not state.draft.text.strip() or len(state.draft.text) > 20000:
        logging.getLogger("campus247.chat").warning("stream_prepare_failure site=2")
        raise StreamFailure()
    status = str(state.terminal)
    if state.terminal in {Terminal.ABSTAINED, Terminal.CANCELLED}:
        response_class = "clarification_request" if "AI_CLARIFICATION_REQUIRED" in state.errors else "safe_refusal"
        if state.terminal == Terminal.ABSTAINED and "RAG_V2_TRANSIENT_ERROR" in state.errors:
            response_class = "system_error"
        guidance = "" if response_class == "system_error" else render_guidance(state.draft.guidance)
        return FinalChatResult(status, response_class, state.draft.text + guidance)
    if state.terminal == Terminal.ANSWERED:
        if state.route == Route.GROUNDED_FAQ:
            if not state.draft.is_grounded or state.draft.gate_decision == "reject":
                return FinalChatResult("abstained", "safe_refusal", SAFE_ABSTENTION)
            try:
                citations = _grounded_citations(state)
            except (ValueError, KeyError, TypeError):
                return FinalChatResult("abstained", "safe_refusal", SAFE_ABSTENTION)
            from campus247.application.retrieval.contact_minimization import present_without_contact_markers
            content = label_grounded_answer(present_without_contact_markers(state.draft.text), cited_statuses=tuple(
                json.loads(citation.citation_json)["source_status"] for citation in citations
            ))
            if state.draft.preface:
                content = state.draft.preface + "\n\n" + content
            guidance = render_guidance(state.draft.guidance)
            if "AI_PARTIAL_COVERAGE" in state.errors:
                return FinalChatResult(status, "partial_answer", content +
                    "\n\n" + (state.draft.partial_note or
                    "Thông tin hiện có chỉ đủ cho một phần câu hỏi. Tôi chưa có đủ nguồn để xác minh phần còn thiếu.") + guidance, citations)
            return FinalChatResult(status, "grounded_answer", content + guidance, citations)
        if state.route == Route.PERSONAL_SCHEDULE:
            return FinalChatResult(status, "tool_result", state.draft.text)
        logging.getLogger("campus247.chat").warning("stream_prepare_failure site=3")
        raise StreamFailure()
    if state.terminal == Terminal.COMPLETED:
        if state.tool_phase == ToolPhase.AWAITING_CONFIRMATION:
            response_class = "action_preview"
        elif state.tool_phase == ToolPhase.SUCCEEDED:
            response_class = "action_result"
        else:
            logging.getLogger("campus247.chat").warning("stream_prepare_failure site=4")
            raise StreamFailure()
        return FinalChatResult(status, response_class, state.draft.text)
    if state.terminal == Terminal.HANDED_OVER:
        return FinalChatResult(status, "handover_notice", state.draft.text)
    logging.getLogger("campus247.chat").warning("stream_prepare_failure site=5")
    raise StreamFailure()


def apply_stream_validation(result: FinalChatResult, validation: StreamValidationResult) -> FinalChatResult:
    if not validation.success:
        # Never publish the raw rejection reason/pattern or retain rejected citations.
        return FinalChatResult("abstained", "safe_refusal", validation.safe_text)
    return replace(result, content=validation.safe_text)
