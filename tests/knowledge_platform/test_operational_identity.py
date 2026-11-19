import hashlib
import json
import secrets

import pytest

from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.local_owner import ISSUER, LocalOwnerIdentityAdapter
from campus247.ports.identity import IdentityRole


def test_owner_authentication_scope_tampering_and_rate_limit(retained_directory):
    salt = secrets.token_bytes(16)
    path = retained_directory / "identity.json"
    value = {"tenant":"test-owner","issuer":ISSUER,"owner_id":generate_uuid7(),"agent_id":generate_uuid7(),
             "username":"owner","salt":salt.hex(),"signing_key":secrets.token_hex(32),
             "password_hash":hashlib.scrypt(b"test-password",salt=salt,n=16384,r=8,p=1).hex()}
    with path.open("x",encoding="utf-8") as stream:
        json.dump(value,stream)
    adapter=LocalOwnerIdentityAdapter(path,"test-owner")
    token=adapter.authenticate("owner","test-password")
    actor=adapter.resolve_token(token)
    assert actor.subject_id==value["owner_id"] and not actor.is_synthetic
    assert actor.issuer==ISSUER and actor.roles==(IdentityRole.KNOWLEDGE_ADMIN,)
    assert adapter.resolve_token(adapter.mint_token(value["agent_id"])).subject_id != actor.subject_id
    with pytest.raises(ValueError):
        adapter.resolve_token(token.split(".")[0]+".AAAAAAAA")
    with pytest.raises(ValueError):
        LocalOwnerIdentityAdapter(path,"another-tenant").resolve_token(token)
    with pytest.raises(ValueError):
        adapter.resolve_token(adapter.mint_token(value["owner_id"],-1))
    for _ in range(5):
        with pytest.raises(ValueError,match="Invalid credentials"):
            adapter.authenticate("owner","wrong")
    with pytest.raises(ValueError,match="rate limited"):
        adapter.authenticate("owner","test-password")
