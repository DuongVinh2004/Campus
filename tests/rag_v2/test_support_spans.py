"""F4.2: the supporting passage lies inside the unit and holds the statement's numbers (200 machine-made pairs from the real index)."""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest

from campus247.rag_v2.outcome.support_spans import find_support, holds_every_number, numbers

ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "data/rag_v2_index/units.jsonl"


def test_verbatim_statement_returns_its_exact_position_even_with_other_whitespace():
    text = "Điều 10. Học phí\nSinh viên nộp học phí 580.500 đồng mỗi tín chỉ trước ngày 15/09/2026. Quá hạn bị phạt."
    span = find_support("nộp học phí 580.500   đồng mỗi tín chỉ", text)
    assert span and text[span[0]:span[1]].startswith("nộp học phí 580.500 đồng")


def test_paraphrase_picks_the_sentence_holding_the_numbers():
    text = "Quy định chung về học phí. Mỗi tín chỉ thu 580.500 đồng. Hạn nộp là 15/09/2026. Liên hệ phòng Tài chính để biết thêm."
    span = find_support("Học phí là 580.500 đồng cho một tín chỉ", text)
    assert span and "580.500" in text[span[0]:span[1]]
    assert holds_every_number("Học phí là 580.500 đồng cho một tín chỉ", text, span)


def test_no_overlap_returns_none_and_empty_inputs_are_safe():
    assert find_support("", "abc") is None and find_support("abc", "") is None
    assert find_support("zzz qqq", "Không có gì liên quan ở đây cả.") is None


def test_number_normalisation_treats_vietnamese_and_plain_separators_alike():
    assert numbers("580.500 đồng và 1,5 triệu") == ["580500", "15"]


@pytest.mark.skipif(not UNITS.exists(), reason="no local RAG v2 index")
def test_200_machine_made_pairs_from_the_index_hold_every_number():
    rng = random.Random(20261126)
    units = [json.loads(line) for line in UNITS.read_text(encoding="utf-8").splitlines()]
    units = [u for u in units if len(numbers(u["text"])) >= 1 and 80 <= len(u["text"]) <= 3000]
    rng.shuffle(units)
    pairs = []
    for unit in units:
        sentences = [s.strip() for s in re.split(r"(?<!\d)[.;]\s+|\n+", unit["text"]) if numbers(s) and len(s.split()) >= 5]
        if not sentences:
            continue
        sentence = rng.choice(sentences)
        words = sentence.split()
        variants = [sentence, " ".join(words), " ".join(words[1:]) if len(words) > 7 else sentence, " ".join(words[:-1]) if len(words) > 7 else sentence]
        pairs.append((rng.choice(variants), unit["text"]))
        if len(pairs) == 200:
            break
    assert len(pairs) == 200
    failures = []
    for statement, text in pairs:
        span = find_support(statement, text)
        if span is None or not (0 <= span[0] < span[1] <= len(text)) or not holds_every_number(statement, text, span):
            failures.append(statement[:60])
    rate = 1 - len(failures) / len(pairs)
    assert rate >= 0.99, f"{rate:.3f}: {failures[:3]}"
