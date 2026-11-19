from __future__ import annotations

import re
import unicodedata

from campus247.agent.state import SafetyDecision, SafetySeverity


_CRITICAL_RULES: tuple[tuple[str, str], ...] = (
    (
        "self_harm_imminent",
        r"(?:\btu\s*(?:tu|sat)\b|\bmuon\s*chet\b|\bkhong\s*muon\s*song\b|"
        r"\bnhay\s+(?:lau|tu\s+tang|xuong)\b|\bcat\s+(?:co|tay)\b|"
        r"\buong\s+thuoc\s+ngu\b|\bket\s*lieu\b)",
    ),
    (
        "violence_imminent",
        r"(?:\b(?:dam|giet)\s+(?:chet|nguoi)\b|\b(?:mang|vac|cam)\s+(?:dao|sung|bom)\b|"
        r"\b(?:dat|danh)\s+bom\b|\bdot\s+(?:truong|phong|nguoi)\b|"
        r"\b(?:dao|sung)\b.{0,60}\b(?:xu|giet|dam|tan\s*cong)\b)",
    ),
    (
        "medical_emergency",
        r"(?:\bngat\s*xiu\b|\bco\s*giat\b|\bkho\s*tho\b|\bdot\s*quy\b|"
        r"\bngung\s*tim\b|\bbat\s*tinh\b|\bdau\s*nguc\b.{0,40}\b(?:kho\s*tho|ngat)\b)",
    ),
)

_HIGH_RULES: tuple[tuple[str, str], ...] = (
    (
        "harassment_or_abuse",
        r"(?:\bquay\s*roi\b|\bxam\s*hai\b|\bbat\s*nat\b|\bboc\s*phot\b|\bdim\s*chet\b|"
        r"\bga\s*tinh\b|\bxin\s*so\s*do\b|\bvo\s*tich\s*su\b|\blam\s*an\s*nhu\s*hac\b|"
        r"\bday\s*dot\s*nhu\s*bo\b|\bcut\s*ve\s*que\b|\blam\s*ban\s*truong\b|\bde\s*doa\b)",
    ),
    (
        "disciplinary_or_legal",
        r"(?:\bto\s*cao\b|\bnhan\s*tien\s*chay\s*diem\b|\bchay\s*diem\b|"
        r"\bkhieu\s*nai\b.{0,40}\bky\s*luat\b|\bbi\s*dinh\s*chi\b)",
    ),
    (
        "academic_rights_impact",
        r"(?:\bdoi\s*diem\b|\bmat\s*quyen\b|\bngoai\s*le\b.{0,40}\bdeadline\b|"
        r"\bgia\s*han\b.{0,40}\bdeadline\b|\bcam\s*thi\b|\btu\s*choi\b.{0,40}\bhoc\s*bong\b)",
    ),
    (
        "privacy_or_security_incident",
        r"(?:\bphishing\b|\bbi\s*hack\b|\blo\s*(?:mat\s*khau|thong\s*tin|tai\s*khoan)\b|"
        r"\bbi\s*danh\s*cap\b.{0,30}\btai\s*khoan\b|\bgui\b.{0,20}\bmat\s*khau\b)",
    ),
    (
        "financial_impact",
        r"(?:\bhoan\s*tien\b|\bmien\s*giam\s*hoc\s*phi\b|\bno\s*hoc\s*phi\b.{0,30}\bbi\b|"
        r"\btang\s*hoc\s*phi\b.{0,30}\bvo\s*ly\b|\bkhong\s*du\s*tien\b.{0,30}\bhoc\b)",
    ),
    (
        "mental_health_distress",
        r"(?:\bkhong\s*chiu\s*noi\b|\bsuy\s*sup\b|\bhoang\s*loan\b|\bap\s*luc\b.{0,30}\bkhong\s*ngu\b|"
        r"\bstress\b.{0,30}\bkhong\s*on\b)",
    ),
)

_PROMPT_INJECTION_RULE = re.compile(
    r"(?:\bignore\s+previous\s+instructions\b|\bsystem\s+prompt\b|"
    r"\bbo\s*qua\s*(?:cac\s*)?chi\s*thi\s*truoc\b|\btiet\s*lo\b.{0,30}\bhuong\s*dan\s*he\s*thong\b|"
    # Requests for secrets, hidden instructions, debug bypasses or other users' conversations.
    r"\b(?:api\s*key|khoa\s*api|secret\s*key)\b|"
    r"\bmat\s*khau\s+(?:he\s*thong|co\s*so\s*du\s*lieu|database|quan\s*tri|admin|server|may\s*chu)\b|"
    r"\btoken\s+(?:he\s*thong|truy\s*cap|quan\s*tri|admin)\b|\bchi\s*dan\s*an\b|"
    r"\b(?:bat|che\s*do)\s*debug\b|\bbo\s*qua\s*(?:viec\s*)?kiem\s*(?:tra\s*)?nguon\b|"
    r"\b(?:noi\s*dung|lich\s*su)\s+(?:cac\s*)?(?:cuoc\s*tro\s*chuyen|hoi\s*thoai)\s+cua\s+"
    r"(?:sinh\s*vien|nguoi\s*dung|user|nguoi)\s+khac\b)"
)


# Requests to print, reveal or ignore the assistant's own instructions. "huong dan he thong" alone can be a legitimate
# phrase ("hướng dẫn hệ thống đăng ký"), so it only counts next to a verb that asks for the hidden text.
_EXFILTRATION_RULE = re.compile(
    r"(?:\b(?:in|hien\s*thi|cho\s*(?:\w+\s+)?xem|tiet\s*lo|doc\s*lai|liet\s*ke|show|print|reveal|repeat)\b.{0,30}"
    r"\b(?:chi\s*dan\s*he\s*thong|chi\s*thi\s*he\s*thong|prompt\s*he\s*thong|system\s*(?:prompt|instructions?)|"
    r"lenh\s*he\s*thong|hidden\s*instructions?)\b"
    r"|\bbo\s*qua\s*(?:cac\s*)?(?:huong\s*dan|quy\s*tac|chi\s*dan|chi\s*thi|lenh)\s*(?:truoc|ben\s*tren|o\s*tren)\b.{0,60}"
    r"\b(?:chi\s*dan|huong\s*dan|prompt|lenh|quy\s*tac)\s*he\s*thong\b)")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return " ".join(without_marks.split())


def _decision(severity: SafetySeverity, reason: str | None, *, crisis: bool = False) -> SafetyDecision:
    return SafetyDecision(severity=severity, is_crisis=crisis, reason=reason)


def _generic_public_rule_question(query_text: str, text: str) -> bool:
    """Human-authorized distinction for generic rules, never an individual case."""
    if "?" not in query_text or not re.match(
            r"^(?:theo (?:noi quy|quy che|quy dinh)[^,?]{0,160},\s*)?"
            r"sinh vien (?:nao )?vi pham noi quy\b", text):
        return False
    if re.search(r"\b(?:toi|em|minh|mssv|ma sinh vien|sv\d+|sinh vien nay|sinh vien do|"
                 r"sinh vien ten|ho so|to cao|khieu nai|chay diem)\b", text):
        return False
    if re.search(r"\b(?:bạn|anh|chị|ông|bà)\b", query_text, re.I):
        return False
    # Names cannot be introduced inside the otherwise generic subject/rule.
    if re.search(r"\b[A-ZĐ][a-zà-ỹ]+(?:\s+[A-ZĐ][a-zà-ỹ]+)+\b", query_text):
        return False
    return True


def _public_waiver_deadline_reference(query_text: str, text: str) -> bool:
    # Students seldom type "?"; an interrogative word makes it a read question just as well.
    if "?" not in query_text and not re.search(
            r"\b(?:nao|bao gio|o dau|may gio|the nao|ra sao|bao lau|hom nao|ngay may)\b", text):
        return False
    if not any(term in text for term in ("han nop", "han cuoi", "han chot", "thoi han nop", "thoi gian tiep nhan",
                                         "noi nop", "nop o dau", "nop tai", "nop ho so")):
        return False
    # The question must name which notice it means: a numbered notice, a school year, or a term/year reference
    # ("học kỳ 1", "kỳ này", "năm nay"). A bare "hồ sơ miễn giảm học phí hạn nộp?" stays protected.
    if not (re.search(r"\bthong bao(?:\s+so)?\s+\d{1,6}\b", text)
            or re.search(r"\b20\d{2}\s*[-–/]\s*20\d{2}\b", text)
            or re.search(r"\b(?:hoc ky|hk|ky)\s*(?:1|2|i|ii|nay|truoc|sau|nay)\b|\bnam (?:nay|hoc|ngoai)\b", text)):
        return False
    # The signals below keep every question about the speaker's own case, refunds, debt or extensions protected.
    # Other money signals (refund, debt, unaffordable fees) are never excused by a deadline.
    if re.search(r"\b(?:hoan\s*tien|no\s*hoc\s*phi|tang\s*hoc\s*phi|khong\s*du\s*tien)\b", text):
        return False
    # "em/tôi" is only how a student addresses the assistant; questions about the speaker's own case stay protected.
    if re.search(r"\b(?:mssv|ma sinh vien|sv\d+|ho so cua|sinh vien ten|gia han|ngoai le|tre han|qua han|"
                 r"duoc mien|xin mien|cua (?:toi|em|minh)|(?:toi|em|minh) (?:co duoc|co thuoc|xin|dang no|bi no|muon xin))\b", text):
        return False
    # Place names ("Hồ Chí Minh") look like personal names to the capitalised-run test; they are not.
    without_places = re.sub(r"(?i)(?:phân hiệu|thành phố)?\s*hồ chí minh|hà nội|phân hiệu|thành phố", " ", query_text)
    if re.search(r"\b[A-ZĐ][a-zà-ỹ]+(?:\s+[A-ZĐ][a-zà-ỹ]+)+\b", without_places):
        return False
    return not bool(_PROMPT_INJECTION_RULE.search(text))


def is_public_policy_question(query_text: str) -> bool:
    """Separate reading a policy from deciding or acting on a private case."""
    from campus247.agent.nodes.intent import (
        is_human_handover_request, is_information_request, is_other_person_data_request,
    )
    text = _normalize(query_text)
    # Deadline questions retain the narrower, bounded notice/year exception below.
    if re.search(r"\b(?:han nop|thoi han|het han|gia han|khi nao|ngay nao|bao gio|"
                 r"truoc ngay|deadline|han chot|tre han|qua han|han dong|han cuoi|chot han|"
                 r"thoi gian nop|thoi gian tiep nhan ho so)\b", text):
        return False
    if (not is_information_request(query_text) or is_human_handover_request(query_text)
            or is_other_person_data_request(query_text) or _PROMPT_INJECTION_RULE.search(text)):
        return False
    policy = bool(re.search(r"\b(?:quy dinh|quy che|thu tuc|quy trinh|huong dan)\b", text))
    if re.search(r"\b(?:ket luan|kiem tra ho so|xem ho so|quyet dinh ky luat cua|phe duyet|duyet ho so)\b", text):
        return False
    if re.search(r"\b(?:toi|em|minh)\s+(?:(?:muon|can|yeu cau)\s+)?(?:khieu nai|to cao|gia han)\b", text):
        return False
    if not policy and re.search(r"\b(?:khieu nai|to cao|chay diem|gia han|ngoai le)\b", text):
        return False
    if (re.search(r"\b(?:mssv|ma sinh vien|sv\d+)\b", text)
            or re.search(r"\b[A-ZĐ][a-zà-ỹ]+(?:\s+[A-ZĐ][a-zà-ỹ]+){2,}\b", query_text)):
        return False
    if (re.search(r"\b(?:no hoc phi|khong du tien)\b", text)
            and not any(p in text for p in ("quy dinh", "quy che", "thu tuc", "dieu kien"))):
        return False
    topic = bool(re.search(r"\b(?:hoc phi|hoc bong|mien|giam|ho tro chi phi|ky luat|"
                           r"dinh chi|phong thi|cam thi|quy dinh|quy che|thu tuc)\b", text))
    read = bool(re.search(r"\b(?:quy dinh|quy che|thu tuc|dieu kien|ho so|giay to|"
                          r"bao nhieu|bao lau|nhu the nao|dung khong|phai nop|can nop|"
                          r"nop lai|moi hoc ky|mot lan|duoc khong)\b", text))
    return topic and read


def evaluate_deterministic_safety(query_text: str) -> SafetyDecision:
    """Apply bounded, ordered safety rules without side effects or external calls."""
    if not isinstance(query_text, str):
        return _decision(SafetySeverity.NORMAL, None)

    text = _normalize(query_text)
    for reason, pattern in _CRITICAL_RULES:
        if re.search(pattern, text):
            return _decision(SafetySeverity.CRITICAL, reason, crisis=True)

    for reason, pattern in _HIGH_RULES:
        match = re.search(pattern, text)
        if match:
            if (reason == "privacy_or_security_incident" and match.group(0).startswith("lo ")
                    and "lộ" not in query_text.lower() and re.search(r"[à-ỹ]", query_text.lower())):
                continue  # "lo mật khẩu" typed with diacritics is "worry about", not "leaked" (lộ)
            if (reason == "privacy_or_security_incident" and match.group(0).startswith("lo ")
                    and re.search(r"\b(?:de|so|nguy co|co the|neu|tranh|ngan|phong|chong)\s+(?:bi\s+)?$",
                                  text[max(0, match.start() - 16):match.start()])):
                continue  # a hypothetical ("dễ bị lộ mật khẩu"), not an incident that already happened
            if (reason in {"financial_impact", "disciplinary_or_legal", "academic_rights_impact"}
                    and is_public_policy_question(query_text)):
                continue
            if reason == "financial_impact" and _public_waiver_deadline_reference(query_text, text):
                continue
            if reason == "disciplinary_or_legal" and _generic_public_rule_question(query_text, text):
                # Only the broad 'bị đình chỉ' branch is disambiguated. Other
                # high-priority rules continue below; critical rules ran first.
                continue
            return _decision(SafetySeverity.HIGH, reason)

    if _EXFILTRATION_RULE.search(text):
        # Asking the assistant to print or reveal its own instructions is never excused by a real question next to it.
        return _decision(SafetySeverity.HIGH, "prompt_injection_signal")

    if _PROMPT_INJECTION_RULE.search(text):
        benign_academic_context = any(
            marker in text
            for marker in ("hoc lai", "hoc bong", "quy dinh", "thu tuc", "hoc phi", "mon hoc")
        )
        if benign_academic_context:
            return _decision(SafetySeverity.NORMAL, "prompt_injection_signal_benign_inquiry")
        return _decision(SafetySeverity.HIGH, "prompt_injection_signal")

    return _decision(SafetySeverity.NORMAL, None)
