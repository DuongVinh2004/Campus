"""Project a conditional yes/no question onto its stated subject and outcome.

Only retrieval uses this wording. The complete user question still governs
applicability, generation and claim verification. No source facts or synonyms
are added, and negation/qualifiers in the subject or outcome are preserved.
"""
import re

_CONDITIONAL = re.compile(
    r"^(?P<subject>.+?)\s+(?:thì|thi)\s+(?:có|co)\s+"
    r"(?:tự\s+động|tu\s+dong|luôn\s+luôn|luon\s+luon|luôn|luon)\s+"
    r"(?P<outcome>.+?)\s+(?:trong\s+(?:mọi|moi)\s+(?:trường\s+hợp|truong\s+hop)\s+)?"
    r"(?:không|khong)\s*[?.!]*$", re.IGNORECASE)


def conditional_retrieval_question(question: str) -> str:
    match = _CONDITIONAL.fullmatch(question.strip())
    if not match:
        return question
    subject, outcome = match["subject"].strip(), match["outcome"].strip()
    if not subject or not outcome or "?" in subject or "?" in outcome:
        return question
    # A search label, never an assertion that the consequence actually applies.
    return f"Điều kiện áp dụng: {subject}; {outcome}?"
