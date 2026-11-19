from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from campus247.domain.shared.values import is_valid_uuid7


class IdentityRole(StrEnum):
    STUDENT = "STUDENT"
    LECTURER = "LECTURER"
    SUPPORT_OFFICER = "SUPPORT_OFFICER"
    KNOWLEDGE_ADMIN = "KNOWLEDGE_ADMIN"
    # May add documents; every document of this role needs a second person's approval before it is published.
    KNOWLEDGE_CONTRIBUTOR = "KNOWLEDGE_CONTRIBUTOR"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class AccountState(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class IdentityContext:
    subject_id: str
    external_subject: str
    issuer: str
    roles: tuple[IdentityRole, ...]
    display_name: str
    auth_time: datetime
    expires_at: datetime
    email: str | None = None
    tenant_id: str | None = None
    unit_ids: tuple[str, ...] = ()
    account_state: AccountState = AccountState.ACTIVE
    mfa: bool = False
    session_id: str = ""
    is_synthetic: bool = True
    student_code: str | None = None
    faculty_code: str | None = None

    def __post_init__(self) -> None:
        if not is_valid_uuid7(self.subject_id):
            raise ValueError(f"subject_id must be a valid UUIDv7 string, got: {self.subject_id}")
        if self.expires_at <= self.auth_time:
            raise ValueError(f"expires_at ({self.expires_at}) must be after auth_time ({self.auth_time})")
        if IdentityRole.STUDENT in self.roles and not self.student_code:
            raise ValueError("student_code is required when role includes STUDENT")

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_active(self) -> bool:
        return self.account_state == AccountState.ACTIVE

    def has_role(self, role: IdentityRole | str) -> bool:
        target = role.value if isinstance(role, IdentityRole) else str(role)
        return any(r.value == target for r in self.roles)


class IdentityProviderPort(Protocol):
    async def extract_identity(self, token: str) -> IdentityContext:
        ...
