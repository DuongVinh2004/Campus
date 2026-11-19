"""Upload on the real local PostgreSQL with a real ClamAV daemon: the scan receipt lands in the audit record and a hit
never reaches the database.

Opt in like the other live-DB tests: KNOWLEDGE_PLATFORM_LIVE_TESTS=1 (needs the local PostgreSQL the runtime uses).
The daemon is a test-only instance with a harmless marker signature; the daemon the system runs is not touched.
"""
import asyncio
import io
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from starlette.datastructures import Headers, UploadFile

from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import IntakeMetadata, PlatformError
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.knowledge.repository import KnowledgeRepository
from campus247.infrastructure.knowledge.storage import FileKnowledgeStorage
from campus247.infrastructure.scanning.clamd import ClamdScanner
from campus247.ports.identity import IdentityContext, IdentityRole

from .conftest import ROOT

pytestmark = pytest.mark.skipif(os.environ.get("KNOWLEDGE_PLATFORM_LIVE_TESTS") != "1",
                                reason="Explicit task-owned PostgreSQL opt-in required")

sys.path.insert(0, str(ROOT / "tests/learning_entry"))
import test_scan_real_daemon as real  # noqa: E402


@pytest.fixture(scope="module")
def daemon():
    if not real.AVAILABLE:
        pytest.skip("needs the retained ClamAV bundle and a refreshed database")
    base = ROOT / ".tooling" / f"clamd-test-{uuid4().hex[:8]}"
    base.mkdir()
    running = real.Daemon(base)
    try:
        yield running
    finally:
        running.stop()


def upload(name, data):
    return UploadFile(io.BytesIO(data), filename=name, headers=Headers({"content-type": "text/plain"}))


def meta(title):
    return IntakeMetadata(title=title, owner_unit="Đơn vị thử nghiệm", canonical_uri="urn:scan-audit:" + uuid4().hex,
                          programs=["PUBLIC"], audiences=["STUDENT"], effective_from=datetime.now(UTC) - timedelta(days=1))


def test_receipt_is_audited_and_a_hit_is_never_registered(daemon, retained_directory):
    async def main():
        import asyncpg
        from knowledge_platform import connection
        pool = await asyncpg.create_pool(**connection(), min_size=1, max_size=3)
        tenant = "knowledge-scan-" + uuid4().hex[:12]
        try:
            storage = FileKnowledgeStorage(ROOT, retained_directory / "artifacts")
            storage.scanner = ClamdScanner(host="127.0.0.1", port=daemon.port, max_database_age=timedelta(days=30))
            platform = KnowledgePlatform(KnowledgeRepository(pool, tenant), storage, ConfirmationTokenService("scan-audit-test-key"))
            now = datetime.now(UTC)
            admin = IdentityContext(generate_uuid7(), "admin", "test", (IdentityRole.KNOWLEDGE_ADMIN,), "admin", now,
                                    now + timedelta(hours=2), tenant_id=tenant, session_id="s-admin")
            accepted = await platform.upload(admin, meta("Tài liệu sạch"), upload("sach.txt", "Nội dung hợp lệ.\n".encode()), "k-clean")
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT metadata_safe FROM audit_event WHERE action_code='knowledge.upload' AND resource_id=$1",
                                        accepted["version_id"])
            assert len(rows) == 1
            detail = rows[0]["metadata_safe"]
            detail = json.loads(detail) if isinstance(detail, str) else detail
            assert detail["scan"]["result"] == "CLEAN" and detail["scan"]["database_version"].isdigit()
            assert detail["scan"]["sha256"] == accepted["original_sha256"]
            with pytest.raises(PlatformError) as raised:
                await platform.upload(admin, meta("Tài liệu có dấu hiệu"), upload("xau.txt", "Nội dung ".encode() + real.MARKER + b"\n"), "k-bad")
            assert (raised.value.status, raised.value.code) == (422, "FILE_REJECTED")
            async with pool.acquire() as conn:
                versions = await conn.fetchval("SELECT count(*) FROM knowledge_ingest_version WHERE tenant_id=$1", tenant)
                audits = await conn.fetchval("SELECT count(*) FROM audit_event WHERE action_code='knowledge.upload' AND actor_id=$1",
                                             admin.subject_id)
            assert versions == 1 and audits == 1  # the hit created no version, no job and no audit of an accepted upload
        finally:
            await pool.close()

    asyncio.run(main())
