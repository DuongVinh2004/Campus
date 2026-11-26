"""A unit's section headings are part of its source: the semester and the prerequisite pair of a reviewed curriculum row."""
from campus247.rag_v2.ingest.units import heading_text
from campus247.rag_v2.types import Scope, Statement, Unit
from campus247.rag_v2.verification.deterministic import check_statement


def row(path, text, uid="a" * 16, title="K71 — Khoa học máy tính — nội dung PDF 71CS"):
    return Unit(uid, ("c",), "doc", "v", title, "khac", "curriculum_row", path, 1,
                f"⟦RAG_V2_CONTEXT⟧\n{title}\n⟦RAG_V2_SOURCE⟧\n{text}", scope=Scope(("K71",)))


def test_locators_are_dropped_and_headings_kept():
    unit = row("71CS — Học kỳ 6 — các ô đã đối chiếu — PDF 1 > Học phần 608807 - 3 > tr.1", "608807 - 3\nHọc máy")
    assert heading_text(unit) == "71CS — Học kỳ 6 — các ô đã đối chiếu > Học phần 608807 - 3"
    noisy = row("Sổ tay sinh viên HUCE năm học 2026–2027 · trang 4 · chars 0:1200 > tr.4", "x", title="Sổ tay sinh viên HUCE năm học 2026–2027")
    assert heading_text(noisy) == ""                          # only the title and locators: nothing to add
    assert "trở về trước" in heading_text(row("K70_and_earlier_verify_individual_row — Kỹ thuật ô tô · trang 2 · chars 0:352 > tr.2", "x"))


def test_a_semester_stated_only_in_the_heading_is_supported():
    unit = row("71CS — Học kỳ 6 — các ô đã đối chiếu — PDF 1 > Học phần 608807 - 3 > tr.1", "608807 - 3\nHọc máy")
    ok = check_statement(Statement("Học máy (608807) được xếp ở học kỳ 6.", ("a" * 16,)), {"a" * 16: unit})
    assert ok.passed, ok.reasons
    wrong = check_statement(Statement("Học máy (608807) được xếp ở học kỳ 7.", ("a" * 16,)), {"a" * 16: unit})
    assert not wrong.passed and "NUMBER_NOT_IN_SOURCE" in wrong.reasons


def test_page_and_character_numbers_of_the_path_do_not_support_a_number():
    unit = row("Kế hoạch giảng dạy · trang 2 · chars 0:4257 > Dòng 191 > tr.2", "Tổng: 180TC", title="Kế hoạch giảng dạy")
    assert not check_statement(Statement("Tổng là 4257 tín chỉ.", ("a" * 16,)), {"a" * 16: unit}).passed
    assert not check_statement(Statement("Có 191 tín chỉ.", ("a" * 16,)), {"a" * 16: unit}).passed


def test_a_curriculum_row_is_kept_beside_its_page_when_its_heading_says_more():
    from campus247.rag_v2.generation.packing import pack_context
    page = Unit("p" * 16, ("c",), "doc", "v", "K71 — Khoa học máy tính", "chunk", "page", "K71 — Khoa học máy tính · trang 1", 1,
                "⟦RAG_V2_CONTEXT⟧\nK71\n⟦RAG_V2_SOURCE⟧\n608825 - 3 Nhập môn trí tuệ nhân tạo 608807 - 3 Học máy ...", scope=Scope(("K71",)))
    semester = row("71CS — Học kỳ 6 — các ô đã đối chiếu — PDF 1 > Học phần 608807 - 3 > tr.1", "608807 - 3\nHọc máy", uid="r" * 16)
    prereq = row("71CS — Học phần tiên quyết — 608825 → 608807 — PDF 1 > Học phần 608825 - 3 > tr.1", "608825 - 3\nNhập môn trí tuệ nhân tạo\n→", uid="q" * 16)
    plain = Unit("x" * 16, ("c",), "doc", "v", "Quy chế", "quy_che", "clause", "Điều 9 > Khoản 3", 1, "Khoản 3 ...", scope=Scope())
    packed, _ = pack_context([semester, prereq, plain], lambda chunk: page, budget=19_000)
    assert list(packed) == ["p" * 16, "r" * 16, "q" * 16]          # the page once, then both rows; a plain clause adds nothing


def test_a_plan_question_about_a_cohort_no_source_mentions_is_told_which_cohorts_exist():
    import asyncio
    from tests.rag_v2.test_service import FakeGateway, UnitIndex, answer
    k71 = Unit("k" * 16, ("c",), "doc", "v", "Kế hoạch K71", "khac", "curriculum_row", "K71 > Học phần", 1,
               "Tổng 180 tín chỉ áp dụng cho K71.", scope=Scope(("K71",)))
    general = Unit("g" * 16, ("c2",), "doc2", "v2", "Quy chế", "quy_che", "clause", "Điều 11", 1,
                   "Sinh viên bị cảnh báo học tập khi điểm trung bình dưới 1,0.", scope=Scope())
    gateway = FakeGateway(drafts=[["Sinh viên bị cảnh báo học tập khi điểm trung bình dưới 1,0."]])
    plan = asyncio.run(answer(gateway=FakeGateway(), index=UnitIndex([k71, general]), question="Chương trình CNTT K74 tổng bao nhiêu tín chỉ?"))
    assert plan.kind == "refuse" and "K74" in plan.text and "K71" in plan.text
    rule = asyncio.run(answer(gateway=gateway, index=UnitIndex([k71, general]), question="Sinh viên K74 bị cảnh báo học tập khi nào?"))
    assert rule.kind != "refuse" or "K74" not in rule.text                 # a general rule is not blocked by the cohort


def label_page(uid, label, chunk="c"):
    return Unit(uid, (chunk,), "doc", "v", "K71 — Khoa học máy tính — nội dung PDF 71CS", "khac", "page", f"71CS — {label}", 1,
                f"⟦RAG_V2_CONTEXT⟧\nK71\n⟦RAG_V2_SOURCE⟧\n71CS\n{label}:\n", scope=Scope(("K71",)))


class Units:
    def __init__(self, units):
        self.units = {u.unit_id: u for u in units}

    def get(self, uid):
        return self.units.get(uid)

    def all_ids(self):
        return tuple(self.units)


def test_label_pages_of_a_curriculum_move_behind_its_rows_and_are_not_pinned_back():
    from campus247.rag_v2.retrieval.hybrid import _label_pages_last
    from campus247.rag_v2.types import Candidate
    labels = [label_page(f"{i:016d}", f"Học phần tiên quyết — 6088{i:02d} → 6088{i + 1:02d}") for i in range(5)]
    learning = row("71CS — Học phần tiên quyết — 608825 → 608807 > Học phần 608807 - 3", "608807 - 3\nHọc máy", uid="h" * 16)
    ranked = [Candidate(u.unit_id, i, None, 1 / (60 + i)) for i, u in enumerate([*labels, learning], 1)]
    order, moved = _label_pages_last(ranked, Units([*labels, learning]))
    assert [c.unit_id for c in order[:2]] == [labels[0].unit_id, "h" * 16]       # the first label keeps its place
    assert moved == {u.unit_id for u in labels[1:]} and len(order) == len(ranked)  # nothing is dropped
    # A short page of a document without rows of its own (a notice, a calendar line) is left where it is.
    notice = [Unit(f"n{i:015d}", ("c",), "doc2", "v", "Thông báo", "khac", "page", "Thông báo", 1, "Hạn nộp: 20/10/2026", scope=Scope())
              for i in range(3)]
    order, moved = _label_pages_last([Candidate(u.unit_id, i, None, 0.1) for i, u in enumerate(notice, 1)], Units(notice))
    assert not moved and [c.unit_id for c in order] == [u.unit_id for u in notice]


def test_a_row_under_a_label_only_page_is_packed_without_the_page():
    from campus247.rag_v2.generation.packing import pack_context
    page = label_page("p" * 16, "Học phần tiên quyết — 608825 → 608807")
    learning = row("71CS — Học phần tiên quyết — 608825 → 608807 > Học phần 608807 - 3", "608807 - 3\nHọc máy", uid="h" * 16)
    selected, truncated = pack_context([learning], {"c": page}.get, budget=10_000)
    assert list(selected) == ["h" * 16] and not truncated


def test_a_cohort_inside_the_sources_range_is_not_an_unstated_code():
    unit = row("K70_and_earlier_verify_individual_row — Ngành Quản lý dự án > Học phần 511381 – 7", "511381 – 7\nKhóa luận tốt nghiệp",
               title="K70_and_earlier_verify_individual_row — Ngành Quản lý dự án")
    from dataclasses import replace
    units = {"a" * 16: replace(unit, scope=Scope())}             # the row declares no cohort of its own
    assert check_statement(Statement("Ngành Quản lý dự án (K69): học phần 511381 – 7 là Khóa luận tốt nghiệp.", ("a" * 16,)), units).passed
    wrong = check_statement(Statement("Ngành Quản lý dự án (K71): học phần 511381 – 7 là Khóa luận tốt nghiệp.", ("a" * 16,)), units)
    assert not wrong.passed                                     # K71 is outside "K70 trở về trước"
    assert not check_statement(Statement("Học phần CS101 là Khóa luận tốt nghiệp.", ("a" * 16,)), units).passed
