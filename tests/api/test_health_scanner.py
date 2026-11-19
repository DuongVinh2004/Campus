"""/health/ready lists the learning scanner as an informational dependency; it never fails chat readiness."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "services" / "api" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "services" / "api" / "src"))

from campus247.presentation.health import router  # noqa: E402


def ready(scanner):
    app = FastAPI()
    app.include_router(router)
    app.state.learning_service = SimpleNamespace(scanner=scanner) if scanner is not False else None
    return TestClient(app).get("/health/ready")


class Reporting:
    def __init__(self, state=None, error=None):
        self.state, self.error = state, error

    async def health(self):
        if self.error:
            raise self.error
        return self.state


def dependency(response, name="learning-scanner"):
    return next((d["status"] for d in response.json()["dependencies"] if d["name"] == name), None)


@pytest.mark.parametrize("state,expected", [
    ({"up": True, "stale": False}, "ready"),
    ({"up": True, "stale": True}, "unavailable"),
    ({"up": False, "code": "SCANNER_UNAVAILABLE"}, "unavailable"),
])
def test_scanner_state_is_listed_but_readiness_stays_ok(state, expected):
    response = ready(Reporting(state))
    assert response.status_code == 200 and response.json()["status"] == "ready"
    assert dependency(response) == expected


def test_a_probe_that_raises_counts_as_unavailable_without_failing_the_endpoint():
    response = ready(Reporting(error=RuntimeError("boom")))
    assert response.status_code == 200 and dependency(response) == "unavailable"


def test_scanners_that_cannot_report_and_a_missing_module_add_nothing():
    assert dependency(ready(SimpleNamespace(name="fixture"))) is None
    assert dependency(ready(False)) is None


def ready_with_knowledge(scanner):
    app = FastAPI()
    app.include_router(router)
    app.state.knowledge_runtime = SimpleNamespace(platform=SimpleNamespace(storage=SimpleNamespace(scanner=scanner)))
    return TestClient(app).get("/health/ready")


@pytest.mark.parametrize("state,expected", [
    ({"up": True, "stale": False}, "ready"),
    ({"up": True, "stale": True}, "unavailable"),
    ({"up": False}, "unavailable"),
])
def test_the_knowledge_upload_scanner_is_listed_too_even_when_learning_is_off(state, expected):
    response = ready_with_knowledge(Reporting(state))
    assert response.status_code == 200 and response.json()["status"] == "ready"
    assert dependency(response, "upload-scanner") == expected and dependency(response) is None


def test_no_scanner_on_the_storage_adds_nothing():
    assert dependency(ready_with_knowledge(None), "upload-scanner") is None
    assert dependency(ready_with_knowledge(SimpleNamespace(name="x")), "upload-scanner") is None
