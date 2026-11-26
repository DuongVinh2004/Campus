"""Conservative value, negation and applicability checks over cited text only."""
from __future__ import annotations

import re
from collections import Counter
import unicodedata
from collections.abc import Mapping

from campus247.rag_v2.generation.contacts import restore
from campus247.rag_v2.ingest.units import heading_text
from campus247.rag_v2.scope_ranges import covers
from campus247.rag_v2.types import Statement, StatementVerdict, Unit

REASON_CODES = frozenset({
    "NUMBER_NOT_IN_SOURCE", "CODE_NOT_IN_SOURCE", "DATE_NOT_IN_SOURCE",
    "NEGATION_MISMATCH", "UNIT_NOT_CITED", "SEMANTIC_UNSUPPORTED", "SCOPE_MISMATCH", "UNIT_MISMATCH",
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
# The negators and the exception word as written with their diacritics. Folding makes other words look like them:
# "chứa đựng" -> "chua", "cầm" -> "cam", "lưu trữ" / "nội trú" / "trụ sở" -> "tru".
_POLARITY_WORDS = {"khong": "không", "chua": "chưa", "cam": "cấm", "tru": "trừ"}


def _polarity_fold(text: str) -> str:
    """Fold for the negation check, keeping a word that folds to a negator but is written with other diacritics apart from it.

    A word written without diacritics ("khong", "chua") still counts as the negator: the text cannot tell, so it stays strict.
    """
    def keep_apart(match: re.Match) -> str:
        word = match.group().casefold()
        folded = _fold(word)
        negator = _POLARITY_WORDS.get(folded)
        return folded + "_" if negator and word not in (folded, negator) else match.group()
    return _fold(re.sub(r"\w+", keep_apart, unicodedata.normalize("NFC", text)))


def _number(value: str) -> str:
    value = re.sub(r"\s", "", value)
    # Three-digit groups are thousands; a final 1/2-digit group is decimal.
    parts = re.split(r"[.,]", value)
    # "0.125" is a decimal even though its last group has three digits.
    if len(parts) == 2 and parts[0] == "0" and parts[1].strip("0"):
        return "0." + parts[1].rstrip("0")
    if len(parts) > 1 and len(parts[-1]) != 3:
        fraction = parts[-1].rstrip("0")
        return str(int("".join(parts[:-1]))) + ("." + fraction if fraction else "")
    return str(int("".join(parts)))


ISO_DATE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_NUMERIC_DATES = re.compile(
    r"\b\d{1,2}\s*[/.-]\s*\d{1,2}\s*[/.-]\s*\d{4}\b|\b\d{4}-\d{1,2}-\d{1,2}\b"
    r"|\bngày\s+\d{1,2}\s+tháng\s+\d{1,2}(?:\s+năm\s+\d{4})?\b")
# Closed list of measure words: a number carries its unit, so "100 USD" does not support "100 EUR".
_UNITS = {"dong": "vnd", "vnd": "vnd", "usd": "usd", "eur": "eur", "kg": "kg", "g": "g", "tan": "tan",
          "km": "km", "gio": "gio", "phut": "phut", "ngay": "ngay", "tuan": "tuan", "thang": "thang",
          "nam": "nam", "tin chi": "tin chi", "tc": "tin chi", "diem": "diem", "lan": "lan",
          "hoc ky": "hoc ky", "phan tram": "%", "%": "%"}
# Same line only: a table cell ending in a number must not pair with the next row's "Học kỳ" header.
_UNIT_PAIR = re.compile(r"(\d+(?:[.,]\d+)*)[ \t]*(" + "|".join(sorted(map(re.escape, _UNITS), key=len, reverse=True))
                        + r")(?!\w)")
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5}
_SEMESTER = re.compile(r"\bhoc\s+ky\s+(iii|ii|iv|i|v|\d)\b")


def _without_dates(text: str) -> str:
    """Dates are verified as dates; their digits must not be re-read as stray numbers."""
    return _NUMERIC_DATES.sub(" ", text)


def _iso_dates(text: str) -> set[tuple[int, int, int]]:
    return {(int(d), int(m), int(y)) for y, m, d in ISO_DATE.findall(_fold(text))}


def _lines(text: str) -> list[str]:
    """Lines of a source, with a sentence wrapped onto a lower-case line rejoined (PDF text)."""
    return re.sub(r"[ \t]*\n\s*(?=[^\W\d_])", lambda m: " " if m.string[m.end()].islower() else "\n", text).split("\n")


# "Học kỳ 2 Học kỳ 3": the number after "Học kỳ" labels that semester, it is not a quantity of the next "Học kỳ".
_LABEL_BEFORE = re.compile(r"hoc ky\s*$")


def _unit_pairs(text: str) -> set[tuple[str, str]]:
    # A number pairs with a unit on its own line: the last number of a table cell is not
    # measured in the next row's "Học kỳ N" header.
    pairs = set()
    for line in _lines(text):
        folded = _fold(_without_dates(line))
        for m in _UNIT_PAIR.finditer(folded):
            if not _LABEL_BEFORE.search(folded[:m.start()]):
                pairs.add((_number(m.group(1)), _UNITS[m.group(2)]))
    return pairs


def _unit_mismatch(text: str, source: str) -> bool:
    claimed, held = _unit_pairs(text), _unit_pairs(source)
    for number, unit in claimed:
        if (number, unit) in held:
            continue
        # The number occurs in the source only under another unit: the statement changes what is measured.
        if any(n == number and u != unit for n, u in held):
            return True
    return False


def _semesters(text: str) -> set[int]:
    return {_ROMAN.get(g, None) or int(g) for g in _SEMESTER.findall(_fold(text))}


def _dates(text: str) -> set[tuple[int, int, int]]:
    return {tuple(map(int, match.groups())) for pattern in (DATE, LONG_DATE)
            for match in pattern.finditer(_fold(text))} | _iso_dates(text)


def _codes(text: str) -> set[str]:
    return {re.sub(r"\s", "", match.group()) for match in CODE.finditer(normalized(text))}


def _value_text(text: str) -> str:
    return CODE.sub(lambda match: re.sub(r"\s", "", match.group()), normalized(text))


def _day_months(text: str) -> set[tuple[int, int]]:
    folded = ISO_DATE.sub(" ", _fold(text))   # "2026-09-01" is year-month-day, not a day/month pair
    found = {tuple(map(int, match.groups()[:2])) for pattern in (DAY_MONTH, LONG_DAY_MONTH)
             for match in pattern.finditer(folded)}
    # A full date also states its day and month ("01.09.2026" supports "01/09").
    return found | {(d, m) for d, m, _ in _dates(text)}


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
    # A statement may combine several cited units ("K64 dùng A1 và K65 dùng B2"): each value it names
    # must be declared by at least one cited unit that declares that kind of scope at all.
    declared_cohorts = {_fold(c).replace("khoa", "k").replace(" ", "") for unit in units for c in unit.scope.cohorts}
    if declared_cohorts:
        # A cohort inside a range the cited text itself states ("K70 trở về trước") is declared by that text.
        undeclared = {c for c in cohorts - declared_cohorts if not any(covers(unit.text, c) for unit in units)}
        if undeclared:
            return True
    declared_years = {_fold(y).replace("/", "-").replace(" ", "") for unit in units for y in unit.scope.academic_years}
    if declared_years:
        if any(f"{start}-{end}" not in declared_years for start, end in years):
            return True
        if any(not any(year in item.split("-") for item in declared_years) for year in single_years):
            return True
    declared_programs = {_fold(p) for unit in units for p in unit.scope.programs}
    if declared_programs:
        if programs - declared_programs:
            return True
        # Names can be followed by a predicate. Match a complete allowed
        # name at the beginning, rather than inferring a program from text.
        if any(not any(re.match(re.escape(p) + r"(?!\w)", name) for p in declared_programs)
               for name in named_programs):
            return True
    return False


def program_mismatch(asked_program: str | None, units: list[Unit]) -> bool:
    """The question names a programme ("kinh tế xây dựng") and the cited text is positively about another one.

    Curriculum rows carry no programme in their declared scope, so a row of "Kỹ thuật xây dựng / Xây dựng DD&CN"
    could answer a question about "Kinh tế xây dựng". It is only a conflict when the cited units name some other
    known programme and never the one asked about; text that names none of them is left to the other checks.
    """
    from campus247.rag_v2.understanding.analyze import _PROGRAMS, contains
    if not asked_program or asked_program not in {code for code, _ in _PROGRAMS}:
        return False
    text = _fold(" ".join(f"{unit.doc_title} {unit.text}" for unit in units))
    mentioned = {code for code, names in _PROGRAMS if any(contains(text, name) for name in names)}
    return asked_program not in mentioned and bool(mentioned)


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
    raw_source = source  # sentence boundaries are read from the original punctuation
    # A colon, dash or comma between a negator and the word it governs ("Cấm: mang nước uống") changes nothing.
    def plain(text: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]+", " ", text))

    statement, source = plain(statement), plain(source)

    def listed_after(negator: str, after: str) -> bool:
        """"Không: nói chuyện, ..., sử dụng điện thoại di động": a negator before a colon governs every item of its list,
        so "không được sử dụng điện thoại" restates it. The item must stand in that list, before the sentence ends."""
        words = after.split()
        if words[:1] == ["duoc"]:
            words = words[1:]
        if len(words) < 2:
            return False
        item = r"(?<!\w)" + re.escape(" ".join(words[:2])) + r"(?!\w)"
        return any(re.search(item, plain(listed.group(1))) for listed in
                   re.finditer(r"(?<!\w)" + re.escape(negator) + r"\s*:\s*([^.;!?\n]+)", raw_source))

    def strict_mismatch(p) -> bool:
        supporting_text = plain(_supporting_sentences(statement, raw_source))
        stated, supporting = Counter(p.findall(statement)), Counter(p.findall(supporting_text))
        if stated == supporting:
            return False
        if supporting - stated:
            return True  # a negator or exception of the supporting text was dropped
        # The statement spans clauses ("...; hoặc quá 4 lần không liên tiếp ...") that the sentence split put
        # apart: an extra negator is fine when the same negator and the word after it stand in the row.
        for match in p.finditer(statement):
            tail = re.match(r"(?:\s+\w+){1,3}", statement[match.end():])
            first = re.match(r"\s+\w+", statement[match.end():])
            if not tail or not first or not re.search(
                    r"(?<!\w)" + re.escape(match.group()) + re.escape(first.group()) + r"(?!\w)", source):
                return True
            # The negator and its first object word stand in the row. Reject only a flip: the statement's own
            # words are stated in the row without that negator ("được bảo lưu" vs "không được rút").
            plain_tail = r"(?<!\w)" + re.escape(tail.group().strip()) + r"(?!\w)"
            negated_tail = r"(?<!\w)" + re.escape(match.group() + tail.group()) + r"(?!\w)"
            if re.search(plain_tail, source) and not re.search(negated_tail, source):
                return True
        return False

    if len(source) <= STRICT_SOURCE_CHARS and any(strict_mismatch(p) for p in patterns):
        return True
    if any(Counter(p.findall(statement)) - Counter(p.findall(source)) for p in patterns):
        return True
    for pattern in patterns:
        # A negator of the statement must govern the same words in the row.
        for match in pattern.finditer(statement):
            first = re.match(r"\s+\w+", statement[match.end():])
            # The first word after the negator is enough: abbreviations ("học phần" / "HP") follow it.
            if first and not re.search(
                    r"(?<!\w)" + re.escape(match.group()) + re.escape(first.group()) + r"(?!\w)", source) \
                    and not listed_after(match.group(), statement[match.end():]):
                return True
        for match in pattern.finditer(source):
            tail = re.match(_TAIL, source[match.end():])
            if not tail or len(tail.group(1).split()) < 3:
                continue
            phrase = tail.group(1).strip()
            phrase_re = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"

            def negated_before(text: str, start: int) -> bool:
                before = [re.sub(r"\W+", "", w) for w in text[:start].rstrip().split()[-1:]] or [""]
                return bool(pattern.fullmatch(before[0])) or before[0] in {"ngoai", "chi"}

            # "2 lần liên tiếp đối với" and "4 lần không liên tiếp đối với" share the words after the negator: if
            # the row also states them without a negator, the statement is not dropping that negation.
            if any(not negated_before(source, hit.start()) for hit in re.finditer(phrase_re, source)):
                continue
            for hit in re.finditer(phrase_re, statement):
                if not negated_before(statement, hit.start()):
                    return True
    return False


def check_statement(stmt: Statement, units_by_id: Mapping[str, Unit]) -> StatementVerdict:
    if (not stmt.unit_ids or any(ref not in units_by_id for ref in stmt.unit_ids)):
        return StatementVerdict(stmt, False, ("UNIT_NOT_CITED",))
    units = [units_by_id[ref] for ref in stmt.unit_ids]
    text = restore(stmt.text, units)
    if text is None or not text.strip():
        return StatementVerdict(stmt, False, ("UNIT_NOT_CITED",))
    # A unit's section headings are part of its source (the semester of a curriculum row is a heading, not row text).
    bodies = [(heading_text(unit) + "\n" + unit.text) if heading_text(unit) else unit.text for unit in units]
    source = "\n".join(bodies)
    reasons = []
    if not _dates(text) <= _dates(source) or not _day_months(text) <= _day_months(source):
        reasons.append("DATE_NOT_IN_SOURCE")
    # A cohort the source covers by a range ("K69" under "K70 trở về trước" / "K70_and_earlier") is stated by the source.
    ranged = source.replace("_and_earlier", " trở về trước")
    unstated = {code for code in _codes(text) - _codes(source) if not (re.fullmatch(r"k\d{2,3}", code) and covers(ranged, code))}
    if unstated:
        reasons.append("CODE_NOT_IN_SOURCE")
    # Dates are compared as dates above; their digits are not stray numbers.
    numbers = {_number(m.group()) for m in NUMBER.finditer(_value_text(_without_dates(text)))}
    source_numbers = {_number(m.group()) for body in bodies
                      for m in NUMBER.finditer(_value_text(_without_dates(body)))}
    # Digits glued to letters in the source ("INT1234") are still the number the statement states.
    source_numbers |= {_number(m.group()) for body in bodies
                       for m in re.finditer(r"\d+(?:[.,]\d+)*", normalized(_without_dates(body)))}
    source_semesters = _semesters(source)
    source_numbers |= {str(n) for n in source_semesters}   # "học kỳ II" supports "học kỳ 2"
    percent = r"(\d+(?:[.,]\d+)?)\s*(?:%|phần trăm)"
    percents = {_number(m.group(1)) for m in re.finditer(percent, normalized(text))}
    source_percents = {_number(m.group(1)) for m in re.finditer(percent, normalized(source))}
    if not numbers <= source_numbers or not percents <= source_percents:
        reasons.append("NUMBER_NOT_IN_SOURCE")
    elif _unit_mismatch(text, source):
        reasons.append("UNIT_MISMATCH")
    claimed_semesters = _semesters(text)
    if source_semesters and not claimed_semesters <= source_semesters:
        reasons.append("NUMBER_NOT_IN_SOURCE")
    # The document title is a label, not a statement about what the cited text says: a title such as "... (không phải văn bản chính thức)"
    # must not count as a negator of every sentence taken from the document.
    polarity_source = "\n".join(unit.text.replace(unit.doc_title, " ", 1) if unit.doc_title else unit.text for unit in units)
    # Never stricter than before: a statement fails only when it fails against the full text and also without the title.
    if (_polarity_mismatch(_polarity_fold(text), _polarity_fold(source))
            and _polarity_mismatch(_polarity_fold(text), _polarity_fold(polarity_source))):
        reasons.append("NEGATION_MISMATCH")
    if _scope_mismatch(text, units):
        reasons.append("SCOPE_MISMATCH")
    reasons = tuple(dict.fromkeys(reasons))
    return StatementVerdict(stmt, not reasons, reasons)
