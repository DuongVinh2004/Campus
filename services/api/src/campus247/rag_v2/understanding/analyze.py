"""Deterministic intent and answer-changing slot detection for HUCE source reads."""
from __future__ import annotations

import re
from collections.abc import Sequence

from campus247.rag_v2.types import Understanding
from campus247.rag_v2.understanding.normalize import fold, normalize_query

_TOPICS = {
    "hoc_phi": ("hoc phi", "muc thu", "dong tien hoc"),
    "hoc_bong": ("hoc bong",), "hoc_phan": ("hoc phan", "dang ky", "rut mon", "tin chi"),
    "quy_che": ("quy che", "quy dinh", "buoc thoi hoc", "canh bao hoc", "bao luu", "nghi hoc"),
    "tot_nghiep": ("tot nghiep",), "ky_tuc_xa": ("ky tuc xa",),
    "thu_vien": ("thu vien",), "chuong_trinh": ("chuong trinh", "nganh", "tien quyet", "song hanh"),
    "thu_tuc": ("thu tuc", "ho so", "bang diem", "giay xac nhan"),
    "lich": ("lich thi", "lich hoc", "nghi tet", "khai giang"),
}
# Codes and names denote the same scope; retrieval also uses this function on
# source scopes. Generic degree/program tracks remain explicit (not inferred).
_PROGRAMS = (
    ("7480201", ("cong nghe thong tin", "7480201")),
    ("7480202", ("an toan thong tin", "7480202")),
    ("7580201", ("ky thuat xay dung", "7580201")),
    ("7580101", ("kien truc", "7580101")),
    ("7580301", ("kinh te xay dung", "7580301")),
    ("7580302", ("quan ly xay dung", "7580302")),
)
_TRACKS = ("chat luong cao", "tien tien", "vua lam vua hoc", "lien thong", "dai tra", "chinh quy")
_TRACK_LABELS = ("chất lượng cao", "tiên tiến", "vừa làm vừa học", "liên thông", "đại trà", "chính quy")
_NO_SUBJECT_WORDS = ("la gi nao the sao ai dau o bao nhieu may khi luc co khong duoc chua nhe a da di voi oi "
                   "vay thi va cua ve cho toi em minh ban anh chi thay xin hoi biet giup can muon hay nay do "
                   "kia cai viec chuyen lam nhu mot nhung cac rat qua chut nua roi se phai nen tu den vi tai "
                   "bi ma neu thu tuc quy dinh thong tin van de huong dan noi dung truong huce sinh vien nha")
_NO_SUBJECT = set(_NO_SUBJECT_WORDS.split())
_SUGGEST = "Bạn muốn hỏi về học phí, học bổng, đăng ký học phần, bảo lưu, tốt nghiệp hay ký túc xá?"


def contains(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))


def program_key(value: str) -> str:
    text = fold(normalize_query(value))
    for code, names in _PROGRAMS:
        if any(contains(text, name) for name in names):
            return code
    return text


def _many(text: str):
    """Whether the question names more than one cohort, year or programme ("so sánh K70 và K71")."""
    cohorts = set(re.findall(r"\bk\s*(\d{2,3})\b", text))
    years = set(re.findall(r"\b20\d{2}-20\d{2}\b", text))
    programs = {code for code, names in _PROGRAMS if any(contains(text, name) for name in names)}
    programs |= set(re.findall(r"\b7\d{6}\b", text))
    return len(cohorts) > 1, len(years) > 1, len(programs) > 1


def _scope(text: str):
    many_cohort, many_year, many_program = _many(text)
    # Several named values are not a filter: keeping only the first would silently drop the others' sources.
    cohort = None if many_cohort else re.search(r"\bk\s*(\d{2,3})\b", text)
    year = None if many_year else re.search(r"\b20\d{2}-20\d{2}\b", text)
    program = None if many_program else next((code for code, names in _PROGRAMS if any(contains(text, name) for name in names)), None)
    if program is None and not many_program:
        code = re.search(r"\b7\d{6}\b", text)
        program = code[0] if code else next((label for key, label in zip(_TRACKS, _TRACK_LABELS)
                                            if contains(text, key)), None)
    return ("K" + cohort[1] if cohort else None, program, year[0] if year else None)


def analyze(question: str, history_turns: Sequence[str] = ()) -> Understanding:
    query = normalize_query(question)
    text = fold(query)
    topics = tuple(key for key, phrases in _TOPICS.items() if any(contains(text, p) for p in phrases))
    cohort, program, year = _scope(text)
    many_cohort, many_year, many_program = _many(text)
    semester = bool(re.search(r"\bhoc ky\s*(?:[123]|i{1,3})\b", text))
    # Carry context only for elliptical follow-ups, never for a new named topic.
    elliptical = bool(re.fullmatch(
        r"(?:con |the con |vay )?(?:k\s*\d{2,3}|20\d{2}-20\d{2}|hoc ky\s*[123]|bao nhieu|khi nao|bao gio)[?!. ]*", text))
    followup = bool(history_turns) and (elliptical or text.startswith(("con ", "the con ", "vay ")))
    if followup:
        for previous in reversed(history_turns[-4:]):
            prior = analyze(previous, ())
            if not prior.topics or prior.out_of_scope:
                continue
            if topics and not set(topics).intersection(prior.topics):
                break
            cohort, program, year = cohort or prior.cohort, program or prior.program, year or prior.academic_year
            if not topics:
                topics = prior.topics
                query = prior.search_query + " ; " + query
                text = fold(query)
            semester = semester or bool(re.search(r"\bhoc ky\s*(?:[123]|i{1,3})\b", fold(prior.search_query)))
            break

    foreign_school = bool(re.search(
        r"\b(?:bach khoa|ngoai thuong|kinh te quoc dan|fpt|vinuni|hust|hcmut|harvard|stanford)\b", text)
        # "nếu" folds to "neu", so only the all-caps acronym names the university.
        or re.search(r"\bNEU\b", question))
    other_school = bool(re.search(
        r"\b(?:truong|dai hoc|dh|hoc vien|cao dang)\s+(?:y ha noi|y duoc|luat|thuong mai|su pham|thuy loi|"
        r"giao thong van tai|giao thong|cong nghiep|hang hai|nong nghiep|mo dia chat|tai nguyen|kien truc ha noi|"
        r"kien truc tp|quoc gia|phenikaa|van lang|duy tan|hoa sen|rmit|fpt|bach khoa|ngoai thuong|kinh te quoc dan|"
        r"cong nghe|tai chinh|ngan hang|bao chi|dien luc|thang long|hoa binh)\b", text))
    own_school = any(contains(text, p) for p in ("huce", "xay dung ha noi", "dhxdhn"))
    # "quy chế của trường khác" names no school, but "học tại trường khác" inside a rule question is ordinary.
    other_school = other_school or bool(re.search(r"(?:^|\bcua )(?:truong|dai hoc) khac\b", text))
    out = ((foreign_school or other_school) and not own_school) or any(contains(text, p) for p in (
        "thoi tiet", "du bao mua", "gia bitcoin", "ty gia", "ket qua bong da", "nau an", "tu vi"))
    qtype = "lookup"
    if out:
        qtype = "oos"
    elif any(contains(text, p) for p in ("han nop", "han dong", "han cuoi", "bao gio", "khi nao", "ngay nao")):
        qtype = "deadline"
    elif any(contains(text, p) for p in ("so sanh", "khac nhau")):
        qtype = "compare"
    elif any(contains(text, p) for p in ("lien he", "email", "dien thoai", "o dau")):
        qtype = "contact"
    elif any(contains(text, p) for p in ("thu tuc", "ho so", "cach", "nhu the nao")):
        qtype = "procedure"
    elif any(contains(text, p) for p in ("dieu kien", "duoc khong", "co duoc", "tien quyet")):
        qtype = "condition"
    elif any(contains(text, p) for p in ("bao nhieu", "may tien", "muc thu", "don gia")):
        qtype = "number"
    elif text in {"xin chao", "chao", "hello", "hi", "cam on"}:
        qtype = "smalltalk"

    required, missing = [], []
    # A general explanation, rule, contact or procedure remains answerable even
    # when a concrete amount/date in a second facet needs more context.
    partial = any(contains(text, p) for p in (
        "quy dinh", "quy che", "dieu kien", "thu tuc", "cach", "lien he", "la gi", "nguyen tac",
        "gom nhung", "cau truc", "phuong thuc", "mien giam", "chinh sach", "doi tuong"))
    # A named decision fixes its own scope ("Quyết định 924 …"); a degree level selects the fee row like a programme.
    named_document = bool(re.search(r"\b(?:quyet dinh|thong bao|van ban|nghi dinh|cong van)\s+\d+", text))
    degree = bool(re.search(r"\b(?:cu nhan|ky su|kien truc su|ks|kts)\b", text))
    if not out and not partial and not named_document:
        if "hoc_phi" in topics and qtype == "number":
            required = ["cohort|academic_year", "program"]
            missing = (["cohort|academic_year"] if not (cohort or year or many_cohort or many_year) else []) + (
                ["program"] if not (program or degree or many_program) else [])
        elif qtype == "deadline" and ("hoc_phi" in topics or contains(text, "mien giam") or contains(text, "hoc bong")):
            required = ["semester|academic_year"]
            missing = [] if semester or year else required.copy()
    prompt = None
    subject = [w for w in re.findall(r"\w+", text) if w not in _NO_SUBJECT]
    # "Cách tính điểm đó?" with no earlier turn: the pronoun points at nothing we can see.
    dangling = (not topics and not history_turns and len(subject) <= 4 and not re.search(r"\d", text)
                and bool(re.search(r"\b(?:do|nay|kia|no)\b", text)))
    unclear = dangling or not topics and (not subject or (len(subject) == 1 and subject[0] in {"diem", "thi", "hoc", "phi", "lop", "mon"})
                              or (len(subject) <= 2 and not re.search(r"\d", text)))
    if not out and qtype != "smalltalk" and unclear:
        qtype, prompt = "unclear", "Câu hỏi chưa rõ nội dung. " + _SUGGEST
    elif missing:
        labels = {"cohort|academic_year": "khóa hoặc năm học", "program": "ngành, hệ hoặc chương trình đào tạo",
                  "semester|academic_year": "học kỳ hoặc năm học"}
        prompt = "Bạn cho biết " + " và ".join(labels[s] for s in missing) + " để tra đúng mức hoặc thời hạn áp dụng."
    return Understanding(question, query, topics, cohort, program, year, qtype,
                         tuple(required), tuple(missing), prompt, out)
