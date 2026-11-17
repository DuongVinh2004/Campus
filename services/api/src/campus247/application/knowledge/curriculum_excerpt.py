"""Exact printed total rows, with their exclusions, from admitted source text."""
import re

from campus247.application.conversation.followup import normalized_question


def printed_total_excerpt(content, question):
    query = normalized_question(question)
    if not ("tong" in query and ("tin chi" in query or re.search(r"\btc\b", query))):
        return None
    matches = list(re.finditer(r"(?mi)^\s*Tổng(?:\s+số\s+(?:TC|tín chỉ)(?:\s+toàn khóa)?)?\s*:\s*\d", content))
    if len(matches) != 1:
        return None
    start = matches[0].start()
    # Preserve the entire printed total and exclusions, including wrapped lines.
    boundary = re.search(r"(?mi)^\s*(?:Ghi chú|Người lập|Người lập biểu)", content[matches[0].end():])
    end = matches[0].end() + boundary.start() if boundary else len(content)
    return content[start:end].strip()


def printed_course_rerank_text(content, question, verified_geometry):
    """Explain a cell inside a dense roster; return full parent as evidence.

    The caller supplies geometry reconstructed from the reviewed source. The
    schema sentence adds no course value and is never quoted as source text.
    """
    query = normalized_question(question)
    codes = set(re.findall(r"\b\d{6}\b", query))
    if (len(codes) != 1 or not verified_geometry
            or not codes.issubset(verified_geometry.get("course_codes", []))
            or codes.intersection(verified_geometry.get("ambiguous_course_codes", []))
            or re.search(r"tien quyet|song hanh|hoc truoc|dieu kien|quan he|\btong\b", query)
            or "ten nguyen van" not in query):
        return None
    # A short one/two-cell parent already supplies its native local context.
    # Dense rosters need a field description to distinguish the requested row.
    if len(re.findall(r"(?m)^\d{6}\s*[-–—]\s*\d{1,2}(?=\s|$)", content)) < 3:
        return None
    code = next(iter(codes))
    matches = list(re.finditer(r"(?m)^" + code + r"\s*[-–—]\s*\d{1,2}(?=\s|$)", content))
    if len(matches) != 1:
        return None
    match = matches[0]
    ends = [pos for separator in ("\n\n", "\nTổng:") if (pos := content.find(separator, match.end())) >= 0]
    following_code = re.search(r"(?m)^\d{6}\s*[-–—]\s*\d{1,2}(?=\s|$)", content[match.end():])
    if following_code:
        ends.append(match.end() + following_code.start())
    end = min(ends) if ends else len(content)
    if not content[match.end():end].strip():
        return None
    literal = content[match.start():end].strip()
    return "Ô học phần đã đối chiếu: mã học phần – giá trị ghi bên cạnh mã; tên học phần nguyên văn.\n" + literal


def printed_elective_rerank_text(content, question, verified_geometry):
    """Describe a verified native free-elective cell without interpreting choice rules."""
    query = normalized_question(question)
    if (not verified_geometry or verified_geometry.get("evidence_kind") != "cell"
            or len(verified_geometry.get("course_codes", [])) < 2
            or "tu chon tu do" not in query or "tu chon tu do" not in normalized_question(content)
            or re.search(r"\b\d{6}\b", query)
            or not re.search(r"phuong an|hoc phan|\bmon\b", query)):
        return None
    return "Ô nhóm học phần tự chọn tự do đã đối chiếu; danh sách học phần ghi trong ô:\n" + content
