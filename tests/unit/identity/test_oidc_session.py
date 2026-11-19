import base64
import json
import os
import stat
import time

import pytest

from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.oidc_session import ISSUER, MAX_TTL_S, OidcSessionAdapter, load_or_create_key
from campus247.ports.identity import IdentityRole

KEY = b"k" * 32


def account(**over):
    return {"subject_id": generate_uuid7(), "roles": (IdentityRole.STUDENT, IdentityRole.KNOWLEDGE_ADMIN), "display_name": "Nguyễn Văn A",
            "external_subject": "user-123", "student_code": "20215678"} | over


def forge(adapter, **claims):
    """A token signed with the right key but with arbitrary claims, to test the claim checks themselves."""
    now = int(time.time())
    base = {"sub": generate_uuid7(), "iss": ISSUER, "tenant": adapter.tenant, "iat": now, "exp": now + 600, "jti": "j", "roles": ["LECTURER"],
            "name": "x", "ext": "e", "code": None}
    encoded = base64.urlsafe_b64encode(json.dumps(base | claims, sort_keys=True).encode()).decode()
    return encoded + "." + adapter._sign(encoded)


def test_a_minted_session_resolves_to_the_same_person_and_roles():
    adapter = OidcSessionAdapter(KEY, "t")
    who = account()
    identity = adapter.resolve_token(adapter.mint(who))
    assert identity.subject_id == who["subject_id"] and identity.roles == who["roles"] and identity.student_code == "20215678"
    assert identity.display_name == "Nguyễn Văn A" and identity.tenant_id == "t" and identity.is_synthetic is False and identity.session_id
    assert identity.issuer == ISSUER and identity.expires_at > identity.auth_time


def test_every_session_has_its_own_id_for_revocation():
    adapter = OidcSessionAdapter(KEY, "t")
    ids = {adapter.resolve_token(adapter.mint(account())).session_id for _ in range(5)}
    assert len(ids) == 5


def test_the_lifetime_is_never_more_than_an_hour():
    adapter = OidcSessionAdapter(KEY, "t")
    identity = adapter.resolve_token(adapter.mint(account(), ttl_s=10 * 3600))
    assert (identity.expires_at - identity.auth_time).total_seconds() <= MAX_TTL_S


def test_a_changed_payload_a_wrong_key_and_malformed_tokens_are_refused():
    adapter = OidcSessionAdapter(KEY, "t")
    token = adapter.mint(account(roles=(IdentityRole.STUDENT,)))
    payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload))
    claims["roles"] = ["SYSTEM_ADMIN"]
    forged = base64.urlsafe_b64encode(json.dumps(claims, sort_keys=True).encode()).decode() + "." + signature
    for bad in (forged, token + "x", payload, "", "a.b.c", "x" * 5000, None):
        with pytest.raises(ValueError):
            adapter.resolve_token(bad)
    with pytest.raises(ValueError):
        OidcSessionAdapter(b"z" * 32, "t").resolve_token(token)


def test_claims_are_checked_even_when_the_signature_is_right():
    adapter = OidcSessionAdapter(KEY, "t")
    now = int(time.time())
    adapter.resolve_token(forge(adapter))
    for bad in ({"exp": now - 5}, {"iss": "urn:campus247:issuer:local-owner"}, {"tenant": "other"}, {"jti": ""}, {"iat": now + 3600, "exp": now + 4000},
                {"exp": now + 7200}, {"iat": "x"}):
        with pytest.raises(ValueError):
            adapter.resolve_token(forge(adapter, **bad))


def test_a_student_session_without_a_student_code_cannot_be_built():
    adapter = OidcSessionAdapter(KEY, "t")
    with pytest.raises(ValueError):
        adapter.resolve_token(forge(adapter, roles=["STUDENT"], code=None))


def test_a_short_key_is_refused():
    with pytest.raises(ValueError):
        OidcSessionAdapter(b"short", "t")


def test_the_key_file_is_created_once_with_owner_only_permissions(tmp_path):
    path = tmp_path / "oidc-session.key"
    first = load_or_create_key(path)
    assert len(first) == 32 and load_or_create_key(path) == first
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
