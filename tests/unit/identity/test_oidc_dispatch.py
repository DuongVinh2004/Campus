"""The campus identity adapter hands an OIDC-session token to the OIDC session adapter, and only when one is configured."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.local_student import LocalCampusIdentityAdapter
from campus247.infrastructure.identity.oidc_session import OidcSessionAdapter
from campus247.ports.identity import IdentityRole

NOWHERE = SimpleNamespace(path=Path("does-not-exist.json"), directory=lambda: {"username": "owner"})


def account():
    return {"subject_id": generate_uuid7(), "roles": (IdentityRole.LECTURER,), "display_name": "Giảng viên", "external_subject": "lec-1", "student_code": None}


def test_an_oidc_session_resolves_through_the_campus_adapter_once_configured():
    sessions = OidcSessionAdapter(b"k" * 32, "t")
    adapter = LocalCampusIdentityAdapter(NOWHERE, NOWHERE)
    token = sessions.mint(account())
    with pytest.raises(ValueError):
        adapter.resolve_token(token)  # not configured: refused like any unknown issuer
    adapter.oidc = sessions
    assert adapter.resolve_token(token).roles == (IdentityRole.LECTURER,)


def test_a_token_signed_with_another_key_is_still_refused():
    adapter = LocalCampusIdentityAdapter(NOWHERE, NOWHERE)
    adapter.oidc = OidcSessionAdapter(b"k" * 32, "t")
    with pytest.raises(ValueError):
        adapter.resolve_token(OidcSessionAdapter(b"z" * 32, "t").mint(account()))
