"""Bind a complete elective catalogue column to its native table cells."""
import re

from campus247.application.knowledge.platform_models import PlatformError


def elective_scope(witness, group, block, page):
    def invalid():
        raise PlatformError(409, "CURRICULUM_ELECTIVE_BINDING", "Cột tự chọn phải giữ đúng tiêu đề, nhãn hàng và đầy đủ phương án nguồn.")
    if not group or group["page"] != page["page"]:
        invalid()
    geometry = witness["geometry_pages"][str(group["page"])]
    table = geometry["tables"][group["table"]]
    column = group["column"]
    if column < 1:
        invalid()
    def cell(row, col):
        return next((c for cells in table["rows"] for c in cells if c["row"] == row and c["column"] == col), None)
    header, caption = cell(0, column), cell(0, 0)
    if header is None or caption is None or group["header"] != header or group["caption"] != caption:
        invalid()
    title_cells = [c for row in geometry["tables"][0]["rows"] for c in row if c["text"].strip()]
    if group["title_cells"] != title_cells:
        invalid()
    match = re.fullmatch(r"HPTCBB\s+(\d+)\s+\(\d+TC\)", header["text"])
    language = "vi"
    if match is None:
        match = re.fullmatch(r"Required Elective\s+(\d+)\s+\(\d+\s+Credits\)", header["text"], re.I)
        language = "en"
    if match is None:
        invalid()
    label = ("HPTCBB " if language == "vi" else "REQUIRED ELECTIVE ") + match[1]
    if group["label"] != label:
        invalid()
    expected_options = []
    for row in range(1, len(table["rows"])):
        value, row_label = cell(row, column), cell(row, 0)
        if value is None or row_label is None or not value["text"].strip() or not row_label["text"].strip():
            invalid()
        if (not header["bbox"][0] <= value["bbox"][0]+1 or not value["bbox"][2] <= header["bbox"][2]+1
                or not header["bbox"][3] <= value["bbox"][1]+1):
            invalid()
        expected_options.append({"row_label": row_label, "value": value})
    if not expected_options or group["options"] != expected_options:
        invalid()
    text = "\n".join(c["text"] for c in title_cells) + "\n" + caption["text"] + "\n" + header["text"]
    codes = []
    for option in expected_options:
        match = re.match(r"^(\d{6})\s*[-–—]", option["value"]["text"])
        if match is None:
            invalid()
        codes.append(match[1])
        text += "\n" + option["row_label"]["text"] + "\n" + option["value"]["text"]
    if text != block["text"]:
        invalid()
    return {"semesters": [], "relation_types": [], "course_codes": codes, "elective_group_labels": [label]}
