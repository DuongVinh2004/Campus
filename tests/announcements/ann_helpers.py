from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from campus247.application.announcements.service import AnnouncementService
from campus247.infrastructure.identity.directory_recipients import LocalRecipientDirectory
from campus247.infrastructure.repositories.sqlite_campus_ops import CampusOpsStore
from campus247.ports.identity import IdentityContext, IdentityRole

NOW = datetime(2026, 11, 26, 3, 0, tzinfo=timezone.utc)


def sid(n: int) -> str:
    return f"01900000-0000-7000-8000-{n:012x}"


def demo_accounts() -> list[dict]:
    """Same shape as the 44-account demo semester: 4 faculties x 10 students in 2 classes each, plus 4 officers."""
    accounts, n = [], 1
    for faculty, code in (("CNTT", "IT"), ("XD", "XD"), ("KT", "KT"), ("KX", "KX")):
        for i in range(10):
            accounts.append({"role": "STUDENT", "subject_id": sid(n), "faculty_code": faculty, "class_code": f"66{code}{1 + i % 2}"})
            n += 1
    for i in range(4):
        accounts.append({"role": "SUPPORT_OFFICER", "subject_id": sid(1000 + i), "unit": "Một cửa"})
    return accounts


def person(subject: str, role: IdentityRole) -> IdentityContext:
    kw = {"student_code": "S" + subject[-4:]} if role == IdentityRole.STUDENT else {}
    return IdentityContext(subject_id=subject, external_subject="x", issuer="l", roles=(role,), display_name="x", auth_time=NOW,
                           expires_at=NOW + timedelta(hours=8), **kw)


class Clock:
    def __init__(self, start=NOW):
        self.now = start

    def __call__(self):
        return self.now


def make_service(tmp_path, accounts=None, *, enabled=lambda key: key != "announcements.second_approval", clock=None, **kw):
    store = CampusOpsStore(tmp_path / "campus-ops.sqlite3")
    directory = LocalRecipientDirectory(lambda: accounts if accounts is not None else demo_accounts(), **{k: kw.pop(k) for k in ("offering_members", "lecturers") if k in kw})
    clock = clock or Clock()
    return AnnouncementService(store, directory, enabled=enabled, clock=clock, **kw), store, clock


def draft(**over) -> dict:
    base = {"title": "Lịch nộp học phí học kỳ 2", "body": "Sinh viên nộp học phí trước ngày 30/12.", "category": "FINANCE", "priority": "NORMAL",
            "audience": {"groups": [{"roles": ["STUDENT"]}]}, "expires_at": (NOW + timedelta(days=10)).isoformat()}
    base.update(over)
    return base
