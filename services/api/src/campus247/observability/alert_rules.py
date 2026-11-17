"""The alert rules: each reads the operations status document (observability.ops_status.build_status) and says whether it is
breached. A rule returns None when it cannot judge (too few samples, nothing configured); the manager then leaves its state
alone instead of calling it healthy or broken.

The numbers are the same as apps/web/src/lib/ops-assess.ts, so a tile on the operations page turns amber when an alert would
fire; tests/unit/observability/test_alert_rules.py compares the two files.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


THRESHOLDS = {
    "p95_seconds_warn": 15,
    "error_rate_warn": 0.02,
    "admission_rate_warn": 0.02,
    "min_turns_for_rate": 20,
    "vector_failed_rate_warn": 0.05,
    "min_retrievals_for_rate": 25,
    "loop_blocked_ms_warn": 3000,
    "cap_near_fraction": 0.8,
    "disk_warn_pct": 15,
    "disk_crit_pct": 5,
    "backup_max_age_hours": 26,
    "rehearsal_max_age_days": 35,
}


@dataclass(frozen=True)
class Reading:
    breached: bool
    value: str  # short text for the message, never user data
    severity: Severity = Severity.WARNING


Evaluate = Callable[[dict[str, Any]], Reading | None]


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    evaluate: Evaluate
    for_s: int = 0  # how long the breach must last before the alert fires


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%".replace(".", ",")


def model_down(status):
    models = status.get("models") or {}
    if not models:
        return None
    down = sorted(name for name, state in models.items() if state != "up")
    return Reading(bool(down), ", ".join(down) + " không trả lời" if down else "đều chạy", Severity.CRITICAL)


def gateway_unreachable(status):
    gateway = status.get("gateway") or {}
    if gateway.get("reachable") is None:
        return None
    return Reading(gateway["reachable"] is False, "không kết nối được cổng gọi model" if gateway["reachable"] is False else "kết nối được", Severity.CRITICAL)


def _today(status):
    gateway = status.get("gateway") or {}
    today = gateway.get("today") if gateway.get("reachable") else None
    return today if today and today.get("cap_enabled") else None


def gateway_cap_reached(status):
    today = _today(status)
    if today is None:
        return None
    return Reading(bool(today["cap_reached"]), f"{today['calls']} lời gọi, ${today['usd']} hôm nay", Severity.CRITICAL)


def gateway_cap_near(status):
    today = _today(status)
    if today is None:
        return None
    used_usd = float(today["usd"]) / float(today["usd_cap"]) if float(today["usd_cap"]) else 0.0
    used_calls = today["calls"] / today["call_cap"] if today["call_cap"] else 0.0
    used = max(used_usd, used_calls)
    return Reading(used >= THRESHOLDS["cap_near_fraction"] and not today["cap_reached"], f"đã dùng {used * 100:.0f}% trần ngày")


def overload_503(status):
    window = status["turns"]["last_5m"]
    attempts = window["turns"] + window["admission_rejected"]
    if attempts < THRESHOLDS["min_turns_for_rate"]:
        return None
    return Reading(window["admission_rejected_rate"] > THRESHOLDS["admission_rate_warn"], f"{_pct(window['admission_rejected_rate'])} lượt bị từ chối vì bận")


def turn_errors(status):
    window = status["turns"]["last_10m"]
    if window["turns"] < THRESHOLDS["min_turns_for_rate"]:
        return None
    return Reading(window["error_rate"] > THRESHOLDS["error_rate_warn"], f"{_pct(window['error_rate'])} lượt lỗi")


def slow_p95(status):
    window = status["turns"]["last_10m"]
    if window["turns"] < THRESHOLDS["min_turns_for_rate"]:
        return None
    bound = window["p95_s_le"]
    if bound is None:
        over = window.get("p95_s_le_over")
        return Reading(True, f"p95 > {over} giây") if over else None
    return Reading(bound > THRESHOLDS["p95_seconds_warn"], f"p95 ≤ {bound:g} giây")


def vector_lost(status):
    retrieval = status["retrieval"]
    if retrieval["retrievals"] < THRESHOLDS["min_retrievals_for_rate"]:
        return None
    return Reading(retrieval["failed_rate"] > THRESHOLDS["vector_failed_rate_warn"], f"mất nhánh vector {_pct(retrieval['failed_rate'])}")


def loop_blocked(status):
    window = status["turns"]["last_5m"]
    return Reading(window["loop_blocked_max_ms"] >= THRESHOLDS["loop_blocked_ms_warn"], f"chặn {window['loop_blocked_max_ms']} ms")


def disk_low(status):
    free = (status.get("storage") or {}).get("data_free_pct")
    if free is None:
        return None
    if free < THRESHOLDS["disk_crit_pct"]:
        return Reading(True, f"còn {free:g}% dung lượng", Severity.CRITICAL)
    return Reading(free < THRESHOLDS["disk_warn_pct"], f"còn {free:g}% dung lượng")


def backup_stale(status):
    backup = status.get("backup") or {}
    if not backup.get("configured"):
        return None
    problems = []
    last = backup.get("last")
    if last is None:
        problems.append("chưa có bản sao lưu")
    elif not last.get("ok"):
        problems.append("lần sao lưu gần nhất lỗi")
    elif (last.get("age_hours") or 0) > THRESHOLDS["backup_max_age_hours"]:
        problems.append(f"bản gần nhất cách đây {last['age_hours']:g} giờ")
    offsite = backup.get("offsite")
    if offsite is not None and not offsite.get("ok"):
        problems.append("bản sao ngoài máy lỗi")
    return Reading(bool(problems), "; ".join(problems) or "đủ mới")


def rehearsal_failed(status):
    backup = status.get("backup") or {}
    record = backup.get("rehearsal")
    if not backup.get("configured") or record is None:
        return None
    age_days = (record.get("age_hours") or 0) / 24
    if not record.get("ok"):
        return Reading(True, "lần diễn tập khôi phục gần nhất lỗi")
    return Reading(age_days > THRESHOLDS["rehearsal_max_age_days"], f"diễn tập gần nhất cách đây {age_days:.0f} ngày")


def learning_worker_down(status):
    worker = (status.get("background") or {}).get("learning_worker")
    if worker is None or worker in {"disabled", "standby", "starting"}:
        return None
    return Reading(worker == "unavailable", f"tiến trình học liệu: {worker}")


def no_worker_reporting(status):
    return Reading(status["workers_reporting"] == 0, f"{status['workers_reporting']} tiến trình API báo số liệu", Severity.CRITICAL)


RULES: tuple[Rule, ...] = (
    Rule("no_worker_reporting", "Không có tiến trình API nào báo số liệu", no_worker_reporting, for_s=120),
    Rule("model_down", "Model embedding hoặc rerank ngừng", model_down, for_s=120),
    Rule("gateway_unreachable", "Không kết nối được cổng gọi model", gateway_unreachable, for_s=120),
    Rule("gateway_cap_reached", "Đã chạm trần chi phí trong ngày", gateway_cap_reached),
    Rule("gateway_cap_near", "Sắp chạm trần chi phí trong ngày", gateway_cap_near),
    Rule("overload_503", "Hệ thống bận, nhiều lượt bị từ chối", overload_503),
    Rule("turn_errors", "Tỉ lệ lượt lỗi cao", turn_errors),
    Rule("slow_p95", "Thời gian trả lời chậm", slow_p95),
    Rule("vector_lost", "Truy hồi mất nhánh vector", vector_lost),
    Rule("loop_blocked", "Vòng lặp xử lý bị chặn lâu", loop_blocked),
    Rule("disk_low", "Sắp hết dung lượng", disk_low),
    Rule("backup_stale", "Sao lưu cũ hoặc lỗi", backup_stale),
    Rule("rehearsal_failed", "Diễn tập khôi phục lỗi hoặc quá cũ", rehearsal_failed),
    Rule("learning_worker_down", "Tiến trình học liệu ngừng", learning_worker_down, for_s=600),
)
RULES_BY_ID = {rule.id: rule for rule in RULES}
