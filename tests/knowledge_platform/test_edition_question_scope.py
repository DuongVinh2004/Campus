"""Explicit query scope is independent of the actor's authorization grants."""
from types import SimpleNamespace as NS

import pytest

from campus247.application.knowledge.document_identity import ApplicabilityScope, ScopeAxis
from campus247.application.knowledge.edition_release import question_axes


@pytest.mark.parametrize("question,expected", [
    ("K68 cần điều kiện nào?", ("K68",)),
    ("Sinh viên khóa 68 cần điều kiện nào?", ("K68",)),
    ("Em không thuộc K68", ()),
    ("Em không phải sinh viên K68 mà học K69", ("K69",)),
    ("Ngoại trừ K68, điều kiện của K69 là gì?", ("K69",)),
    ("Điều 68 có quy định gì?", ()),
    ("Em chưa biết học phí K68 có thay đổi không?", ("K68",)),
    ("So sánh K68 và K69", ("K68", "K69")),
])
def test_cohort_mentions_do_not_turn_negation_or_an_article_number_into_applicability(question, expected):
    candidates = [NS(identity=NS(scope=ApplicabilityScope(cohorts=ScopeAxis(kind="VALUES", values=("K68", "K69")))))]
    assert question_axes(question, candidates)["cohorts"] == expected
