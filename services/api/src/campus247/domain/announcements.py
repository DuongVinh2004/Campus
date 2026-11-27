"""Announcements (F1.1): audience model, validation, state machine and the approval rule. Pure code: no I/O."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlparse

CATEGORIES = ("ACADEMIC", "EXAM", "FINANCE", "STUDENT_AFFAIRS", "FACILITIES", "EVENT", "SYSTEM")
PRIORITIES = ("NORMAL", "IMPORTANT", "URGENT")
STATUSES = ("DRAFT", "PENDING_APPROVAL", "SCHEDULED", "PUBLISHING", "PUBLISHED", "EXPIRED", "WITHDRAWN")
ROLES = ("STUDENT", "LECTURER", "SUPPORT_OFFICER", "KNOWLEDGE_ADMIN", "KNOWLEDGE_CONTRIBUTOR", "SYSTEM_ADMIN")
MAX_GROUPS, MAX_SUBJECTS, MAX_LINKS = 10, 500, 10
LARGE_AUDIENCE = 500
MIN_GROUP_FOR_STATS = 5
BATCH = 1000
CLASS_COHORT = re.compile(r"^(\d{2})")

# (state, action) -> new state. Anything not listed is a 409 ANNOUNCEMENT_STATE.
TRANSITIONS: dict[tuple[str, str], str] = {
    ("DRAFT", "submit_approval"): "PENDING_APPROVAL", ("DRAFT", "schedule"): "SCHEDULED", ("DRAFT", "start_publish"): "PUBLISHING",
    ("PENDING_APPROVAL", "approve_schedule"): "SCHEDULED", ("PENDING_APPROVAL", "approve_publish"): "PUBLISHING", ("PENDING_APPROVAL", "reject"): "DRAFT",
    ("SCHEDULED", "start_publish"): "PUBLISHING", ("SCHEDULED", "unschedule"): "DRAFT", ("SCHEDULED", "withdraw"): "WITHDRAWN",
    ("PUBLISHING", "finish"): "PUBLISHED", ("PUBLISHING", "withdraw"): "WITHDRAWN",
    ("PUBLISHED", "expire"): "EXPIRED", ("PUBLISHED", "withdraw"): "WITHDRAWN", ("PUBLISHED", "revise"): "PUBLISHED",
}
FINAL = {"EXPIRED", "WITHDRAWN"}


def transition(state: str, action: str) -> str | None:
    return TRANSITIONS.get((state, action))


def cohort_of(class_code: str | None) -> str | None:
    match = CLASS_COHORT.match(class_code or "")
    return match.group(1) if match else None


@dataclass(frozen=True)
class Recipient:
    subject_id: str
    roles: tuple[str, ...]
    faculty_code: str | None = None
    cohort: str | None = None
    class_code: str | None = None


@dataclass(frozen=True)
class Group:
    roles: tuple[str, ...] = ()
    faculty_codes: tuple[str, ...] = ()
    cohorts: tuple[str, ...] = ()
    class_codes: tuple[str, ...] = ()
    offering_ids: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()

    def is_everyone(self) -> bool:
        return not any((self.roles, self.faculty_codes, self.cohorts, self.class_codes, self.offering_ids, self.subjects))


@dataclass(frozen=True)
class AudienceSpec:
    groups: tuple[Group, ...] = ()
    include_guests: bool = False

    def canonical(self) -> dict:
        return {"groups": sorted(({"roles": sorted(g.roles), "faculty_codes": sorted(g.faculty_codes), "cohorts": sorted(g.cohorts),
                                   "class_codes": sorted(g.class_codes), "offering_ids": sorted(g.offering_ids), "subjects": sorted(g.subjects)}
                                  for g in self.groups), key=lambda d: json.dumps(d, sort_keys=True)),
                "include_guests": self.include_guests}

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.canonical(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def has_everyone_group(self) -> bool:
        return any(g.is_everyone() for g in self.groups)


class AnnouncementInvalid(Exception):
    def __init__(self, errors: list[dict[str, str]]):
        super().__init__("; ".join(f"{e['field']}:{e['code']}" for e in errors))
        self.errors = errors


def parse_audience(raw: dict | None) -> AudienceSpec:
    """Build the spec from request JSON; shape errors raise AnnouncementInvalid."""
    errors: list[dict[str, str]] = []
    raw = raw or {}
    groups_raw = raw.get("groups") or []
    if not isinstance(groups_raw, list) or not groups_raw:
        raise AnnouncementInvalid([{"field": "audience", "code": "AUDIENCE_EMPTY"}])
    if len(groups_raw) > MAX_GROUPS:
        raise AnnouncementInvalid([{"field": "audience", "code": "AUDIENCE_TOO_MANY_GROUPS"}])
    groups = []
    for index, g in enumerate(groups_raw):
        if not isinstance(g, dict) or set(g) - {"roles", "faculty_codes", "cohorts", "class_codes", "offering_ids", "subjects"}:
            raise AnnouncementInvalid([{"field": f"audience.groups[{index}]", "code": "AUDIENCE_SHAPE"}])

        def tup(name, _g=g):
            values = _g.get(name) or []
            if not isinstance(values, list) or any(not isinstance(v, str) or not v or len(v) > 64 for v in values):
                errors.append({"field": f"audience.groups[{index}].{name}", "code": "AUDIENCE_SHAPE"})
                return ()
            return tuple(dict.fromkeys(values))

        group = Group(tup("roles"), tup("faculty_codes"), tup("cohorts"), tup("class_codes"), tup("offering_ids"), tup("subjects"))
        if any(r not in ROLES for r in group.roles):
            errors.append({"field": f"audience.groups[{index}].roles", "code": "AUDIENCE_ROLE_UNKNOWN"})
        if len(group.subjects) > MAX_SUBJECTS:
            errors.append({"field": f"audience.groups[{index}].subjects", "code": "AUDIENCE_TOO_MANY_SUBJECTS"})
        groups.append(group)
    guests = bool(raw.get("include_guests", False))
    spec = AudienceSpec(tuple(groups), guests)
    if guests and not spec.has_everyone_group():
        errors.append({"field": "audience.include_guests", "code": "GUESTS_NEED_EVERYONE_GROUP"})
    if errors:
        raise AnnouncementInvalid(errors)
    return spec


def matches(spec: AudienceSpec, who: Recipient, offering_members: dict[str, set[str]] | None = None) -> bool:
    """OR over groups; AND inside a group. An empty group is everyone."""
    members = offering_members or {}
    for g in spec.groups:
        if g.roles and not set(g.roles) & set(who.roles):
            continue
        if g.faculty_codes and who.faculty_code not in g.faculty_codes:
            continue
        if g.cohorts and who.cohort not in g.cohorts:
            continue
        if g.class_codes and who.class_code not in g.class_codes:
            continue
        if g.offering_ids and not any(who.subject_id in members.get(o, ()) for o in g.offering_ids):
            continue
        if g.subjects and who.subject_id not in g.subjects:
            continue
        return True
    return False


def _https(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc) and len(url) <= 2000


def validate(*, title: str, body: str, category: str, priority: str, publish_at: datetime | None, expires_at: datetime | None,
             requires_ack: bool, ack_deadline: datetime | None, links: list, now: datetime) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not 5 <= len((title or "").strip()) <= 200:
        errors.append({"field": "title", "code": "TITLE_LENGTH"})
    if not 1 <= len((body or "").strip()) <= 10000:
        errors.append({"field": "body", "code": "BODY_LENGTH"})
    if category not in CATEGORIES:
        errors.append({"field": "category", "code": "CATEGORY_UNKNOWN"})
    if priority not in PRIORITIES:
        errors.append({"field": "priority", "code": "PRIORITY_UNKNOWN"})
    start = publish_at or now
    if expires_at is None or not start < expires_at <= start + timedelta(days=365):
        errors.append({"field": "expires_at", "code": "EXPIRY_RANGE"})
    if publish_at is not None and publish_at < now - timedelta(minutes=1):
        errors.append({"field": "publish_at", "code": "PUBLISH_IN_PAST"})
    if requires_ack and (ack_deadline is None or (expires_at is not None and ack_deadline > expires_at) or ack_deadline <= start):
        errors.append({"field": "ack_deadline", "code": "ACK_DEADLINE"})
    if not requires_ack and ack_deadline is not None:
        errors.append({"field": "ack_deadline", "code": "ACK_DEADLINE"})
    if len(links or []) > MAX_LINKS:
        errors.append({"field": "links", "code": "LINKS_TOO_MANY"})
    for index, link in enumerate(links or []):
        if not isinstance(link, dict) or not link.get("label") or ("url" in link) == ("knowledge_version_id" in link):
            errors.append({"field": f"links[{index}]", "code": "LINK_SHAPE"})
        elif "url" in link and not _https(link["url"]):
            errors.append({"field": f"links[{index}]", "code": "LINK_SCHEME"})
    return errors


def needs_second_approval(*, flag_on: bool, spec: AudienceSpec, estimated: int, priority: str) -> bool:
    return flag_on and (spec.has_everyone_group() or estimated > LARGE_AUDIENCE or priority == "URGENT")


def is_public(spec: AudienceSpec) -> bool:
    """Public enough to enter the shared knowledge store: everyone, with guests."""
    return spec.include_guests and spec.has_everyone_group()


def group_small_counts(counts: dict[str, int], minimum: int = MIN_GROUP_FOR_STATS) -> dict[str, int]:
    """Counts below the minimum are merged into 'khác' so a small group cannot be singled out."""
    out: dict[str, int] = {}
    other = 0
    for key, n in counts.items():
        if n >= minimum:
            out[key] = n
        else:
            other += n
    if other:
        out["khác"] = other
    return out


@dataclass
class AnnouncementDraft:
    title: str
    body: str
    category: str = "ACADEMIC"
    priority: str = "NORMAL"
    issuer_unit: str = ""
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    requires_ack: bool = False
    ack_deadline: datetime | None = None
    source_ref: dict = field(default_factory=dict)
    links: list = field(default_factory=list)
