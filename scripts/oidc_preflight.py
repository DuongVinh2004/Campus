"""Check an OpenID Connect provider configuration before anyone signs in with it. Reads nothing secret and signs nobody in.

  python scripts/oidc_preflight.py --config <config.json> [--secret-file-check]

It reads the configuration, validates it (roles, patterns, https), fetches the provider's discovery document and key set, and prints one
line per check with PASS / FAIL / WARN. The exit code is 0 only when no check failed. Output never contains the client secret, a token
or a claim value. This is the first thing to run once the university has handed over the provider's details; it does not prove a
sign-in works (that needs a real user and the registered redirect address).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))

import httpx  # noqa: E402

from campus247.infrastructure.identity.oidc import OidcClient, OidcConfig, OidcError  # noqa: E402
from campus247.infrastructure.identity.oidc_accounts import validate_config  # noqa: E402


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


async def run(config_path: Path, http: httpx.AsyncClient | None = None) -> list[tuple[str, str, str]]:
    results: list[tuple[str, str, str]] = []

    def add(status: str, name: str, detail: str = "") -> None:
        results.append((status, name, detail))

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        config = OidcConfig.from_dict(raw, secret_reader=_read)
    except (OSError, ValueError):
        add("FAIL", "configuration file can be read")
        return results
    except OidcError as error:
        add("FAIL", "configuration is complete", error.code)
        return results
    add("PASS", "configuration is complete")
    try:
        validate_config(config)
        add("PASS", "roles: the provider can only grant STUDENT and LECTURER; privileged accounts are listed by the owner")
    except OidcError as error:
        add("FAIL", "role configuration", error.code)
    if not config.redirect_uri.startswith("https://"):
        add("WARN", "redirect address is not https", "required by almost every provider outside local tests")
    else:
        add("PASS", "redirect address uses https")
    if config.client_secret is None:
        add("WARN", "no client secret file", "fine for a public client; most university providers register a confidential one")
    if not config.role_map:
        add("WARN", "role_map is empty", "nobody would receive a role, so every sign-in would be refused")
    if config.jit_provisioning:
        add("WARN", "JIT provisioning is on", "anyone the provider authenticates and maps to a role gets an account")

    owned = http is None
    http = http or httpx.AsyncClient(trust_env=False)
    try:
        client = OidcClient(config, http)
        document = await client.discovery()
        add("PASS", "discovery document is reachable and names this issuer")
        methods = document.get("code_challenge_methods_supported")
        add("PASS" if methods is None or "S256" in methods else "FAIL", "provider supports PKCE S256", "not advertised" if methods is None else "")
        types = document.get("response_types_supported")
        add("PASS" if types is None or "code" in types else "FAIL", "provider supports the authorization code flow")
        algs = document.get("id_token_signing_alg_values_supported")
        add("PASS" if algs is None or {"RS256", "ES256"} & set(algs) else "FAIL", "provider signs ID tokens with RS256 or ES256")
        jwks = await client._get_json(document["jwks_uri"])  # noqa: SLF001 -- same fetch the sign-in uses
        usable = [k for k in jwks.get("keys", []) if isinstance(k, dict) and k.get("kty") in {"RSA", "EC"} and k.get("use", "sig") == "sig"]
        add("PASS" if usable else "FAIL", "key set has at least one signing key", f"{len(usable)} key(s)")
    except OidcError as error:
        add("FAIL", "provider check", error.code)
    finally:
        if owned:
            await http.aclose()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    results = asyncio.run(run(args.config))
    for status, name, detail in results:
        print(f"{status:4} {name}" + (f"  [{detail}]" if detail else ""))
    return 1 if any(status == "FAIL" for status, _, _ in results) else 0


if __name__ == "__main__":
    sys.exit(main())
