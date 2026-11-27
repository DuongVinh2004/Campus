"""Recipient directory over the local campus directory accounts (F1.2): role, faculty, cohort (from the class code), class, subject list.

Class-section membership comes from an optional callable so this works without the learning module.
"""
from __future__ import annotations

from typing import Callable, Iterator

from campus247.domain.announcements import AudienceSpec, Recipient, cohort_of, matches


class LocalRecipientDirectory:
    def __init__(self, accounts: Callable[[], list[dict]], *, offering_members: Callable[[str], set[str]] | None = None,
                 lecturers: Callable[[str], set[str]] | None = None):
        self._accounts, self._members, self._lecturers = accounts, offering_members, lecturers

    def all_recipients(self) -> list[Recipient]:
        out = []
        for a in self._accounts():
            out.append(Recipient(a["subject_id"], (a["role"],), a.get("faculty_code"), cohort_of(a.get("class_code")), a.get("class_code")))
        return sorted(out, key=lambda r: r.subject_id)

    def _members_for(self, spec: AudienceSpec) -> dict[str, set[str]]:
        if not self._members:
            return {}
        return {o: set(self._members(o)) for g in spec.groups for o in g.offering_ids}

    def recipients(self, spec: AudienceSpec) -> Iterator[Recipient]:
        members = self._members_for(spec)
        for who in self.all_recipients():
            if matches(spec, who, members):
                yield who

    def teaches(self, subject_id: str, offering_id: str) -> bool:
        return bool(self._lecturers) and subject_id in self._lecturers(offering_id)
