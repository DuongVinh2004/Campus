"""Presentation guidance for software instructions; no answers or source facts."""
from campus247.application.conversation.followup import normalized_question


def software_answer_style(question):
    text = normalized_question(question)
    if not (any(word in text for word in ("office", "microsoft", "phan mem"))
            and any(word in text for word in ("tai", "cai dat", "cach", "nhu the nao"))):
        return None
    return ("Với hướng dẫn phần mềm, giữ nguyên tên nút/menu bằng ngôn ngữ nguồn, "
        "không thay nhãn nút bằng lời diễn giải. Trình bày mỗi bước cần thiết trong một claim ngắn, "
        "ưu tiên từ ngữ của bước tương ứng trong nguồn; không thêm chủ ngữ, lý do hoặc hướng dẫn ngoài nguồn. "
        "Giữ output contract, giới hạn claims và citation_ids; tên miền không kèm giao thức.")
