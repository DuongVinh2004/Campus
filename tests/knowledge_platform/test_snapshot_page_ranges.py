"""A continued source clause must retain its witnessed page range."""
from datetime import UTC, datetime

import pytest

from campus247.application.knowledge.platform_models import PlatformError, digest
from campus247.application.knowledge.source_snapshot import PROCESSOR, validate_snapshot


@pytest.mark.parametrize("end,block_end,valid", [(3, 3, True), (2, 3, False), (4, 3, False),
    (1, 1, False), (True, True, False), (None, 3, False)])
def test_source_continuation_range_cannot_be_shortened_extended_or_reversed(end, block_end, valid):
    now = datetime(2026, 10, 25, tzinfo=UTC)
    text = "Điều kiện đầy đủ ở trang trước và phần tiếp nối ở trang sau."
    scope = {"kind": "INFORMATION_SNAPSHOT", "reviewed_at": now.isoformat(),
        "admission_only": True, "legal_effective_from": None}
    block = {"block_id": "0", "page": 2, "page_end": block_end, "text": text}
    page = {"block_id": "0", "page": 2, "page_end": end, "char_start": 0,
        "char_end": len(text), "text": text, "text_sha256": digest(text.encode())}
    extracted = {"original_sha256": "a" * 64, "blocks": [block]}
    rendition = {"processor": PROCESSOR, "original_sha256": "a" * 64,
        "applicability": scope, "issues": [], "pages": [page]}
    if valid:
        assert validate_snapshot(rendition, extracted, original_sha256="a" * 64, effective_from=now) == scope
    else:
        with pytest.raises(PlatformError, match="SOURCE_SPAN_MISMATCH"):
            validate_snapshot(rendition, extracted, original_sha256="a" * 64, effective_from=now)
