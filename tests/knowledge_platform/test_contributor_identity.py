"""Contributor principal: provisioned by the owner, gets only the contributor role, cannot act as an administrator."""
import hashlib
import json
import secrets
import sys
from datetime import UTC, datetime, timedelta

import pytest

from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import PlatformError
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.local_owner import ISSUER, LocalOwnerIdentityAdapter
from campus247.ports.identity import IdentityContext, IdentityRole

from .conftest import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from provision_knowledge_contributor import provision  # noqa: E402


def identity_file(directory):
    salt = secrets.token_bytes(16)
    path = directory / "identity.json"
    value = {"tenant": "t", "issuer": ISSUER, "owner_id": generate_uuid7(), "agent_id": generate_uuid7(), "username": "owner",
             "salt": salt.hex(), "signing_key": secrets.token_hex(32),
             "password_hash": hashlib.scrypt(b"owner-pass", salt=salt, n=16384, r=8, p=1).hex()}
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_provisioned_contributor_logs_in_with_contributor_role_only(retained_directory):
    path = identity_file(retained_directory)
    credentials = provision(path, "dong-gop-01", "Cán bộ đóng góp")
    secret = json.loads(credentials.read_text(encoding="utf-8"))
    adapter = LocalOwnerIdentityAdapter(path, "t")
    actor = adapter.resolve_token(adapter.authenticate(secret["username"], secret["password"]))
    assert actor.roles == (IdentityRole.KNOWLEDGE_CONTRIBUTOR,) and actor.display_name == "Cán bộ đóng góp"
    owner = adapter.resolve_token(adapter.authenticate("owner", "owner-pass"))
    assert owner.roles == (IdentityRole.KNOWLEDGE_ADMIN,) and owner.subject_id != actor.subject_id
    with pytest.raises(ValueError, match="Invalid credentials"):
        adapter.authenticate("dong-gop-01", "wrong")


def test_provision_never_changes_existing_principals_and_keeps_a_backup(retained_directory):
    path = identity_file(retained_directory)
    before = json.loads(path.read_text(encoding="utf-8"))
    provision(path, "dong-gop-02", "A")
    after = json.loads(path.read_text(encoding="utf-8"))
    assert {k: after[k] for k in before} == before and len(after["contributors"]) == 1
    assert list(retained_directory.glob("identity.json.bak-*"))
    with pytest.raises(ValueError, match="already exists"):
        provision(path, "dong-gop-02", "B")
    with pytest.raises(ValueError, match="already exists"):
        provision(path, "owner", "B")


def actor(*roles):
    at = datetime.now(UTC)
    return IdentityContext(generate_uuid7(), "x", "test", roles, "X", at, at + timedelta(hours=1), tenant_id="t", session_id="s",
                           student_code="S1" if IdentityRole.STUDENT in roles else None)


def test_gates_contributor_may_add_but_not_administer():
    from types import SimpleNamespace
    platform = KnowledgePlatform(SimpleNamespace(tenant="t"), None, None)
    contributor = actor(IdentityRole.KNOWLEDGE_CONTRIBUTOR)
    platform.contributor(contributor)
    with pytest.raises(PlatformError) as error:
        platform.admin(contributor)
    assert error.value.status == 403
    for roles in ((IdentityRole.KNOWLEDGE_ADMIN,), (IdentityRole.SYSTEM_ADMIN,)):
        platform.contributor(actor(*roles))
        platform.admin(actor(*roles))
    for roles in ((IdentityRole.STUDENT,), (IdentityRole.SUPPORT_OFFICER,)):
        with pytest.raises(PlatformError):
            platform.contributor(actor(*roles))
    assert platform.is_admin(actor(IdentityRole.KNOWLEDGE_ADMIN)) and not platform.is_admin(contributor)
