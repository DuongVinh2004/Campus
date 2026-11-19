"""Rule-based detection of personal data in crawled text. A hit keeps the page out of the chatbot's knowledge.

Deliberately conservative: school pages legitimately list a few staff phone numbers or institutional emails, but never
lists of students with ids, birth dates or grades, nor identity-card numbers. Concrete HUCE formats are refined against
real pages before a source is switched on (the dry run reports every decision).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

CCCD = re.compile(r"(?<!\d)\d{12}(?!\d)")
CMND_CONTEXT = re.compile(r"\b(?:cccd|cmnd|can cuoc|chung minh)\b", re.I)
PHONE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.\-]?\d){9,10}(?!\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})")
PERSONAL_DOMAINS = {"gmail.com", "yahoo.com", "yahoo.com.vn", "outlook.com", "hotmail.com", "icloud.com", "live.com"}
PERSON_HEADER = re.compile(r"\b(?:ma sinh vien|msv|mssv|ma sv|ho va ten|ho ten|ngay sinh|diem|so cmnd|so cccd)\b")
ID_CELL = re.compile(r"^\d{6,10}$")
NAME_CELL = re.compile(r"^(?:[^\W\d_]+[ ]+){1,5}[^\W\d_]+$", re.UNICODE)

PERSON_ROWS_BLOCK = 5
PHONES_BLOCK = 8
PERSONAL_EMAILS_BLOCK = 5


@dataclass(frozen=True)
class PiiFinding:
    kind: str
    count: int
    note: str


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn").replace("đ", "d")


def scan_personal_data(text: str) -> list[PiiFinding]:
    findings = []
    folded = _fold(text)
    ids = CCCD.findall(text)
    if ids:  # any 12-digit number is treated as a possible identity-card number; the report says why a page was kept out
        findings.append(PiiFinding("IDENTITY_NUMBER", len(ids), "số 12 chữ số có thể là số căn cước"))
    rows = 0
    header_rows = 0
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 2:
            continue
        if PERSON_HEADER.search(_fold(line)):
            header_rows += 1
        has_id = any(ID_CELL.match(c) for c in cells)
        has_name = any(NAME_CELL.match(c) and len(c) <= 40 and c[:1].isupper() and sum(w[:1].isupper() for w in c.split()) >= 2 for c in cells)
        if has_id and has_name:
            rows += 1
    if rows >= PERSON_ROWS_BLOCK or (rows >= 3 and header_rows):
        findings.append(PiiFinding("PERSON_LIST", rows, "danh sách người kèm mã định danh"))
    phones = len(set(re.sub(r"\D", "", m.group()) for m in PHONE.finditer(text)))
    if phones >= PHONES_BLOCK:
        findings.append(PiiFinding("PHONE_LIST", phones, "nhiều số điện thoại"))
    personal = len({m.group().lower() for m in EMAIL.finditer(text) if m.group(1).lower() in PERSONAL_DOMAINS})
    if personal >= PERSONAL_EMAILS_BLOCK:
        findings.append(PiiFinding("PERSONAL_EMAIL_LIST", personal, "nhiều email cá nhân"))
    return findings


def contains_personal_data(text: str) -> bool:
    return bool(scan_personal_data(text))
