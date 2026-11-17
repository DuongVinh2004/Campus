"""Uncapped aggregate usage with retained, monotonic native accounting."""
import json
import re


def native_snapshot(directory, checked):
    rows = []
    transition = directory / "resource-transition.json"
    if transition.is_file():
        rows.append(json.loads(checked(transition).read_text(encoding="utf-8")))
    for kind, counter in (("native", "inference"), ("http", "http")):
        candidates = []
        for path in directory.glob(kind + "-*-reservation.json"):
            match = re.fullmatch(kind + r"-([0-9]{5,})-reservation\.json", path.name)
            if not match:
                raise ValueError("Unrecognized accounting record")
            candidates.append((int(match[1]), path))
        if candidates:
            for ordinal, path in sorted(candidates, reverse=True)[:2]:
                value = json.loads(checked(path).read_text(encoding="utf-8"))
                if value["counts"][counter] != ordinal:
                    raise ValueError("Accounting record counter mismatch")
                rows.append(value)
    if not rows:
        raise ValueError("Retained accounting is required")
    value = max(rows, key=lambda r: (r["counts"]["inference"], r["counts"]["http"]))
    if (set(value["counts"]) != {"http", "inference", "tokens"}
            or any(type(n) is not int or n < 0 for n in value["counts"].values())
            or any(value["counts"][k] < r["counts"][k] for r in rows for k in value["counts"])):
        raise ValueError("Accounting counters regressed")
    return value


def accounting_continuation(previous):
    return dict(previous["counts"]), {k: None for k in ("http", "inference", "tokens")}


def exceeds(count, cap):
    return cap is not None and count > cap
