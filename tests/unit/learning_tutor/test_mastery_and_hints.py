"""F7 pure parts: BKT numbers, bands, class map k-anonymity, hint checks, deterministic fallback."""
from __future__ import annotations

import random

import pytest

from campus247.domain.learning.mastery import (MASTERED, NEEDS_REVIEW, NOT_ENOUGH, PROGRESSING, Mastery, band, class_map, guess_for, option_rates,
    review_order, update)
from campus247.domain.learning.tutor_hints import hint_issues, level_for, template_hint

PAGE = "Điểm trung bình tích lũy được tính theo trọng số là số tín chỉ của học phần. Sinh viên có điểm D được tính là đạt học phần."


def test_bkt_matches_hand_computed_value():
    # P(K)=0.2, correct, guess 0.25: posterior = .2*.9 / (.2*.9 + .8*.25) = .18/.38 ; then + (1-post)*.15
    post = 0.18 / 0.38
    assert update(0.2, True, guess=0.25) == pytest.approx(post + (1 - post) * 0.15)
    post = 0.2 * 0.1 / (0.2 * 0.1 + 0.8 * 0.75)
    assert update(0.2, False, guess=0.25) == pytest.approx(post + (1 - post) * 0.15)
    assert guess_for(4) == 0.25 and guess_for(None) == 0.05


def test_bkt_properties_seeded():
    rng = random.Random(3)
    for _ in range(500):
        p, g, w = rng.random() * 0.98 + 0.01, rng.random() * 0.8 + 0.1, rng.choice([0.25, 0.5, 1.0])
        right, wrong = update(p, True, guess=g, weight=w), update(p, False, guess=g, weight=w)
        assert 0 < wrong < right < 1  # a correct answer never lowers belief below a wrong one
        assert update(p, True, guess=g, weight=0.5) <= update(p, True, guess=g, weight=1.0)  # less weight, less learning
    m = Mastery()
    for _ in range(12):
        m = m.apply(True, guess=0.25)
    assert m.band == MASTERED and m.attempts == 12 and m.correct == 12
    m = Mastery()
    for _ in range(4):
        m = m.apply(False, guess=0.25)
    assert m.band == NEEDS_REVIEW


def test_bands():
    assert band(0.99, 2) == NOT_ENOUGH and band(0.7, 3) == PROGRESSING and band(0.95, 3) == MASTERED and band(0.59, 3) == NEEDS_REVIEW


def test_review_order_puts_lowest_mastery_concept_first_and_keeps_sm2_ties():
    mastery = {"a": Mastery(0.9, 5, 5), "b": Mastery(0.3, 5, 1)}
    due = [{"id": 1, "concept_ids": ["a"]}, {"id": 2, "concept_ids": ["b"]}, {"id": 3, "concept_ids": []}, {"id": 4, "concept_ids": ["b"]}]
    assert [i["id"] for i in review_order(due, mastery)] == [2, 4, 1, 3]


def rows(concept, n, p, attempts=5, label="Khái niệm"):
    return [{"concept_id": concept, "label": label, "student": f"{concept}-s{i}", "p_known": p, "attempts": attempts} for i in range(n)]


def test_class_map_hides_small_cells_and_never_carries_identity():
    data = rows("c1", 4, 0.3) + rows("c2", 10, 0.3)[:6] + rows("c2", 10, 0.99)[6:]
    result = {e["concept_id"]: e for e in class_map(data)}
    assert result["c1"]["students"] == "<5" and result["c1"]["bands"] is None and result["c1"]["needs_review_rate"] is None
    assert result["c2"]["students"] == 10 and result["c2"]["bands"]["NEEDS_REVIEW"] == 6 and result["c2"]["bands"]["MASTERED"] == "<5"
    assert "s0" not in str(class_map(data))
    assert class_map(data)[0]["concept_id"] == "c2"  # concepts with data first, highest "needs review" rate first


def test_option_rates_respect_k():
    attempts = [{"item_id": "i1", "option": "A", "correct": True, "first": True}] * 3 + [{"item_id": "i2", "option": o, "correct": o == "B", "first": True} for o in "AABBBBBB"]
    out = option_rates(attempts)
    assert out["i1"]["attempts"] == "<5" and out["i1"]["options"] is None
    assert out["i2"]["first_try_rate"] == 0.75 and "A" not in out["i2"]["options"] and out["i2"]["options"]["B"] == 0.75


def test_hint_checks():
    quote = "Sinh viên có điểm D được tính là đạt học phần"
    assert hint_issues("Hãy xem lại cách tính điểm D.", quote, PAGE, level=1, correct_answers=["Đạt"]) == []
    assert "QUOTE_NOT_VERBATIM" in hint_issues("ok", "câu không có trong trang", PAGE, level=1, correct_answers=[])
    assert "QUOTE_NOT_VERBATIM" in hint_issues("ok", "ngắn", PAGE, level=1, correct_answers=[])
    assert "LEAKS_ANSWER" in hint_issues("Câu trả lời là điểm D được tính là đạt học phần", quote, PAGE, level=1, correct_answers=["điểm D được tính là đạt học phần"])
    assert "LEAKS_ANSWER" not in hint_issues("Xem lại", quote, PAGE, level=3, correct_answers=["điểm D được tính là đạt học phần"])  # level 3 may reveal
    assert "LEAKS_OPTION_CODE" in hint_issues("Hãy cân nhắc đáp án B", quote, PAGE, level=2, correct_answers=[])
    assert "HINT_LINK" in hint_issues("xem https://x.vn", quote, PAGE, level=1, correct_answers=[])
    assert "HINT_MARKDOWN" in hint_issues("# Tiêu đề\nxem lại", quote, PAGE, level=1, correct_answers=[])
    assert "HINT_LENGTH" in hint_issues("x" * 601, quote, PAGE, level=1, correct_answers=[])


def test_template_fallback_and_levels():
    t1 = template_hint(PAGE, "Điểm trung bình tích lũy tính theo trọng số nào?", 12, 1)
    assert t1["origin"] == "TEMPLATE" and "trang 12" in t1["hint"] and t1["quote"] in PAGE
    assert hint_issues(t1["hint"].replace("Xem lại trang 12: ", ""), t1["quote"], PAGE, level=1, correct_answers=[]) in ([], ["HINT_LENGTH"])
    t2 = template_hint(PAGE, "Điểm trung bình tích lũy tính theo trọng số nào?", 12, 2)
    assert len(t2["quote"]) >= len(t1["quote"])
    t3 = template_hint(PAGE, "x", 12, 3, solution="Điểm D là đạt.")
    assert "Điểm D là đạt." in t3["hint"]
    assert level_for(1, reveal_after=2) == 1 and level_for(2, reveal_after=3) == 2 and level_for(3, reveal_after=3) == 3
    assert level_for(1, reveal_after=3, asked_more=True) == 2 and level_for(1, reveal_after=3, asked_solution=True) == 3
