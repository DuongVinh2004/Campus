from __future__ import annotations

import dataclasses
import re
from campus247.domain.publication import official_huce_uri
from campus247.agent.state import AgentState, DraftResponse, Route, Terminal
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.evidence_gate import EvidenceGate, GroundedDraft
from campus247.rag_v2.discipline import CONDITIONAL_FRAME

SECRET_PATTERNS = [
    r"sk-[a-zA-Z0-9_-]{16,}",
    r"bearer\s+[a-zA-Z0-9_\-\.]{20,}",
    r"password\s*[:=]\s*\S+",
    r"secret_token\s*[:=]\s*\S+",
]


def _verified_general_discipline_rule(state: AgentState) -> bool:
    """Only source-verified generic rules can mention disciplinary conditions.

    A quoted public eligibility rule is not a decision about the current user.
    Keep the exception narrower than the ordinary EvidenceGate: every material
    word of affected claims must occur in the cited official document.
    """
    draft = state.draft
    candidates = state.tool_flow.candidates if state.tool_flow else None
    if (state.route != Route.GROUNDED_FAQ or not draft or not draft.is_grounded
            or draft.gate_decision != "grounded" or not draft.grounded_claims or not candidates):
        return False
    claims = draft.grounded_claims
    rendered = "\n".join(c.text + " " + " ".join(f"[{r}]" for r in c.citation_ids) for c in claims)
    if rendered != draft.text:
        return False  # No unverified prose outside the material claims.
    affected = [c for c in claims if re.search(r"kỷ luật", c.text, re.IGNORECASE)]
    bundle = CitationBundle.build(candidates)
    for claim in affected:
        text = " ".join(claim.text.casefold().split())
        if claim.claim_type not in {"policy", "procedure"}:
            return False
        # An individual name/code cannot occupy the generic subject position.
        conditional_subject = bool(re.match(r"^sinh viên nào vi phạm\b", text))
        if not conditional_subject and not re.match(r"^(?:sinh viên (?=không|phải|cần|có|được|thuộc|đã)|"
                        r"tại thời điểm xét tốt nghiệp|hạng tốt nghiệp|điều kiện |"
                        r"không bị kỷ luật|không đang trong thời gian)", text):
            return False
        if re.search(r"\b(?:bạn|em|tôi|mình|anh|chị|ông|bà|mssv|mã sinh viên|"
                     r"sinh viên này|sinh viên đó|sinh viên tên|sv\d+)\b", text):
            return False
        # Past disciplinary history is a condition only when framed as a
        # general conditional rule, never a standalone factual accusation.
        if re.search(r"sinh viên (?:đã |sẽ |phải )?bị kỷ luật", text) and not CONDITIONAL_FRAME.search(text):
            return False
        if not claim.citation_ids:
            return False
        for ref in claim.citation_ids:
            record = bundle.resolve(ref)
            if record is None or record.simulation_label:
                return False
            if not (official_huce_uri(record.canonical_uri)
                    or record.publication is not None and record.publication.binds(record)):
                return False
            # The additional generic conditional form must be a contiguous
            # source quotation. Token overlap cannot rearrange it into a verdict.
            if conditional_subject and text.rstrip(".") not in " ".join(record.content_text.casefold().split()):
                return False
        if not EvidenceGate(min_token_overlap_ratio=1.0).verify(
                GroundedDraft(claim.text, (claim,)), bundle).passed:
            return False
    return bool(affected)


class ComposeGroundedNode:
    """Synthesizes grounded draft response using active citation bundle context."""

    def execute(self, state: AgentState, bundle: CitationBundle) -> AgentState:
        citations = bundle.citations
        if not citations:
            return dataclasses.replace(
                state,
                draft=DraftResponse(
                    text="Không có thông tin trích dẫn để soạn thảo câu trả lời.",
                    claim_count=0,
                    is_grounded=False,
                ),
            )

        # Build grounded draft referencing citations
        first_cit_id = sorted(citations.keys())[0]
        first_rec = citations[first_cit_id]

        response_text = f"{first_rec.content_text} [{first_cit_id}]."
        return dataclasses.replace(
            state,
            draft=DraftResponse(
                text=response_text,
                claim_count=1,
                is_grounded=True,
            ),
        )


_PERSON = re.compile(r"\b(?:bạn|em|tôi|mình|anh|chị|ông|bà)\b", re.IGNORECASE)
# A source requirement ("không vi phạm pháp luật") or a general condition ("nếu vi phạm pháp luật") quoted in an
# answer is a rule, not a legal verdict about anyone; a clause aimed at a person stays blocked.
_GENERIC_LEGAL_PHRASE = re.compile(
    r"(?:\b(?:không|chưa)\b(?: (?:có|bị|thuộc|hành vi|trường hợp))* vi phạm pháp luật"
    r"|\b(?:nếu|khi|trường hợp)\b[^.;\n]{0,40}?vi phạm pháp luật)", re.IGNORECASE)


def _legal_verdict_text(text: str) -> str:
    """Text for the legal-verdict check with generic rule phrases removed (clauses naming a person are kept)."""
    clauses = re.split(r"(?<=[.;\n])", text)
    return "".join(c if _PERSON.search(c) else _GENERIC_LEGAL_PHRASE.sub("", c) for c in clauses)


class OutputGuardNode:
    """Scans response draft for secret leakage and unsafe content before delivery."""

    def execute(self, state: AgentState) -> AgentState:
        if not state.draft or not state.draft.text:
            return dataclasses.replace(state, terminal=Terminal.SAFE_FAILURE)

        text = state.draft.text

        rejection_conditions = [
            (r"hứa sẽ trả lời trong vòng \d+ (phút|giờ|ngày)", "hứa human response time chưa approved"),
            (r"(cứu hộ|cảnh sát|cấp cứu|đã gọi|đã báo) thành công", "tuyên bố đã gọi/chuyển thành công không xác nhận"),
            (r"(chẩn đoán|kết luận pháp lý|vi phạm pháp luật)", "có chẩn đoán/phán quyết pháp lý"),
            (r"(sudo|rm -rf|chmod 777|DROP TABLE)", "có executable instruction nguy hiểm"),
            (r"(hidden prompt|chain-of-thought|<thought>)", "hidden prompt, chain-of-thought leakage"),
        ]
        if re.search(r"kỷ luật", text, re.IGNORECASE) and not _verified_general_discipline_rule(state):
            rejection_conditions.append((r"kỷ luật", "phán quyết cá nhân hoặc quy định chưa được kiểm chứng"))

        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return dataclasses.replace(
                    state,
                    terminal=Terminal.SAFE_FAILURE,
                    draft=DraftResponse(
                        text="Phản hồi bị chặn do vi phạm quy tắc an toàn bảo mật thông tin.",
                        is_grounded=False,
                    ),
                    errors=state.errors + ("Secret leakage detected in output",),
                )

        legal_text = _legal_verdict_text(text)
        for pattern, reason in rejection_conditions:
            if re.search(pattern, legal_text if "pháp luật" in pattern else text, re.IGNORECASE):
                return dataclasses.replace(
                    state,
                    terminal=Terminal.SAFE_FAILURE,
                    draft=DraftResponse(
                        text="Phản hồi bị chặn do vi phạm quy tắc nội dung.",
                        is_grounded=False,
                    ),
                    errors=state.errors + (f"Policy violation: {reason}",),
                )

        terminal = state.terminal if state.terminal is not None else Terminal.ANSWERED
        return dataclasses.replace(state, terminal=terminal)
