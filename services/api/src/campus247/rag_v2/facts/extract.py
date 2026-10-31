"""Conservative typed facts. Values and quotes always come from the source body."""
from __future__ import annotations

import re
from collections.abc import Iterable
from hashlib import sha256

from campus247.rag_v2.ingest.units import context_text, source_text
from campus247.rag_v2.types import Fact, Unit

_MONEY = re.compile(r"(?<![\d.])\d{1,3}(?:[.,]\d{3})+(?![\d.])")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}?(?=(?i:Website|Email|Hotline|Fax)\s*:|[^\w-]|$)")
_DATE = re.compile(r"\b(?:[0-3]?\d\s*[/.-]\s*[01]?\d\s*[/.-]\s*20\d{2}|(?:ngày\s+)?[0-3]?\d\s+tháng\s+[01]?\d\s+năm\s+20\d{2})\b", re.IGNORECASE)
_PHONE = re.compile(r"(?:điện thoại|đt|hotline|tel|fax)\s*[:.]\s*((?:\+84|\(?0)[\d(). \t-]{7,25}\d)", re.IGNORECASE)
_ORG = re.compile(r"\b(?:Phòng|Khoa|Trung tâm|Ban|Trạm|Thư viện)[ \t]+(?!\s*[Pp]?\d)[^\n,:;@]{2,100}(?:\n\s*(?:và|&)\s+[^\n,:;@]{2,60})?", re.IGNORECASE)


def extract_facts(units: Iterable[Unit]) -> list[Fact]:
    facts = {}
    for unit in units:
        body, context = source_text(unit), context_text(unit)

        def add(kind, subject, value, quote, attributes=None, *, body=body, unit=unit):
            if not value or value not in quote or quote not in body:
                return
            attributes = attributes or {}
            key = sha256(f"{unit.unit_id}|{kind}|{subject}|{value}|{quote}|{sorted(attributes.items())}".encode()).hexdigest()[:16]
            facts[key] = Fact(key, kind, subject, value, unit.unit_id, quote,
                              unit.scope, attributes)

        def contact(value, quote, position, kind, *, body=body, unit=unit, add=add):
            begin = max(0, position - 250)
            value_position = body.find(value, position)
            orgs = list(_ORG.finditer(body[begin:value_position if value_position >= 0 else position]))
            orgs = [m for m in orgs if not re.search(r"\b(?:trong|theo|email|để|liên hệ|hành)\b", m.group(), re.IGNORECASE)]
            attrs = {"contact_type": kind}
            if orgs:
                org = orgs[-1]
                attrs["organization"] = org.group().strip()
                quote_end = body.find(quote, position)
                if quote_end >= 0:
                    quote = body[begin + org.start():quote_end + len(quote)].strip()
                add("contact", attrs["organization"], attrs["organization"], quote,
                    {"contact_type": "organization"})
            add("contact", attrs.get("organization", unit.doc_title), value, quote, attrs)

        lines = body.splitlines(keepends=True)
        position = 0
        for line in lines:
            quote = line.strip()
            # Pipe tables have explicit headers. Never interpret arbitrary numbers
            # in fee waivers, percentages or curriculum credits as tuition amounts.
            if unit.kind == "table_row" and "|" in line and re.search(r"học phí.*(?:tín chỉ|đvht)", context, re.IGNORECASE):
                cells = [c.strip() for c in quote.split("|")]
                headers = next((l for l in context.splitlines() if "|" in l and re.search(r"học phí", l, re.IGNORECASE)), "")
                column_names = [c.strip() for c in headers.split("|")]
                fee_columns = [i for i, c in enumerate(column_names) if re.search(r"học phí", c, re.IGNORECASE)]
                if len(cells) == len(column_names) and len(fee_columns) == 1:
                    i = fee_columns[0]
                    if _MONEY.fullmatch(cells[i]):
                        attrs = {"currency": "VND", "basis": "ĐVHT" if "ĐVHT" in quote else "tín chỉ",
                                 "column_header": column_names[i], "row": quote}
                        for j, name in enumerate(column_names):
                            if j != i:
                                attrs[name] = cells[j]
                        attrs["cohort_constraint"] = next((c for c in cells if re.search(r"\bK\d{2}\b", c)), "")
                        subject = cells[1] if len(cells) > 1 else unit.doc_title
                        add("fee", subject, cells[i], quote, attrs)
            # Explicit monetary units only; preserve annual surcharges as annual.
            if re.search(r"học phí|phụ thu", context + "\n" + quote, re.IGNORECASE):
                for m in _MONEY.finditer(quote):
                    suffix = quote[m.end():]
                    amount_unit = re.match(r"\s*(?:đồng|đ)\s*/\s*(năm|tín chỉ|ĐVHT)", suffix, re.IGNORECASE)
                    if amount_unit:
                        value = quote[m.start():m.end() + amount_unit.end()]
                        program = next((l for l in reversed(context.splitlines()) if re.search(r"phụ thu", l, re.IGNORECASE)), unit.doc_title)
                        if re.search(r"phụ thu", quote, re.IGNORECASE):
                            program = quote[:m.start()].strip()
                        add("fee", program, value, quote,
                            {"currency": "VND", "basis": amount_unit[1], "row": quote,
                             "cohort_constraint": quote[:m.start()].strip()})
            # Only a local scheduling/submission cue makes a date a deadline fact.
            previous = body[max(0, position - 100):position]
            cue = re.search(r"hạn\s+(?:nộp|đăng ký|gửi)|(?:thời gian|hạn chót|tiếp nhận hồ sơ)|(?:nộp|gửi|đăng ký).*(?:trước|đến|ngày)", quote, re.IGNORECASE)
            if not cue and _DATE.search(quote) and re.search(r"thời gian|hạn chót|tiếp nhận hồ sơ|(?:nộp|gửi|đăng ký).*(?:trước|đến|ngày)", previous, re.IGNORECASE | re.DOTALL):
                cue = True
            if cue:
                dates = list(_DATE.finditer(quote))
                for m in dates:
                    role = "date"
                    if re.search(r"từ(?:\s+ngày)?\s*$", quote[:m.start()], re.IGNORECASE):
                        role = "start"
                    elif re.search(r"đến|trước|hạn", previous + quote[:m.start()], re.IGNORECASE):
                        role = "end"
                    add("deadline", unit.path, m.group(), quote, {"date_role": role})
            for m in _EMAIL.finditer(quote):
                # Include nearby department text in the *verbatim* quote when it
                # precedes a line-wrapped address. No organization is guessed.
                contact(m.group(), quote, position, "email")
            for m in _PHONE.finditer(quote):
                value = m[1].strip()
                if 9 <= len(re.sub(r"\D", "", value)) <= 12:
                    contact(value, quote, position, "phone")
            # Relations need an explicit subject and object. Diagram legends in
            # the real corpus deliberately produce no prerequisite edges.
            relation = re.search(r"(?P<subject>\b\d{6}\b[^\n:;|]{0,100}?)\s*(?:có\s+)?(?:học phần\s+)?(?P<relation>tiên quyết|song hành)\s*:\s*(?P<object>[^;|\n]+)", quote, re.IGNORECASE)
            if relation and re.search(r"\b\d{6}\b", relation["object"]):
                add("prerequisite", relation["subject"].strip(), relation["object"].strip(), quote,
                    {"relation": relation["relation"].casefold()})
            position += len(line)
        # Explicit prerequisite table columns are safe even without prose.
        header = next((line for line in context.splitlines() if "|" in line and re.search(r"tiên quyết|song hành", line, re.IGNORECASE)), "")
        if header and unit.kind == "table_row":
            names = [c.strip() for c in header.split("|")]
            for line in body.splitlines():
                cells = [c.strip() for c in line.split("|")]
                if len(cells) != len(names) or not re.search(r"\b\d{6}\b", cells[0]):
                    continue
                for i, name in enumerate(names):
                    if re.search(r"tiên quyết|song hành", name, re.IGNORECASE) and re.fullmatch(r"\d{6}(?:\s*[,;]\s*\d{6})*", cells[i]):
                        add("prerequisite", cells[0], cells[i], line.strip(), {"relation": name})
    return sorted(facts.values(), key=lambda fact: fact.fact_id)
