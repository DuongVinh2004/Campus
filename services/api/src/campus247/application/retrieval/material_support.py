"""Deterministic factual checks supplement lexical and semantic support checks."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation


def normalized(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold())
                   if unicodedata.category(c) != "Mn").replace("đ", "d")


_NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*(?![\w]|[.,]\d)")


def numeric_text(text: str) -> str:
    text = normalized(text)
    # Resolve only recognized OCR comparator/unit joins, keeping the raw source
    # unchanged. Never take a fractional tail from an unrecognized identifier.
    text = re.sub(r"(?<=\d)(?=(?:den|diem|tin chi|vnd|dong|ngay|gio|phut|nam|tuan|thang|nguoi|lan)(?:\b|\d))", " ", text)
    return re.sub(r"\b(tu|den|duoi|tren|hon|toi thieu|toi da|it nhat)(?=\d)", r"\1 ", text)


def numeric_value(value: str) -> Decimal:
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", value):
        value = value.replace(".", "").replace(",", "")
    else:
        value = value.replace(",", ".")
    return Decimal(value)


def quantities(text: str) -> list[tuple[Decimal, str | None]]:
    text = numeric_text(text)
    result = []
    for match in _NUMBER.finditer(text):
        try:
            value = numeric_value(match.group())
        except InvalidOperation:
            continue
        before = text[max(0, match.start() - 50):match.start()]
        after = text[match.end():match.end() + 45]
        operator = None
        for pattern, kind in (
            (r"(?:>=|≥|it nhat|toi thieu|khong (?:nho|thap) hon|tu)\s*$", "ge"),
            (r"(?:<=|≤|toi da|khong (?:lon|cao) hon|khong qua|den)\s*$", "le"),
            (r"(?:>|lon hon|cao hon|tren)\s*$", "gt"),
            (r"(?:<|nho hon|thap hon|duoi)\s*$", "lt"),
        ):
            if re.search(pattern.replace(r"\s*$", r"\s*(?:la|bang|o muc)?\s*$"), before):
                operator = kind
                break
        if re.match(r"\s*(?:diem\s*)?(?:tro len|va tro len)", after):
            operator = "ge"
        elif re.match(r"\s*(?:diem\s*)?(?:tro xuong|va tro xuong)", after):
            operator = "le"
        result.append((value, operator))
    return result


_STOP = frozenset(["la", "va", "cua", "co", "thi", "sinh", "vien", "voi", "cac", "mot",
                   "nhung", "duoc", "khong", "chua", "toi", "em", "minh", "ban"])


def quantity_units(text: str) -> list[tuple[Decimal, str]]:
    text = numeric_text(text)
    values = []
    for number in _NUMBER.finditer(text):
        unit = re.match(r"\s*(ngay lam viec|ngay|gio|phut|tin chi|vnd|dong|%|diem|nam|tuan|thang|nguoi)(?=\W|$)",
                        text[number.end():])
        if unit:
            # A new-line chart heading such as "Năm 2" labels a column;
            # it is not the unit of the preceding course-credit cell.
            suffix = text[number.end():]
            if ("\n" in suffix[:unit.start(1)] and unit.group(1) in {"nam", "thang", "tuan", "ngay"}
                    and re.match(r"[ \t]+\d", suffix[unit.end():])):
                continue
            try:
                name = "dong" if unit.group(1) == "vnd" else unit.group(1)
                values.append((numeric_value(number.group()), name))
            except InvalidOperation:
                continue
    return values


def grade_subjects(text: str) -> frozenset[str]:
    text = normalized(text)
    return frozenset(re.findall(r"\bdiem(?:\s+chu)?\s+([abcdf])\b", text)
                     + re.findall(r"^\s*([abcdf])\s*[:|]\s*", text))


def passing_grade_subjects(evidence: str) -> frozenset[str]:
    """Resolve grade scope only from explicit source headings and table rows."""
    text = normalized(evidence)
    headings = list(re.finditer(r"(?m)^\s*(?:[a-z]\)\s*)?loai (khong )?dat\b", text))
    found: dict[str, set[bool]] = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = text[heading.end():end]
        passed = heading.group(1) is None
        for grade in re.findall(r"(?m)^\s*([abcdf])(?:\+|')?\s*[:_]", section):
            found.setdefault(grade, set()).add(passed)
    return frozenset(grade for grade, labels in found.items() if labels == {True})


def symbolic_thresholds(text: str) -> list[tuple[str, str]]:
    """Keep equality for a referenced credit limit distinct from a minimum."""
    pattern = (r"\b(toi thieu(?:\s+bang)?|it nhat(?:\s+bang)?|khong nho hon|"
        r"toi da(?:\s+bang)?|khong lon hon|khong qua|lon hon|nho hon|bang)"
        r"\s+(so tin chi (?:toi da|toi thieu))\b")
    values = []
    for match in re.finditer(pattern, normalized(text)):
        phrase = match.group(1)
        if phrase.startswith(("toi thieu", "it nhat", "khong nho hon")):
            operator = "ge"
        elif phrase.startswith(("toi da", "khong lon hon", "khong qua")):
            operator = "le"
        else:
            operator = {"lon hon": "gt", "nho hon": "lt", "bang": "eq"}[phrase]
        values.append((match.group(2), operator))
    return values


def predicate_polarities(text: str) -> dict[str, frozenset[bool]]:
    classes = {"duoc": "permission", "cho phep": "permission",
        "phai": "requirement", "can": "requirement", "bat buoc": "requirement",
        "dat": "achievement", "du": "eligibility"}
    found: dict[str, set[bool]] = {}
    for match in re.finditer(r"\b(?:(khong|chua)\s+)?(cho phep|bat buoc|duoc|phai|can|dat|du)\b", text):
        predicate = match.group(2)
        before = text[max(0, match.start() - 20):match.start()]
        # "Phải đạt" is a requirement, not a factual achievement verdict.
        if predicate in {"dat", "du"} and re.search(r"\b(?:phai|can)\s*$", before):
            continue
        negative = bool(match.group(1))
        if predicate == "phai" and re.search(r"\bkhong can\s*$", before):
            negative = True
        found.setdefault(classes[predicate], set()).add(negative)
    return {kind: frozenset(values) for kind, values in found.items()}


def missing_parenthetical_condition(claim: str, evidence: str) -> bool:
    """Check explicit, action-scoped parenthetical qualifiers, not general NLI.

    An exception after the last alternative qualifies that alternative only.
    Short or ambiguous anchors remain for semantic verification to assess.
    """
    source = normalized(evidence)
    claim_tokens = set(re.findall(r"[a-z]+", normalized(claim)))
    claim_body = " ".join(re.findall(r"[a-z]+", normalized(claim)))
    connective = {"la", "va", "hoac", "cua", "cac", "mot", "nhung", "trong", "truong", "hop",
        "doi", "voi", "ngoai", "tru", "neu", "khi", "chi", "ap", "dung"}
    for match in re.finditer(r"\(([^()]+)\)", source):
        condition = " ".join(match.group(1).split())
        if not re.search(r"\b(?:trong truong hop|doi voi|ngoai tru|chi ap dung|neu|khi)\b", condition):
            continue
        preceding = " ".join(source[:match.start()].split())
        branch = re.split(r"[;.!?]|\bhoac\b", preceding)[-1]
        words = re.findall(r"[a-z]+", branch)
        anchor = " ".join(words[-6:])
        if (len(words) < 5 or len(set(words[-6:])) < 4
                or not re.search(r"\b(?:hoc doi|dang ky|chuyen|su dung|nop|rut|muon|hoan|du thi|thuc hien)\b", anchor)
                or anchor not in claim_body):
            continue
        required = set(re.findall(r"[a-z]+", condition)) - connective
        if len(required) >= 3 and not required.issubset(claim_tokens):
            return True
    return False


def missing_conjunctive_condition(claim: str, evidence: str) -> bool:
    """A subset of an explicit all-conditions list cannot grant permission.

    Only affirmative sufficiency language ("then may", "only need") triggers
    this check. Necessary conditions, exclusions and time-only facts remain
    for the ordinary lexical/semantic checks; this is not a general NLI model.
    """
    body, source = normalized(claim), normalized(evidence)
    # An enumerated alternative can still be subject to additional conditions.
    # A claim restating that eligibility list must retain the printed qualifier;
    # an independent earliest-date/year fact does not restate the list.
    compact_source, compact_body = " ".join(source.split()), " ".join(body.split())
    if (re.search(r"dieu kien sau va cac dieu kien khac", compact_source)
            and re.search(r"phai dap ung\s+(?:0?1|mot)\s+trong\s+(?:0?2|hai)\s+dieu kien", compact_body)
            and "cac dieu kien khac" not in compact_body):
        return True
    if not re.search(r"\b(?:thi (?:se )?duoc|chi can)\b", body):
        return False
    claim_words = set(re.findall(r"[a-z]+", body)) - _STOP
    for heading in re.finditer(r"([^.!?]+?)\bkhi co du cac dieu kien sau\s*:", source):
        permission = re.search(r"\bduoc\b(.+)", heading.group(1))
        if permission is None:
            continue
        action = set(re.findall(r"[a-z]+", permission.group(1))) - _STOP
        if len(action) < 4 or len(action & claim_words) / len(action) < .6:
            continue
        section = re.split(r"(?m)^\s*\d+\.\s", source[heading.end():], maxsplit=1)[0]
        clauses = re.split(r"(?m)^\s*[a-z]\)\s*", section)[1:]
        if len(clauses) < 2:
            continue
        for clause in clauses:
            required = set(re.findall(r"[a-z]+", clause)) - _STOP
            if len(required) >= 4 and len(required & claim_words) / len(required) < .6:
                return True
    return False


def grade_numeric_sources(claim: str, evidence: str) -> list[str]:
    """Bind an explicit grade range to one exact source row, never D to D+."""
    text = numeric_text(claim)
    labels = {grade.replace("'", "+") for grade in re.findall(
        r"\bdiem(?:\s+(?:chu|hoc phan))?\s+([abcdf](?:\+|')?)(?![a-z0-9+'])", text)}
    other_measure = re.search(r"\b(?:gpa|dqt|diem qua trinh|diem ren luyen|tin chi|hoc ky|hoc phi|"
        r"ngay|gio|thang|nam|nguoi|dong|vnd)\b|%", text)
    range_claim = any(operator is not None for _, operator in quantities(claim)) or re.search(
        r"\d(?:[.,]\d+)?\s*[-–—]\s*\d", text)
    if len(labels) != 1 or other_measure or not range_claim:
        return [evidence]
    target = next(iter(labels))
    rows = [row for grade, row in re.findall(r"(?m)^\s*([abcdf](?:\+|')?)\s*[:_]\s*([^\n]+)",
        normalized(evidence)) if grade.replace("'", "+") == target and quantities(row)]
    return rows or [evidence]


def price_rate_units(text: str) -> list[tuple[Decimal, str]]:
    """Keep explicit price denominators, including row-local table overrides.

    A mixed header such as 'đồng/tín chỉ (ĐVHT)' cannot select a denominator
    for every row. Only explicit prose or the particular row supplies it.
    """
    text = numeric_text(text)
    units = r"tin chi|dvht|don vi hoc trinh"
    found = []
    for number in _NUMBER.finditer(text):
        suffix = re.match(r"\s*(?:dong|vnd)\s*(?:/|tren\s+|cho moi\s+|moi\s+)(" + units + r")\b",
                          text[number.end():])
        if suffix:
            denominator = "tin_chi" if suffix.group(1) == "tin chi" else "dvht"
            found.append((numeric_value(number.group()), denominator))
            tail = text[number.end() + suffix.end():]
            if denominator == "tin_chi" and re.match(r"\s*\(\s*dvht\s*\)", tail):
                found.append((numeric_value(number.group()), "dvht"))
    table_credit_header = bool(re.search(r"dong[^\n]*[/]tin chi", text))
    for line in text.splitlines():
        cells = line.split("|")
        if len(cells) < 3:
            continue
        amount = cells[-1].strip()
        if _NUMBER.fullmatch(amount):
            if re.search(r"\b(?:dvht|don vi hoc trinh)\b", "|".join(cells[:-1])):
                found.append((numeric_value(amount), "dvht"))
            elif table_credit_header:
                found.append((numeric_value(amount), "tin_chi"))
    return found


def table_fee_issues(claim: str, evidence: str) -> list[str]:
    """Bind a price to its row's cohort, program and section, not table-wide words."""
    body, source = normalized(claim), normalized(evidence)
    if not re.search(r"\b(?:hoc phi|dong|vnd)\b", body):
        return []
    rows, section = [], ""
    for line in source.splitlines():
        if re.match(r"\s*[ivx]+[.]\s", line):
            section = line
        cells = line.split("|")
        if len(cells) >= 4 and _NUMBER.fullmatch(cells[-1].strip()):
            rows.append((numeric_value(cells[-1].strip()), section + " " + cells[1], cells[-2]))
    if not rows:
        return []
    def programs(text):
        return {label for pattern, label in ((r"\b(?:cu nhan|cn)\b", "cn"),
            (r"\b(?:ky su|ks|kien truc su|kts)\b", "ks")) if re.search(pattern, text)}
    def cohort_matches(cohort, scope):
        values = [int(v) for v in re.findall(r"\bk\s*(\d{2})\b", scope)]
        if not values:
            return True
        if "tro ve truoc" in scope:
            return cohort <= values[0]
        if re.search(r"\btu\s+k", scope):
            return cohort >= values[0]
        return min(values) <= cohort <= max(values)
    cohorts = [int(v) for v in re.findall(r"\bk\s*(\d{2})\b", body)]
    amounts = {n for n, _ in quantities(claim) if n >= 10000}
    for amount in amounts:
        matching = []
        for price, program, scope in rows:
            if price != amount:
                continue
            if any((term in body) != (term in program) for term in ("cdio", "chat luong cao", "vua lam vua hoc")):
                continue
            if programs(body) and not programs(body).issubset(programs(program)):
                continue
            if "tich hop" in body and "tich hop" not in program:
                continue
            if len(cohorts) == 1 and not cohort_matches(cohorts[0], scope):
                continue
            matching.append(program)
        if any(price == amount for price, _, _ in rows) and not matching:
            return ["CONTRADICTED_TABLE_ROW"]
    return []


def applicable_fee_row_ranges(evidence: str, question: str) -> list[tuple[int, int]] | None:
    """Exact table spans for one explicit cohort/program, never a rendered answer.

    Ambiguous, comparative and surcharge questions keep the complete evidence.
    Citation readback and both evidence gates always retain the whole source.
    """
    query = normalized(question)
    cohorts = {int(v) for v in re.findall(r"\b(?:k\s*|khoa\s+)(\d{2})\b", query)}
    if "hoc phi" not in query or "phu thu" in query or len(cohorts) != 1:
        return None
    cohort = next(iter(cohorts))
    degree_patterns = (r"\b(?:cu nhan|cn)\b", r"\b(?:ky su|ks|kien truc su|kts)\b")
    degrees = {i for i, pattern in enumerate(degree_patterns) if re.search(pattern, query)}
    if len(degrees) != 1:
        return None
    ranges, section, offset, header_end, section_range = [], "", 0, None, None
    for line in evidence.splitlines(keepends=True):
        source = normalized(line)
        if re.match(r"\s*[ivx]+[.]\s", source):
            section = source
            section_range = (offset, offset + len(line))
            if header_end is None:
                header_end = offset
        cells = source.split("|")
        if len(cells) >= 4 and _NUMBER.fullmatch(cells[-1].strip()):
            if header_end is None:
                header_end = offset
            program, scope = section + " " + cells[1], cells[-2]
            program_degrees = {i for i, pattern in enumerate(degree_patterns) if re.search(pattern, program)}
            tags_match = all((term in query) == (term in program) for term in ("cdio", "chat luong cao", "vua lam vua hoc"))
            post_degree = bool(re.search(r"da co bang (?:cn|cu nhan)", program))
            post_requested = bool(re.search(r"da co bang (?:cn|cu nhan)", query))
            values = [int(v) for v in re.findall(r"\bk\s*(\d{2})\b", scope)]
            if not values:
                applies = True
            elif "tro ve truoc" in scope:
                applies = cohort <= min(values)
            elif re.search(r"\btu\s+k", scope):
                applies = cohort >= min(values)
            else:
                applies = min(values) <= cohort <= max(values)
            if (tags_match and degrees.issubset(program_degrees) and post_degree == post_requested and applies
                    and ("tich hop" not in query or "tich hop" in program)):
                ranges.append((section_range, (offset, offset + len(line))))
        offset += len(line)
    if len(ranges) != 1 or not header_end:
        return None
    group, row = ranges[0]
    return [(0, header_end), *([group] if group else []), row]


def fee_unit_span(evidence: str, row_ranges: list[tuple[int, int]]) -> tuple[int, int] | None:
    """Locate the exact printed denominator for one unambiguous table row."""
    if len(row_ranges) not in (2, 3):
        return None
    header, row = row_ranges[0], row_ranges[-1]
    start, end = row
    override = re.search(r"\bĐVHT\b|đơn vị học trình", evidence[start:end], re.I)
    if override:
        return start + override.start(), start + override.end()
    start, end = header
    credit = re.search(r"tín chỉ", evidence[start:end], re.I)
    if credit:
        return start + credit.start(), start + credit.end()
    return None


def quantity_support_issues(claim: str, evidence: str) -> list[str]:
    values = quantities(evidence)
    allowed = {value for value, _ in values}
    issues = []
    source_rates = price_rate_units(evidence)
    for value, denominator in price_rate_units(claim):
        supported = {unit for amount, unit in source_rates if amount == value}
        if supported and denominator not in supported:
            issues.append("CONTRADICTED_UNIT")
    source_units = quantity_units(evidence)
    for value, unit in quantity_units(claim):
        existing = {name for number, name in source_units if number == value}
        if existing and unit not in existing:
            issues.append("CONTRADICTED_UNIT")
    for value, operator in quantities(claim):
        if value not in allowed:
            issues.append("UNSUPPORTED_QUANTITY")
        elif operator is not None:
            supported = {kind for number, kind in values if number == value and kind is not None}
            if supported and operator not in supported:
                issues.append("CONTRADICTED_THRESHOLD")
    return issues


def support_issues(claim: str, evidence: str) -> tuple[str, ...]:
    """Reject invented numbers, weakened thresholds and reversed local rules.

    This is a conservative guard, not an entailment model. Semantic validation
    and evaluation remain necessary, especially for missing exceptions.
    """
    # One row must support the complete range. Unioning endpoints across rows
    # or sources would silently invent a wider range.
    issues = min((quantity_support_issues(claim, source) for source in grade_numeric_sources(claim, evidence)), key=len)
    source = normalized(evidence)
    if "hoc ky" in source and re.search(r"\d\s*tc\b", source):
        for code, credits in re.findall(r"\bma(?: hoc phan| mon)?\s+(\d{6})\s*[-–−]\s*(\d{1,2})\b", normalized(claim)):
            if re.search(r"(?m)^\s*" + code + r"\s*[-–−]\s*" + credits + r"\s*$", source):
                issues.append("CONTRADICTED_COURSE_CODE")
    issues.extend(table_fee_issues(claim, evidence))
    if missing_parenthetical_condition(claim, evidence) or missing_conjunctive_condition(claim, evidence):
        issues.insert(0, "MISSING_MATERIAL_CONDITION")
    source_thresholds = symbolic_thresholds(evidence)
    for target, operator in symbolic_thresholds(claim):
        supported = {kind for variable, kind in source_thresholds if variable == target}
        if supported and operator not in supported:
            issues.append("CONTRADICTED_THRESHOLD")
    body = normalized(claim)
    # Match the strongest local sentence instead of using an unrelated ban
    # elsewhere in a long document as evidence against the current claim.
    topic = set(re.findall(r"[a-z]+", body)) - _STOP
    claim_grades = grade_subjects(body)
    source_passing_grades = passing_grade_subjects(evidence)
    ranked = []
    for sentence in re.split(r"[;\n]|(?<=[.!?])\s+", normalized(evidence)):
        source_grades = grade_subjects(sentence)
        if claim_grades and source_grades and claim_grades.isdisjoint(source_grades):
            continue  # A rule about F cannot negate a statement about D.
        if (claim_grades and claim_grades.issubset(source_passing_grades) and not source_grades
                and re.search(r"\b(?:diem hoc phan|hoc phan) (?:khong|chua) dat\b", sentence)):
            continue  # The source explicitly limits this rule to failed courses.
        words = set(re.findall(r"[a-z]+", sentence)) - _STOP
        ranked.append((len(topic & words) / max(1, len(topic)), sentence))
    if topic and ranked:
        score, sentence = max(ranked, key=lambda item: item[0])
        if score >= .8:
            claim_predicates, source_predicates = predicate_polarities(body), predicate_polarities(sentence)
            for kind, polarity in claim_predicates.items():
                other = source_predicates.get(kind, frozenset())
                if len(polarity) == len(other) == 1 and polarity != other:
                    issues.append("CONTRADICTED_POLARITY")
                    break
    return tuple(dict.fromkeys(issues))
