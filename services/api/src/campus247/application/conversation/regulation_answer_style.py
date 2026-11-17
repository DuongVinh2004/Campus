"""Source-faithful presentation guidance, without supplying policy answers."""
import re

from campus247.application.conversation.followup import normalized_question


def regulation_answer_style(question):
    if not re.search(r"\bquy che\s+\d+\b", normalized_question(question)):
        return None
    return (
        "Với quy chế được nêu số, giữ câu dẫn xác định đúng đối tượng và quan hệ điều kiện của danh sách. "
        "Giữ nguyên và, hoặc, một trong, có đủ, các điều kiện khác; không biến điều kiện cần thành đủ. "
        "Có thể ghép câu dẫn với các mục liên quan trong cùng một claim; không thêm đối tượng hay thuật ngữ ngoài nguồn. "
        "Khi hỏi một nhánh trong danh sách, giữ các điều kiện và ngoại lệ gắn với nhánh đó, không liệt kê nhánh không được hỏi. "
        "Nếu có từ kỷ luật, dùng claim_type policy và giữ câu dẫn chung cùng các điều kiện liên quan trong một claim; "
        "không tách một mục thành khẳng định độc lập rằng sinh viên đã bị kỷ luật. "
        "Chép đúng chủ ngữ từ nguồn, kể cả Hạng tốt nghiệp; không thêm từ Điều kiện nếu nguồn không có từ đó. "
        "Với bảng điểm chữ, dùng nhãn và khoảng nguyên văn như trong từng dòng nguồn, giữ dấu cộng và từ chỉ cận; "
        "không thêm lời dẫn Điểm chữ, nằm trong khoảng hoặc đơn vị không được in ở dòng. "
        "Chỉ nội dung nguồn xác minh được mới nằm trong claims; giữ nguyên output contract và citation_ids."
    )
