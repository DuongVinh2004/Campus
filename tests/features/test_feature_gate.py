"""F0.2 / F0.4 / F0.5: every served route and page has an owner; switching a feature off closes exactly its entry points."""
from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from campus247.application.features.jobs import run_gated
from campus247.application.features.service import FeatureService
from campus247.features import registry as reg
from campus247.presentation.features import FeatureGateMiddleware

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import runtime_routes as rr  # noqa: E402

ROUTE = re.compile(r'@(?:router|r|app)\.(?:get|post|put|patch|delete)\(\s*f?"(/v1/[^"]*)"')
SOURCES = [*(ROOT / "services/api/src/campus247/presentation").glob("*.py"), ROOT / "scripts/knowledge_platform.py"]
# Served on 8015 through a path prefix (routers with a prefix=...), so the regex above cannot see their full path.
PREFIXED_ROUTERS = ["/v1/learning/terms", "/v1/policy-graph/x"]


def served_routes() -> set[str]:
    found = set(PREFIXED_ROUTERS)
    for source in SOURCES:
        found.update(m.replace("{", "x").replace("}", "") for m in ROUTE.findall(source.read_text(encoding="utf-8")))
    return {r for r in found if rr.api_path_allowed(r) or r.startswith("/v1/policy-graph")}


def test_every_served_route_has_an_owner():
    orphans = sorted(r for r in served_routes() if reg.feature_for_path(r) is None)
    assert not orphans, f"route served but in no feature: {orphans}"


def test_every_allowed_prefix_and_page_has_an_owner():
    split = {"/v1/knowledge/", "/v1/assistant/"}  # shared by many features; the route scan above checks each concrete route
    assert not [p for p in (*rr.ALLOWED_API_PREFIXES, *rr.ALLOWED_API_PATHS) if p not in split and reg.feature_for_path(p) is None]
    assert not [p for p in rr.page_routes() if reg.feature_for_page(p) is None], "page without a feature"


def test_registry_entry_points_exist():
    pages = rr.page_routes()
    for f in reg.FEATURES:
        for page in f.pages:
            assert page in pages or page == "admin/features", f"{f.key}: page {page} does not exist"


def make_client(off: str):
    svc = FeatureService(env={"CAMPUS247_FEATURES_OFF": off})
    app = FastAPI()
    app.add_middleware(FeatureGateMiddleware, service=svc)

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    def anything(path: str):
        return {"ok": True}

    return TestClient(app), svc


SAMPLE = {f.key: ([p.rstrip("/") + "/x" for p in f.api_prefixes[:1]] or [None])[0] for f in reg.FEATURES if not f.locked}


@pytest.mark.parametrize("key", sorted(k for k, path in SAMPLE.items() if path))
def test_switching_a_feature_off_closes_its_routes_and_leaves_others(key):
    path = SAMPLE[key]
    client, svc = make_client(key)
    owner = reg.feature_for_path(path)
    response = client.get(path)
    if owner == key:
        assert response.status_code == 404 and response.json()["code"] == "FEATURE_DISABLED" and response.json()["feature"] == key
        assert response.headers["cache-control"] == "no-store"
    # a route of an unrelated feature stays open; core routes never close
    assert client.get("/v1/users/me").status_code == 200
    unrelated = "/v1/rooms/x" if key != "rooms.booking" else "/v1/students/me/schedule"
    assert client.get(unrelated).status_code == 200


def test_children_close_with_their_parent_and_reads_stay_in_system_state():
    client, svc = make_client("chat.assistant")
    assert client.get("/v1/conversations/1/messages/2/feedback").status_code == 404
    assert client.get("/v1/assistant/conversations").status_code == 404
    assert client.get("/v1/features").status_code == 200  # locked core


def test_unknown_v1_path_is_not_blocked_by_the_gate():
    client, _ = make_client("*")
    assert client.get("/v1/not-registered").status_code == 200  # the runtime boundary, not the gate, decides these


def test_job_runs_only_while_enabled_and_restarts():
    async def scenario():
        state = {"on": True, "ticks": 0}

        async def job():
            while True:
                state["ticks"] += 1
                await asyncio.sleep(0.01)

        runner = asyncio.create_task(run_gated(lambda: state["on"], job, poll_s=0.02))
        await asyncio.sleep(0.15)
        assert state["ticks"] > 3
        state["on"] = False
        await asyncio.sleep(0.1)
        frozen = state["ticks"]
        await asyncio.sleep(0.15)  # three or more polling cycles with the flag off
        assert state["ticks"] == frozen
        state["on"] = True
        await asyncio.sleep(0.15)
        assert state["ticks"] > frozen
        runner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await runner

    asyncio.run(scenario())


def test_tools_and_jobs_follow_their_feature():
    svc = FeatureService(env={"CAMPUS247_FEATURES_OFF": "notifications.inbox"})
    assert not svc.job_enabled("exam_reminders") and svc.job_enabled("alerts")
    assert svc.tool_enabled("some_unowned_tool")
    assert not svc.tool_enabled("procedure_check")  # new feature, off by default
