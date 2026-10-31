"""Conservative Vietnamese search normalization, without model calls or v1 imports."""
from __future__ import annotations

import re
import unicodedata


def fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
                   if unicodedata.category(c) != "Mn")


# Whole phrases only: ambiguous tokens such as hp, cntt in identifiers and nam
# are deliberately not restored on their own. These are search terms, not facts.
_PHRASES = {
    "hoc phi": "học phí", "hoc bong": "học bổng", "hoc phan": "học phần",
    "hoc ky": "học kỳ", "ky 1": "học kỳ 1", "ky 2": "học kỳ 2", "ky 3": "học kỳ 3",
    "nam hoc": "năm học", "tin chi": "tín chỉ", "dang ky": "đăng ký",
    "han nop": "hạn nộp", "han dong": "hạn đóng", "bao nhieu": "bao nhiêu",
    "khi nao": "khi nào", "bao gio": "bao giờ", "dieu kien": "điều kiện",
    "thu tuc": "thủ tục", "quy che": "quy chế", "quy dinh": "quy định",
    "tot nghiep": "tốt nghiệp", "bao luu": "bảo lưu", "thoi hoc": "thôi học",
    "buoc thoi hoc": "buộc thôi học", "duoi hoc": "buộc thôi học",
    "rot mon": "không đạt học phần", "truot mon": "không đạt học phần",
    "no mon": "học phần chưa đạt", "ky tuc xa": "ký túc xá",
    "thu vien": "thư viện", "lien he": "liên hệ", "ren luyen": "rèn luyện",
    "cong nghe thong tin": "công nghệ thông tin", "an toan thong tin": "an toàn thông tin",
    "ky thuat xay dung": "kỹ thuật xây dựng", "kien truc": "kiến trúc",
    "kinh te xay dung": "kinh tế xây dựng", "quan ly xay dung": "quản lý xây dựng",
    "dai tra": "đại trà", "chinh quy": "chính quy", "chat luong cao": "chất lượng cao",
    "tien tien": "tiên tiến", "lien thong": "liên thông", "vua lam vua hoc": "vừa làm vừa học",
    "chuong trinh": "chương trình", "nganh": "ngành", "he dao tao": "hệ đào tạo",
    "xin chao": "xin chào", "thoi tiet": "thời tiết",
}
_TOKENS = {"sv": "sinh viên", "đk": "đăng ký", "dk": "đăng ký", "đc": "được", "dc": "được",
           "ko": "không", "hok": "không", "j": "gì", "ntn": "như thế nào", "ktx": "ký túc xá",
           "rl": "rèn luyện", "qđ": "quyết định", "qd": "quyết định", "tc": "tín chỉ",
           "gv": "giảng viên", "cntt": "công nghệ thông tin", "attt": "an toàn thông tin"}
_TOKEN = re.compile(r"(?<![\w/.-])(" + "|".join(map(re.escape, _TOKENS)) + r")(?![\w/.-])", re.IGNORECASE)
_PHRASE = re.compile(r"(?<!\w)(" + "|".join(sorted(map(re.escape, _PHRASES), key=len, reverse=True)) + r")(?!\w)")


def normalize_query(question: str) -> str:
    text = unicodedata.normalize("NFC", " ".join(question.split())).lower()
    text = _TOKEN.sub(lambda m: _TOKENS[m[0].lower()], text)
    text = re.sub(r"\bhk\s*([123])\b", r"học kỳ \1", text)
    # NFC Vietnamese letters fold one-to-one. Keep offsets for other Unicode
    # scripts too, so a foreign character cannot move a replacement boundary.
    plain, offsets = [], []
    for i, char in enumerate(text):
        for c in fold(char):
            plain.append(c)
            offsets.append(i)
    for match in reversed(list(_PHRASE.finditer("".join(plain)))):
        start, end = offsets[match.start()], offsets[match.end() - 1] + 1
        text = text[:start] + _PHRASES[match[0]] + text[end:]

    def year(m: re.Match) -> str:
        a, b = int(m[1]), int(m[2])
        return f"20{a:02d}-20{b:02d}" if 20 <= a <= 40 and b == a + 1 else m[0]

    text = re.sub(r"(?<![\w/.-])(\d{2})\s*[-–/]\s*(\d{2})(?![\w/.-])", year, text)
    text = re.sub(r"\b(20\d{2})\s*[-–/]\s*(20\d{2})\b", r"\1-\2", text)
    return re.sub(r"\bk\s*(\d{2,3})\b", lambda m: "K" + m[1], text, flags=re.IGNORECASE)
