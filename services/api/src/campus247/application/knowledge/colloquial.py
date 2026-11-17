"""Deterministic expansion of common student shorthand before retrieval.

Only the text sent to lexical search, the embedding model and the reranker changes. The
original question still reaches generation and claim verification. Rules replace whole
tokens only, never invent facts, and leave ambiguous abbreviations alone (for example
"hp" can be học phần or học phí).
"""
import re

_TOKENS = {
    "sv": "sinh viên", "đk": "đăng ký", "dk": "đăng ký", "đc": "được", "dc": "được",
    "ko": "không", "hok": "không", "j": "gì", "ntn": "như thế nào", "ktx": "ký túc xá",
    "rl": "rèn luyện", "qđ": "quyết định", "qd": "quyết định", "tc": "tín chỉ", "gv": "giảng viên",
}
_PHRASES = (
    (re.compile(r"(?<!\w)đuổi học(?!\w)", re.IGNORECASE), "buộc thôi học"),
    (re.compile(r"(?<!\w)(?:rớt|trượt) môn(?!\w)", re.IGNORECASE), "không đạt học phần"),
    (re.compile(r"(?<!\w)nợ môn(?!\w)", re.IGNORECASE), "học phần chưa đạt"),
    (re.compile(r"(?<!\w)môn(?!\w)(?!\s+học)", re.IGNORECASE), "học phần"),
    (re.compile(r"(?<!\w)hk\s*(\d)(?!\w)", re.IGNORECASE), r"học kỳ \1"),
)
# Not inside document identifiers such as 924/QĐ-ĐHXDHN or 12-TB.
_TOKEN = re.compile(r"(?<![\w/-])(" + "|".join(sorted(map(re.escape, _TOKENS), key=len, reverse=True)) + r")(?![\w/-])", re.IGNORECASE)
_SHORT_YEAR = re.compile(r"(?<![\w/.-])(\d{2})\s*[-–/]\s*(\d{2})(?![\w/.-])")


def _year(match):
    first, second = int(match[1]), int(match[2])
    return f"20{first}-20{second}" if 20 <= first <= 40 and second == first + 1 else match[0]


def expand_colloquial(question):
    text = _TOKEN.sub(lambda m: _TOKENS[m[1].lower()], question)
    for pattern, replacement in _PHRASES:
        text = pattern.sub(replacement, text)
    return _SHORT_YEAR.sub(_year, text)
