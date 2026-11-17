import re
from copy import deepcopy
from pathlib import Path

import pytest
from campus247.observability import alert_rules as r
from campus247.observability.alert_rules import RULES, RULES_BY_ID, THRESHOLDS, Severity


def window(**over):
    base = {"turns": 100, "ok": 98, "abstained": 2, "errors": {}, "error_rate": 0.0, "p50_s_le": 5.0, "p95_s_le": 12.0, "first_token_p95_s_le": 3.0,
            "admission_rejected": 0, "admission_rejected_rate": 0.0, "rate_limited": {}, "loop_blocked": 0, "loop_blocked_max_ms": 0}
    return base | over


def status(**over):
    base = {"workers_reporting": 2,
            "turns": {"last_5m": window(), "last_10m": window(), "last_60m": window()},
            "load": {"in_flight": 3, "waiting": 0, "limit": 32},
            "retrieval": {"retrievals": 100, "failed": 1, "timeouts": 0, "failed_rate": 0.01, "vector_ms_max": 900},
            "models": {"embedding": "up", "reranker": "up"},
            "gateway": {"reachable": True, "today": {"usd": "1.00", "calls": 400, "usd_cap": "5.00", "call_cap": 2000, "cap_enabled": True, "cap_reached": False}},
            "background": {"leader": True, "learning_worker": "ready"},
            "storage": {"data_free_pct": 40.0, "backup_free_pct": 40.0},
            "backup": {"configured": True, "last": {"ok": True, "age_hours": 5.0}, "offsite": {"ok": True, "age_hours": 5.0},
                       "rehearsal": {"ok": True, "age_hours": 24.0}}}
    result = deepcopy(base)
    for key, value in over.items():
        result[key] = value
    return result


def reading(rule_id, doc):
    return RULES_BY_ID[rule_id].evaluate(doc)


def test_a_healthy_status_breaches_nothing():
    breached = [rule.id for rule in RULES if (got := rule.evaluate(status())) is not None and got.breached]
    assert breached == []


def test_model_down_is_critical_and_names_the_model():
    got = reading("model_down", status(models={"embedding": "up", "reranker": "down"}))
    assert got.breached and got.severity == Severity.CRITICAL and "reranker" in got.value
    assert reading("model_down", status(models={})) is None


def test_no_worker_reporting_is_critical():
    assert reading("no_worker_reporting", status(workers_reporting=0)).severity == Severity.CRITICAL
    assert not reading("no_worker_reporting", status()).breached


def test_gateway_rules_distinguish_unreachable_near_and_reached():
    ok = status()
    assert reading("gateway_unreachable", status(gateway={"reachable": None})) is None
    assert reading("gateway_unreachable", status(gateway={"reachable": False})).breached
    today = lambda **o: {"reachable": True, "today": {"usd": "1.00", "calls": 400, "usd_cap": "5.00", "call_cap": 2000, "cap_enabled": True, "cap_reached": False} | o}  # noqa: E731
    assert not reading("gateway_cap_near", ok).breached
    assert reading("gateway_cap_near", status(gateway=today(calls=1600))).breached
    assert reading("gateway_cap_near", status(gateway=today(usd="4.00"))).breached
    assert not reading("gateway_cap_near", status(gateway=today(calls=2000, cap_reached=True))).breached  # the critical rule speaks instead
    reached = reading("gateway_cap_reached", status(gateway=today(cap_reached=True)))
    assert reached.breached and reached.severity == Severity.CRITICAL
    assert reading("gateway_cap_reached", status(gateway=today(cap_enabled=False))) is None
    assert reading("gateway_cap_near", status(gateway={"reachable": False})) is None


def test_rate_rules_need_enough_samples():
    few = status(turns={"last_5m": window(turns=5, admission_rejected=5, admission_rejected_rate=0.5), "last_10m": window(turns=10, error_rate=0.5), "last_60m": window()})
    assert reading("overload_503", few) is None and reading("turn_errors", few) is None and reading("slow_p95", few) is None
    many = status(turns={"last_5m": window(turns=60, admission_rejected=5, admission_rejected_rate=5 / 65),
                         "last_10m": window(turns=100, error_rate=0.03, p95_s_le=20.0), "last_60m": window()})
    assert reading("overload_503", many).breached and reading("turn_errors", many).breached and reading("slow_p95", many).breached
    assert not reading("slow_p95", status(turns={"last_5m": window(), "last_10m": window(p95_s_le=15.0), "last_60m": window()})).breached


def test_the_overflow_bucket_counts_as_slow():
    doc = status(turns={"last_5m": window(), "last_10m": window(p95_s_le=None, p95_s_le_over=30.0), "last_60m": window()})
    got = reading("slow_p95", doc)
    assert got.breached and "> 30" in got.value


def test_vector_loop_and_disk_rules():
    assert reading("vector_lost", status(retrieval={"retrievals": 10, "failed": 9, "timeouts": 9, "failed_rate": 0.9, "vector_ms_max": 1})) is None
    assert reading("vector_lost", status(retrieval={"retrievals": 100, "failed": 10, "timeouts": 9, "failed_rate": 0.1, "vector_ms_max": 1})).breached
    assert reading("loop_blocked", status(turns={"last_5m": window(loop_blocked_max_ms=3400), "last_10m": window(), "last_60m": window()})).breached
    assert reading("disk_low", status(storage={"data_free_pct": 14.0})).severity == Severity.WARNING
    assert reading("disk_low", status(storage={"data_free_pct": 4.0})).severity == Severity.CRITICAL
    assert not reading("disk_low", status(storage={"data_free_pct": 15.0})).breached and reading("disk_low", status(storage={"data_free_pct": None})) is None


def test_backup_rules():
    base = {"configured": True, "last": {"ok": True, "age_hours": 5.0}, "offsite": None, "rehearsal": None}
    assert reading("backup_stale", status(backup={"configured": False})) is None
    assert not reading("backup_stale", status(backup=base)).breached
    assert "chưa có" in reading("backup_stale", status(backup=base | {"last": None})).value
    assert reading("backup_stale", status(backup=base | {"last": {"ok": False, "age_hours": 1.0}})).breached
    assert reading("backup_stale", status(backup=base | {"last": {"ok": True, "age_hours": 27.0}})).breached
    assert "ngoài máy" in reading("backup_stale", status(backup=base | {"offsite": {"ok": False, "age_hours": 1.0}})).value
    assert reading("rehearsal_failed", status(backup=base)) is None
    assert reading("rehearsal_failed", status(backup=base | {"rehearsal": {"ok": False, "age_hours": 24.0}})).breached
    assert reading("rehearsal_failed", status(backup=base | {"rehearsal": {"ok": True, "age_hours": 36 * 24.0}})).breached
    assert not reading("rehearsal_failed", status(backup=base | {"rehearsal": {"ok": True, "age_hours": 10 * 24.0}})).breached


def test_learning_worker_only_judged_when_it_should_be_running():
    for worker in ("disabled", "standby", "starting"):
        assert reading("learning_worker_down", status(background={"learning_worker": worker})) is None
    assert reading("learning_worker_down", status(background={"learning_worker": "unavailable"})).breached
    assert not reading("learning_worker_down", status(background={"learning_worker": "ready"})).breached


def test_rule_ids_are_unique_and_every_message_value_is_plain_text():
    assert len({rule.id for rule in RULES}) == len(RULES)
    for rule in RULES:
        got = rule.evaluate(status())
        assert got is None or isinstance(got.value, str)


def test_thresholds_equal_the_ones_on_the_operations_page():
    """The page and the alerts must turn at the same numbers (apps/web/src/lib/ops-assess.ts)."""
    source = (Path(__file__).resolve().parents[3] / "apps/web/src/lib/ops-assess.ts").read_text(encoding="utf-8")
    block = source[source.index("export const THRESHOLDS"):source.index("} as const")]
    web = {name: float(value) for name, value in re.findall(r"(\w+):\s*([0-9.]+)", block)}
    pairs = {"p95SecondsWarn": "p95_seconds_warn", "errorRateWarn": "error_rate_warn", "admissionRateWarn": "admission_rate_warn",
             "minTurnsForRate": "min_turns_for_rate", "vectorFailedRateWarn": "vector_failed_rate_warn", "minRetrievalsForRate": "min_retrievals_for_rate",
             "loopBlockedMsWarn": "loop_blocked_ms_warn", "capNearFraction": "cap_near_fraction", "diskWarnPct": "disk_warn_pct",
             "diskCritPct": "disk_crit_pct", "backupMaxAgeHours": "backup_max_age_hours"}
    assert set(web) == set(pairs)
    for web_name, py_name in pairs.items():
        assert web[web_name] == THRESHOLDS[py_name], web_name
    assert r.THRESHOLDS is THRESHOLDS
