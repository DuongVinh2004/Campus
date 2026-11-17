import json
import re
from collections import Counter
from pathlib import Path

import pytest
from campus247.rag_v2.facts.extract import extract_facts
from campus247.rag_v2.ingest.units import build_units, source_text

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def corpus():
    rows = [json.loads(line) for line in (ROOT / "evals/corpus/served-chunks.jsonl").read_text(encoding="utf8").splitlines()]
    units = build_units(rows)
    return rows, units, extract_facts(units)


def test_every_real_fact_has_machine_verified_source(corpus):
    rows, units, facts = corpus
    sources = {r["chunk_id"]: r["text"] for r in rows}
    index = {u.unit_id: u for u in units}
    assert {f.kind for f in facts} >= {"fee", "deadline", "contact"}
    for fact in facts:
        unit = index[fact.unit_id]
        assert fact.value in fact.quote
        assert fact.quote in source_text(unit)
        assert all(fact.quote in sources[c] for c in unit.chunk_ids)
    assert facts == extract_facts(reversed(units))


def test_fee_gold_all_real_tariff_rows(corpus):
    rows, _, facts = corpus
    source = next(r["text"] for r in rows if "STT | Chương trình đào tạo | Đối tượng áp dụng" in r["text"])
    # Independent gold: every numeric rate in the final table column, plus the
    # three explicitly annual surcharges. Duplicate amounts are separate rows.
    gold = [line for line in source.splitlines() if "|" in line and line.split("|")[-1].strip() in
            {"580.500", "649.000", "336.000", "533.000", "592.500", "547.000", "696.500", "964.500", "870.500"}]
    gold += [line for line in source.splitlines() if "đ/năm" in line]
    assert len(gold) == 13
    assert all(any(f.kind == "fee" and f.quote == line for f in facts) for line in gold)
    credit = next(f for f in facts if f.kind == "fee" and f.value == "336.000")
    assert credit.attributes["basis"] == "ĐVHT"
    assert credit.scope.cohorts == ("K66",)
    assert "trở về trước" in credit.attributes["cohort_constraint"]
    international = next(f for f in facts if f.kind == "fee" and f.value == "19.500.000 đ/năm")
    assert "Quốc tế" in international.subject
    assert "Anh ngữ" not in international.subject


@pytest.mark.parametrize("kind,value", [
    ("deadline", "20/10/2026"), ("deadline", "29/9/2026"),
    ("deadline", "04/10/2026"), ("deadline", "06/10/2026"),
    ("deadline", "31/10/2025"), ("deadline", "13/02/2026"),
    ("deadline", "21/10/2026"),
    ("contact", "thuymt@huce.edu.vn"), ("contact", "lantt@huce.edu.vn"),
    ("contact", "dhxaydung@huce.edu.vn"), ("contact", "(024) 3869 6397"),
    ("contact", "024.38.691.684"),
    ("contact", "doanthanhnien@huce.edu.vn"),
])
def test_real_gold_values(corpus, kind, value):
    rows, _, facts = corpus
    assert any(value in r["text"] for r in rows)
    assert any(f.kind == kind and f.value == value for f in facts)


def test_deadline_roles_and_scope(corpus):
    _, _, facts = corpus
    end = next(f for f in facts if f.kind == "deadline" and f.value == "20/10/2026")
    start = next(f for f in facts if f.kind == "deadline" and f.value == "29/9/2026")
    assert end.attributes["date_role"] == "end"
    assert start.attributes["date_role"] == "start"
    assert end.scope.academic_years == ("2026-2027",)


def test_contacts_keep_department_and_ignore_room_as_department(corpus):
    _, _, facts = corpus
    fact = next(f for f in facts if f.value == "lantt@huce.edu.vn")
    assert "và Thư viện" in fact.attributes["organization"]
    assert not any(f.attributes.get("organization", "").startswith("Phòng 405") for f in facts)
    assert any(f.attributes.get("contact_type") == "organization" for f in facts)


def test_real_corpus_email_inventory_coverage(corpus):
    rows, _, facts = corpus
    gold = set()
    for row in rows:
        separated = re.sub(r"(?i)(Website|Email|Hotline|Fax)\s*:", r" \1:", row["text"])
        for token in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", separated):
            gold.add(token.rstrip(".;"))
    found = {f.value for f in facts if f.attributes.get("contact_type") == "email"}
    assert len(gold) == 29
    assert found == gold
    # Conference research metrics use @ too; mAP@0.5 is not an address.
    assert "mAP@0.5" not in found


def test_real_prerequisite_legends_do_not_invent_edges(corpus):
    rows, _, facts = corpus
    legends = [r for r in rows if "Học phần tiên quyết Học phần; Học phần song hành" in r["text"]]
    assert legends
    assert not extract_facts(build_units(legends))
    assert Counter(f.kind for f in facts)["prerequisite"] == 0


@pytest.mark.parametrize("text", [
    "471755 có học phần tiên quyết: 471754.\n",
    "Mã học phần | Tên | Tiên quyết\n471755 | CTDL 2 | 471754\n",
    "Mã học phần | Tên | Song hành\n471755 | CTDL 2 | 471754\n",
])
def test_explicit_prerequisite_relations(text):
    row = {"chunk_id": "c", "document_id": "d", "version_id": "v", "doc_title": "CTĐT K71 ngành 7480201", "doc_family": "ctdt", "text": text}
    facts = extract_facts(build_units([row]))
    assert len(facts) == 1
    assert facts[0].kind == "prerequisite"
    assert "471754" in facts[0].value
    assert facts[0].scope.programs == ("7480201",)


def test_amount_without_fee_unit_and_dates_without_deadline_cues_are_skipped():
    row = {"chunk_id": "c", "document_id": "d", "version_id": "v", "doc_title": "Tài liệu", "doc_family": "khac",
           "text": "Ngày 10/06/2026 ban hành quyết định.\nHọc bổng 10.000.000 đồng/sinh viên.\nMã số: 02438696397.\nMật khẩu có @ # !"}
    assert extract_facts(build_units([row])) == []
