"""Small explicitly authored source map. All emitted relations are candidates."""
from datetime import datetime, timezone

from campus247.domain.policy_graph import GraphProposal, GraphScope, PolicyEdge, PolicyNode, SourceRef, source_fingerprint


def authored_public_proposal(corpus, *, graph_id, index_fingerprint):
    scope = GraphScope(tenant_id=corpus.tenant_id, campus_id=corpus.campus_id,
        audiences=("STUDENT",), faculties=("PUBLIC",), programs=("PUBLIC",))
    rows = corpus.rows
    page = lambda n: next(r for r in rows if r["page_start"] == n and "Sổ tay" in r["title"])
    article = lambda n: next(r for r in rows if r["section_path"].startswith(f"Điều {n}."))
    nodes, edges = [], []

    def ref(row, quote=None):
        quote = quote or row["content_text"]
        if quote not in row["content_text"]:
            raise ValueError("authored span is absent from retained original")
        return SourceRef(source_id=row["source_id"], document_version_id=row["document_version_id"],
            chunk_id=row["chunk_id"], content_sha256=row["quote_span_hash"], locator=row["locator"], quote=quote)

    def node(key, kind, label, row, quote=None, **kwargs):
        nodes.append(PolicyNode(id=key, kind=kind, label=label, scope=scope, source=ref(row, quote), **kwargs))
        return key

    def edge(left, relation, right, row, quote=None):
        key = f"edge-{len(edges)+1:03d}"
        edges.append(PolicyEdge(id=key, from_id=left, to_id=right, relation=relation, scope=scope, source=ref(row, quote)))

    p35, p39, p61, a13, a15 = page(35), page(39), page(61), article(13), article(15)
    for key, row in (("handbook-catalog", p35), ("certificate-clause", p39), ("appeal-clause", p61),
                     ("graduation-clause", a13), ("transfer-clause", a15)):
        node(key, "Clause", row["section_path"] + " — " + key, row)
    node("certificate-process", "Procedure", "Quy trình xác nhận sinh viên/cựu sinh viên", p39,
        p39["content_text"].split("3. Quy trình")[0].strip(), aliases=("quy trình xác nhận", "nhận giấy xác nhận"))
    edge("certificate-process", "defined_by", "certificate-clause", p39, nodes[-1].source.quote)
    node("certificate-form", "Form", "Mẫu xác nhận được chọn trên dịch vụ một cửa", p39,
        "-Chọn mục dịch vụ và mẫu xác nhận rồi gửi yêu cầu", qualifiers=("Mã/phiên bản mẫu chi tiết chưa được nguồn xác minh",))
    edge("certificate-process", "requires", "certificate-form", p39, nodes[-1].source.quote)
    node("ctct-qlsv", "OrganizationUnit", "Phòng CTCT & QLSV", p39,
        "-Sinh viên/Cựu sinh viên nhận lại giấy xác nhận tại\nCỰU SINH VIÊN TRẢ KẾT QUẢ phòng CTCT & QLSV (tầng 2, tòa nhà TT hỗ trợ SV)\nCV PHỤ TRÁCH theo lịch hẹn đã gửi",
        aliases=("phòng công tác chính trị và quản lý sinh viên",))
    edge("certificate-process", "handled_by", "ctct-qlsv", p39, nodes[-1].source.quote)
    node("student-and-alumni", "Audience", "Sinh viên/Cựu sinh viên", p39,
        "-Sinh viên/Cựu sinh viên đăng nhập vào trang\nSINH VIÊN ĐĂNG KÝ XÁC NHẬN motcua.huce.edu.vn")
    edge("certificate-process", "applies_to", "student-and-alumni", p39, nodes[-1].source.quote)
    for key, label, alias, quote in (
        ("student-certificate", "Đăng ký xác nhận sinh viên", "giấy xác nhận sinh viên",
         "ĐĂNG KÝ Dùng để nộp cho cơ quan, ngân hàng,\nXÁC NHẬN SINH VIÊN địa phương xác nhận đang học tại trường"),
        ("alumni-program-certificate", "Xác nhận ngành đào tạo", "xác nhận ngành đào tạo",
         "XÁC NHẬN NGÀNH ĐÀO TẠO Làm rõ chuyên ngành,\nđịnh hướng học tập")):
        node(key, "Procedure", label, p35, quote, aliases=(alias,))
        edge(key, "defined_by", "handbook-catalog", p35, quote)
        # Page 39 explicitly includes both students and former students.
        edge(key, "defined_by", "certificate-clause", p39, nodes[5].source.quote)

    node("appeal", "Procedure", "Phúc khảo điểm thi kết thúc học phần", p61,
        "QUY TRÌNH PHÚC KHẢO ĐIỂM THI\nKẾT THÚC HỌC PHẦN", aliases=("phúc khảo",))
    edge("appeal", "defined_by", "appeal-clause", p61)
    node("appeal-fee", "Condition", "Đóng lệ phí phúc khảo trực tuyến", p61,
        "Đóng lệ phí phúc khảo trực tuyến\nqua tài khoản ngân hàng", qualifiers=("Không có mức tiền được xác minh",))
    edge("appeal", "requires", "appeal-fee", p61, nodes[-1].source.quote)
    # The page's multi-column OCR interleaves lines. Keep the complete original
    # as the exception span; do not manufacture a joined quotation or a deadline.
    node("appeal-exception", "Exception", "Ngoại lệ hình thức vấn đáp, thực hành — cần đọc sơ đồ gốc", p61,
        qualifiers=("Bố cục OCR nhiều cột; không dùng để thực thi rule",))
    edge("appeal", "has_exception", "appeal-exception", p61)

    text = a15["content_text"]
    group_quote = text[text.index("1. Sinh viên"):text.index("2. Sinh viên")].strip()
    import re
    members = [m.group().strip() for m in re.finditer(r"(?ms)^[a-d]\).*?(?=^[a-d]\)|\Z)", group_quote)]
    if len(members) != 4:
        raise ValueError("full transfer ALL group required")
    node("transfer", "Procedure", "Chuyển chương trình, ngành hoặc phân hiệu", a15, group_quote,
        aliases=("chuyển ngành", "chuyển chương trình"))
    edge("transfer", "defined_by", "transfer-clause", a15, group_quote)
    member_ids = tuple(f"transfer-condition-{i+1}" for i in range(4))
    node("transfer-all", "ConditionGroup", "Đủ cả bốn điều kiện chuyển ngành", a15, group_quote,
        operator="ALL", members=member_ids)
    edge("transfer", "requires", "transfer-all", a15, group_quote)
    for key, quote in zip(member_ids, members):
        node(key, "Condition", "Điều kiện chuyển ngành " + key[-1], a15, quote)
        edge("transfer-all", "requires", key, a15, quote)

    text = a13["content_text"]
    any_quote = text[text.index("3. Hạng tốt nghiệp"):text.index("4. Sinh viên")].strip()
    members = [m.group().strip() for m in re.finditer(r"(?ms)^[ab]\).*?(?=^[ab]\)|\Z)", any_quote)]
    if len(members) != 2:
        raise ValueError("full graduation ANY group required")
    node("graduation-grade", "Procedure", "Xếp hạng tốt nghiệp", a13, any_quote,
        aliases=("xếp loại tốt nghiệp", "hạng tốt nghiệp"))
    edge("graduation-grade", "defined_by", "graduation-clause", a13, any_quote)
    node("grade-reduction", "Exception", "Giảm một mức hạng xuất sắc hoặc giỏi", a13, any_quote)
    edge("graduation-grade", "has_exception", "grade-reduction", a13, any_quote)
    node("grade-any", "ConditionGroup", "Một trong hai trường hợp giảm hạng", a13, any_quote,
        operator="ANY", members=("grade-repeat", "grade-discipline"))
    edge("grade-reduction", "requires", "grade-any", a13, any_quote)
    for key, quote in zip(("grade-repeat", "grade-discipline"), members):
        node(key, "Condition", "Học lại vượt 5% số tín chỉ" if key == "grade-repeat" else "Kỷ luật từ cảnh cáo", a13, quote)
        edge("grade-any", "requires", key, a13, quote)
    return GraphProposal(id=graph_id, author="authored-public-source-mapper-v1", origin="manual_candidate",
        acquired_at=datetime(2026, 10, 13, tzinfo=timezone.utc), index_fingerprint=index_fingerprint,
        source_fingerprint=source_fingerprint(rows), nodes=tuple(nodes), edges=tuple(edges))
