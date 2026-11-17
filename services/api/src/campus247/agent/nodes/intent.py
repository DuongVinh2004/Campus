from __future__ import annotations

import dataclasses
import re
import unicodedata
from campus247.agent.state import AgentState, Route, SafetySeverity


def is_personal_schedule_request(query: str) -> bool:
    from campus247.application.conversation.followup import normalized_question
    text = normalized_question(query)
    owner = bool(re.search(r"\b(?:cua (?:toi|em|minh)|cho (?:toi|em) xem|(?:toi|em|minh) (?:phai |se )?(?:hoc|thi))\b", text))
    schedule = any(topic in text for topic in ("lich hoc", "lich thi", "thoi khoa bieu"))
    owner = owner or (schedule
        and bool(re.search(r"\b(?:hom nay|ngay mai|tuan nay|tuan sau)\b", text))
        and bool(re.search(r"\b(?:nhung mon|mon nao|phong nao|tiet nao|may gio)\b", text)))
    # A personal room/time lookup may never mention the word 'schedule'. It
    # still needs the personal API, rather than a public-document search.
    slot = bool(re.search(r"\b(?:hoc|thi)\b.{0,50}\b(?:phong nao|phong may|o dau|luc nao|may gio|tiet nao)\b", text))
    return (owner and (schedule or slot)
            and not any(marker in text for marker in ("quy dinh", "thu tuc", "huong dan", "quy che")))


def is_information_request(query: str) -> bool:
    """Procedure questions are reads, even when they mention a write capability."""
    text = "".join(c for c in unicodedata.normalize("NFD", query.lower())
                   if unicodedata.category(c) != "Mn").replace("đ", "d")
    text = re.sub(r"\s+", " ", text).strip()
    return any(marker in text for marker in (
        "thu tuc", "quy trinh", "quy che", "quy dinh", "dieu kien", "huong dan",
        "cach ", "nhu the nao", "lam sao", "o dau", "bao lau", "bao nhieu",
        "can gi", "can nhung", "giay to", "ho so", "tra cuu", "cho minh hoi",
        "cho em hoi", "minh muon hoi", "toi muon hoi", "xin hoi", "?",
    ))


def is_human_handover_request(query: str) -> bool:
    from campus247.application.conversation.followup import normalized_question
    text = normalized_question(query)
    return any(marker in text for marker in (
        "gap can bo", "gap tu van vien", "chuyen nguoi truc", "gap nguoi ho tro",
        "gap nguoi", "can bo truc tiep", "lien he nhan vien", "chuyen cho chuyen vien",
    ))


def is_other_person_data_request(query: str) -> bool:
    from campus247.application.conversation.followup import normalized_question
    text = normalized_question(query)
    private = bool(re.search(r"\b(?:bang diem|diem trung binh|diem thi|ho so (?:ca nhan|ky luat|cua)|bi ky luat|"
                             r"ky luat canh cao|lich su ky luat|so dien thoai|dia chi nha)\b", text))
    other = bool(re.search(r"\b(?:sinh vien (?:khac|ma|co ma|ten)|ban (?:em|toi|minh)|"
                           r"thay|co giao|giang vien|chu nhiem|nguoi khac)\b", text)
                 or re.search(r"\b(?i:bạn|ban|sinh viên|sinh vien)\s+[A-ZĐ][a-zà-ỹ]+\s+[A-ZĐ][a-zà-ỹ]+", query))
    # General rules about who may read a record do not disclose that record.
    general = any(marker in text for marker in ("quy dinh", "quy che", "thu tuc", "dieu kien"))
    lookup = bool(re.search(r"\b(?:xem|tra cuu|cho biet|cung cap)\b.{0,50}\b(?:bang diem|ho so|diem thi)\b|"
                            r"\b(?:sinh vien (?:ma|co ma|ten)|bi ky luat (?:vi|bao))\b", text))
    return private and other and (not general or lookup)


class IntentRouterNode:
    """Classifies user intent into a validated route with safety override."""

    def route(self, state: AgentState) -> AgentState:
        # Safety priority: if critical, high crisis or safety trigger, force sensitive case
        if state.safety.is_crisis or state.safety.severity in (
            SafetySeverity.CRITICAL,
            SafetySeverity.HIGH,
        ):
            return dataclasses.replace(state, route=Route.SENSITIVE_CASE)

        query = state.request.query.lower().strip()

        # Keyword-based deterministic classification
        if any(kw in query for kw in ["tự tử", "tự sát", "muốn chết", "ngất xỉu", "co giật", "khong muon song", "đập nó", "chẳng thiết sống", "tỉnh lẻ", "server trường", "tâm lý nhạy cảm", "trực bàn tuyển sinh", "vác dao", "xử đẹp", "nhảy từ tầng thượng", "chẳng còn mặt mũi"]):
            chosen = Route.SENSITIVE_CASE
        elif any(kw in query for kw in ["sql_query", "quản trị viên", "cuộc trò chuyện của user khác", "user khác", "chain-of-thought", "prompt ẩn", "canary", "thời tiết", "nấu", "phở", "món ăn", "không liên quan"]):
            chosen = Route.UNSUPPORTED
        elif is_personal_schedule_request(query):
            chosen = Route.PERSONAL_SCHEDULE
        elif is_human_handover_request(query):
            chosen = Route.HUMAN_HANDOVER
        elif is_information_request(query):
            chosen = Route.GROUNDED_FAQ
        elif any(kw in query for kw in ["khiếu nại", "phản ánh", "báo cáo sự cố", "ticket"]):
            chosen = Route.TICKET_CREATE
        elif any(kw in query for kw in ["gặp cán bộ", "tư vấn viên", "chuyển người trực", "gặp người", "cán bộ trực tiếp", "phòng đào tạo làm ăn", "nhìn ngon quá", "đòi tiền sinh viên", "dạy quá tệ", "học phí tăng vô lý", "bóc phốt", "dìm chết", "chạy điểm", "tố cáo chính thức", "dạy dốt", "đồ lừa đảo"]):
            chosen = Route.HUMAN_HANDOVER
        elif any(kw in query for kw in ["mượn phòng", "đặt phòng", "giảng đường", "tìm phòng", "phòng còn trống", "hết thời gian chờ", "xác nhận đúng nội dung xem trước đặt phòng"]):
            chosen = Route.ROOM_BOOKING
        elif any(kw in query for kw in ["hồ sơ xin", "cần những mục nào", "bao nhiêu ngày làm việc", "thời điểm", "khoảng thời gian nào", "khi nào", "thời gian giải quyết", "quy trình xin", "điều kiện xin"]):
            chosen = Route.GROUNDED_FAQ
        elif any(kw in query for kw in ["tạo yêu cầu", "xin cấp", "đăng ký cấp", "giấy giới thiệu", "bảng điểm", "giấy xác nhận", "giấy chứng nhận", "hoãn nghĩa vụ", "vay vốn"]) and "nhân tạo" not in query:
            chosen = Route.DOCUMENT_REQUEST
        elif any(kw in query for kw in ["thời khóa biểu", "lịch học", "lịch thi", "tiết học", "xem lịch", "lịch của sinh viên"]):
            chosen = Route.PERSONAL_SCHEDULE
        elif any(
            kw in query
            for kw in [
                "học phí",
                "quy chế",
                "tín chỉ",
                "học bổng",
                "cảnh báo học tập",
                "điều kiện",
                "hướng dẫn",
            ]
        ):
            chosen = Route.GROUNDED_FAQ
        else:
            # Default to Grounded FAQ for general queries, or unsupported
            chosen = Route.GROUNDED_FAQ

        return dataclasses.replace(state, route=chosen)
