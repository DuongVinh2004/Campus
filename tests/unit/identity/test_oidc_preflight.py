import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
from fake_oidc_provider import CLIENT_ID, ISSUER, REDIRECT, FakeProvider  # noqa: E402

spec = importlib.util.spec_from_file_location("oidc_preflight", ROOT / "scripts/oidc_preflight.py")
preflight = importlib.util.module_from_spec(spec)
sys.modules["oidc_preflight"] = preflight
spec.loader.exec_module(preflight)


def write(tmp_path, **over):
    data = {"issuer": ISSUER, "client_id": CLIENT_ID, "redirect_uri": REDIRECT, "role_map": {"sinhvien": "STUDENT"}} | over
    path = tmp_path / "oidc.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def run(path, provider):
    return asyncio.run(preflight.run(path, provider.client()))


def by_status(results, status):
    return [name for s, name, _ in results if s == status]


def test_a_good_configuration_and_provider_pass_everything(tmp_path):
    results = run(write(tmp_path), FakeProvider())
    assert by_status(results, "FAIL") == [] and any("discovery document" in name for name in by_status(results, "PASS"))
    assert any("no client secret" in name for name in by_status(results, "WARN"))


def test_missing_fields_and_unreadable_files_fail_before_any_network_call(tmp_path):
    provider = FakeProvider()
    assert by_status(run(tmp_path / "missing.json", provider), "FAIL") == ["configuration file can be read"]
    path = tmp_path / "oidc.json"
    path.write_text(json.dumps({"issuer": ISSUER}), encoding="utf-8")
    assert by_status(run(path, provider), "FAIL") == ["configuration is complete"] and provider.requests == []


def test_a_role_map_granting_admin_fails(tmp_path):
    assert any("role configuration" in name for name in by_status(run(write(tmp_path, role_map={"quantri": "SYSTEM_ADMIN"}), FakeProvider()), "FAIL"))


def test_risky_but_legal_settings_warn(tmp_path):
    results = run(write(tmp_path, redirect_uri="http://localhost/cb", jit_provisioning=True, role_map={}), FakeProvider())
    warnings = " | ".join(by_status(results, "WARN"))
    assert "not https" in warnings and "JIT" in warnings and "role_map is empty" in warnings


def test_a_provider_without_pkce_or_code_flow_or_keys_fails(tmp_path):
    provider = FakeProvider()
    provider.discovery_override = provider.metadata() | {"code_challenge_methods_supported": ["plain"], "response_types_supported": ["token"],
                                                         "id_token_signing_alg_values_supported": ["HS256"]}
    provider.published.clear()
    failed = by_status(run(write(tmp_path), provider), "FAIL")
    assert {"provider supports PKCE S256", "provider supports the authorization code flow", "provider signs ID tokens with RS256 or ES256",
            "key set has at least one signing key"} <= set(failed)


def test_an_unreachable_provider_is_one_failure_with_a_code(tmp_path):
    provider = FakeProvider()
    provider.down = True
    results = run(write(tmp_path), provider)
    assert [(s, d) for s, n, d in results if s == "FAIL"] == [("FAIL", "PROVIDER_UNREACHABLE")]


def test_the_report_never_contains_the_secret(tmp_path, capsys):
    secret = tmp_path / "secret.txt"
    secret.write_text("SUPER-SECRET-VALUE", encoding="utf-8")
    path = write(tmp_path, client_secret_file=str(secret))
    results = run(path, FakeProvider())
    assert "SUPER-SECRET-VALUE" not in json.dumps(results) and not any("no client secret" in n for n in by_status(results, "WARN"))
