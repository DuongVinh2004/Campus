from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.evidence_gate import GroundedClaim, GroundedDraft
from campus247.application.retrieval.procedure_scope import procedure_scope_issues, requested_procedure_names

SOURCE = ("2. Quy trình xác nhận sinh viên\nSinh viên đăng nhập Một cửa rồi gửi yêu cầu.\n"
          "3. Quy trình xin nghỉ học tạm thời\nSinh viên làm đơn phải có chữ ký của phụ huynh.\n")
QUESTION = "Giấy xác nhận sinh viên có buộc chữ ký phụ huynh giống nghỉ học tạm thời không?"


def check(text, question=QUESTION):
    bundle = CitationBundle.build([{"content_text": SOURCE}])
    claim = GroundedClaim("CLM-001", text, ("CIT-001",), "procedure")
    return procedure_scope_issues(question, GroundedDraft(text, (claim,)), bundle, .78)


def test_generic_or_wrongly_named_condition_cannot_cross_procedure_boundary():
    assert check("Sinh viên làm đơn phải có chữ ký của phụ huynh.") == {"CLM-001": "MISSING_PROCEDURE_SCOPE"}
    assert check("Xác nhận sinh viên làm đơn phải có chữ ký của phụ huynh.") == {"CLM-001": "MISBOUND_PROCEDURE_SCOPE"}


def test_explicit_original_scope_and_single_procedure_questions_remain_usable():
    assert check("Nghỉ học tạm thời: sinh viên làm đơn phải có chữ ký của phụ huynh.") == {}
    assert check("Sinh viên đăng nhập Một cửa rồi gửi yêu cầu.", "Xin xác nhận sinh viên bắt đầu thế nào?") == {}


def test_requested_names_are_original_source_headings_only():
    bundle = CitationBundle.build([{"content_text": SOURCE}])
    assert requested_procedure_names(QUESTION, bundle) == ["Quy trình xin nghỉ học tạm thời", "Quy trình xác nhận sinh viên"]
    assert requested_procedure_names("Xin xác nhận sinh viên, hoàn tiền học phí?", bundle) == ["Quy trình xác nhận sinh viên"]
    assert requested_procedure_names("Thủ tục không có trong nguồn?", bundle) == []
