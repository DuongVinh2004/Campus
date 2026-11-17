"""Attachment memo behavior using a fake verifier and a deterministic clock."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from campus247.domain.publication import VerifiedPublication
from campus247.infrastructure.knowledge import publication


@pytest.fixture
def memo(monkeypatch):
    publication.clear_attachment_cache()
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(publication, "monotonic", lambda: clock.now)
    result = VerifiedPublication("https://huce.edu.vn/publisher", "https://example.org/file.pdf",
                                 "source", "version", "checksum", "a" * 64, "release")
    verifier = AsyncMock(return_value=result)
    monkeypatch.setattr(publication, "_verify_attachment", verifier)
    yield clock, verifier, result
    publication.clear_attachment_cache()


@pytest.fixture
def platform():
    from pathlib import Path

    return SimpleNamespace(storage=SimpleNamespace(workspace=Path(__file__).resolve().parents[2]),
                           repo=SimpleNamespace(tenant="tenant"))


@pytest.fixture
def row():
    return {"id": "chunk", "content_checksum": "checksum", "document_version_id": "version",
            "canonical_uri": "https://example.org/file.pdf", "source_id": "source",
            "content_text": "retained evidence"}


@pytest.mark.asyncio
async def test_identical_calls_reuse_verification(memo, platform, row):
    clock, verifier, result = memo
    assert await publication.verified_attachment(platform, None, row, "release") is result
    clock.now += 29.999
    assert await publication.verified_attachment(platform, None, dict(row), "release") is result
    verifier.assert_awaited_once_with(platform, None, row, "release")


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["id", "content_checksum", "document_version_id", "canonical_uri",
                                  "source_id", "content_text", "release_id"])
async def test_changed_binding_does_not_reuse_entry(memo, platform, row, field):
    _, verifier, _ = memo
    await publication.verified_attachment(platform, None, row, "release")
    changed = dict(row)
    release = "release"
    if field == "release_id":
        release = "different-release"
    else:
        changed[field] = "different-value"
    await publication.verified_attachment(platform, None, changed, release)
    await publication.verified_attachment(platform, None, row, "release")
    assert verifier.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("negative", [False, True])
async def test_success_and_none_expire_at_ttl(memo, platform, row, negative):
    clock, verifier, result = memo
    if negative:
        verifier.return_value = None
        result = None
    assert await publication.verified_attachment(platform, None, row, "release") is result
    clock.now += 29
    assert await publication.verified_attachment(platform, None, row, "release") is result
    assert verifier.await_count == 1
    clock.now += 1
    renewed = VerifiedPublication("https://huce.edu.vn/new", row["canonical_uri"], "source",
                                "version", "checksum", "b" * 64, "release")
    verifier.return_value = renewed
    assert await publication.verified_attachment(platform, None, row, "release") is renewed
    assert verifier.await_count == 2


@pytest.mark.asyncio
async def test_exception_is_never_cached(memo, platform, row):
    _, verifier, result = memo
    verifier.side_effect = OSError("unreadable retained evidence")
    for _ in range(2):
        with pytest.raises(OSError, match="unreadable retained evidence"):
            await publication.verified_attachment(platform, None, row, "release")
    verifier.side_effect = None
    assert await publication.verified_attachment(platform, None, row, "release") is result
    assert await publication.verified_attachment(platform, None, row, "release") is result
    assert verifier.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("different_root", [False, True])
async def test_platform_instances_do_not_share_entries(memo, platform, row, different_root):
    _, verifier, _ = memo
    root = platform.storage.workspace
    if different_root:
        root = root / "other-workspace"
    other = SimpleNamespace(storage=SimpleNamespace(workspace=root), repo=platform.repo)
    await publication.verified_attachment(platform, None, row, "release")
    await publication.verified_attachment(other, None, row, "release")
    await publication.verified_attachment(platform, None, row, "release")
    assert verifier.await_count == 2


@pytest.mark.asyncio
async def test_clear_forces_reverification(memo, platform, row):
    _, verifier, _ = memo
    await publication.verified_attachment(platform, None, row, "release")
    publication.clear_attachment_cache()
    await publication.verified_attachment(platform, None, row, "release")
    assert verifier.await_count == 2


@pytest.mark.asyncio
async def test_limit_evicts_oldest_insertion_without_refreshing_hits(memo, platform, row):
    _, verifier, _ = memo
    for index in range(512):
        await publication.verified_attachment(platform, None, {**row, "id": str(index)}, "release")
    await publication.verified_attachment(platform, None, {**row, "id": "0"}, "release")
    assert verifier.await_count == 512
    await publication.verified_attachment(platform, None, {**row, "id": "512"}, "release")
    await publication.verified_attachment(platform, None, {**row, "id": "1"}, "release")
    assert verifier.await_count == 513
    assert len(publication._attachment_cache) == 512
    await publication.verified_attachment(platform, None, {**row, "id": "0"}, "release")
    assert verifier.await_count == 514
    assert len(publication._attachment_cache) == 512
