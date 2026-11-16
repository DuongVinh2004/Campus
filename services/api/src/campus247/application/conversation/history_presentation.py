"""A safe source-opening alternative when the existing history policy rejects text."""
from dataclasses import replace

from campus247.agent.state import AgentState, Route, Terminal
from campus247.application.retrieval.citations import CitationBundle
from campus247.application.retrieval.public_notice_contacts import is_pinned_public_notice, public_notice_contact_redactor


def history_policy_alternative(state, result):
    text = "Nội dung này chưa thể hiển thị trong cuộc trò chuyện theo quy tắc lưu lịch sử hiện tại. Bạn có thể mở tài liệu gốc hoặc gửi yêu cầu hỗ trợ."
    if (isinstance(state, AgentState) and state.route == Route.GROUNDED_FAQ and state.terminal == Terminal.ANSWERED
            and state.draft and state.draft.is_grounded and state.draft.gate_decision == "grounded"
            and state.tool_flow and result.response_class == "grounded_answer"):
        bundle = CitationBundle.build(state.tool_flow.candidates)
        redact = public_notice_contact_redactor(bundle)
        contacts = [r for r in bundle.citations.values() if is_pinned_public_notice(r) and redact(r.content_text) != r.content_text]
        if len(contacts) == 1:
            record = contacts[0]
            location = f" ở trang {record.page_start}" if type(record.page_start) is int and record.page_start > 0 else ""
            text = f"Bạn có thể xem số điện thoại/email liên hệ{location} trong [thông báo HUCE gốc]({record.publication.publisher_uri})."
    return replace(result, status="abstained", response_class="safe_refusal", content=text, citations=())
