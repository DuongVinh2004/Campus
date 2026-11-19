"""OIDC token verification against a simulated provider, including the attacks."""
import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).parent))
from fake_oidc_provider import CLIENT_ID, ISSUER, REDIRECT, FakeProvider  # noqa: E402

from campus247.infrastructure.identity.oidc import OidcClient, OidcConfig, OidcError, new_pkce  # noqa: E402


def config(**over):
    return OidcConfig(issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT, **over)


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def oidc(provider):
    return OidcClient(config(), provider.client())


async def fails(oidc, token, code, nonce="n-1"):
    with pytest.raises(OidcError) as failure:
        await oidc.verify_id_token(token, nonce=nonce)
    assert failure.value.code == code


@pytest.mark.asyncio
async def test_a_good_token_returns_its_claims(oidc, provider):
    claims = await oidc.verify_id_token(provider.sign(), nonce="n-1")
    assert claims["sub"] == "user-123" and claims["student_id"] == "20215678"


@pytest.mark.asyncio
async def test_an_ec_signed_token_is_accepted_too(oidc, provider):
    provider.published.append("ec-1")
    assert (await oidc.verify_id_token(provider.sign(alg="ES256", kid="ec-1"), nonce="n-1"))["sub"] == "user-123"


@pytest.mark.asyncio
@pytest.mark.parametrize(("over", "code"), [
    ({"iss": "https://evil.example/realms/huce"}, "TOKEN_ISSUER_MISMATCH"),
    ({"aud": "someone-else"}, "TOKEN_AUDIENCE_MISMATCH"),
    ({"exp": 1}, "TOKEN_EXPIRED"),
    ({"nonce": "n-other"}, "TOKEN_NONCE_MISMATCH"),
    ({"nonce": None}, "TOKEN_NONCE_MISMATCH"),
    ({"sub": None}, "TOKEN_INVALID"),
    ({"exp": None}, "TOKEN_INVALID"),
    ({"aud": [CLIENT_ID, "other"]}, "TOKEN_AUTHORIZED_PARTY_MISMATCH"),
])
async def test_claim_failures_are_refused_with_a_fixed_code(oidc, provider, over, code):
    await fails(oidc, provider.sign(**over), code)


@pytest.mark.asyncio
async def test_two_audiences_are_fine_when_the_authorized_party_is_us(oidc, provider):
    assert await oidc.verify_id_token(provider.sign(aud=[CLIENT_ID, "other"], azp=CLIENT_ID), nonce="n-1")


@pytest.mark.asyncio
async def test_a_token_from_the_future_beyond_the_leeway_is_refused(oidc, provider):
    import time
    await fails(oidc, provider.sign(iat=int(time.time()) + 3600, nbf=int(time.time()) + 3600), "TOKEN_INVALID")


@pytest.mark.asyncio
async def test_a_tampered_payload_fails_the_signature_check(oidc, provider):
    header, payload, signature = provider.sign().split(".")
    forged = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    forged["sub"] = "admin"
    new_payload = base64.urlsafe_b64encode(json.dumps(forged).encode()).rstrip(b"=").decode()
    await fails(oidc, f"{header}.{new_payload}.{signature}", "TOKEN_SIGNATURE_INVALID")


@pytest.mark.asyncio
async def test_a_token_signed_with_another_key_is_refused(oidc, provider):
    provider.add_rsa_key("kid-1-evil", publish=False)
    await fails(oidc, provider.sign(kid="kid-1", key=provider.rsa["kid-1-evil"]), "TOKEN_SIGNATURE_INVALID")


@pytest.mark.asyncio
async def test_alg_none_is_refused_before_any_key_is_fetched(oidc, provider):
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(provider.claims()).encode()).rstrip(b"=").decode()
    await fails(oidc, f"{header}.{payload}.", "TOKEN_ALGORITHM_NOT_ALLOWED")
    assert provider.requests == []


@pytest.mark.asyncio
async def test_the_hmac_confusion_attack_is_refused(oidc, provider):
    """The classic attack: sign with HS256 using the provider's public key as the secret. PyJWT refuses to build that token, so craft it by hand."""
    public_pem = provider.rsa["kid-1"].public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "kid": "kid-1", "typ": "JWT"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps(provider.claims()).encode()).rstrip(b"=")
    signature = base64.urlsafe_b64encode(hmac.new(public_pem, header + b"." + payload, hashlib.sha256).digest()).rstrip(b"=")
    await fails(oidc, (header + b"." + payload + b"." + signature).decode(), "TOKEN_ALGORITHM_NOT_ALLOWED")


@pytest.mark.asyncio
async def test_garbage_is_malformed(oidc):
    await fails(oidc, "not-a-jwt", "TOKEN_MALFORMED")
    await fails(oidc, "", "TOKEN_MALFORMED")


@pytest.mark.asyncio
async def test_a_rotated_key_is_found_after_one_refresh_but_not_more_than_once_a_minute(provider):
    now = [1000.0]
    oidc = OidcClient(config(), provider.client(), clock=lambda: now[0])
    await oidc.verify_id_token(provider.sign(), nonce="n-1")                      # first fetch of the key set
    provider.add_rsa_key("kid-2")
    now[0] += 61
    assert await oidc.verify_id_token(provider.sign(kid="kid-2"), nonce="n-1")    # unknown kid, set is old enough: refreshed
    assert provider.count("/certs") == 2
    provider.add_rsa_key("kid-3", publish=False)
    for _ in range(5):                                                             # an attacker cannot make us refetch on every request
        await fails(oidc, provider.sign(kid="kid-3"), "SIGNING_KEY_UNKNOWN")
    assert provider.count("/certs") == 2
    now[0] += 61
    await fails(oidc, provider.sign(kid="kid-3"), "SIGNING_KEY_UNKNOWN")
    assert provider.count("/certs") == 3


@pytest.mark.asyncio
async def test_discovery_must_name_the_configured_issuer(provider):
    provider.discovery_override = provider.metadata() | {"issuer": "https://other.example/realms/x"}
    with pytest.raises(OidcError) as failure:
        await OidcClient(config(), provider.client()).discovery()
    assert failure.value.code == "ISSUER_MISMATCH"


@pytest.mark.asyncio
async def test_discovery_endpoints_must_be_https(provider):
    provider.discovery_override = provider.metadata() | {"token_endpoint": "http://idp.example.edu.vn/token"}
    with pytest.raises(OidcError) as failure:
        await OidcClient(config(), provider.client()).discovery()
    assert failure.value.code == "PROVIDER_METADATA_INVALID"


def test_an_http_issuer_is_refused_unless_it_is_the_local_test_setting():
    with pytest.raises(OidcError) as failure:
        OidcClient(OidcConfig(issuer="http://idp.example.edu.vn", client_id="c", redirect_uri=REDIRECT), FakeProvider().client())
    assert failure.value.code == "CONFIG_INSECURE_ISSUER"
    OidcClient(OidcConfig(issuer="http://localhost:8080/realms/x", client_id="c", redirect_uri=REDIRECT, allow_insecure_localhost=True), FakeProvider().client())


@pytest.mark.asyncio
async def test_a_provider_that_is_down_is_a_fixed_code_not_an_exception(provider):
    provider.down = True
    with pytest.raises(OidcError) as failure:
        await OidcClient(config(), provider.client()).discovery()
    assert failure.value.code == "PROVIDER_UNREACHABLE"


@pytest.mark.asyncio
async def test_discovery_is_cached_for_an_hour(provider):
    now = [0.0]
    oidc = OidcClient(config(), provider.client(), clock=lambda: now[0])
    await oidc.discovery()
    await oidc.discovery()
    assert provider.count("openid-configuration") == 1
    now[0] += 3601
    await oidc.discovery()
    assert provider.count("openid-configuration") == 2


@pytest.mark.asyncio
async def test_the_authorization_url_carries_pkce_state_nonce_and_the_redirect(oidc):
    verifier, challenge = new_pkce()
    url = await oidc.authorization_url(state="s1", nonce="n1", code_challenge=challenge)
    query = {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}
    assert url.startswith(ISSUER + "/protocol/openid-connect/auth?")
    assert query["response_type"] == "code" and query["client_id"] == CLIENT_ID and query["redirect_uri"] == REDIRECT
    assert query["state"] == "s1" and query["nonce"] == "n1" and query["code_challenge_method"] == "S256" and query["scope"] == "openid profile email"
    assert query["code_challenge"] == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def test_pkce_values_are_long_random_and_url_safe():
    first, second = new_pkce(), new_pkce()
    assert first != second and len(first[0]) >= 43 and all(c.isalnum() or c in "-_" for c in first[0] + first[1])


@pytest.mark.asyncio
async def test_a_code_can_be_exchanged_once_with_the_right_verifier(oidc, provider):
    verifier, _ = new_pkce()
    provider.issued_codes["code-1"] = {"verifier": verifier, "id_token": provider.sign()}
    body = await oidc.exchange_code("code-1", verifier)
    assert (await oidc.verify_id_token(body["id_token"], nonce="n-1"))["sub"] == "user-123"
    with pytest.raises(OidcError) as replay:
        await oidc.exchange_code("code-1", verifier)
    assert replay.value.code == "TOKEN_EXCHANGE_FAILED"
    provider.issued_codes["code-2"] = {"verifier": verifier, "id_token": provider.sign()}
    with pytest.raises(OidcError):
        await oidc.exchange_code("code-2", "a-different-verifier")


def test_config_from_a_dict_reads_the_secret_from_a_file_and_rejects_missing_fields():
    data = {"issuer": ISSUER, "client_id": CLIENT_ID, "redirect_uri": REDIRECT, "client_secret_file": "/secrets/x", "role_map": {"sinhvien": "STUDENT"}}
    built = OidcConfig.from_dict(data, secret_reader=lambda path: "s3cret" if path == "/secrets/x" else "")
    assert built.client_secret == "s3cret" and built.role_map == {"sinhvien": "STUDENT"} and built.claims["student_code"] == "student_id"
    assert built.jit_provisioning is False
    with pytest.raises(OidcError):
        OidcConfig.from_dict({"issuer": ISSUER})
    with pytest.raises(OidcError):
        OidcConfig.from_dict(data)  # a secret file is named but nothing can read it
