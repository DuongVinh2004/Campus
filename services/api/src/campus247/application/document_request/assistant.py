"""Deterministic proposal boundary for the first service intent."""
from campus247.application.conversation.followup import normalized_question
from campus247.application.assistance.unified_contracts import IntentProposal, CandidateFact


REQUIRED = {"STUDENT_CERTIFICATE": ("purpose", "recipient"),
            "GRADE_APPEAL": ("course_record_id", "reason"), "GENERAL_SUPPORT": ("reason",)}


def understand_student_goal(message, *, workflow=None, fields=None, resource=None, constraints=()):
    """Explicit user statements and freshly authorized saved facts only.

    This deterministic intent specialist deliberately does not extract targets,
    recipients or academic facts from ambiguous prose or historical answers.
    """
    text = normalized_question(message)
    matches = []
    if certificate_intent(message):
        matches.append("STUDENT_CERTIFICATE")
    if any(term in text for term in ("phuc khao", "cham lai")):
        matches.append("GRADE_APPEAL")
    if any(term in text for term in ("ho tro chung", "gui yeu cau ho tro", "can can bo ho tro")):
        matches.append("GENERAL_SUPPORT")
    ambiguous = len(matches) > 1 or (workflow and matches and workflow not in matches)
    chosen = None if ambiguous else workflow or (matches[0] if matches else None)
    values = fields or {}
    missing = [key for key in REQUIRED.get(chosen, ()) if values.get(key) in (None, "")]
    clarification = ("Bạn muốn chuẩn bị giấy xác nhận, phúc khảo hay yêu cầu hỗ trợ chung? Chọn một thủ tục và hồ sơ cụ thể."
                     if not chosen else "Cần bổ sung: " + ", ".join(missing))
    return IntentProposal(goal=message, workflow=chosen, resource=resource,
        purpose=values.get("purpose") or values.get("reason") or None, constraints=list(constraints),
        facts=[CandidateFact(key=key, value=value, origin="user_statement") for key, value in values.items()
               if value is not None and isinstance(value, (str, int, bool))],
        missing_fields=missing, status="needs_clarification" if not chosen or missing else "candidate",
        clarification=clarification if not chosen or missing else None)


def certificate_intent(message: str) -> bool:
    text = normalized_question(message)
    return "xac nhan" in text and ("sinh vien" in text or "giay" in text)


def propose_certificate(message: str, guidance: dict):
    if not certificate_intent(message):
        return {"intent": None, "draft": None, "missing_fields": []}
    intent = understand_student_goal(message)
    return {"intent": intent.workflow, "draft": None, "missing_fields": intent.missing_fields,
            "understanding": intent.model_dump(mode="json"), "message": intent.clarification,
            "guidance": guidance, "requires_explicit_confirmation": True}
