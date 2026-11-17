"""Distinguish verified facts from an unanswered outcome or procedure relation."""
from campus247.application.conversation.followup import normalized_question
from campus247.application.retrieval.procedure_scope import sections


def requires_loan_outcome(question):
    text = normalized_question(question)
    return "vay" in text.split() and any(marker in text for marker in (
        "chac chan", "duyet", "bao dam", "du dieu kien", "du de vay", "du de duoc vay"))


def loan_outcome_unanswered(question, draft):
    if not requires_loan_outcome(question):
        return False
    body = normalized_question(" ".join(claim.text for claim in draft.claims))
    return not any(marker in body for marker in (
        "chac chan", "duyet", "bao dam", "du dieu kien", "du de vay", "du de duoc vay"))


def relation_partial_note(current_request, resolved_question, draft, bundle):
    body = normalized_question(" ".join(claim.text for claim in draft.claims))
    if requires_loan_outcome(current_request) and (
            "vay" in body.split() or ("ngan hang" in body and "giay" in body)):
        return ("Nguồn hiện có chỉ hỗ trợ phần giấy tờ hoặc thủ tục đã nêu. "
                "Tôi chưa xác minh được điều kiện đủ hoặc kết quả xét duyệt vay; "
                "bạn cần hỏi đơn vị tiếp nhận hồ sơ vay để kiểm tra trường hợp của mình.")
    question = normalized_question(resolved_question)
    named = {name for record in bundle.citations.values()
             for name in sections(record.content_text) if name in question}
    if len(named) >= 2:
        return ("Tôi chỉ xác minh được các bước của từng quy trình đã nêu. Nguồn hiện có chưa đủ để "
                "kết luận một điều kiện của quy trình này cũng bắt buộc hoặc được miễn ở quy trình kia. "
                "Bạn cần kiểm tra đúng biểu mẫu và đơn vị tiếp nhận; không tự chuyển điều kiện giữa hai quy trình.")
    return None
