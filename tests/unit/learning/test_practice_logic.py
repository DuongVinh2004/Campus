import unicodedata
from datetime import UTC, datetime, timedelta

import pytest
from campus247.application.learning.practice import (
    ReviewState,
    grade_choice,
    grade_short_answer,
    next_review,
    normalize_text,
    pick_session,
    verify_citation,
    verify_item_citations,
)

NOW = datetime(2026, 11, 17, 3, 0, tzinfo=UTC)
PAGE = "Mạng máy tính chia làm bốn tầng.\nTầng giao vận dùng TCP hoặc UDP để  truyền dữ liệu giữa các tiến trình."


class TestCitations:
    def test_exact_quote_on_the_cited_page_passes(self):
        assert verify_citation(PAGE, "Tầng giao vận dùng TCP hoặc UDP").ok

    def test_line_breaks_and_double_spaces_do_not_matter(self):
        assert verify_citation(PAGE, "chia làm bốn tầng. Tầng giao vận dùng TCP").ok
        assert verify_citation(PAGE, "UDP để truyền dữ liệu giữa các tiến trình")

    def test_decomposed_unicode_matches_composed_text(self):
        quote = unicodedata.normalize("NFD", "Tầng giao vận dùng TCP")
        assert verify_citation(PAGE, quote).ok
        assert verify_citation(unicodedata.normalize("NFD", PAGE), "Tầng giao vận dùng TCP").ok

    def test_zero_width_characters_in_the_page_are_ignored(self):
        assert verify_citation("Tầng giao​ vận dùng TCP hoặc UDP", "Tầng giao vận dùng TCP hoặc UDP").ok

    def test_a_paraphrase_fails(self):
        result = verify_citation(PAGE, "Giao vận dùng giao thức TCP hoặc UDP")
        assert (result.ok, result.reason) == (False, "QUOTE_NOT_ON_PAGE")

    def test_a_different_case_fails(self):
        assert not verify_citation(PAGE, "TẦNG GIAO VẬN DÙNG TCP HOẶC UDP").ok

    def test_short_quotes_are_refused_even_if_present(self):
        assert verify_citation(PAGE, "TCP").reason == "QUOTE_TOO_SHORT"
        assert verify_citation(PAGE, "   a   b   ").reason == "QUOTE_TOO_SHORT"

    def test_missing_page(self):
        assert verify_citation(None, "Tầng giao vận dùng TCP").reason == "PAGE_MISSING"

    def test_item_level_check_reports_which_citation_failed(self):
        pages = {1: PAGE, 2: "Tầng mạng định tuyến gói tin qua nhiều nút."}
        citations = [
            {"page_no": 1, "quote": "Tầng giao vận dùng TCP hoặc UDP"},
            {"page_no": 2, "quote": "Tầng giao vận dùng TCP hoặc UDP"},  # right words, wrong page
            {"page_no": 9, "quote": "Tầng mạng định tuyến gói tin"},
            {"page_no": True, "quote": "Tầng mạng định tuyến gói tin"},  # a bool is not a page number
        ]
        failures = verify_item_citations(citations, pages)
        assert [(i, r.reason) for i, r in failures] == [(1, "QUOTE_NOT_ON_PAGE"), (2, "PAGE_MISSING"), (3, "PAGE_MISSING")]

    def test_an_item_without_citations_fails(self):
        assert [r.reason for _, r in verify_item_citations([], {1: PAGE})] == ["PAGE_MISSING"]

    def test_normalize_text(self):
        assert normalize_text("  a \n\t b​ ") == "a b"


class TestGrading:
    @pytest.mark.parametrize("given", ["TCP", " tcp ", "Tcp!", "t-c-p".replace("-", "")])
    def test_short_answer_ignores_case_punctuation_and_spacing(self, given):
        assert grade_short_answer(given, ["TCP"])

    def test_punctuation_between_letters_separates_words(self):
        assert not grade_short_answer("T.C.P", ["TCP"])

    def test_short_answer_accepts_any_listed_form_and_never_empty(self):
        assert grade_short_answer("giao thức điều khiển truyền tải", ["TCP", "Giao thức điều khiển truyền tải"])
        assert not grade_short_answer("   ", ["TCP"])
        assert not grade_short_answer("TCP", [])
        assert not grade_short_answer("", [""])

    def test_choices_are_exact_sets(self):
        assert grade_choice(["b"], ["b"])
        assert grade_choice(["c", "a"], ["a", "c"])
        assert not grade_choice(["a"], ["a", "c"])
        assert not grade_choice(["a", "b", "c"], ["a", "c"])
        assert not grade_choice([], [])


class TestSpacing:
    def test_first_right_answer_comes_back_tomorrow(self):
        state = next_review(ReviewState(), correct=True, now=NOW)
        assert (state.interval_days, state.repetitions) == (1, 1)
        assert state.due_at == NOW + timedelta(days=1)

    def test_right_answers_stretch_the_interval(self):
        state, now, intervals = ReviewState(), NOW, []
        for _ in range(5):
            state = next_review(state, correct=True, now=now)
            intervals.append(state.interval_days)
            now = state.due_at
        assert intervals == [1, 3, 8, 23, 69]  # 1, 1*2.7, 3*2.8, 8*2.9, 23*3.0, rounded
        assert state.ease == pytest.approx(3.0)

    def test_a_wrong_answer_resets_to_one_day_and_lowers_ease(self):
        grown = ReviewState(ease=2.7, interval_days=24, repetitions=4, due_at=NOW)
        state = next_review(grown, correct=False, now=NOW)
        assert (state.interval_days, state.repetitions) == (1, 0)
        assert state.ease == pytest.approx(2.5) and state.due_at == NOW + timedelta(days=1)

    def test_ease_never_leaves_its_bounds(self):
        state = ReviewState()
        for _ in range(20):
            state = next_review(state, correct=False, now=NOW)
        assert state.ease == pytest.approx(1.3)
        for _ in range(40):
            state = next_review(state, correct=True, now=NOW)
        assert state.ease == pytest.approx(3.0) and state.interval_days == 365

    def test_naive_now_is_rejected(self):
        with pytest.raises(ValueError):
            next_review(ReviewState(), correct=True, now=datetime(2026, 1, 1))


class TestSession:
    def test_overdue_first_then_new_then_upcoming(self):
        states = {
            "late-2": ReviewState(due_at=NOW - timedelta(days=2)),
            "late-5": ReviewState(due_at=NOW - timedelta(days=5)),
            "new-b": ReviewState(),
            "new-a": ReviewState(),
            "soon": ReviewState(due_at=NOW + timedelta(days=1)),
            "far": ReviewState(due_at=NOW + timedelta(days=9)),
        }
        assert pick_session(states, now=NOW, size=10) == ["late-5", "late-2", "new-a", "new-b", "soon", "far"]
        assert pick_session(states, now=NOW, size=3) == ["late-5", "late-2", "new-a"]

    def test_due_exactly_now_counts_as_due(self):
        assert pick_session({"x": ReviewState(due_at=NOW), "y": ReviewState()}, now=NOW) == ["x", "y"]

    def test_empty_and_zero_size(self):
        assert pick_session({}, now=NOW) == []
        assert pick_session({"x": ReviewState()}, now=NOW, size=0) == []
