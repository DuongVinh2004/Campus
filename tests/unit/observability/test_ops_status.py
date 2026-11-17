import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from campus247.observability.ops_metrics import OpsMetrics, write_snapshot
from campus247.observability.ops_status import OpsConfig, ProbeCache, backup_state, build_status, quality_state

NOW = datetime(2026, 11, 17, 3, 0, 20, tzinfo=UTC)


def seeded(tmp_path, *, turns=5):
    clock = lambda: NOW.timestamp() - 10  # noqa: E731 -- written ten seconds ago
    metrics = OpsMetrics(clock)
    for _ in range(turns):
        metrics.record_turn(outcome="ok", first_token_s=1.0, total_s=4.0)
    metrics.record_turn(outcome="error", error_code="AI_WORKFLOW_UNAVAILABLE", total_s=40.0)
    metrics.set_gauges(in_flight=3, waiting=1, limit=16)
    write_snapshot(tmp_path / "m", metrics.snapshot({"retrievals": 25, "failed": 1, "timeouts": 0, "vector_ms_max": 900}))
    return tmp_path / "m"


def transport(models_up=True, gateway="ok"):
    seen = []

    def handler(request: httpx.Request):
        seen.append(str(request.url))
        if request.url.port in (18081, 18082):
            return httpx.Response(200 if models_up else 503, json={})
        if request.url.path == "/v1/status":
            if gateway == "down":
                raise httpx.ConnectError("refused")
            if request.headers.get("x-gateway-token") != "tok":
                return httpx.Response(401, json={"error": "unauthorized"})
            return httpx.Response(200, json={"counters": {"ok": 9, "refused": 0, "failed": 1, "in_flight": 2},
                                             "today": {"usd": "1.21", "calls": 940, "usd_cap": "5.00", "call_cap": 2000,
                                                       "cap_enabled": True, "cap_reached": False}})
        return httpx.Response(404)

    return httpx.MockTransport(handler), seen


def config(tmp_path, **kwargs):
    base = dict(metrics_dir=seeded(tmp_path), data_dir=tmp_path, backup_dir=tmp_path / "backups",
                model_urls={"embedding": "http://127.0.0.1:18081/info", "reranker": "http://127.0.0.1:18082/info"},
                gateway_url="http://127.0.0.1:8025", gateway_token="tok",
                background=lambda: {"leader": True, "learning_worker": "ready"})
    return OpsConfig(**(base | kwargs))


@pytest.mark.asyncio
async def test_status_document_has_every_section_and_is_json_serializable(tmp_path):
    handler, _ = transport()
    async with httpx.AsyncClient(transport=handler) as client:
        status = await build_status(config(tmp_path), client=client, cache=ProbeCache(), now=NOW)
    json.dumps(status)  # no infinity, no non-serializable object
    assert status["workers_reporting"] == 1 and status["window_minutes"] == 60
    five = status["turns"]["last_5m"]
    assert five["turns"] == 6 and five["errors"] == {"AI_WORKFLOW_UNAVAILABLE": 1}
    assert five["p50_s_le"] == 5.0 and five["p95_s_le"] is None and five["p95_s_le_over"] == 30.0  # the 40 s turn overflowed
    assert status["load"] == {"in_flight": 3, "waiting": 1, "limit": 16}
    assert status["retrieval"]["failed_rate"] == pytest.approx(0.04)
    assert status["models"] == {"embedding": "up", "reranker": "up"}
    assert status["gateway"]["reachable"] and status["gateway"]["today"]["usd"] == "1.21"
    assert status["background"] == {"leader": True, "learning_worker": "ready"}
    assert 0 < status["storage"]["data_free_pct"] <= 100
    assert len(status["series"]["minute"]) == 60 and sum(status["series"]["turns"]) == 6 and sum(status["series"]["errors"]) == 1


@pytest.mark.asyncio
async def test_a_down_model_and_an_unreachable_gateway_are_reported_not_raised(tmp_path):
    handler, _ = transport(models_up=False, gateway="down")
    async with httpx.AsyncClient(transport=handler) as client:
        status = await build_status(config(tmp_path), client=client, cache=ProbeCache(), now=NOW)
    assert status["models"] == {"embedding": "down", "reranker": "down"}
    assert status["gateway"] == {"reachable": False, "reason": "unreachable"}


@pytest.mark.asyncio
async def test_a_wrong_gateway_token_shows_as_unreachable_with_the_http_status(tmp_path):
    handler, _ = transport()
    async with httpx.AsyncClient(transport=handler) as client:
        status = await build_status(config(tmp_path, gateway_token="wrong"), client=client, cache=ProbeCache(), now=NOW)
    assert status["gateway"] == {"reachable": False, "reason": "HTTP 401"}


@pytest.mark.asyncio
async def test_probes_are_cached_so_repeated_requests_do_not_hit_the_services(tmp_path):
    handler, seen = transport()
    cache = ProbeCache(clock=lambda: 100.0)
    async with httpx.AsyncClient(transport=handler) as client:
        cfg = config(tmp_path)
        for _ in range(5):
            await build_status(cfg, client=client, cache=cache, now=NOW)
    assert len(seen) == 3  # two models and the gateway, once


@pytest.mark.asyncio
async def test_cache_expires(tmp_path):
    handler, seen = transport()
    now = [0.0]
    cache = ProbeCache(clock=lambda: now[0])
    async with httpx.AsyncClient(transport=handler) as client:
        cfg = config(tmp_path)
        await build_status(cfg, client=client, cache=cache, now=NOW)
        now[0] = 11.0
        await build_status(cfg, client=client, cache=cache, now=NOW)
    assert len(seen) == 6


@pytest.mark.asyncio
async def test_nothing_configured_still_answers(tmp_path):
    cfg = OpsConfig(metrics_dir=tmp_path / "none", data_dir=tmp_path)
    async with httpx.AsyncClient(transport=transport()[0]) as client:
        status = await build_status(cfg, client=client, cache=ProbeCache(), now=NOW)
    assert status["workers_reporting"] == 0 and status["models"] == {}
    assert status["gateway"] == {"reachable": None, "reason": "not_configured"}
    assert status["backup"] == {"configured": False} and status["turns"]["last_5m"]["turns"] == 0


class TestBackupState:
    def write(self, directory: Path, name, body):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(json.dumps(body), encoding="utf-8")

    def test_reads_the_status_files_and_computes_their_age(self, tmp_path):
        self.write(tmp_path, "LAST_BACKUP.json", {"finished_at": (NOW - timedelta(hours=5)).isoformat(), "verified": True})
        self.write(tmp_path, "REHEARSAL.json", {"at": "2026-10-20T03:00:00Z", "ok": False})
        state = backup_state(tmp_path, now=NOW)
        assert state["last"] == {"at": (NOW - timedelta(hours=5)).isoformat(), "ok": True, "age_hours": 5.0}
        assert state["offsite"] is None
        assert state["rehearsal"]["ok"] is False and state["rehearsal"]["age_hours"] == pytest.approx(672.0, abs=0.1)  # 28 days

    def test_damaged_or_missing_files_are_none(self, tmp_path):
        (tmp_path / "LAST_BACKUP.json").write_text("{nope", encoding="utf-8")
        assert backup_state(tmp_path, now=NOW)["last"] is None
        assert backup_state(None, now=NOW) == {"configured": False}

    def test_an_unreadable_timestamp_keeps_the_record_without_an_age(self, tmp_path):
        self.write(tmp_path, "LAST_BACKUP.json", {"finished_at": "yesterday", "verified": True})
        assert backup_state(tmp_path, now=NOW)["last"]["age_hours"] is None


class TestQualityState:
    def latest(self, directory: Path, **over):
        directory.mkdir(parents=True, exist_ok=True)
        record = {"at": (NOW - timedelta(hours=3)).isoformat(), "ok": True, "baseline": True, "regressions": [],
                  "metrics": {"cases": 120, "any": 0.95, "fused_top8": 0.9, "survive": 0.85, "rerank": "http", "embedding": "http"}} | over
        (directory / "LATEST.json").write_text(json.dumps(record), encoding="utf-8")

    def test_reports_the_newest_check_with_only_the_numbers_the_page_needs(self, tmp_path):
        self.latest(tmp_path, regressions=["fused_top8 fell 4.0 points"])
        state = quality_state(tmp_path, now=NOW)
        assert state["ok"] and state["age_hours"] == 3.0 and state["regressions"] == ["fused_top8 fell 4.0 points"] and state["has_baseline"]
        assert state["metrics"] == {"cases": 120, "any": 0.95, "fused_top8": 0.9, "survive": 0.85}

    def test_a_skipped_check_is_reported_as_skipped_with_no_numbers(self, tmp_path):
        self.latest(tmp_path, ok=False, skipped="models_down", metrics=None, baseline=False)
        state = quality_state(tmp_path, now=NOW)
        assert state["skipped"] == "models_down" and state["ok"] is False and state["metrics"] is None

    def test_not_configured_and_never_ran(self, tmp_path):
        assert quality_state(None, now=NOW) == {"configured": False}
        assert quality_state(tmp_path, now=NOW) == {"configured": True, "ran": False}

    @pytest.mark.asyncio
    async def test_the_status_document_carries_it(self, tmp_path):
        self.latest(tmp_path / "q")
        handler, _ = transport()
        async with httpx.AsyncClient(transport=handler) as client:
            status = await build_status(config(tmp_path, quality_dir=tmp_path / "q"), client=client, cache=ProbeCache(), now=NOW)
        assert status["quality"]["metrics"]["fused_top8"] == 0.9
        json.dumps(status)
