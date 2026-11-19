"""An operational session refuses non-https source URIs before touching storage or the database."""
import asyncio
import io
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from starlette.datastructures import Headers, UploadFile

from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import IntakeMetadata, PlatformError
from campus247.domain.shared.values import generate_uuid7
from campus247.ports.identity import IdentityContext, IdentityRole


class Untouched:
    """Storage/repository stand-in: any use proves the check ran too late."""
    tenant = "t"

    def __getattr__(self, name):
        raise AssertionError("storage or repository used before the URI check: " + name)


def platform(operational):
    service = KnowledgePlatform(Untouched(), Untouched(), None)
    service.repo = SimpleNamespace(tenant="t")  # admin() reads only the tenant
    service.operational = operational
    return service


def actor():
    at = datetime.now(UTC)
    return IdentityContext(generate_uuid7(), "editor", "test", (IdentityRole.KNOWLEDGE_ADMIN,), "Editor", at,
                           at + timedelta(hours=1), tenant_id="t", session_id="s")


def metadata(uri):
    return IntakeMetadata(title="Tài liệu thử", owner_unit="Phòng thử", canonical_uri=uri, programs=["PUBLIC"],
                          audiences=["STUDENT"], effective_from=datetime.now(UTC) - timedelta(days=1))


def upload():
    return UploadFile(io.BytesIO(b"noi dung"), filename="a.txt", headers=Headers({"content-type": "text/plain"}))


def test_operational_session_refuses_urn_before_any_storage_use():
    with pytest.raises(PlatformError) as error:
        asyncio.run(platform(True).upload(actor(), metadata("urn:test:abc"), upload(), "key-1"))
    assert error.value.status == 422 and error.value.code == "OPERATIONAL_SOURCE_URI_REQUIRED"


def test_operational_session_lets_https_through_the_uri_check():
    # The stand-in storage then raises: the point is that the URI check did not.
    with pytest.raises(AssertionError):
        asyncio.run(platform(True).upload(actor(), metadata("https://huce.edu.vn/van-ban"), upload(), "key-2"))


def test_local_test_session_still_accepts_urn():
    with pytest.raises(AssertionError):
        asyncio.run(platform(False).upload(actor(), metadata("urn:test:abc"), upload(), "key-3"))
