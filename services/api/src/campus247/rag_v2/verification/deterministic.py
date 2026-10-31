"""Conservative value, negation and applicability checks over cited text only."""
from __future__ import annotations

import re
from collections import Counter
import unicodedata
from collections.abc import Mapping

from campus247.rag_v2.generation.contacts import restore
from campus247.rag_v2.types import Statement, StatementVerdict, Unit

REASON_CODES = frozenset({
    "NUMBER_NOT_IN_SOURCE", "CODE_NOT_IN_SOURCE", "DATE_NOT_IN_SOURCE",
    "NEGATION_MISMATCH", "UNIT_NOT_CITED", "SEMANTIC_UNSUPPORTED", "SCOPE_MISMATCH",
})


def normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", normalized(text))
                   if unicodedata.category(c) != "Mn").replace("đ", "d")


NUMBER = re.compile(r"(?<!\w)\d+(?:[.,\u00a0\u202f ]\d+)*(?!\w)")
DATE = re.compile(r"\b(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{4})\b")
LONG_DATE = re.compile(r"\bngay\s+(\d{1,2})\s+thang\s+(\d{1,2})\s+nam\s+(\d{4})\b")
DAY_MONTH = re.compile(r"\b(\d{1,2})\s*[/-]\s*(\d{1,2})(?!\d)(?:\s*[/-]\s*\d{4})?\b")
LONG_DAY_MONTH = re.compile(r"\bngay\s+(\d{1,2})\s+thang\s+(\d{1,2})\b")
CODE = re.compile(
    r"(?<!\w)(?:\d+\s*/\s*[a-zđ]+(?:\s*[-/]\s*[a-zđ0-9]+)*"
    r"|[a-zđ]+\d+[a-zđ0-9]*(?:\s*[-/]\s*[a-zđ0-9]+)*|\d+[a-zđ]+[a-zđ0-9]*)(?!\w)")
# A code keeps its letters and digits together ("k71qd", "qd924"). Allowing whitespace between them
# glued a table cell like "CTN\n160470 - 2" into one code, hid the course code 160470 from the number
# check and rejected correct statements.
NEGATIVE = re.compile(r"\b(?:khong|chua|cam)\b")
EXCEPTION = re.compile(r"\b(?:ngoai\s+tru|tru)\b")


def _number(value: str) -> str:
    value = re.sub(r"\s", "", value)
    # Three-digit groups are thousands; a final 1/2-digit group is decimal.
    parts = re.split(r"[.,]", value)
    if len(parts) > 1 and len(parts[-1]) != 3:
        fraction = parts[-1].rstrip("0")
        return str(int("".join(parts[:-1]))) + ("." + fraction if fraction else "")
    return str(int("".join(parts)))


def _dates(text: str) -> set[tuple[int, int, int]]:
    return {tuple(map(int, match.groups())) for pattern in (DATE, LONG_DATE)
            for match in pattern.finditer(_fold(text))}


def _codes(text: str) -> set[str]:
    return {re.sub(r"\s", "", match.group()) for match in CODE.finditer(normalized(text))}


def _value_text(text: str) -> str:
    return CODE.sub(lambda match: re.sub(r"\s", "", match.group()), normalized(text))


def _day_months(text: str) -> set[tuple[int, int]]:
    return {tuple(map(int, match.groups())) for pattern in (DAY_MONTH, LONG_DAY_MONTH)
            for match in pattern.finditer(_fold(text))}


def _scope_mismatch(text: str, units: list[Unit]) -> bool:
    text = _fold(text)
    cohorts = {"k" + match for match in re.findall(r"\b(?:k\s*|khoa\s+)(\d{2,3})\b", text)}
    years = re.findall(r"\b(?:nam(?:\s+hoc)?\s+)?(20\d{2})\s*[-/]\s*(20\d{2})\b", text)
    # The year of a full date ("ngay 21 thang 6 nam 2024", the date of a decision the source mentions) is
    # checked as a date against the source; it does not claim an academic year for the unit.
    undated = re.sub(r"\bngay\s+\d{1,2}\s+thang\s+\d{1,2}\s+nam\s+20\d{2}\b", " ", text)
    single_years = set(re.findall(r"\bnam(?:\s+hoc)?\s+(20\d{2})\b", undated))
    programs = set(re.findall(r"\b(?:nganh|chuong trinh)\s+(\d{7})\b", text))
    named_programs = re.findall(r"\b(?:nganh|chuong trinh)\s+([^.;\n]+)", text)
    for unit in units:
        scope = unit.scope
        allowed_cohorts = {_fold(c).replace("khoa", "k").replace(" ", "") for c in scope.cohorts}
        if allowed_cohorts and not cohorts <= allowed_cohorts:
            return True
        allowed_years = {_fold(y).replace("/", "-").replace(" ", "") for y in scope.academic_years}
        if allowed_years:
            if any(f"{start}-{end}" not in allowed_years for start, end in years):
                return True
            if any(not any(year in item.split("-") for item in allowed_years) for year in single_years):
                return True
        if scope.programs:
            allowed = {_fold(p) for p in scope.programs}
            if programs - allowed:
                return True
            # Names can be followed by a predicate. Match a complete allowed
            # name at the beginning, rather than inferring a program from text.
            if any(not any(re.match(re.escape(p) + r"(?!\w)", name) for p in allowed)
                   for name in named_programs):
                return True
    return False


STRICT_SOURCE_CHARS = 600
# Three words identify a proposition; two ("duoc su", "truy nhap") also occur in unrelated affirmative text.
_TAIL = r"((?:\s+\w+){1,3})"


def _supporting_sentences(statement: str, source: str) -> str:
    """The sentences of a short source that the statement restates; the whole source if none clearly does.

    "Sinh viên được bảo lưu. Sinh viên không được rút học phần." supports "Sinh viên được bảo lưu"
    without the negator of its neighbour sentence.
    """
    sentences = [part for part in re.split(r"(?<=[.;!?])\s+|\n+", source) if part.strip()]
    if len(sentences) < 2:
        return source
    words = set(re.findall(r"\w{3,}", statement))
    overlaps = [len(words & set(re.findall(r"\w{3,}", part))) for part in sentences]
    best = max(overlaps)
    chosen = [part for part, overlap in zip(sentences, overlaps) if overlap == best]
    return " ".join(chosen) if best >= 2 else source


def _polarity_mismatch(statement: str, source: str) -> bool:
    """Negation or exception introduced, or dropped, relative to the cited text.

    A short cited text must carry exactly the negators of the statement. A whole source row holds
    many unrelated negators (on the dev set an equality test rejected most correct statements), so
    there a statement is rejected when it adds a negator the row lacks, or when it states the words
    that follow a negator of the row ("khong duoc nghi" -> "duoc nghi") without that negator.
    """
    patterns = (NEGATIVE, EXCEPTION)
    if len(source) <= STRICT_SOURCE_CHARS and any(
            sorted(p.findall(statement)) != sorted(p.findall(_supporting_sentences(statement, source)))
            for p in patterns):
        return True
    if any(Counter(p.findall(statement)) - Counter(p.findall(source)) for p in patterns):
        return True
    for pattern in patterns:
        # A negator of the statement must govern the same words in the row.
        for match in pattern.finditer(statement):
            first = re.match(r"\s+\w+", statement[match.end():])
            # The first word after the negator is enough: abbreviations ("học phần" / "HP") follow it.
            if first and not re.search(
                    r"(?<!\w)" + re.escape(match.group()) + re.escape(first.group()) + r"(?!\w)", source):
                return True
        for match in pattern.finditer(source):
            tail = re.match(_TAIL, source[match.end():])
            if not tail or len(tail.group(1).split()) < 3:
                continue
            phrase = tail.group(1).strip()
            for hit in re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", statement):
                before = [re.sub(r"\W+", "", w) for w in statement[:hit.start()].rstrip().split()[-1:]] or [""]
                if not pattern.fullmatch(before[0]) and before[0] not in {"ngoai", "chi"}:
                    return True
    return False


def check_statement(stmt: Statement, units_by_id: Mapping[str, Unit]) -> StatementVerdict:
    if (not stmt.unit_ids or any(ref not in units_by_id for ref in stmt.unit_ids)):
        return StatementVerdict(stmt, False, ("UNIT_NOT_CITED",))
    units = [units_by_id[ref] for ref in stmt.unit_ids]
    text = restore(stmt.text, units)
    if text is None or not text.strip():
        return StatementVerdict(stmt, False, ("UNIT_NOT_CITED",))
    source = "\n".join(unit.text for unit in units)
    reasons = []
    if not _dates(text) <= _dates(source) or not _day_months(text) <= _day_months(source):
        reasons.append("DATE_NOT_IN_SOURCE")
    if not _codes(text) <= _codes(source):
        reasons.append("CODE_NOT_IN_SOURCE")
    numbers = {_number(m.group()) for m in NUMBER.finditer(_value_text(text))}
    source_numbers = {_number(m.group()) for unit in units for m in NUMBER.finditer(_value_text(unit.text))}
    # Digits glued to letters in the source ("INT1234") are still the number the statement states.
    source_numbers |= {_number(m.group()) for unit in units
                       for m in re.finditer(r"\d+(?:[.,]\d+)*", normalized(unit.text))}
    percents = {_number(m.group(1)) for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*%", text)}
    source_percents = {_number(m.group(1)) for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*%", source)}
    if not numbers <= source_numbers or not percents <= source_percents:
        reasons.append("NUMBER_NOT_IN_SOURCE")
    if _polarity_mismatch(_fold(text), _fold(source)):
        reasons.append("NEGATION_MISMATCH")
    if _scope_mismatch(text, units):
        reasons.append("SCOPE_MISMATCH")
    return StatementVerdict(stmt, not reasons, tuple(reasons))
