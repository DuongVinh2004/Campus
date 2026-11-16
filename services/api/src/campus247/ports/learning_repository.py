"""Atomic tenant aggregate repository port, including publication and outbox."""
from typing import Protocol

COLLECTIONS = ("terms", "courses", "offerings", "members", "sessions", "materials", "blobs", "links", "versions", "uploads", "reader_states", "bookmarks", "previews", "receipts", "notifications", "audit", "jobs", "outbox", "annotations", "questions", "replies", "reading_instructions", "presentations")


def empty_state():
    return {key: {} for key in COLLECTIONS}


class LearningRepository(Protocol):
    def transaction(self): ...
