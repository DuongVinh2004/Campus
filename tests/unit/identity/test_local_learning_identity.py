"""Role and signature boundaries for separately provisioned learning accounts."""
import base64
import hashlib
import json
from datetime import UTC, datetime

import pytest

from campus247.infrastructure.identity.local_learning import ISSUER, LocalLearningIdentityAdapter
from campus247.ports.identity import IdentityRole

TENANT = "019a0000-0000-7000-8000-000000000001"
SUBJECT = "019a0000-0000-7000-8000-000000000002"


@pytest.fixture
def adapter(tmp_path):
    path = tmp_path / "identity.json"
    salt = bytes(range(16))
    path.write_text(json.dumps({"schema": "local-learning-v1", "tenant": TENANT, "issuer": ISSUER,
        "university_identity_verified": False, "signing_key": "a1" * 32,
        "accounts": [{"username": "teacher", "subject_id": SUBJECT, "role": "LECTURER",
            "display_name": "Synthetic teacher", "is_synthetic": True, "salt": salt.hex(),
            "password_hash": hashlib.scrypt(b"test-password", salt=salt, n=16384, r=8, p=1).hex()}]}), encoding="utf-8")
    return LocalLearningIdentityAdapter(path, TENANT)


def test_authenticated_role_resolves_from_trusted_directory(adapter):
    actor = adapter.resolve_token(adapter.authenticate("teacher", "test-password"))
    assert actor.roles == (IdentityRole.LECTURER,)
    assert actor.tenant_id == TENANT and actor.is_synthetic
    assert actor.expires_at > datetime.now(UTC)
    assert set(adapter.public_directory()[0]) == {"subject_id", "display_name", "roles", "is_synthetic"}


def test_untrusted_claim_change_fails_signature(adapter):
    token = adapter.authenticate("teacher", "test-password")
    encoded, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(encoded))
    claims["sub"] = TENANT
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode() + "." + signature
    with pytest.raises(ValueError):
        adapter.resolve_token(forged)


def test_wrong_tenant_and_password_fail_closed(adapter):
    with pytest.raises(ValueError):
        LocalLearningIdentityAdapter(adapter.path, SUBJECT).directory()
    with pytest.raises(ValueError):
        adapter.authenticate("teacher", "incorrect")


def test_directory_role_never_taken_from_token(adapter):
    token = adapter.authenticate("teacher", "test-password")
    directory = json.loads(adapter.path.read_text(encoding="utf-8"))
    directory["accounts"][0]["role"] = "SYSTEM_ADMIN"
    adapter.path.write_text(json.dumps(directory), encoding="utf-8")
    assert adapter.resolve_token(token).roles == (IdentityRole.SYSTEM_ADMIN,)


def test_failed_logins_are_rate_limited(adapter):
    for _ in range(5):
        with pytest.raises(ValueError, match="credentials"):
            adapter.authenticate("teacher", "incorrect")
    with pytest.raises(ValueError, match="rate limited"):
        adapter.authenticate("teacher", "test-password")


def test_existing_student_can_be_enrolled_without_exposing_secrets(adapter, tmp_path):
    from types import SimpleNamespace
    from campus247.infrastructure.identity.local_student import LocalCampusIdentityAdapter
    marker = tmp_path / "existing-student.json"
    marker.write_text("retained test marker", encoding="utf-8")
    student = SimpleNamespace(path=marker, directory=lambda: {
        "username": "existing-student", "subject_id": TENANT, "signing_key": "must-never-leak"})
    owner = SimpleNamespace(directory=lambda: {"username": "existing-owner"})
    combined = LocalCampusIdentityAdapter(owner, student, adapter)
    rows = combined.learning_directory()
    assert len(rows) == 2
    assert all(set(row) == {"subject_id", "display_name", "roles", "is_synthetic"} for row in rows)
    assert rows[-1]["subject_id"] == TENANT and rows[-1]["roles"] == ["STUDENT"]
    assert marker.read_text(encoding="utf-8") == "retained test marker"
