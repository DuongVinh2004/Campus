from campus247.application.knowledge.deadline_excerpt import (
    is_submission_deadline_question,
    submission_deadline_excerpt,
)


def test_issue_date_and_application_appendix_do_not_establish_a_deadline():
    appendix = "Ngày 28 tháng 9 năm 2026\nHƯỚNG DẪN HỒ SƠ MIỄN GIẢM HỌC PHÍ\nSinh viên chỉ nộp hồ sơ minh chứng 01 lần."
    assert submission_deadline_excerpt(appendix) is None
    assert submission_deadline_excerpt("Đơn xin hỗ trợ. Ngày ... tháng ... năm ...") is None


def test_actual_period_is_an_exact_source_span_with_conditions():
    source = "2. Thời gian tiếp nhận hồ sơ\n- Từ ngày 29/9/2026 đến hết ngày 20/10/2026.\n- Nộp đủ hồ sơ theo phụ lục.\n3. Địa điểm tiếp nhận hồ sơ\nTầng 2."
    excerpt = submission_deadline_excerpt(source)
    assert excerpt in source and "29/9/2026" in excerpt and "20/10/2026" in excerpt
    assert "Nộp đủ hồ sơ theo phụ lục" in excerpt and "Tầng 2" not in excerpt
    assert is_submission_deadline_question("Thông báo miễn giảm học phí có hạn nộp hồ sơ ngày nào?")
    assert not is_submission_deadline_question("Hồ sơ miễn giảm gồm những gì?")
