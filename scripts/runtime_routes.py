"""One source of truth for what the runtime (port 8015) serves.

Three hand-written lists used to decide this (pages copied into the frontend snapshot, pages the API proxies to the frontend, and the
/v1 paths the operational boundary lets through). They drifted apart: pages and static files existed in the build but returned 404 on 8015.
Pages are now read from the app folder, so a new page is served without editing a list. The /v1 side is an explicit list with a test
(tests/test_runtime_routes.py) that fails when a route exists in neither the allowed nor the blocked list.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "apps/web/src/app"

# Static files and folders the frontend serves at the site root, besides pages.
STATIC_PREFIXES = ("_next/", "images/", "fonts/", "icons/")
STATIC_FILES = frozenset({"sw.js", "manifest.webmanifest", "favicon.ico"})

# /v1 prefixes the operational boundary lets through to the application.
ALLOWED_API_PREFIXES = (
    "/v1/knowledge/", "/v1/conversations", "/v1/privacy/", "/v1/assistant/", "/v1/student-preparations", "/v1/learning/",
    "/v1/rooms", "/v1/tickets", "/v1/students/me/schedule", "/v1/staff/tickets", "/v1/notifications",
    "/v1/admin/overview", "/v1/admin/operations/", "/v1/answer-gap-reports", "/v1/features", "/v1/admin/features",
    "/v1/announcements", "/v1/answer-receipts",
    "/v1/nudges", "/v1/policy-simulator", "/v1/policy-rules",
)
ALLOWED_API_PATHS = frozenset({"/v1/users/me", "/v1/auth/logout"})

# Routes that exist in the code but are deliberately not served in the operational runtime (legacy demo flows with no real back end).
BLOCKED_LEGACY_API_PREFIXES = (
    "/v1/auth/demo-session", "/v1/auth/oidc", "/v1/auth/providers", "/v1/capabilities", "/v1/document-requests",
    "/v1/handovers", "/v1/knowledge-operations", "/v1/operations/capabilities", "/v1/service-assistant",
    "/v1/service-course-records", "/v1/service-guidance", "/v1/service-knowledge", "/v1/service-requests",
    "/v1/service-staff-directory", "/v1/staff/document-requests", "/v1/staff/handovers", "/v1/staff/service-requests",
)


def page_routes() -> frozenset[str]:
    """Every page under the app folder as a URL path without the leading slash ('' is the home page)."""
    routes = set()
    for page in APP_DIR.rglob("page.tsx"):
        relative = page.parent.relative_to(APP_DIR).as_posix()
        routes.add("" if relative == "." else relative)
    return frozenset(routes)


def top_level_page_folders() -> frozenset[str]:
    return frozenset(route.split("/", 1)[0] for route in page_routes() if route)


def is_served_path(path: str) -> bool:
    """True when the API may proxy this path (without the leading slash) to the frontend."""
    if ".." in path or "\\" in path:
        return False
    path = path.rstrip("/") if path else path
    return path in page_routes() or path in STATIC_FILES or path.startswith(STATIC_PREFIXES)


def api_path_allowed(path: str) -> bool:
    return path in ALLOWED_API_PATHS or path.startswith(ALLOWED_API_PREFIXES)


# Baseline headers on every response from the single browser origin (8015). Routes that already set a stricter header (for example
# "Content-Security-Policy: sandbox" on document downloads) keep it. The web never frames its own pages (certificate previews use
# a sandboxed srcdoc iframe, which these headers do not affect), so framing by any site is refused.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "frame-ancestors 'none'",
}


def apply_security_headers(headers) -> None:
    """Add each baseline header the response does not already carry."""
    for name, value in SECURITY_HEADERS.items():
        if name not in headers:
            headers[name] = value


NOT_FOUND_HTML = (
    '<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    "<title>Không tìm thấy trang — Campus 24/7</title>"
    "<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f3f1ea;color:#13343b;font:16px/1.6 system-ui,sans-serif}"
    "main{max-width:28rem;padding:2rem;text-align:center}h1{font:600 2rem Georgia,serif;margin:0 0 .5rem}"
    "a{display:inline-block;margin-top:1rem;padding:.7rem 1.4rem;border-radius:.6rem;background:#14615f;color:#fff;text-decoration:none}</style></head>"
    "<body><main><h1>Không tìm thấy trang</h1><p>Địa chỉ này không tồn tại hoặc chưa được mở trong phiên bản hiện tại.</p>"
    '<a href="/chat">Về trợ lý học vụ</a></main></body></html>'
)


def not_found_response(request):
    """404 for an unknown path: a readable page for people, a JSON problem for API clients."""
    from starlette.responses import HTMLResponse, JSONResponse

    path = request.url.path
    wants_html = "text/html" in request.headers.get("accept", "") and not path.startswith("/v1/")
    if wants_html:
        return HTMLResponse(NOT_FOUND_HTML, status_code=404, headers={"Cache-Control": "no-store"})
    return JSONResponse({"detail": "Không tìm thấy tài nguyên."}, status_code=404, headers={"Cache-Control": "no-store"})
