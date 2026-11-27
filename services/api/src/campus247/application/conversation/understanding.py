"""Server-authored conversational responses; user goals never grant authority."""
import re
from dataclasses import dataclass

from campus247.application.conversation.followup import (
    is_followup_question,
    normalized_question,
    prepare_followup_question,
    question_topics,
)

_CALENDAR_YEAR = re.compile(r"(?<![0-9])[1-9][0-9]{3}(?![0-9])")
_DATE_REQUEST = re.compile(
    r"\b(?:ngay nao|bao gio|khi nao|bat dau|ket thuc|dien ra|tu ngay|den ngay|"
    r"thoi gian|thang nao|tuan nao|ngay cu the|ngay chinh xac)\b")


@dataclass(frozen=True)
class DatedCalendarRequest:
    years: frozenset[str]
    event: str
    source_terms: tuple[str, ...]

    def matches_source_span(self, content: str) -> bool:
        text = " " + normalized_question(content) + " "
        return bool(self.years & set(_CALENDAR_YEAR.findall(text)) and any(
            " " + term + " " in text for term in self.source_terms))


def dated_calendar_request(question: str) -> DatedCalendarRequest | None:
    """Only explicit dated event reads constrain source years.

    Retrieval continuity puts prior user goals on earlier lines. Inspect the
    current request line, excluding server-added term expansion, so a year in
    passive history cannot restrict an unrelated general policy question.
    """
    current = question.split("\nThuật ngữ tra cứu:", 1)[0].rsplit("\n", 1)[-1]
    text = " " + normalized_question(current) + " "
    years = frozenset(_CALENDAR_YEAR.findall(text))
    if not years or not _DATE_REQUEST.search(text):
        return None
    if " tet " in text and (" nghi " in text or " lich " in text):
        return DatedCalendarRequest(years, "tet", ("tet",))
    for event, query_terms, source_terms in (
        ("exam", ("lich thi", "lich kiem tra", "ky thi", "thi hoc ky", "thi ket thuc hoc phan"),
         ("thi", "kiem tra")),
        ("classes", ("lich hoc", "lich giang day"), ("lich hoc", "ke hoach hoc tap", "ke hoach giang day")),
        ("summer_break", ("nghi he",), ("nghi he",)),
        ("opening", ("khai giang",), ("khai giang",)),
    ):
        if any(" " + term + " " in text for term in query_terms):
            return DatedCalendarRequest(years, event, source_terms)
    return None


# Words that carry no searchable subject: question words, politeness, pronouns and generic nouns.
_NO_SUBJECT = frozenset((
    "la gi nao the sao ai dau o bao nhieu may khi luc co khong duoc ko chua nhe a da di voi oi vay thi va "
    "cua ve cho toi em minh ban anh chi thay xin hoi biet giup can muon hay nay do kia cai viec chuyen lam "
    "nhu mot nhung cac rat qua chut nua roi se phai nen tu den vi tai bi ma neu thu tuc quy dinh thong tin "
    "van de huong dan noi dung truong huce sinh vien nha").split())
# Single words that name no topic by themselves (điểm what? thi what?).
_NEEDS_QUALIFIER = frozenset(("diem", "thi", "hoc", "phi", "lop", "mon"))
UNDERSPECIFIED_RESPONSE = (
    "Câu hỏi chưa nêu rõ nội dung cần tra cứu. Bạn muốn hỏi về chủ đề nào, ví dụ: học phí, học bổng, "
    "đăng ký hoặc rút học phần, bảo lưu và nghỉ học tạm thời, thôi học, tốt nghiệp, ký túc xá hay thư viện? "
    "Nếu có chương trình, khóa hoặc năm học cụ thể, bạn cho biết thêm để tôi tra đúng nguồn.")


# A question with this many words of its own subject is self-contained even when it opens like a follow-up ("Nếu em bị ốm xuống
# Trạm Y tế trường khám thì có phải xuất trình thẻ BHYT không?"): asking which topic it continues would be wrong.
SELF_CONTAINED_WORDS = 6


def subject_words(question: str) -> list[str]:
    return [word for word in normalized_question(question).split() if word not in _NO_SUBJECT]


def underspecified_question(question: str) -> bool:
    """No subject left after removing question words and generic nouns (digits and codes count)."""
    subject = [word for word in normalized_question(question).split() if word not in _NO_SUBJECT]
    return not subject or (len(subject) == 1 and subject[0] in _NEEDS_QUALIFIER)


def conversational_response(question: str, history=None) -> str | None:
    text = normalized_question(question)
    if (any(marker in text for marker in ("khong nho", "quen", "khong biet"))
            and any(marker in text for marker in ("ma sinh vien", "mssv"))
            and "xac nhan" in text):
        return ("Tôi không thể tự suy ra mã sinh viên. Bạn cần liên hệ đơn vị quản lý sinh viên "
                "để được hỗ trợ xác minh thông tin. Khi đã có thông tin cần thiết, mở phần chuẩn bị hồ sơ "
                "để điền, xem trước và xác nhận gửi; tôi chưa tạo hoặc gửi hồ sơ từ câu hỏi này.")
    if ("dang hoc" in text and "tot nghiep" in text
            and any(phrase in text for phrase in ("cung mau", "cung loai"))
            and any(phrase in text for phrase in ("deu xin", "cung xin", "chon mau", "mac dinh"))):
        return ("Bạn cho biết mục đích xin giấy của từng người và người đã tốt nghiệp có đăng ký "
                "học một chương trình hiện tại khác không? Tôi cần phân biệt từng trường hợp trước khi chọn mẫu.")
    if text in {"xin chao", "chao", "hello", "hi", "ban giup duoc gi", "ban lam duoc gi",
                "ban co the giup gi", "ban co the lam gi", "ban la ai", "gioi thieu", "help"}:
        return ("Tôi là trợ lý Campus 24/7. Tôi có thể tra cứu tài liệu HUCE về học bổng, "
                "học phí, quy chế học tập, thủ tục sinh viên và thư viện, kèm nguồn để bạn kiểm tra. "
                "Bạn có thể hỏi tiếp để bổ sung điều kiện. Lịch học cá nhân cần phiên đăng nhập "
                "và kết nối dữ liệu được cấp quyền; yêu cầu ghi cần xem trước và xác nhận. "
                "Bạn muốn tìm hiểu nội dung nào?")
    if text in {"tu van quy che hoc vu huce", "tu van hoc vu", "tu van quy che", "hoc vu", "quy che"}:
        return ("Bạn muốn tìm hiểu học bổng, học phí, xin bảng điểm, hoãn thi, chuyển ngành "
                "hay một quy định khác? Hãy nêu nội dung cần tra cứu để tôi tìm nguồn phù hợp.")
    if re.fullmatch(r"(?:(?:toi|em|minh) (?:muon|can) (?:hoi|biet|tim hieu)(?: ve)? |(?:cho (?:toi|em|minh) hoi|tu van)(?: ve)? )?hoc bong(?: huce)?", text):
        return ("Bạn muốn tìm hiểu điều kiện xét, mức học bổng hay hồ sơ và thời hạn đăng ký? "
                "Nếu có học kỳ, năm học hoặc tên học bổng cụ thể, bạn cho biết thêm để tôi tra đúng nguồn.")
    # HistoryContext is always truthy; only its turns say whether a prior topic exists.
    if not getattr(history, "turns", history) and underspecified_question(question):
        return UNDERSPECIFIED_RESPONSE
    self_contained_exam = "thi" in text.split() and any(marker in text for marker in ("hoan", "ngay thi", "buoi thi"))
    self_contained_quantity = text.startswith("bao nhieu") and any(marker in text for marker in ("tin chi", "hoc phan", "qua mon"))
    if (is_followup_question(question) and not question_topics(question) and not self_contained_exam and not self_contained_quantity
            and len(subject_words(question)) < SELF_CONTAINED_WORDS
            and prepare_followup_question(question, history=history) is None
            and not has_user_context(history)):
        return "Bạn đang hỏi tiếp về học bổng, học phí hay quy định nào? Hãy nêu chủ đề để tôi tra đúng nguồn."
    return None


def has_user_context(history) -> bool:
    """Earlier user turns exist, so a short follow-up ("vậy DELF thì sao?") can be resolved by the question rewrite.

    The keyword topic list only knows a few subjects; asking the student to restate a topic they just named is the
    wrong answer when the conversation already holds it. The rewrite (RAG v2) resolves the reference or the turn is
    understood on its own; it never takes a fact from an earlier answer.
    """
    turns = getattr(history, "turns", history) or ()
    return any(getattr(turn, "role", None) == "user" and str(getattr(turn, "content", "")).strip() for turn in turns)


def retrieval_subqueries(question: str, *, limit: int = 3) -> tuple[str, ...]:
    """Decompose explicit multi-topic reads, preserving qualifiers in each query."""
    if type(limit) is not int or not 1 <= limit <= 3:
        raise ValueError("bounded retrieval query limit required")
    topics = question_topics(question)
    text = normalized_question(question)
    expansions = [canonical for phrase, canonical in (
        ("cham lai", "phúc khảo"), ("nang diem", "học cải thiện"),
        ("chuong trinh thu hai", "học cùng lúc hai chương trình"),
        ("nam dau", "năm thứ nhất"), ("nam nhat", "năm thứ nhất"), ("ban ghi ket qua", "bảng điểm"),
        ("tu nghien cuu", "khối lượng học tập tín chỉ"),
    ) if phrase in text]
    if "hoc phi" in topics and any(term in text for term in ("bao nhieu", "may tien", "gia", "muc thu", "don gia")):
        expansions.append("mức học phí đồng/tín chỉ chương trình đào tạo khóa học")
    if "tin chi tot nghiep" in topics:
        expansions.append("khung chương trình đào tạo tổng số tín chỉ kỹ sư cử nhân")
    if expansions:
        question += "\nThuật ngữ tra cứu: " + "; ".join(expansions)
    if len(topics) < 2 or len(topics) > limit:
        # A bounded plan must not silently select only some explicit subjects.
        # Keep a combined query when decomposition would exceed its call cap.
        return (question,)
    # Every subquery retains the original question: numbers, dates, exceptions
    # and user constraints must not be invented or discarded by query planning.
    return tuple(f"{topic}: {question}" for topic in sorted(topics))
