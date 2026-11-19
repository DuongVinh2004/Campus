"""Local student credentials grant public-reader access, never owner authority."""
import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import secrets
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from starlette.responses import JSONResponse

from campus247.application.conversation.messages import ConversationMessageService
from campus247.application.identity.session_service import SessionService
from campus247.application.knowledge.platform import KnowledgePlatform
from campus247.application.knowledge.platform_models import PlatformError
from campus247.domain.shared.values import generate_uuid7
from campus247.infrastructure.identity.local_owner import LocalOwnerIdentityAdapter, ISSUER as OWNER_ISSUER
from campus247.infrastructure.identity.local_student import LocalStudentIdentityAdapter, LocalCampusIdentityAdapter, ISSUER
from campus247.ports.identity import AccountState, IdentityRole
from campus247.presentation.chat import create_chat_router
from campus247.presentation.identity import IdentityMiddleware
from campus247.presentation.knowledge_platform import create_knowledge_platform_router


def setup(path):
    salt = secrets.token_bytes(16)
    common = {"tenant":"local-student-test", "salt":salt.hex(),"signing_key":secrets.token_hex(32),
        "password_hash":hashlib.scrypt(b"test-only-password",salt=salt,n=16384,r=8,p=1).hex()}
    owner = {**common,"issuer":OWNER_ISSUER,"username":"owner","owner_id":generate_uuid7(),"agent_id":generate_uuid7()}
    student = {**common,"schema":"local-student-v1","issuer":ISSUER,"username":"student",
        "subject_id":generate_uuid7(),"student_code":"LOCAL-STUDENT-001","role":"STUDENT",
        "signing_key":secrets.token_hex(32),"university_identity_verified":False}
    for name, value in (("owner.json",owner),("student.json",student)):
        with (path/name).open("x",encoding="utf-8") as stream:
            json.dump(value,stream)
    owner_adapter = LocalOwnerIdentityAdapter(path/"owner.json",common["tenant"])
    student_adapter = LocalStudentIdentityAdapter(path/"student.json",common["tenant"])
    return LocalCampusIdentityAdapter(owner_adapter,student_adapter),student


def signed(claims, key):
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode()
    signature = hmac.new(bytes.fromhex(key),encoded.encode(),hashlib.sha256).digest()
    return encoded+"."+base64.urlsafe_b64encode(signature).decode()


def test_student_password_and_signed_role_binding_cannot_escalate_to_owner(retained_directory):
    adapter, student = setup(retained_directory)
    token = adapter.authenticate("student","test-only-password")
    actor = adapter.resolve_token(token)
    assert actor.roles == (IdentityRole.STUDENT,) and actor.subject_id == student["subject_id"]
    assert actor.issuer == ISSUER and actor.student_code.startswith("LOCAL-STUDENT-")
    assert adapter.resolve_token(adapter.authenticate("owner","test-only-password")).roles == (IdentityRole.KNOWLEDGE_ADMIN,)
    claims = json.loads(base64.urlsafe_b64decode(token.split(".")[0]))
    # Even a client claim signed with the fixture key cannot select a role.
    assert adapter.resolve_token(signed({**claims,"roles":["SYSTEM_ADMIN"]},student["signing_key"])).roles == (IdentityRole.STUDENT,)
    with pytest.raises(ValueError):
        adapter.resolve_token(signed({**claims,"iss":OWNER_ISSUER},student["signing_key"]))
    for change in ({"tenant":"another"},{"sub":generate_uuid7()},{"exp":claims["iat"]-1},
        {"exp":claims["iat"]+7200},{"iat":claims["exp"]+1},{"jti":""},{"iss":"https://sso.huce.invalid"}):
        with pytest.raises(ValueError):
            adapter.resolve_token(signed({**claims,**change},student["signing_key"]))
    for _ in range(5):
        with pytest.raises(ValueError,match="Invalid credentials"):
            adapter.authenticate("student","incorrect")
    with pytest.raises(ValueError,match="rate limited"):
        adapter.authenticate("student","test-only-password")
    # A student's failed attempts do not consume the owner's login limit.
    assert adapter.resolve_token(adapter.authenticate("owner","test-only-password")).has_role(IdentityRole.KNOWLEDGE_ADMIN)


def test_reader_revalidates_tenant_expiry_account_and_role_without_relaxing_admin(retained_directory):
    adapter, _ = setup(retained_directory)
    actor = adapter.resolve_token(adapter.authenticate("student","test-only-password"))
    platform = KnowledgePlatform(SimpleNamespace(tenant=actor.tenant_id),None,None)
    platform.reader(actor)
    with pytest.raises(PlatformError):
        platform.admin(actor)
    for change in ({"tenant_id":"different"},{"session_id":""},{"account_state":AccountState.SUSPENDED},
        {"auth_time":datetime.now(UTC)-timedelta(hours=2),"expires_at":datetime.now(UTC)-timedelta(hours=1)},
        {"roles":(IdentityRole.SUPPORT_OFFICER,)}):
        with pytest.raises(PlatformError):
            platform.reader(replace(actor,**change))


def test_unavailable_student_directory_does_not_block_existing_owner(retained_directory):
    adapter, _ = setup(retained_directory)
    path = retained_directory/"invalid-student.json"
    with path.open("x",encoding="utf-8") as stream:
        json.dump({},stream)
    composite = LocalCampusIdentityAdapter(adapter.owner,LocalStudentIdentityAdapter(path,"local-student-test"))
    token = composite.authenticate("owner","test-only-password")
    assert composite.resolve_token(token).roles == (IdentityRole.KNOWLEDGE_ADMIN,)
    with pytest.raises(ValueError):
        composite.authenticate("student","test-only-password")


def test_student_transport_is_denied_admin_operations_and_other_users_history(retained_directory):
    adapter, _ = setup(retained_directory)
    platform = KnowledgePlatform(SimpleNamespace(tenant="local-student-test"),SimpleNamespace(),None)
    platform.state = AsyncMock(return_value={"test":True})
    app = FastAPI()
    sessions = SessionService()
    app.add_middleware(IdentityMiddleware,adapter=adapter,session_service=sessions)
    @app.exception_handler(PlatformError)
    async def problem(request,error):
        return JSONResponse({"code":error.code},status_code=error.status)
    app.include_router(create_knowledge_platform_router(platform,None,None))
    app.include_router(create_chat_router(ConversationMessageService(),authorize_conversation=platform.reader))
    token = adapter.authenticate("student","test-only-password")
    owner = adapter.authenticate("owner","test-only-password")
    headers = {"Authorization":"Bearer "+token}
    with TestClient(app) as client:
        assert client.get("/v1/knowledge/platform/state",headers=headers).status_code == 403
        platform.state.assert_not_called()
        now = datetime.now(UTC)
        bodies = {"uploads":{},"intakes":{},
            "schedules":{"kind":"URL_REFRESH","target_id":generate_uuid7(),"confirmed":True,
                "not_before":now.isoformat(),"expires_at":(now+timedelta(minutes=10)).isoformat(),
                "interval_seconds":900,"expected_original_sha256":"a"*64},
            "previews":{"operation":"activate","target_id":generate_uuid7(),"expected_generation":0},
            "confirmations":{"preview_id":generate_uuid7(),"confirmation_token":"test-only-invalid-confirmation","confirmed":True}}
        for endpoint, body in bodies.items():
            assert client.post("/v1/knowledge/platform/"+endpoint,json=body,headers=headers).status_code == 403
        assert client.get("/v1/knowledge/platform/state",headers={"Authorization":"Bearer "+owner}).status_code == 200
        own = client.post("/v1/conversations",json={"mode":"temporary"},headers=headers)
        other = client.post("/v1/conversations",json={"mode":"temporary"},headers={"Authorization":"Bearer "+owner})
        assert own.status_code == other.status_code == 201
        assert client.get("/v1/conversations/"+other.json()["id"]+"/messages",headers=headers).status_code == 404
        assert client.get("/v1/conversations/"+own.json()["id"]+"/messages",headers=headers).status_code == 200
        sessions.revoke_session(token)
        assert client.get("/v1/conversations/"+own.json()["id"]+"/messages",headers=headers).status_code == 401
