"""Narrow search aliases; never change the user's goal or evidence bytes."""
import re


def canonical_search_query(query: str) -> str:
    # Everyday "chứng nhận sinh viên" names the student confirmation topic.
    # Preserve surrounding negation, dates and qualifiers; other certificates
    # (graduation, language, professional credentials) are not interchangeable.
    return re.sub(r"\b(?:(?:giấy|giay)\s+)?(?:chứng|chung)\s+(?:nhận|nhan)\s+sinh\s+(?:viên|vien)\b",
                  "giấy xác nhận sinh viên", query, flags=re.I)
