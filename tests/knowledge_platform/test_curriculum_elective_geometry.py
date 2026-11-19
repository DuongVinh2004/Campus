from copy import deepcopy

import pytest

from campus247.application.knowledge.curriculum_elective_geometry import elective_scope
from campus247.application.knowledge.curriculum_geometry import geometry_allows
from campus247.application.knowledge.platform_models import PlatformError


def fixture():
    def cell(row, column, text, top):
        return {"row": row, "column": column, "text": text, "bbox": [column*100, top, (column+1)*100, top+10]}
    title = cell(0, 0, "Programme (2025)", 0)
    rows = [[cell(0, 0, "Học phần tự chọn bắt buộc", 20), cell(0, 1, "HPTCBB 1 (2TC)", 20), cell(0, 2, "HPTCBB 2 (3TC)", 20)],
        [cell(1, 0, "Lựa chọn 1", 30), cell(1, 1, "123456 – Môn A", 30), cell(1, 2, "345678 – Môn C", 30)],
        [cell(2, 0, "Lựa chọn 2", 40), cell(2, 1, "234567 – Môn B", 40), cell(2, 2, "456789 – Môn D", 40)]]
    witness = {"geometry_pages": {"1": {"tables": [{"rows": [[title]]}, {"rows": rows}]}}}
    group = {"page": 1, "table": 1, "column": 1, "header": rows[0][1], "caption": rows[0][0],
        "title_cells": [title], "label": "HPTCBB 1", "options": [
            {"row_label": rows[1][0], "value": rows[1][1]}, {"row_label": rows[2][0], "value": rows[2][1]}]}
    block = {"text": "Programme (2025)\nHọc phần tự chọn bắt buộc\nHPTCBB 1 (2TC)\nLựa chọn 1\n123456 – Môn A\nLựa chọn 2\n234567 – Môn B"}
    return witness, group, block, {"page": 1}


def test_column_proves_both_options_and_group_credit_without_claiming_a_semester_or_relation():
    witness, group, block, page = fixture()
    caps = elective_scope(witness, group, block, page)
    assert caps["course_codes"] == ["123456", "234567"]
    assert geometry_allows("Nhóm HPTCBB 1 có những phương án nào?", caps)
    for query in ("Nhóm HPTCBB 2?", "HPTCBB 1 ở học kỳ 2?", "HPTCBB 1 là tiên quyết?", "HPTCBB 1 phải chọn mấy môn?",
            "Môn 123456 có 2 tín chỉ không?", "Môn 999999 có tên gì?"):
        assert not geometry_allows(query, caps)


@pytest.mark.parametrize("fault", ["column", "drop_option", "other_option", "row_label", "title", "body", "page"])
def test_group_cannot_adopt_a_neighbor_column_or_lose_an_option(fault):
    witness, group, block, page = deepcopy(fixture())
    if fault == "column": group["column"] = 2
    elif fault == "drop_option": group["options"].pop()
    elif fault == "other_option": group["options"][1]["value"] = witness["geometry_pages"]["1"]["tables"][1]["rows"][2][2]
    elif fault == "row_label": group["options"][0] = {**group["options"][0], "row_label": {"text": "Bắt buộc chọn1"}}
    elif fault == "title": group["title_cells"] = [{"text": "Other programme"}]
    elif fault == "body": block["text"] += "\nMỗi phương án đều 2TC."
    elif fault == "page": page["page"] = 2
    with pytest.raises(PlatformError, match="CURRICULUM_ELECTIVE_BINDING"):
        elective_scope(witness, group, block, page)
