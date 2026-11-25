"""F1 acceptance: audience resolution matches an independent SQL reference on 40 machine-made audiences; 30 000 recipients publish fast."""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ann_helpers import demo_accounts, draft, make_service, person, sid  # noqa: E402

from campus247.domain.announcements import AnnouncementInvalid, parse_audience  # noqa: E402
from campus247.infrastructure.identity.directory_recipients import LocalRecipientDirectory  # noqa: E402
from campus247.ports.identity import IdentityRole  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "audiences.jsonl"
ROOT = Path(__file__).resolve().parents[2]


def generate(accounts, count=40, seed=20261126):
    """Machine-made audiences: combinations of role, faculty, cohort, class and subjects, with OR between groups and empty edge cases."""
    rng = random.Random(seed)
    roles = ["STUDENT", "SUPPORT_OFFICER", "LECTURER"]
    faculties = sorted({a["faculty_code"] for a in accounts if a.get("faculty_code")})
    classes = sorted({a["class_code"] for a in accounts if a.get("class_code")})
    cohorts = sorted({c[:2] for c in classes})
    subjects = [a["subject_id"] for a in accounts]
    specs = [{"groups": [{}]}, {"groups": [{"roles": ["LECTURER"]}]}, {"groups": [{"class_codes": ["NO-SUCH"]}]}, {"groups": [{"roles": ["STUDENT"], "faculty_codes": ["CNTT"], "cohorts": ["67"]}]}]
    while len(specs) < count:
        groups = []
        for _ in range(rng.randint(1, 3)):
            g = {}
            if rng.random() < .5:
                g["roles"] = rng.sample(roles, rng.randint(1, 2))
            if rng.random() < .5:
                g["faculty_codes"] = rng.sample(faculties, rng.randint(1, 2))
            if rng.random() < .4:
                g["cohorts"] = rng.sample(cohorts, 1)
            if rng.random() < .4:
                g["class_codes"] = rng.sample(classes, rng.randint(1, 3))
            if rng.random() < .3:
                g["subjects"] = rng.sample(subjects, rng.randint(1, 6))
            groups.append(g)
        specs.append({"groups": groups})
    return specs


def reference(accounts, spec):
    """Independent implementation: load the accounts into SQLite and answer with a WHERE clause per group (OR between groups)."""
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE a(subject TEXT, role TEXT, faculty TEXT, class TEXT, cohort TEXT)")
    for a in accounts:
        cls = a.get("class_code")
        db.execute("INSERT INTO a VALUES(?,?,?,?,?)", (a["subject_id"], a["role"], a.get("faculty_code"), cls, cls[:2] if cls and cls[:2].isdigit() else None))
    clauses, args = [], []
    for g in spec["groups"]:
        parts = []
        for column, key in (("role", "roles"), ("faculty", "faculty_codes"), ("cohort", "cohorts"), ("class", "class_codes"), ("subject", "subjects")):
            if g.get(key):
                parts.append(f"{column} IN ({','.join('?' * len(g[key]))})")
                args += g[key]
        clauses.append("(" + (" AND ".join(parts) or "1=1") + ")")
    return {r[0] for r in db.execute("SELECT subject FROM a WHERE " + " OR ".join(clauses), args)}


def test_fixture_is_the_machine_generated_set_and_resolver_equals_sql_reference_on_all_40():
    accounts = demo_accounts()
    generated = generate(accounts)
    FIXTURE.parent.mkdir(exist_ok=True)
    if not FIXTURE.exists():
        FIXTURE.write_text("\n".join(json.dumps(s, sort_keys=True) for s in generated) + "\n", encoding="utf-8")
    specs = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines()]
    assert specs == json.loads(json.dumps(generated))  # fixture and generator cannot drift
    assert len(specs) == 40
    directory = LocalRecipientDirectory(lambda: accounts)
    mismatches = [i for i, spec in enumerate(specs) if {r.subject_id for r in directory.recipients(parse_audience(spec))} != reference(accounts, spec)]
    assert not mismatches, f"audiences differing from the SQL reference: {mismatches}"
    sizes = [len(reference(accounts, s)) for s in specs]
    assert min(sizes) == 0 and max(sizes) == 44  # the set includes the empty and the everyone cases


def test_parse_rejects_bad_shapes():
    for bad in ({}, {"groups": "x"}, {"groups": [{"nope": 1}]}, {"groups": [{"roles": [1]}]}):
        try:
            parse_audience(bad)
        except AnnouncementInvalid:
            continue
        raise AssertionError(bad)


def test_publish_30000_recipients_in_15_seconds(tmp_path):
    accounts = [{"role": "STUDENT", "subject_id": sid(10_000 + n), "faculty_code": "CNTT", "class_code": "66IT1"} for n in range(30_000)]
    accounts.append({"role": "SUPPORT_OFFICER", "subject_id": sid(1), "unit": "x"})
    svc, store, _ = make_service(tmp_path, accounts, enabled=lambda key: False)
    officer = person(sid(1), IdentityRole.SUPPORT_OFFICER)
    created = svc.create_draft(officer, draft(audience={"groups": [{"roles": ["STUDENT"]}]}))
    preview = svc.publish_preview(officer, created["id"])
    started = time.perf_counter()
    svc._snapshots.clear()
    svc.publish_confirm(officer, preview["preview_id"], preview["confirmation_token"], "p")
    while svc.publish_step(created["id"]) == "PUBLISHING":
        pass
    seconds = time.perf_counter() - started
    deliveries = store.one("SELECT COUNT(*) n FROM ann_deliveries")["n"]
    notices = store.one("SELECT COUNT(*) n FROM ops_notifications WHERE kind='ANNOUNCEMENT'")["n"]
    out = ROOT / "evals/results/announcements-20261126"
    out.mkdir(parents=True, exist_ok=True)
    (out / "perf.json").write_text(json.dumps({"recipients": 30_000, "seconds": round(seconds, 2), "batch": 1000, "deliveries": deliveries, "notifications": notices,
                                               "method": "synthetic accounts, local SQLite WAL, one process"}, indent=2), encoding="utf-8")
    assert deliveries == notices == 30_000
    assert seconds <= 15, f"{seconds:.1f}s"
