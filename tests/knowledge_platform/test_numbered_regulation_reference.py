from campus247.application.knowledge.document_reference import preferred_document_versions, focused_named_document_question
from campus247.application.knowledge.question_scope import focused_source_question


def test_numbered_regulation_reference_selects_the_named_document_before_curriculum_matches():
    versions = [{"version_id": "regulation", "title": "Quy chế đào tạo — Quyết định 1486"},
        {"version_id": "curriculum", "title": "Sơ đồ tự chọn ngành Công nghệ thông tin"}]
    question = "Theo Điều 3 Quy chế 1486, học phần tự chọn được định nghĩa thế nào?"
    assert preferred_document_versions(question, versions) == ["regulation"]
    assert focused_source_question(question) == "học phần tự chọn được định nghĩa thế nào?"
    assert preferred_document_versions("Theo Quy chế 1486 và Quyết định 2114?", versions) is None
    assert focused_source_question("Theo Quy chế 1486 áp dụng năm 2023, môn nào?") == "Theo Quy chế 1486 áp dụng năm 2023, môn nào?"


def test_named_stem_forms_search_fields_after_bibliographic_narrowing():
    versions = [{"version_id": "stem", "title": "Chương trình Học bổng STEM Quỹ Châu Á"},
        {"version_id": "other", "title": "Mẫu hồ sơ miễn giảm học phí"}]
    question = "Theo mẫu sơ yếu lý lịch học bổng STEM Quỹ Châu Á năm học 2025-2026, cần ảnh cỡ nào?"
    assert preferred_document_versions(question, versions) == ["stem"]
    assert focused_named_document_question(question) == "cần ảnh cỡ nào?"
    assert focused_named_document_question("Theo mẫu đơn học bổng STEM Quỹ Châu Á năm học 2025-2026, ý7 và8 ghi gì?") == "ý 7 và 8 ghi gì?"
    assert focused_named_document_question("Theo thông báo khác, cần ảnh cỡ nào?") == "Theo thông báo khác, cần ảnh cỡ nào?"
    assert preferred_document_versions(question, versions[1:]) is None
    notice = "Theo thông báo học bổng STEM Quỹ Châu Á năm học 2025-2026, mức học bổng và điều kiện điểm học tập là gì?"
    assert focused_named_document_question(notice) == notice
