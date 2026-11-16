"""Avoid presenting a known different cohort/major as a program's credit total."""
import re

from campus247.application.conversation.followup import normalized_question


def matches_programme_scope(question: str, source: dict) -> bool:
    query = normalized_question(question.split("\nThuật ngữ tra cứu:", 1)[0])
    body = normalized_question(source["title"] + " " + source["content_text"])
    requested = set(re.findall(r"\bk(\d{2})\b", query))
    source_cohorts = set(re.findall(r"\bk(\d{2})\b", body))
    if requested and source_cohorts and not requested.intersection(source_cohorts):
        return False
    # A project-management course in another named degree is not evidence
    # for the project-management programme's total.
    title = normalized_question(source["title"])
    for aliases in (("quan ly du an", "qlda"), ("quan ly xay dung", "qlxd"), ("quan ly do thi",)):
        if any(re.search(r"\b" + alias + r"\b", query) for alias in aliases):
            programme = title if re.match(r"^k\d{2}\b", title.strip()) else body
            if not any(re.search(r"\b" + alias + r"\b", programme) for alias in aliases):
                return False
    # These are routing aliases only, never program facts or source evidence.
    families = (
        ("cntt", "cong nghe thong tin"), ("dan dung", "dd cn"), ("cau duong",),
        ("kien truc",), ("khoa hoc may tinh", "khmt"), ("an toan thong tin", "attt"),
        ("ky thuat moi truong",), ("cap thoat nuoc",), ("kinh te xay dung",),
        ("co khi",), ("ky thuat dien",), ("ky thuat o to",), ("logistics",),
        ("vat lieu",), ("cong trinh thuy",), ("cong trinh bien",), ("quy hoach",),
    )
    return all(not any(re.search(r"\b" + re.escape(alias) + r"\b", query) for alias in aliases)
               or any(re.search(r"\b" + re.escape(alias) + r"\b", body) for alias in aliases)
               for aliases in families)
