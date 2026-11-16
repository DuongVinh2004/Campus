"""A deadline question needs a dated submission-period field, not an appendix."""
import re

from campus247.application.conversation.followup import normalized_question


def is_submission_deadline_question(question):
    text = normalized_question(question)
    return any(term in text for term in ("han nop ho so", "thoi han nop", "thoi gian tiep nhan ho so"))


def submission_deadline_excerpt(content):
    anchor = re.search(r"(?:Hạn\s+nộp\s+hồ\s+sơ|Thời\s+gian\s+(?:tiếp\s+nhận|nộp)\s+hồ\s+sơ)", content, re.IGNORECASE)
    if not anchor: return None
    tail = content[anchor.start():]
    boundary = re.search(r"(?m)\n\s*\d+\.\s+|\n\s*(?:Nơi nhận hồ sơ|Địa điểm tiếp nhận)", tail)
    if boundary: tail = tail[:boundary.start()]
    if not re.search(r"\b\d{1,2}\s*[/.-]\s*\d{1,2}\s*[/.-]\s*20\d{2}\b|ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+20\d{2}", tail[:600], re.IGNORECASE):
        return None
    return tail.strip()
