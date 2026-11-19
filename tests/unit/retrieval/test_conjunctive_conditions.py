"""Reject live-observed sufficiency inflation while preserving narrower facts."""
from pathlib import Path

import pytest
from campus247.application.retrieval.material_support import support_issues
from campus247.infrastructure.retrieval.public_knowledge import PublicKnowledgeStore

ROOT = Path(__file__).resolve().parents[3]
INCOMPLETE = ("Sinh viên không đang là sinh viên trình độ năm thứ nhất hoặc năm cuối khóa, "
    "không thuộc diện bị xem xét buộc thôi học và còn đủ thời gian học tập theo quy định tại "
    "khoản 5 Điều 2 của Quy chế này thì được xem xét chuyển sang học một chương trình, "
    "một ngành đào tạo khác.")


@pytest.fixture
def source():
    value = PublicKnowledgeStore(ROOT / "data/huce-public-20261013", tenant_id="HUCE", campus_id="HUCE")
    return next(row["content_text"] for row in value.rows if row["section_path"].startswith("Điều 15."))


def test_live_subset_of_transfer_conditions_is_not_sufficient(source):
    assert "MISSING_MATERIAL_CONDITION" in support_issues(INCOMPLETE, source)


@pytest.mark.parametrize("claim", [
    "Một điều kiện để được xem xét chuyển ngành là không đang là sinh viên trình độ năm thứ nhất hoặc năm cuối khóa.",
    "Sinh viên trình độ năm thứ nhất không được xem xét chuyển ngành.",
    "Sinh viên chỉ được xem xét chuyển ngành khi có đủ các điều kiện theo Điều 15.",
])
def test_necessary_conditions_and_exclusions_are_not_sufficient_claims(source, claim):
    assert "MISSING_MATERIAL_CONDITION" not in support_issues(claim, source)


def test_complete_conjunctive_permission_is_supported():
    source = ("Sinh viên được xem xét chuyển ngành đào tạo khi có đủ các điều kiện sau:\n"
        "a) Sinh viên hoàn thành học kỳ đầu tiên;\n"
        "b) Hiệu trưởng đồng ý hồ sơ chuyển ngành.\n\n2. Quy trình nộp đơn.")
    complete = ("Sinh viên hoàn thành học kỳ đầu tiên và Hiệu trưởng đồng ý hồ sơ chuyển ngành "
        "thì được xem xét chuyển ngành đào tạo.")
    assert "MISSING_MATERIAL_CONDITION" not in support_issues(complete, source)
    assert "MISSING_MATERIAL_CONDITION" in support_issues(
        "Sinh viên chỉ cần hoàn thành học kỳ đầu tiên thì được xem xét chuyển ngành đào tạo.", source)


def test_unrelated_all_conditions_list_does_not_reject_other_permission():
    source = ("Sinh viên được xem xét chuyển ngành đào tạo khi có đủ các điều kiện sau:\n"
        "a) Sinh viên hoàn thành học kỳ đầu tiên;\n"
        "b) Hiệu trưởng đồng ý hồ sơ chuyển ngành.\n\n2. Thư viện mở cửa thì được vào đọc sách.")
    assert "MISSING_MATERIAL_CONDITION" not in support_issues("Thư viện mở cửa thì được vào đọc sách.", source)
