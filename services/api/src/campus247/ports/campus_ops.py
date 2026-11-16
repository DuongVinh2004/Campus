"""Contract between the campus operations rules and their durable store.

The business rules (rooms, timetable, notifications, tickets) live in the application layer and only know this
port; the SQLite adapter in the infrastructure layer implements it.
"""
from __future__ import annotations

from collections.abc import Iterable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

ICT = timezone(timedelta(hours=7))


class OpsError(Exception):
    """Business rule failure carrying an HTTP status and a stable code."""

    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status, self.code, self.detail = status, code, detail


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def uuid7() -> str:
    from campus247.domain.shared.values import generate_uuid7
    return generate_uuid7()


class CampusOpsStorePort(Protocol):
    """Reads, short IMMEDIATE transactions, and the two append-only side effects every write records."""

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]: ...

    def one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None: ...

    def tx(self) -> AbstractContextManager[Any]: ...

    def audit(self, connection: Any, actor: str, action: str, resource: str, detail: dict[str, Any] | None = None) -> None: ...

    def notify(self, connection: Any, recipient: str, kind: str, title: str, body: str, link: str = "") -> None: ...
