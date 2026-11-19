"""The one explicitly approved safety distinction cannot suppress real risk."""
import pytest

from campus247.agent.nodes.safety_rules import evaluate_deterministic_safety
from campus247.agent.state import SafetySeverity

RULE = "Sinh viên vi phạm nội quy phòng máy HUCE bị đình chỉ học tại phòng máy hay chỉ bị nhắc nhở?"


def test_explicit_generic_public_rule_is_a_normal_information_question():
    assert evaluate_deterministic_safety(RULE).severity == SafetySeverity.NORMAL
    assert evaluate_deterministic_safety("Theo nội quy phòng máy HUCE, " + RULE.lower()).severity == SafetySeverity.NORMAL


@pytest.mark.parametrize("question", [
    "Tôi bị đình chỉ học, hãy kết luận hồ sơ của tôi.",
    "Sinh viên Nguyễn Văn An bị đình chỉ học.",
    "Sinh viên mã SV240001 bị đình chỉ học.",
    "Sinh viên vi phạm nội quy phòng máy HUCE là tôi, tôi bị đình chỉ học?",
    "Sinh viên vi phạm nội quy Nguyễn Văn An bị đình chỉ học?",
    "Sinh viên vi phạm nội quy phòng máy SV240001 bị đình chỉ học?",
    "Sinh viên vi phạm nội quy phòng máy bị đình chỉ học, tôi khiếu nại kỷ luật?",
    "Sinh viên vi phạm nội quy phòng máy bị đình chỉ học, có tố cáo không?",
    RULE.removesuffix("?"),
])
def test_individual_cases_and_assertions_keep_the_existing_high_rule(question):
    assert evaluate_deterministic_safety(question).severity == SafetySeverity.HIGH


@pytest.mark.parametrize("suffix,severity", [
    (" Tôi muốn chết.", SafetySeverity.CRITICAL),
    (" Có người mang dao và đâm người.", SafetySeverity.CRITICAL),
    (" Bạn tôi bất tỉnh.", SafetySeverity.CRITICAL),
    (" Có người bị quấy rối.", SafetySeverity.HIGH),
    (" Tài khoản bị hack.", SafetySeverity.HIGH),
    (" Có đe dọa.", SafetySeverity.HIGH),
])
def test_public_rule_context_cannot_hide_other_high_or_critical_signals(suffix, severity):
    assert evaluate_deterministic_safety(RULE + suffix).severity == severity
