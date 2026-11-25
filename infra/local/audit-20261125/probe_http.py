"""Read-only role x endpoint probe against the live 8015 runtime. Never prints a credential or token.

Signs in through POST /v1/knowledge/platform/session (the same call the login form makes), then issues GET requests only, plus:
forged/absent token, cross-origin login, logout-then-reuse, and a 429 burst on one throwaway account.
"""
from __future__ import annotations

import http.client
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KP = ROOT / "infra/local/knowledge-platform-20261023"
HOST, PORT = "127.0.0.1", 8015
ORIGIN = f"http://{HOST}:{PORT}"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


directory = {a["username"]: a for a in load(KP / "campus-directory-credentials.json")["accounts"]}
learning = {a["username"]: a for a in load(ROOT / "infra/local/learning-materials-20261104-01/credentials.json")["accounts"]}
ACCOUNTS = {
    "student": directory["sv.demo01"], "student2": directory["sv.demo02"], "officer": directory["nv.demo01"],
    "lecturer": learning["gv.demo01"], "learning_admin": learning["qt.hoctap.demo"],
    "owner": load(KP / "owner-credentials.json"), "staff_local": load(KP / "staff-credentials.json"),
    "contributor": load(KP / "contributor-ctv.demo01-credentials.json"),
}


def call(method, path, token=None, body=None, origin=ORIGIN, cookie=None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=30)
    headers = {"Accept": "application/json"}
    if origin:
        headers["Origin"] = origin
    if token:
        headers["Cookie"] = f"auth_token={token}"
    if cookie:
        headers["Cookie"] = cookie
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=headers)
    res = conn.getresponse()
    raw = res.read()
    set_cookie = res.getheader("set-cookie") or ""
    conn.close()
    try:
        payload = json.loads(raw) if raw else None
    except ValueError:
        payload = None
    return res.status, payload, set_cookie


def login(account, origin=ORIGIN):
    status, payload, set_cookie = call("POST", "/v1/knowledge/platform/session",
                                       body={"username": account["username"], "password": account["password"]}, origin=origin)
    token = None
    for part in set_cookie.split(";"):
        if part.strip().startswith("auth_token="):
            token = part.strip().split("=", 1)[1]
    flags = sorted(f.strip().split("=")[0].lower() for f in set_cookie.split(";")[1:])
    return status, (payload or {}).get("roles"), token, flags


