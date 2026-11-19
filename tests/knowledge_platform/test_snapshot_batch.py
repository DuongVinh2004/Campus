import asyncio
import json
from types import SimpleNamespace
from uuid import UUID

import pytest

from campus247.application.knowledge.platform_models import PlatformError
from campus247.application.knowledge.source_snapshot import read_snapshot, read_release_snapshots, PROCESSOR
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage
from .conftest import ROOT
from .test_source_snapshot import fixture, NOW


def test_batch_is_equivalent_and_still_checks_each_payload_and_tenant(retained_directory):
    async def run():
        storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
        rendition, extracted = fixture()
        source = storage.write_json(json.dumps(extracted, ensure_ascii=False).encode(), "source-extraction")
        rendition.update(source_extraction_id=source.id, source_extraction_sha256=source.sha256)
        saved = storage.write_json(json.dumps(rendition, ensure_ascii=False).encode(), "rendition")
        rows = {UUID(a.id): {**a.__dict__, "id": UUID(a.id), "tenant_id": "scope-one"} for a in (source, saved)}
        class Conn:
            def __init__(self): self.selects = 0
            async def fetch(self, sql, identifiers, tenant):
                self.selects += 1
                return [rows[UUID(str(i))] for i in identifiers if UUID(str(i)) in rows and rows[UUID(str(i))]["tenant_id"] == tenant]
            async def fetchrow(self, sql, identifier, tenant):
                self.selects += 1
                row = rows.get(UUID(str(identifier)))
                return row if row and row["tenant_id"] == tenant else None
        platform = SimpleNamespace(repo=SimpleNamespace(tenant="scope-one"), storage=storage)
        version = {"version_id": UUID(saved.id), "processor_profile": PROCESSOR, "rendition_id": UUID(saved.id),
            "rendition_sha256": saved.sha256, "original_sha256": "a"*64, "effective_from": NOW}
        conn = Conn()
        expected = await read_snapshot(platform, conn, version)
        conn.selects = 0
        result = await read_release_snapshots(platform, conn, [version])
        assert result[version["version_id"]] == expected and conn.selects == 2
        with pytest.raises(PlatformError, match="ARTIFACT_INTEGRITY"):
            await read_release_snapshots(platform, conn, [{**version, "rendition_sha256": "f"*64}])
        wrong_scope = SimpleNamespace(repo=SimpleNamespace(tenant="scope-two"), storage=storage)
        with pytest.raises(PlatformError, match="ARTIFACT_INTEGRITY"):
            await read_release_snapshots(wrong_scope, conn, [version])
        # A new corrupt record is added; no retained file is overwritten to test the guard.
        altered = storage.write_json(b'{"not":"the verified source"}', "corrupt-test-fixture")
        rows[UUID(source.id)] = {**altered.__dict__, "id": UUID(source.id), "tenant_id": "scope-one"}
        with pytest.raises(PlatformError, match="ARTIFACT_INTEGRITY"):
            await read_release_snapshots(platform, conn, [version])
    asyncio.run(run())
