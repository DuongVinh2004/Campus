"""Build display text exclusively from verified statements and original units."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from campus247.rag_v2.generation.contacts import restore
from campus247.rag_v2.ingest.units import source_text
from campus247.rag_v2.outcome.support_spans import find_support
from campus247.rag_v2.types import (
    Citation,
    Outcome,
    RefuseReason,
    Statement,
    StatementCheck,
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
TOPIC_CHIPS = ("Học phí", "Học bổng", "Đăng ký học phần", "Bảo lưu kết quả học tập", "Điều kiện tốt nghiệp")
EXEMPTION_CHIPS = ("Điều kiện miễn giảm học phí", "Miễn học phần ngoại ngữ", "Miễn giáo dục thể chất")
PARTIAL_NOTE ="Mình chỉ xác minh được phần thông tin trên; các phần còn lại chưa đủ căn cứ."
TRANSIENT_MESSAGE = "Mình đang gặp lỗi kết nối khi kiểm tra thông tin."
RETRY_HINT = "Bạn vui lòng thử lại sau ít phút."
# The turn ran out of its time budget while checking sources; nothing unverified is shown.
TIMEOUT_MESSAGE = "Câu hỏi này cần đối chiếu nhiều nguồn nên mình chưa kịp xác minh xong trong thời gian cho phép."
TIMEOUT_HINT = "Bạn thử hỏi từng ý riêng, hoặc hỏi lại sau ít phút."


def build_outcome(
    understanding: Understanding, verdicts: Sequence[StatementVerdict] = (),
    units_by_id: Mapping[str, Unit] | None = None, *, candidate_count: int | None = None,
    semantic_results: Sequence[bool] | None = None, semantic_required: bool = True,
    coverage: float = 1.0, infra_error: bool = False,
    refuse_reason: RefuseReason | None = None, suggestions: Sequence[str] = (),
    missing_parts: Sequence[str] = (), scope_note: str | None = None,
    facets: Sequence[tuple[str, str]] = (), facet_of: Sequence[str] = (),
) -> Outcome:
    """Semantic results align with *all* verdicts; unavailable means fail closed.

    Optional missing slots cause a partial result. Required missing slots should
    already have a fixed clarify_prompt from the understanding stage.
    """
    if refuse_reason is not None or understanding.out_of_scope:
        reason = refuse_reason or "out_of_scope"
        return Outcome("refuse", REFUSAL_MESSAGES[reason], reason=reason,
                       suggestions=tuple(suggestions) if reason in {"no_source", "unverified"} else ())
    if understanding.clarify_prompt:
        hints = tuple(suggestions) or tuple(understanding.missing_slots)
        if not hints and understanding.question_type == "unclear":
            # Tappable starting points instead of a bare question: each one is a topic the sources really cover.
            hints = (EXEMPTION_CHIPS if "miễn" in understanding.clarify_prompt else TOPIC_CHIPS)
        return Outcome("clarify", understanding.clarify_prompt, suggestions=hints)
    if infra_error:
        return Outcome("transient_error", TRANSIENT_MESSAGE, retry_hint=RETRY_HINT)
    units_by_id = units_by_id or {}
    candidates = len(units_by_id) if candidate_count is None else candidate_count
    semantic_valid = (semantic_results is not None and len(semantic_results) == len(verdicts)
                      and all(type(item) is bool for item in semantic_results))
    accepted, citations, accepted_facets, checks = [], {}, [], []
    rejected: dict[str, int] = {}
    for index, verdict in enumerate(verdicts):
        rechecked = check_statement(verdict.statement, units_by_id) if verdict.passed else verdict
        if not verdict.passed or not rechecked.passed:
            for code in (verdict.reasons if not verdict.passed else rechecked.reasons) or ("UNVERIFIED",):
                rejected[code] = rejected.get(code, 0) + 1
            continue
        if semantic_valid:
            if not semantic_results[index]:
                rejected["SEMANTIC_UNSUPPORTED"] = rejected.get("SEMANTIC_UNSUPPORTED", 0) + 1
                continue
        elif semantic_required:
            rejected["SEMANTIC_UNSUPPORTED"] = rejected.get("SEMANTIC_UNSUPPORTED", 0) + 1
            continue
        stmt = verdict.statement
        units = [units_by_id[ref] for ref in stmt.unit_ids]
        text = restore(stmt.text, units)
        if text is None:
            continue
        accepted.append(Statement(text, stmt.unit_ids))
        checks.append(_check(text, units, semantic_valid))
        accepted_facets.append(facet_of[index] if index < len(facet_of) else "")
        for unit in units:
            # The whole indivisible unit is an exact quote containing every
            # referenced value, including values restored from contact labels.
            citations[unit.unit_id] = Citation(
                unit.unit_id, unit.chunk_ids, unit.document_id, unit.version_id,
                unit.doc_title, unit.path, unit.page, unit.text,
            )
    if not accepted:
        reason = "unverified" if candidates or verdicts else "no_source"
        return Outcome("refuse", REFUSAL_MESSAGES[reason], reason=reason, suggestions=tuple(suggestions), rejected_counts=rejected)
    incomplete = len(accepted) < len(verdicts) or coverage < 1.0 or bool(missing_parts)
    # An answer that holds for several scopes (cohort, programme, term) is complete for what the sources say;
    # the server then invites the user to narrow it down instead of calling it incomplete.
    open_scope = bool(understanding.missing_slots) and bool(understanding.ask_back)
    partial = incomplete or bool(understanding.missing_slots) or bool(scope_note)
    text = "\n".join(stmt.text for stmt in accepted)
    note = None
    if incomplete:
        note = PARTIAL_NOTE
        if missing_parts:
            # The parts are the user's own words from the question, never model-authored text.
            note += " Chưa tìm thấy căn cứ cho: " + "; ".join(missing_parts) + "."
        if open_scope:
            note += " " + understanding.ask_back
    elif open_scope:
        note = understanding.ask_back
    elif partial:
        note = PARTIAL_NOTE
    if note:
        text += "\n\n" + note
    return Outcome("partial" if partial else "answer", text, tuple(accepted), tuple(citations.values()),
                   partial_note=note, suggestions=tuple(suggestions), preface=scope_note,
                   groups=_groups(facets, accepted_facets), checks=tuple(checks), rejected_counts=rejected)


def _check(text: str, units: Sequence[Unit], semantic_ran: bool) -> StatementCheck:
    wanted = " ".join(text.split())
    bodies = [(unit.unit_id, source_text(unit)) for unit in units]
    verbatim = any(wanted and wanted in " ".join(body.split()) for _, body in bodies)
    spans = []
    for unit_id, body in bodies:
        found = find_support(text, body)
        if found:
            spans.append((unit_id, found[0], found[1]))
    return StatementCheck("PASSED", verbatim, "PASSED" if semantic_ran else "NOT_RUN", tuple(spans))


def _groups(facets: Sequence[tuple[str, str]], accepted_facets: Sequence[str]) -> tuple[tuple[str, tuple[int, ...]], ...]:
    """Accepted statements per answered part of the question, in the question's order; unassigned ones last ("")."""
    groups = [(ask, tuple(i for i, f in enumerate(accepted_facets) if f == facet_id)) for facet_id, ask in facets]
    groups = [(ask, idx) for ask, idx in groups if idx]
    if len(groups) < 2:
        return ()
    known = {facet_id for facet_id, _ in facets}
    rest = tuple(i for i, f in enumerate(accepted_facets) if f not in known)
    return tuple(groups) + ((("", rest),) if rest else ())
