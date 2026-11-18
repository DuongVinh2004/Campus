"""The runtime (port 8015) serves pages and API paths from one module; these tests keep the lists from drifting apart again."""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import runtime_routes as rr  # noqa: E402

ROUTE_DECORATOR = re.compile(r'@(?:router|r|app)\.(?:get|post|put|patch|delete)\(\s*f?"(/v1/[^"]*)"')
SOURCES = [*(ROOT / "services/api/src/campus247/presentation").glob("*.py"), ROOT / "scripts/knowledge_platform.py"]


def _api_routes() -> set[str]:
    found = set()
    for source in SOURCES:
        found.update(ROUTE_DECORATOR.findall(source.read_text(encoding="utf-8")))
    return found


def test_every_page_in_the_app_folder_is_served():
    pages = rr.page_routes()
    assert {"chat", "login", "admin", "memory", "offline", "knowledge/freshness", "knowledge/policy-graph"} <= pages
    for page in pages:
        assert rr.is_served_path(page), page


def test_pwa_files_are_served_and_exist_in_the_build_input():
    for name in ("sw.js", "manifest.webmanifest"):
        assert rr.is_served_path(name)
    assert (ROOT / "apps/web/public/sw.js").is_file() and (ROOT / "apps/web/src/app/manifest.ts").is_file()
    for icon in ("icon-192.png", "icon-512.png", "icon-maskable-512.png"):
        assert rr.is_served_path("icons/" + icon)
        assert (ROOT / "apps/web/public/icons" / icon).is_file()


def test_unknown_and_unsafe_paths_are_not_served():
    for path in ("khong-ton-tai", "chat/../admin", "chat" + chr(92) + "x", "v1/users/me", "knowledge/khong-co"):
        assert not rr.is_served_path(path), path


def test_every_api_route_is_either_allowed_or_deliberately_blocked():
    undecided = sorted(
        route for route in _api_routes()
        if not rr.api_path_allowed(route) and not route.startswith(rr.BLOCKED_LEGACY_API_PREFIXES)
    )
    assert not undecided, f"route exists but is neither allowed nor listed as blocked legacy: {undecided}"


def test_operations_status_is_allowed():
    assert rr.api_path_allowed("/v1/admin/operations/status")


def test_not_found_is_html_for_people_and_json_for_api_clients():
    def request(path, accept):
        return SimpleNamespace(url=SimpleNamespace(path=path), headers={"accept": accept})

    page = rr.not_found_response(request("/khong-co", "text/html,application/xhtml+xml"))
    assert page.status_code == 404 and page.media_type == "text/html" and b"Kh\xc3\xb4ng t\xc3\xacm th\xe1\xba\xa5y trang" in page.body
    assert rr.not_found_response(request("/v1/abc", "text/html")).media_type == "application/json"
    assert rr.not_found_response(request("/khong-co", "*/*")).media_type == "application/json"


def test_modules_import_without_tzdata(monkeypatch):
    """The runtime Python on Windows has no tzdata: importing the reminder and alert modules must not crash."""
    import zoneinfo

    def missing(key):
        raise ZoneInfoNotFoundError(key)

    monkeypatch.setattr(zoneinfo, "ZoneInfo", missing)
    for name in ("campus247.application.campus_ops.reminders", "campus247.observability.alerts"):
        module = importlib.reload(importlib.import_module(name))
        assert module.VN.utcoffset(None).total_seconds() == 7 * 3600
    importlib.reload(importlib.import_module("campus247.application.campus_ops.reminders"))
    importlib.reload(importlib.import_module("campus247.application.knowledge.freshness_reminders"))
