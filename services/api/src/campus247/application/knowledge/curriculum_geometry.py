"""Capabilities bound to reviewed original cells and visible graph endpoints."""
import re
import unicodedata

from campus247.application.conversation.followup import normalized_question
from campus247.application.knowledge.platform_models import PlatformError, digest


def assert_axis_line_binding(edge, origin, target):
    """A plain native arrow cannot cross into an orthogonal neighbour cell.

    Bent paths still require their explicit reviewed objects. This necessary
    axis/direction check supplements that review; it cannot establish a link.
    """
    objects = edge["arrow_objects"]
    shafts = [s for s in objects if min(s["x1"]-s["x0"], s["bottom"]-s["top"]) <= 2.2
        and max(s["x1"]-s["x0"], s["bottom"]-s["top"]) >= 5
        and max(s["x1"]-s["x0"], s["bottom"]-s["top"]) >= 4*min(s["x1"]-s["x0"], s["bottom"]-s["top"])]
    if len(shafts) != 1:
        return
    shaft = shafts[0]
    heads = [s for s in objects if s is not shaft]
    points = [list(dict.fromkeys(tuple(round(v, 3) for v in p) for p in s.get("pts", []))) for s in heads]
    if not heads or any(len(p) != 3 for p in points):
        return
    if len(heads) != (1 if edge["kind"] == "PREREQUISITE" else 2):
        raise PlatformError(409, "CURRICULUM_EDGE_KIND", "Số đầu mũi tên không khớp loại quan hệ được gán.")
    vertical = shaft["bottom"]-shaft["top"] > shaft["x1"]-shaft["x0"]
    axis = (shaft["x0"]+shaft["x1"])/2 if vertical else (shaft["top"]+shaft["bottom"])/2
    low, high = (0, 2) if vertical else (1, 3)
    if any(not c["bbox"][low]-1 <= axis <= c["bbox"][high]+1 for c in (origin, target)):
        raise PlatformError(409, "CURRICULUM_EDGE_AXIS", "Đường thẳng không đi trong cả hai ô được gán.")
    along_low, along_high = ("top", "bottom") if vertical else ("x0", "x1")
    start, end = min(s[along_low] for s in objects), max(s[along_high] for s in objects)
    reach = max(max(s["x1"]-s["x0"], s["bottom"]-s["top"]) for s in heads) + 1
    a, b = (1, 3) if vertical else (0, 2)
    if any(c["bbox"][b] < start-reach or c["bbox"][a] > end+reach for c in (origin, target)):
        raise PlatformError(409, "CURRICULUM_EDGE_AXIS", "Ô được gán nằm ngoài đoạn đường thẳng.")
    if edge["kind"] == "PREREQUISITE" and len(heads) == 1:
        p = points[0]
        for index, tip in enumerate(p):
            base = [v for j, v in enumerate(p) if j != index]
            perpendicular = 0 if vertical else 1
            coordinate = 1 if vertical else 0
            if abs(base[0][perpendicular]-base[1][perpendicular]) >= 3 and abs(base[0][coordinate]-base[1][coordinate]) <= .5:
                direction = tip[coordinate]-(base[0][coordinate]+base[1][coordinate])/2
                placement = (target["bbox"][a]+target["bbox"][b])-(origin["bbox"][a]+origin["bbox"][b])
                if direction*placement <= 0:
                    raise PlatformError(409, "CURRICULUM_EDGE_DIRECTION", "Chiều mũi tên không khớp thứ tự ô được gán.")
                break


def geometry_scopes(rendition, extracted):
    witness = extracted.get("curriculum_geometry")
    if witness is None:
        return None
    scope = rendition["applicability"]
    if (scope.get("kind") != "COHORT_SNAPSHOT" or witness.get("schema") != "reviewed-curriculum-geometry-v1"
            or scope.get("geometry_witness_sha256") != digest(witness)
            or witness.get("original_sha256") != rendition["original_sha256"]
            or witness.get("ambiguous_course_cells") or witness.get("reviewed") is not True):
        raise PlatformError(409, "CURRICULUM_GEOMETRY_BINDING", "Chứng cứ hình học không khớp bản nguồn đã duyệt.")
    cells = {c["id"]: c for c in witness["cells"]}
    edges = {e["id"]: e for e in witness["edges"]}
    semesters = {s["id"]: s for s in witness.get("semester_groups", [])}
    electives = {g["id"]: g for g in witness.get("elective_groups", [])}
    for cell in cells.values():
        geometry = witness["geometry_pages"][str(cell["page"])]
        table = geometry["tables"][cell["table"]]
        native = next((c for row in table["rows"] for c in row
            if c["row"] == cell["row"] and c["column"] == cell["column"]), None)
        header = cell["header"]
        native_header = next((c for row in table["rows"] for c in row
            if c["row"] == header["row"] and c["column"] == header["column"]), None)
        if (native is None or native_header != header or native["text"] != cell["text"]
                or native["bbox"] != cell["bbox"] or cell["semester_header"] != header["text"]
                or re.fullmatch(r"Học kỳ\s+" + str(cell["semester"]), header["text"]) is None
                or not header["bbox"][0] <= cell["bbox"][0]+1
                or not cell["bbox"][2] <= header["bbox"][2]+1
                or not header["bbox"][3] <= cell["bbox"][1]+1):
            raise PlatformError(409, "CURRICULUM_COLUMN_BINDING", "Ô hoặc tiêu đề học kỳ không khớp tọa độ nguồn.")
        printed_codes = re.findall(r"(?m)^(\d{6})\s*[-–—]\s*\d{1,2}(?=\s|$)", cell["text"])
        if cell["course_codes"] != printed_codes:
            raise PlatformError(409, "CURRICULUM_CODE_BINDING", "Mã học phần không khớp nội dung ô nguồn.")
    occurrences = {}
    for cell in cells.values():
        entries = list(re.finditer(r"(?m)^(\d{6})\s*[-–—]\s*(\d{1,2})(?=\s|$)", cell["text"]))
        for index, entry in enumerate(entries):
            end = entries[index+1].start() if index+1 < len(entries) else len(cell["text"])
            label = " ".join(unicodedata.normalize("NFC", cell["text"][entry.end():end]).split())
            occurrences.setdefault((cell["page"], entry[1]), set()).add((entry[2], label))
    ambiguous_codes = {code for (_, code), variants in occurrences.items() if len(variants) > 1}
    global_caps = {"semesters": [], "relation_types": [], "course_codes": [], "physical_education_labels": [],
        "elective_group_labels": [], "ambiguous_course_codes": sorted(ambiguous_codes)}
    result = {}
    blocks = {str(b["block_id"]): b for b in extracted["blocks"]}
    for page in rendition["pages"]:
        block = blocks[str(page["block_id"])]
        binding = block.get("geometry_binding", {})
        kind, identifier = binding.get("kind"), binding.get("id")
        caps = {"semesters": [], "relation_types": [], "course_codes": []}
        if kind == "cell":
            cell = cells.get(identifier)
            if cell is None:
                raise PlatformError(409, "CURRICULUM_CELL_BINDING", "Ô không thuộc chứng cứ đã duyệt.")
            expected = witness["programme_code"] + "\n" + cell["semester_header"] + "\n" + cell["text"]
            if witness.get("include_printed_unit_context"):
                expected += "\n" + witness["printed_total"]
            if page["page"] != cell["page"] or block["text"] != expected or digest(cell["text"].encode()) != cell["text_sha256"]:
                raise PlatformError(409, "CURRICULUM_CELL_BINDING", "Nội dung ô hoặc cột học kỳ không khớp.")
            caps = {"semesters": [cell["semester"]], "relation_types": [],
                "course_codes": cell["course_codes"], "unlabelled_credits": cell.get("unlabelled_credits", False)}
        elif kind == "semester":
            group = semesters.get(identifier)
            expected_cells = [c for c in cells.values() if group and c["semester"] == group["semester"]]
            if not group or group["cell_ids"] != [c["id"] for c in expected_cells] or not expected_cells:
                raise PlatformError(409, "CURRICULUM_SEMESTER_BINDING", "Danh sách học kỳ phải giữ đủ các ô đã duyệt theo thứ tự.")
            expected = witness["programme_code"] + "\n" + expected_cells[0]["semester_header"] + "\n"
            expected += "\n\n".join(c["text"] for c in expected_cells) + "\n" + witness["printed_total"]
            if block["text"] != expected or page["page"] != expected_cells[0]["page"]:
                raise PlatformError(409, "CURRICULUM_SEMESTER_BINDING", "Đoạn học kỳ không khớp toàn bộ ô nguồn.")
            caps = {"semesters": [group["semester"]], "relation_types": [],
                "course_codes": [code for c in expected_cells for code in c["course_codes"]],
                "unlabelled_credit_names": [c["text"] for c in expected_cells if c.get("unlabelled_credits")]}
        elif kind == "edge":
            edge = edges.get(identifier)
            if edge is None or edge["kind"] not in {"PREREQUISITE", "COREQUISITE"}:
                raise PlatformError(409, "CURRICULUM_EDGE_BINDING", "Đường nối chưa được xác minh.")
            origin, target = cells.get(edge["from_cell"]), cells.get(edge["to_cell"])
            if not origin or not target or not edge.get("arrow_objects") or edge.get("legend_verified") is not True:
                raise PlatformError(409, "CURRICULUM_EDGE_BINDING", "Thiếu ô đầu/cuối, mũi tên hoặc chú giải.")
            native_shapes = {s["object_index"]: s for s in witness["geometry_pages"][str(edge["page"])]["shapes"]}
            if any(native_shapes.get(s["object_index"]) != s for s in edge["arrow_objects"]):
                raise PlatformError(409, "CURRICULUM_EDGE_BINDING", "Hình học đường nối không khớp nguồn.")
            assert_axis_line_binding(edge, origin, target)
            label, symbol = ("Học phần tiên quyết", "→") if edge["kind"] == "PREREQUISITE" else ("Học phần song hành", "↔")
            expected = witness["programme_code"] + "\n" + label + ":\n" + origin["text"] + "\n" + symbol + "\n" + target["text"]
            if block["text"] != expected or page["page"] != edge["page"]:
                raise PlatformError(409, "CURRICULUM_EDGE_BINDING", "Đoạn quan hệ không khớp đường nối và chiều đã duyệt.")
            caps = {"semesters": [], "relation_types": [edge["kind"]],
                "course_codes": origin["course_codes"] + target["course_codes"]}
        elif kind == "elective":
            from campus247.application.knowledge.curriculum_elective_geometry import elective_scope
            caps = elective_scope(witness, electives.get(identifier), block, page)
        elif kind == "total":
            if block["text"] != witness["programme_code"] + "\n" + witness["printed_total"]:
                raise PlatformError(409, "CURRICULUM_TOTAL_BINDING", "Dòng tổng không khớp nguồn in sẵn.")
        else:
            raise PlatformError(409, "CURRICULUM_BLOCK_BINDING", "Đoạn hình học phải có loại chứng cứ rõ ràng.")
        named_cells = [cell] if kind == "cell" else expected_cells if kind == "semester" else []
        caps["physical_education_labels"] = sorted({int(number) for value in named_cells
            for number in re.findall(r"\b(?:giao duc|gd)\s+the chat\s+([1-3])\b", normalized_question(value["text"]))})
        caps.setdefault("elective_group_labels", [])
        caps["evidence_kind"] = kind
        caps["ambiguous_course_codes"] = sorted(ambiguous_codes.intersection(caps["course_codes"]))
        result[page["text_sha256"]] = caps
        for field in global_caps:
            global_caps[field] = sorted(set(global_caps[field] + caps.get(field, [])))
        if "unlabelled_credit_names" in caps:
            global_caps.setdefault("unlabelled_credit_names", [])
            global_caps["unlabelled_credit_names"] = sorted(set(global_caps["unlabelled_credit_names"] + caps["unlabelled_credit_names"]))
    return global_caps, result


def geometry_allows(question, caps):
    text = normalized_question(question)
    groups = set(re.findall(r"\b(?:hptcbb|required elective)\s+\d+\b", text))
    if groups and not groups.issubset(normalized_question(label) for label in caps.get("elective_group_labels", [])):
        return False
    physical = {int(number) for number in re.findall(r"\b(?:giao duc|gd)\s+the chat\s+([1-3])\b", text)}
    if physical and not physical.issubset(caps.get("physical_education_labels", [])):
        return False
    if re.search(r"\b(?:phai|can)\s+chon\s+(?:may|bao nhieu|\d+)\s*(?:mon|hoc phan)?|\bchon\s+(?:may|bao nhieu)\s+(?:mon|hoc phan)", text):
        return False  # A visible elective list does not prove its selection requirement.
    relations = set()
    if "tien quyet" in text:
        relations.add("PREREQUISITE")
    if "song hanh" in text:
        relations.add("COREQUISITE")
    if re.search(r"hoc truoc|dieu kien (?:de )?hoc", text):
        return False
    if relations and not relations.issubset(caps.get("relation_types", [])):
        return False
    semesters = {int(n) for n in re.findall(r"(?:hoc ky\s*(?:thu\s+)?|\bhk\s*)(\d+)\b", text)}
    if re.search(r"(?:hoc ky\s*(?:thu\s+)?|\bhk\s*)[ivx]+\b", text):
        return False  # Roman labels require their own explicit verified mapping.
    if semesters and not semesters.issubset(caps.get("semesters", [])):
        return False
    codes = set(re.findall(r"\b\d{6}\b", text))
    if caps.get("evidence_kind") == "cell" and semesters and not codes:
        group_lookup = "tu chon" in text and re.search(r"\b(?:nhom|phan|muc)\b", text) and not re.search(r"tat ca|toan bo", text)
        if not group_lookup and re.search(r"hoc phan|\bmon\b|hoc nhung|\bgom\b|danh sach", text):
            return False  # One course/elective cell cannot prove a complete semester roster.
    if codes.intersection(caps.get("ambiguous_course_codes", [])):
        return False  # Preserve printed variants without resolving a unique code/name association.
    if codes and not codes.issubset(caps.get("course_codes", [])):
        return False
    if caps.get("elective_group_labels") and codes and re.search(r"tin chi|\btc\b|\bcredits?\b", text):
        return False  # A catalogue group's credit does not prove each option's credit.
    if caps.get("unlabelled_credits") and re.search(r"tin chi|\btc\b", text):
        return False
    if re.search(r"tin chi|\btc\b", text) and any(needle in text and any(needle in normalized_question(name)
            for name in caps.get("unlabelled_credit_names", [])) for needle in ("the chat", "quoc phong")):
        return False
    return True
