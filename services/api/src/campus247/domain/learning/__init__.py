"""Learning material invariants and transport-independent errors."""
from dataclasses import dataclass
import re


class LearningError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail
        super().__init__(detail)


def require(condition: bool, status: int = 404, code: str = "RESOURCE_NOT_FOUND", detail: str = "Không tìm thấy học liệu được phép truy cập."):
    if not condition:
        raise LearningError(status, code, detail)


@dataclass(frozen=True)
class ByteSelection:
    status: int
    start: int
    stop: int
    content_range: str | None

    @property
    def length(self):
        return self.stop - self.start


def select_bytes(size: int, value: str | None, *, method="GET", if_range=None, etag=None):
    require(isinstance(size, int) and not isinstance(size, bool) and size >= 0, 503, "INVALID_BLOB", "Không đọc được kích thước tài liệu.")
    whole = ByteSelection(200, 0, size, None)
    if method.upper() != "GET" or value is None:
        return whole
    if if_range is not None and (not etag or not etag.startswith('"') or if_range != etag):
        return whole
    if len(value) > 256:
        return whole
    match = re.fullmatch(r"bytes=([0-9]*)-([0-9]*)", value.strip(), re.I)
    if not match or not any(match.groups()):
        return whole
    first, last = match.groups()
    if first:
        start, end = int(first), int(last) if last else size - 1
        if last and start > end:
            return whole
        if start >= size:
            return ByteSelection(416, 0, 0, f"bytes */{size}")
        stop = min(end + 1, size)
    else:
        suffix = int(last)
        if not suffix or not size:
            return ByteSelection(416, 0, 0, f"bytes */{size}")
        start, stop = max(0, size - suffix), size
    return ByteSelection(206, start, stop, f"bytes {start}-{stop - 1}/{size}")
