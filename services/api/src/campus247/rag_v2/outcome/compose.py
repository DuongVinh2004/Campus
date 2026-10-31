"""Build display text exclusively from verified statements and original units."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from campus247.rag_v2.generation.contacts import restore
from campus247.rag_v2.types import (
    Citation,
    Outcome,
    RefuseReason,
    Statement,
    StatementVerdict,
    Understanding,
    Unit,
)
from campus247.rag_v2.verification.deterministic import check_statement

REFUSAL_MESSAGES = {
    "no_source": "Mình chưa tìm thấy nguồn phù hợp để trả lời câu hỏi này.",
    "out_of_scope": "Câu hỏi này nằm ngoài phạm vi thông tin mình hỗ trợ.",
    "unverified": "Mình đã tìm thấy nguồn nhưng chưa xác minh được phát biểu để trả lời.",
    "unsafe": "Mình không thể hỗ trợ yêu cầu này vì có thể ảnh hưởng đến an toàn hoặc quyền riêng tư.",
}
PARTIAL_NOTE = "Mình chỉ xác minh được phần thông tin trên; các phần còn lại chưa đủ căn cứ."
TRANSIENT_MESSAGE = "Mình đang gặp lỗi kết nối khi kiểm tra thông tin."
RETRY_HINT = "Bạn vui lòng thử lại sau ít phút."


def build_outcome(
    understanding: Understanding, verdicts: Sequence[StatementVerdict] = (),
    units_by_id: Mapping[str, Unit] | None = None, *, candidate_count: int | None = None,
    semantic_results: Sequence[bool] | None = None, semantic_required: bool = True,
    coverage: float = 1.0, infra_error: bool = False,
    refuse_reason: RefuseReason | None = None, suggestions: Sequence[str] = (),
    missing_parts: Sequence[str] = (),
) -> Outcome:
    """Semantic results align with *all* verdicts; unavailable means fail closed.

    Optional missing slots cause a partial result. Required missing slots should
    already have a fixed clarify_prompt from the understanding stage.
    """
    if refuse_reason is not None or understanding.out_of_scope:
        reason = refuse_reason or "out_of_scope"
        return Outcome("refuse", REFUSAL_MESSAGES[reason], reason=reason)
    if understanding.clarify_prompt:
        hints = tuple(suggestions) or tuple(understanding.missing_slots)
        return Outcome("clarify", understanding.clarify_prompt, suggestions=hints)
    if infra_error:
        return Outcome("transient_error", TRANSIENT_MESSAGE, retry_hint=RETRY_HINT)
    units_by_id = units_by_id or {}
    candidates = len(units_by_id) if candidate_count is None else candidate_count
    semantic_valid = (semantic_results is not None and len(semantic_results) == len(verdicts)
                      and all(type(item) is bool for item in semantic_results))
    accepted, citations = [], {}
    for index, verdict in enumerate(verdicts):
        if not verdict.passed or not check_statement(verdict.statement, units_by_id).passed:
            continue
        if semantic_valid:
            if not semantic_results[index]:
                continue
        elif semantic_required:
            continue
        stmt = verdict.statement
        units = [units_by_id[ref] for ref in stmt.unit_ids]
        text = restore(stmt.text, units)
        if text is None:
            continue
        accepted.append(Statement(text, stmt.unit_ids))
        for unit in units:
            # The whole indivisible unit is an exact quote containing every
            # referenced value, including values restored from contact labels.
            citations[unit.unit_id] = Citation(
                unit.unit_id, unit.chunk_ids, unit.document_id, unit.version_id,
                unit.doc_title, unit.path, unit.page, unit.text,
            )
    if not accepted:
        reason = "unverified" if candidates or verdicts else "no_source"
        return Outcome("refuse", REFUSAL_MESSAGES[reason], reason=reason)
    partial = len(accepted) < len(verdicts) or coverage < 1.0 or bool(missing_parts) or bool(understanding.missing_slots)
    text = "\n".join(stmt.text for stmt in accepted)
    if partial:
        text += "\n\n" + PARTIAL_NOTE
        if missing_parts:
            # The parts are the user's own words from the question, never model-authored text.
            text += " Chưa tìm thấy căn cứ cho: " + "; ".join(missing_parts) + "."
    return Outcome("partial" if partial else "answer", text, tuple(accepted),
                   tuple(citations.values()), partial_note=PARTIAL_NOTE if partial else None)
