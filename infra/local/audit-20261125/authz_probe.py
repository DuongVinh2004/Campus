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


ENDPOINTS = [
    "/v1/users/me", "/v1/tickets", "/v1/students/me/schedule", "/v1/notifications", "/v1/rooms/bookings/mine",
    "/v1/staff/tickets", "/v1/admin/overview", "/v1/admin/operations/status",
    "/v1/knowledge/platform/state", "/v1/knowledge/platform/documents", "/v1/knowledge/platform/crawl-sources",
    "/v1/knowledge/platform/intakes", "/v1/assistant/conversations", "/v1/learning/classes",
]

out = {"logins": {}, "matrix": {}, "checks": {}}
tokens = {}
for role, account in ACCOUNTS.items():
    status, roles, token, flags = login(account)
    out["logins"][role] = {"status": status, "roles": roles, "cookie_flags": flags}
    tokens[role] = token

for role, token in tokens.items():
    if not token:
        continue
    row = {}
    for path in ENDPOINTS:
        row[path] = call("GET", path, token)[0]
    out["matrix"][role] = row
    time.sleep(0.5)
out["matrix"]["anonymous"] = {path: call("GET", path)[0] for path in ENDPOINTS}

# Forged token, cross-origin sign-in.
out["checks"]["forged_token_users_me"] = call("GET", "/v1/users/me", "forged.invalid.token")[0]
out["checks"]["cross_origin_login"] = login(ACCOUNTS["student2"], origin="https://evil.example")[0]

# IDOR: one student's ticket read by another student and through the staff route.
status, tickets, _ = call("GET", "/v1/tickets", tokens["student"])
items = tickets.get("items", tickets) if isinstance(tickets, dict) else (tickets or [])
ticket_id = items[0]["id"] if items and isinstance(items, list) and isinstance(items[0], dict) and "id" in items[0] else None
out["checks"]["idor_ticket_found"] = bool(ticket_id)
if ticket_id:
    out["checks"]["idor_owner_reads_own"] = call("GET", f"/v1/tickets/{ticket_id}", tokens["student"])[0]
    out["checks"]["idor_other_student_reads"] = call("GET", f"/v1/tickets/{ticket_id}", tokens["student2"])[0]
    out["checks"]["idor_student_via_staff_route"] = call("GET", f"/v1/staff/tickets/{ticket_id}", tokens["student2"])[0]
    out["checks"]["idor_officer_via_staff_route"] = call("GET", f"/v1/staff/tickets/{ticket_id}", tokens["officer"])[0]

# CSRF-style: a state-changing POST with a foreign Origin and an invalid body (nothing can be created).
out["checks"]["cross_origin_post_tickets"] = call("POST", "/v1/tickets", tokens["student"], body={}, origin="https://evil.example")[0]
out["checks"]["same_origin_post_tickets_invalid_body"] = call("POST", "/v1/tickets", tokens["student"], body={})[0]

# Logout, then reuse the same token.
student2 = tokens["student2"]
out["checks"]["logout"] = call("POST", "/v1/auth/logout", student2, body={})[0]
out["checks"]["reuse_after_logout"] = call("GET", "/v1/users/me", student2)[0]

# 429: burst on a throwaway account.
if "--burst" in sys.argv:
    s, _, t, _ = login(directory["sv.demo40"])
    codes = [call("GET", "/v1/notifications", t)[0] for _ in range(40)]
    out["checks"]["burst_40_codes"] = {str(c): codes.count(c) for c in sorted(set(codes))}
    out["checks"]["burst_first_429_at"] = codes.index(429) + 1 if 429 in codes else None

print(json.dumps(out, ensure_ascii=False, indent=1))
