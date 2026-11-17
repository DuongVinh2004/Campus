"""Exact human-approved quota transition; historical charges remain immutable."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from multi_agent_workspace import ROOT, STATE, checked, retain

sys.path[:0] = [str(ROOT), str(ROOT / "infra/local/rag-fixture")]
AUTHORIZATION = STATE / "resource-authorization-02.json"
PAID_STATE = ROOT / "infra/local/public-rag-20261013"
NATIVE_STATE = ROOT / "infra/local/rag-advanced-models-20261013-07"
NATIVE_PRIOR = ROOT / "infra/local/rag-advanced-models-20261013-06"
PAID_CAPS = {"usd": "10", "calls": 10000}
NATIVE_CAPS = {"http": 20000, "inference": 10000, "tokens": 5000000}
OLD_NATIVE_CAPS = {"http": 6000, "inference": 2000, "tokens": 750000}
HUMAN_ANSWER = "Tổng 10 USD; áp dụng các trần kỹ thuật đề xuất"
CALL_EXTENSION = STATE / "resource-authorization-04.json"
EXTENDED_PAID_CAPS = {"usd": "10", "calls": 12000}
CALL_EXTENSION_ANSWER = "Cho phép 12.000 calls; giữ tổng 10 USD"
STAGE5_CALL_EXTENSION = STATE / "resource-authorization-05.json"
STAGE5_PAID_CAPS = {"usd": "10", "calls": 12192}
STAGE5_CALL_EXTENSION_ANSWER = "Cho phép 12.192 calls; giữ tổng 10 USD"
UNCAPPED_AUTHORIZATION = STATE / "resource-authorization-06-accounting-only.json"
UNCAPPED_REQUESTS = ["bỏ phần ngân hàng lượt gọi đi", "bỏ luôn cả trần chi phí đi"]


def pending_records(snapshot):
    old = checked(ROOT / "infra/local/rag-fixture/manual-20261013-76/b001")
    inherited = json.loads((old / "predecessor.json").read_bytes())["pending_reservation_records"]
    records = {}
    for ordinal in snapshot["unsettled_attempts_retained"]:
        key = str(ordinal)
        if key in inherited:
            records[key] = inherited[key]
        else:
            path = checked(PAID_STATE / f"provider-{ordinal:05d}-reservation.json")
            if not path.exists():
                path = checked(old / f"provider-reservation-{ordinal:03}.json")
            records[key] = json.loads(path.read_bytes())
    return records


def same_workspace_path(stored, actual):
    """The authorization records absolute paths of the machine it was written on (a Windows drive path ending in
    infra/local/<name>). The same namespace on another machine has another prefix: compare the part below the
    workspace root, which is what names it."""
    if not isinstance(stored, str):
        return False
    actual = checked(actual)
    if stored == str(actual):
        return True
    relative = actual.resolve().relative_to(ROOT.resolve()).as_posix()
    return stored.replace("\\", "/").rstrip("/").endswith("/" + relative)


def load_authorization():
    value = json.loads(checked(AUTHORIZATION, STATE).read_text(encoding="utf-8"))
    if (value.get("human_answer") != HUMAN_ANSWER or value.get("paid_caps") != PAID_CAPS
            or value.get("native_caps") != NATIVE_CAPS
            or not same_workspace_path(value.get("native_namespace"), NATIVE_STATE)
            or not same_workspace_path(value.get("native_predecessor"), NATIVE_PRIOR)):
        raise ValueError("explicit resource authorization mismatch")
    return value


def resume_paid(snapshot, records, authorization, *, prior_migration=None):
    from public_rag_budget import FullBudget, resume_authorized_budget
    before, historical = authorization["paid_before"], authorization["pending_reservation_records"]
    old_migration = prior_migration if prior_migration is not None else json.loads(checked(PAID_STATE / "authorized-cap-3.json").read_text(encoding="utf-8"))
    resume_authorized_budget(before, historical, old_migration)
    if authorization["paid_caps"] != PAID_CAPS:
        raise ValueError("UNAUTHORIZED_RESOURCE_CAP")
    if snapshot["hard_cap_usd"] == "3":
        if snapshot != before or records != historical:
            raise ValueError("UNBOUND_RESOURCE_TRANSITION")
    elif snapshot["hard_cap_usd"] != "10" or snapshot["call_cap"] != 10000:
        raise ValueError("UNAUTHORIZED_RESOURCE_CAP")
    if (Decimal(snapshot["conservative_charged_usd"]) < Decimal(before["conservative_charged_usd"])
            or any(snapshot[key] < before[key] for key in ("calls", "input_tokens_charged", "output_tokens_charged"))
            or not set(historical) <= set(records)):
        raise ValueError("HISTORICAL_USAGE_MUST_REMAIN_CHARGED")
    normalized = {}
    for key, record in records.items():
        if key in historical:
            if record != historical[key]:
                raise ValueError("REWRITTEN_HISTORICAL_RESERVATION")
        elif record["snapshot"]["hard_cap_usd"] != "10":
            raise ValueError("UNBOUND_NEW_RESERVATION")
        normalized[key] = {**record, "snapshot": {**record["snapshot"], "hard_cap_usd": "10"}}
    view = {**snapshot, "hard_cap_usd": "10", "call_cap": 10000,
            "remaining_usd": str(Decimal("10")-Decimal(snapshot["conservative_charged_usd"]))}
    if snapshot["hard_cap_usd"] == "10" and snapshot != view:
        raise ValueError("INVALID_RESOURCE_CONTINUATION")
    return FullBudget.resume_full_records(view, normalized, cap_usd="10", call_cap=10000)


def load_call_extension():
    value = json.loads(checked(CALL_EXTENSION, STATE).read_text(encoding="utf-8"))
    if (value.get("human_answer") != CALL_EXTENSION_ANSWER
            or value.get("paid_caps") != EXTENDED_PAID_CAPS
            or value.get("prior_paid_caps") != PAID_CAPS
            or value.get("native_caps") != NATIVE_CAPS
            or value.get("authorization_sha256") != hashlib.sha256(checked(AUTHORIZATION, STATE).read_bytes()).hexdigest()
            or value.get("other_protections_changed") is not False):
        raise ValueError("explicit provider call extension mismatch")
    return value


def resume_paid_extended(snapshot, records, authorization, extension, *, prior_migration=None):
    from public_rag_budget import FullBudget
    before, historical = extension["paid_before"], extension["pending_reservation_records"]
    # Validate the entire predecessor chain before accepting the one changed cap.
    resume_paid(before, historical, authorization, prior_migration=prior_migration)
    if (extension["paid_caps"] != EXTENDED_PAID_CAPS or extension["prior_paid_caps"] != PAID_CAPS
            or extension["native_caps"] != NATIVE_CAPS
            or snapshot["hard_cap_usd"] != "10" or snapshot["call_cap"] not in (10000, 12000)):
        raise ValueError("UNAUTHORIZED_RESOURCE_CAP")
    if snapshot["call_cap"] == 10000 and (snapshot != before or records != historical):
        raise ValueError("UNBOUND_CALL_EXTENSION")
    if (Decimal(snapshot["conservative_charged_usd"]) < Decimal(before["conservative_charged_usd"])
            or any(snapshot[key] < before[key] for key in ("calls", "input_tokens_charged", "output_tokens_charged"))
            or not set(historical) <= set(records)):
        raise ValueError("HISTORICAL_USAGE_MUST_REMAIN_CHARGED")
    normalized = {}
    for key, record in records.items():
        if key in historical:
            if record != historical[key]:
                raise ValueError("REWRITTEN_HISTORICAL_RESERVATION")
        elif record["snapshot"]["hard_cap_usd"] != "10" or record["snapshot"]["call_cap"] != 12000:
            raise ValueError("UNBOUND_NEW_RESERVATION")
        normalized[key] = {**record, "snapshot": {**record["snapshot"], "hard_cap_usd": "10"}}
    return FullBudget.resume_full_records({**snapshot, "call_cap": 12000}, normalized, cap_usd="10", call_cap=12000)


def restore_paid(snapshot, records):
    authorization = load_authorization()
    if UNCAPPED_AUTHORIZATION.exists():
        from public_rag_accounting import AccountingBudget
        transition = load_uncapped_authorization()
        before, historical = transition["paid_before"], transition["pending_reservation_records"]
        resume_paid_stage5(before, historical, authorization, load_call_extension(), load_stage5_call_extension())
        return AccountingBudget.resume_accounting(snapshot, records, before, historical)
    if STAGE5_CALL_EXTENSION.exists():
        return resume_paid_stage5(snapshot, records, authorization, load_call_extension(), load_stage5_call_extension())
    return (resume_paid_extended(snapshot, records, authorization, load_call_extension())
            if CALL_EXTENSION.exists() else resume_paid(snapshot, records, authorization))


def authorized_paid_caps():
    if not AUTHORIZATION.exists():
        return {"usd": "3", "calls": 8500}
    load_authorization()
    if UNCAPPED_AUTHORIZATION.exists():
        return load_uncapped_authorization()["paid_caps"]
    if STAGE5_CALL_EXTENSION.exists():
        return load_stage5_call_extension()["paid_caps"]
    return load_call_extension()["paid_caps"] if CALL_EXTENSION.exists() else dict(PAID_CAPS)


def load_uncapped_authorization():
    value = json.loads(checked(UNCAPPED_AUTHORIZATION, STATE).read_text(encoding="utf-8"))
    if (value.get("human_requests") != UNCAPPED_REQUESTS
            or value.get("paid_caps") != {"usd": None, "calls": None}
            or value.get("prior_extension_sha256") != hashlib.sha256(checked(STAGE5_CALL_EXTENSION, STATE).read_bytes()).hexdigest()
            or value.get("historical_usage_retained") is not True
            or value.get("uncertain_refunded") is not False
            or value.get("other_protections_changed") is not False):
        raise ValueError("explicit uncapped accounting authorization mismatch")
    return value


def create_uncapped_authorization():
    if UNCAPPED_AUTHORIZATION.exists():
        raise ValueError("accounting authorization must be new")
    snapshot = latest_paid_snapshot()
    records = pending_records(snapshot)
    restore_paid(snapshot, records)
    retain(UNCAPPED_AUTHORIZATION, {"created_at": datetime.now(timezone.utc).isoformat(),
        "human_requests": UNCAPPED_REQUESTS, "paid_caps": {"usd": None, "calls": None},
        "prior_extension_sha256": hashlib.sha256(checked(STAGE5_CALL_EXTENSION, STATE).read_bytes()).hexdigest(),
        "paid_before": snapshot, "pending_reservation_records": records,
        "historical_usage_retained": True, "uncertain_refunded": False, "other_protections_changed": False})


def load_stage5_call_extension():
    load_call_extension()
    value = json.loads(checked(STAGE5_CALL_EXTENSION, STATE).read_text(encoding="utf-8"))
    if (value.get("human_answer") != STAGE5_CALL_EXTENSION_ANSWER
            or value.get("paid_caps") != STAGE5_PAID_CAPS
            or value.get("prior_paid_caps") != EXTENDED_PAID_CAPS
            or value.get("native_caps") != NATIVE_CAPS
            or value.get("prior_extension_sha256") != hashlib.sha256(checked(CALL_EXTENSION, STATE).read_bytes()).hexdigest()
            or value.get("historical_usage_retained") is not True
            or value.get("uncertain_refunded") is not False
            or value.get("other_protections_changed") is not False):
        raise ValueError("explicit stage5 provider call extension mismatch")
    return value


def resume_paid_stage5(snapshot, records, authorization, prior_extension, extension, *, prior_migration=None):
    from public_rag_budget import FullBudget
    before, historical = extension["paid_before"], extension["pending_reservation_records"]
    resume_paid_extended(before, historical, authorization, prior_extension, prior_migration=prior_migration)
    if (extension["human_answer"] != STAGE5_CALL_EXTENSION_ANSWER
            or extension["paid_caps"] != STAGE5_PAID_CAPS
            or extension["prior_paid_caps"] != EXTENDED_PAID_CAPS or extension["native_caps"] != NATIVE_CAPS
            or snapshot["hard_cap_usd"] != "10" or snapshot["call_cap"] not in (12000, 12192)):
        raise ValueError("UNAUTHORIZED_RESOURCE_CAP")
    if snapshot["call_cap"] == 12000 and (snapshot != before or records != historical):
        raise ValueError("UNBOUND_STAGE5_CALL_EXTENSION")
    if (Decimal(snapshot["conservative_charged_usd"]) < Decimal(before["conservative_charged_usd"])
            or any(snapshot[key] < before[key] for key in ("calls", "input_tokens_charged", "output_tokens_charged"))
            or not set(historical) <= set(records)):
        raise ValueError("HISTORICAL_USAGE_MUST_REMAIN_CHARGED")
    normalized = {}
    for key, record in records.items():
        if key in historical:
            if record != historical[key]:
                raise ValueError("REWRITTEN_HISTORICAL_RESERVATION")
        elif record["snapshot"]["hard_cap_usd"] != "10" or record["snapshot"]["call_cap"] != 12192:
            raise ValueError("UNBOUND_NEW_RESERVATION")
        normalized[key] = {**record, "snapshot": {**record["snapshot"], "hard_cap_usd": "10"}}
    return FullBudget.resume_full_records({**snapshot, "call_cap": 12192}, normalized, cap_usd="10", call_cap=12192)


def create_stage5_call_extension():
    if STAGE5_CALL_EXTENSION.exists():
        raise ValueError("stage5 call extension record must be new")
    snapshot = latest_paid_snapshot()
    records = pending_records(snapshot)
    authorization, previous = load_authorization(), load_call_extension()
    resume_paid_extended(snapshot, records, authorization, previous)
    retain(STAGE5_CALL_EXTENSION, {"created_at": datetime.now(timezone.utc).isoformat(),
        "human_answer": STAGE5_CALL_EXTENSION_ANSWER, "paid_caps": dict(STAGE5_PAID_CAPS),
        "prior_paid_caps": dict(EXTENDED_PAID_CAPS), "native_caps": dict(NATIVE_CAPS),
        "prior_extension_sha256": hashlib.sha256(checked(CALL_EXTENSION, STATE).read_bytes()).hexdigest(),
        "paid_before": snapshot, "pending_reservation_records": records,
        "authorized_campaign": "12 query runs, 2 extraction runs, 2 repair envelopes; 12 calls admission each",
        "historical_usage_retained": True, "uncertain_refunded": False, "other_protections_changed": False})


def create_call_extension():
    if CALL_EXTENSION.exists():
        raise ValueError("call extension record must be new")
    snapshot = latest_paid_snapshot()
    records = pending_records(snapshot)
    authorization = load_authorization()
    resume_paid(snapshot, records, authorization)
    retain(CALL_EXTENSION, {"created_at": datetime.now(timezone.utc).isoformat(),
        "human_answer": CALL_EXTENSION_ANSWER, "paid_caps": EXTENDED_PAID_CAPS,
        "prior_paid_caps": PAID_CAPS, "native_caps": NATIVE_CAPS,
        "authorization_sha256": hashlib.sha256(checked(AUTHORIZATION, STATE).read_bytes()).hexdigest(),
        "paid_before": snapshot, "pending_reservation_records": records,
        "historical_usage_retained": True, "uncertain_refunded": False,
        "other_protections_changed": False})


def native_transition(last, authorization):
    if (authorization["native_caps"] != NATIVE_CAPS or last["caps"] != OLD_NATIVE_CAPS
            or authorization["native_before"]["caps"] != OLD_NATIVE_CAPS
            or any(last["counts"][key] < authorization["native_before"]["counts"][key] for key in OLD_NATIVE_CAPS)):
        raise ValueError("native quota transition mismatch")
    counts = dict(last["counts"])
    # The predecessor did not append every /info HTTP request. Preserve its
    # entire admitted-request ceiling conservatively instead of resetting an
    # unknown portion. Inference and token reservations remain exact.
    counts["http"] = max(counts["http"], OLD_NATIVE_CAPS["http"])
    return counts, dict(NATIVE_CAPS)


def latest_paid_snapshot():
    candidates = []
    for path in PAID_STATE.glob("provider-*.json"):
        match = re.fullmatch(r"provider-([0-9]{5,})-(reservation|result)\.json", path.name)
        if match is None:
            raise ValueError("unrecognized paid ledger record name")
        candidates.append((int(match[1]), match[2] == "result", path))
    if not candidates:
        raise ValueError("retained paid ledger required")
    ordinal, result, path = max(candidates, key=lambda value: value[:2])
    row = json.loads(checked(path).read_text(encoding="utf-8"))
    if row["snapshot"]["calls"] != ordinal or row["stage"] != ("result" if result else "reservation"):
        raise ValueError("paid ledger filename/snapshot mismatch")
    return row["snapshot"]


def latest_native_record(directory, kind):
    candidates = []
    for path in directory.glob(kind+"-*-reservation.json"):
        match = re.fullmatch(kind+r"-([0-9]{5})-reservation\.json", path.name)
        if match is None:
            raise ValueError("unrecognized native ledger record name")
        candidates.append((int(match[1]), path))
    if not candidates:
        return None
    ordinal, path = max(candidates, key=lambda value: value[0])
    row = json.loads(checked(path).read_text(encoding="utf-8"))
    if row["counts"]["inference" if kind == "native" else "http"] != ordinal:
        raise ValueError("native ledger filename/snapshot mismatch")
    return row


def native_directory_snapshot(directory):
    rows = [row for kind in ("native", "http") if (row := latest_native_record(directory, kind)) is not None]
    transition = directory / "resource-transition.json"
    if transition.is_file():
        rows.append(json.loads(checked(transition).read_text(encoding="utf-8")))
    return max(rows, key=lambda row: (row["counts"]["inference"], row["counts"]["http"])) if rows else None


def continue_native(last, authorization, state, predecessor):
    state, predecessor = checked(state), checked(predecessor)
    target = re.fullmatch(r"rag-advanced-models-20261013-([0-9]{2})", state.name)
    prior = re.fullmatch(r"rag-advanced-models-20261013-([0-9]{2})", predecessor.name)
    if (target is None or prior is None or state.parent != ROOT / "infra/local"
            or predecessor.parent != state.parent or int(prior[1]) < 7 or int(target[1]) != int(prior[1])+1
            or last["caps"] != NATIVE_CAPS or authorization["native_caps"] != NATIVE_CAPS
            or any(last["counts"][key] < authorization["native_before"]["counts"][key] for key in NATIVE_CAPS)):
        raise ValueError("native continuation must retain authorized counters in the next owned namespace")
    return dict(last["counts"]), dict(NATIVE_CAPS)


def native_process_stopped(pid):
    """Fail closed unless Windows proves the recorded worker has exited."""
    import ctypes
    from ctypes import wintypes
    if sys.platform != "win32" or type(pid) is not int or pid <= 0:
        raise ValueError("Windows worker liveness proof required")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only
    if not handle:
        if ctypes.get_last_error() == 87:  # PID no longer exists
            return True
        raise ValueError("cannot prove model worker stopped")
    try:
        return kernel.WaitForSingleObject(handle, 0) == 0
    finally:
        kernel.CloseHandle(handle)


def recover_native_successor(last, authorization, state, predecessor):
    """Skip one stopped successor only when it recorded absolutely no usage.

    No historical ledger is rewritten. The full predecessor counters and caps
    remain charged, including reservations whose result may be unknown.
    """
    state, predecessor = checked(state), checked(predecessor)
    prior = re.fullmatch(r"rag-advanced-models-20261013-([0-9]{2})", predecessor.name)
    if prior is None or int(prior[1]) < 7:
        raise ValueError("recognized native predecessor required")
    skipped = checked(predecessor.parent / f"rag-advanced-models-20261013-{int(prior[1])+1:02d}")
    # Reuse all existing authorization and namespace checks, then require the
    # actual destination to be exactly one slot after the stale successor.
    counts, caps = continue_native(last, authorization, skipped, predecessor)
    if state != predecessor.parent / f"rag-advanced-models-20261013-{int(prior[1])+2:02d}":
        raise ValueError("exact stale-successor recovery destination required")
    if native_directory_snapshot(predecessor) != last:
        raise ValueError("predecessor changed during recovery")
    allowed = {"launch.json", "predecessor.json", "resource-transition.json", "stderr.log", "exit.json"}
    files = list(skipped.iterdir())
    if any(not p.is_file() or p.name not in allowed for p in files):
        raise ValueError("stale successor contains usage or unknown evidence")
    proof = {}
    for directory in (predecessor, skipped):
        launch_path = checked(directory / "launch.json")
        launch = json.loads(launch_path.read_bytes())
        if not native_process_stopped(launch["owned_pid"]):
            raise ValueError("model predecessor or stale successor still running")
        proof[str(launch_path)] = hashlib.sha256(launch_path.read_bytes()).hexdigest()
    inherited_path = checked(skipped / "predecessor.json")
    inherited = json.loads(inherited_path.read_bytes())
    transition_path = checked(skipped / "resource-transition.json")
    transition = json.loads(transition_path.read_bytes())
    if (inherited.get("path") != str(predecessor) or inherited.get("reset") is not False
            or transition.get("reset") is not False or transition.get("caps") != caps
            or inherited.get("retained_counts") != transition.get("counts")
            or set(transition["counts"]) != set(counts)
            or any(type(transition["counts"][k]) is not int or not 0 <= transition["counts"][k] <= counts[k] for k in counts)):
        raise ValueError("stale successor lineage does not match predecessor")
    # A different namespace must never hide usage above any inherited counter.
    for directory in predecessor.parent.glob("rag-advanced-models-*"):
        observed = native_directory_snapshot(checked(directory))
        if observed and (set(observed["counts"]) != set(counts)
                         or any(observed["counts"][k] > counts[k] for k in counts)):
            raise ValueError("other native namespace has additional usage")
    for path in files:
        proof[str(checked(path))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return counts, caps, {"skipped_namespace": str(skipped), "evidence_sha256": proof,
                          "skipped_usage_records": 0, "historical_usage_retained": True,
                          "caps_changed": False}


def paid_view():
    snapshot = latest_paid_snapshot()
    if not AUTHORIZATION.exists():
        return snapshot
    return restore_paid(snapshot, pending_records(snapshot)).snapshot()


def native_view():
    records = [row for directory in (ROOT / "infra/local").glob("rag-advanced-models-20261013-*")
               if (row := native_directory_snapshot(directory)) is not None]
    if not records:
        raise ValueError("retained native ledger required")
    observed = max(records, key=lambda row: (row["counts"]["inference"], row["counts"]["http"]))
    if not AUTHORIZATION.exists():
        return observed
    authorization = load_authorization()
    if observed["caps"] == NATIVE_CAPS:
        return observed
    counts, caps = native_transition(observed, authorization)
    return {**observed, "counts": counts, "caps": caps, "http_prior_actual": None,
            "http_prior_conservative_envelope": OLD_NATIVE_CAPS["http"]}


def create_authorization():
    from evaluate_certificate_rag import paid_snapshot, native_snapshot
    from public_rag_budget import resume_authorized_budget
    snapshot, native = paid_snapshot(), native_snapshot()
    records = pending_records(snapshot)
    migration = json.loads(checked(PAID_STATE / "authorized-cap-3.json").read_text(encoding="utf-8"))
    resume_authorized_budget(snapshot, records, migration)
    if native["caps"] != OLD_NATIVE_CAPS or AUTHORIZATION.exists() or NATIVE_STATE.exists():
        raise ValueError("fresh exact transition required")
    retain(AUTHORIZATION, {"created_at": datetime.now(timezone.utc).isoformat(),
        "human_request": "bỏ giới hạn, cứ làm triệt để đi", "human_answer": HUMAN_ANSWER,
        "paid_caps": PAID_CAPS, "native_caps": NATIVE_CAPS, "paid_before": snapshot,
        "native_before": native, "pending_reservation_records": records,
        "native_namespace": str(checked(NATIVE_STATE)), "native_predecessor": str(checked(NATIVE_PRIOR)),
        "historical_usage_retained": True, "uncertain_refunded": False,
        "other_protections_changed": False})


if __name__ == "__main__":
    create_authorization()
