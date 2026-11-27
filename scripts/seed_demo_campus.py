"""Seed the simulated semester (scripts/demo/campus_2026hk1.py) into the local runtime stores.

    python scripts/seed_demo_campus.py plan        # what would be created, writes nothing
    python scripts/seed_demo_campus.py accounts    # simulated students/officers + learning lecturers
    python scripts/seed_demo_campus.py ops         # rooms, timetables, exams, requests, bookings, notifications
    python scripts/seed_demo_campus.py verify      # counts of the batch in every store

Rules: existing accounts, keys and rows are never changed or removed. Every file touched is first copied to
infra/local/seed-backup-<stamp>/ with its SHA-256. Each step runs once per batch (DEMO-2026HK1-01); a rerun reports
"already seeded". Passwords go only to credentials files next to the identity files and are never printed.
Everything created is simulated and labelled so; none of it is HUCE data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
import shutil
import sqlite3
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api/src"), str(ROOT / "scripts")]

from demo import campus_2026hk1 as sem  # noqa: E402
from campus247.domain.shared.values import generate_uuid7  # noqa: E402
from campus247.infrastructure.identity.local_directory import ISSUER as DIRECTORY_ISSUER, SCHEMA as DIRECTORY_SCHEMA  # noqa: E402

STATE = ROOT / "infra/local/knowledge-platform-20261023"
LEARNING = ROOT / "infra/local/learning-materials-20261104-01"
TENANT = "huce-local-public"
DIRECTORY = STATE / "campus-directory.json"
DIRECTORY_CREDENTIALS = STATE / "campus-directory-credentials.json"
OPS_DB = STATE / "campus-ops.sqlite3"
RECEIPTS = ROOT / "infra/local/seed-demo-2026hk1"
NOW = datetime.now(timezone.utc).replace(microsecond=0)
LEARNING_ACCOUNTS = [(f"gv.demo{n:02d}", key, "LECTURER") for n, key in enumerate(sem.LECTURERS, start=1)] + [
    ("qt.hoctap.demo", None, "SYSTEM_ADMIN")]


def inside(path: Path) -> Path:
    resolved = path.resolve()
    if ROOT.resolve() not in resolved.parents:
        raise ValueError(f"outside the workspace: {resolved}")
    return resolved


def backup(*paths: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = inside(ROOT / "infra/local" / ("seed-backup-" + stamp + "-" + secrets.token_hex(2)))
    target.mkdir(parents=True)  # never reuse a backup directory
    manifest = []
    for path in paths:
        if not path.exists():
            continue
        destination = target / path.name
        if path.suffix == ".sqlite3":  # consistent copy of a live WAL database
            source = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
            copy = sqlite3.connect(destination)
            source.backup(copy)
            copy.close()
            source.close()
        else:
            shutil.copy2(path, destination)
        manifest.append({"source": str(path.relative_to(ROOT)), "copy": str(destination.relative_to(ROOT)),
                         "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"backup: {target.relative_to(ROOT)} ({len(manifest)} files)")
    return target


def write_new(path: Path, value) -> None:
    with inside(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def replace_json(path: Path, value) -> None:
    temporary = inside(path.with_suffix(path.suffix + ".seed-tmp"))
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    temporary.replace(path)


def hashed(password: str) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    return salt.hex(), hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()


def students() -> list[sem.Student]:
    return sem.build_students(random.Random(20260907))


# ------------------------------------------------------------------------------------------------------ accounts
def accounts(_args) -> None:
    learning_identity = LEARNING / "identity.json"
    learning_credentials = LEARNING / "credentials.json"
    identity = json.loads(learning_identity.read_text(encoding="utf-8"))
    missing_learning = [a for a in LEARNING_ACCOUNTS if a[0] not in {x["username"] for x in identity["accounts"]}]
    if DIRECTORY.exists() and not missing_learning:
        print("accounts: already seeded")
        return
    backup(learning_identity, learning_credentials, DIRECTORY, DIRECTORY_CREDENTIALS)
    if not DIRECTORY.exists():
        rows, secrets_out = [], []
        for s in students():
            password = secrets.token_urlsafe(12)
            salt, digest = hashed(password)
            subject = generate_uuid7()
            rows.append({"username": s.username, "role": "STUDENT", "subject_id": subject, "display_name": s.display_name,
                         "student_code": s.student_code, "faculty_code": s.faculty, "class_code": s.class_code,
                         "salt": salt, "password_hash": digest})
            secrets_out.append({"username": s.username, "password": password, "role": "STUDENT", "display_name": s.display_name,
                                "class_code": s.class_code})
        for username, name, unit in sem.STAFF:
            password = secrets.token_urlsafe(12)
            salt, digest = hashed(password)
            rows.append({"username": username, "role": "SUPPORT_OFFICER", "subject_id": generate_uuid7(), "display_name": name,
                         "staff_code": "SIM-NV-" + username[-2:], "unit": unit, "salt": salt, "password_hash": digest})
            secrets_out.append({"username": username, "password": password, "role": "SUPPORT_OFFICER", "display_name": name, "unit": unit})
        directory = {"schema": DIRECTORY_SCHEMA, "issuer": DIRECTORY_ISSUER, "tenant": TENANT, "simulated": True,
                     "university_identity_verified": False, "seed_batch": sem.BATCH,
                     "authority": "Owner approval 2026-11-21: simulated demo semester accounts, not HUCE SSO",
                     "signing_key": secrets.token_hex(32), "accounts": rows}
        write_new(DIRECTORY_CREDENTIALS, {"seed_batch": sem.BATCH, "login_url": "http://127.0.0.1:8015/login",
                                          "scope": "Simulated demo accounts; local runtime only", "accounts": secrets_out})
        write_new(DIRECTORY, directory)
        print(f"accounts: {len(rows)} directory accounts written to {DIRECTORY.name} (passwords in {DIRECTORY_CREDENTIALS.name})")
    if missing_learning:
        credentials = json.loads(learning_credentials.read_text(encoding="utf-8"))
        for username, key, role in missing_learning:
            password = secrets.token_urlsafe(12)
            salt, digest = hashed(password)
            subject = generate_uuid7()
            name = sem.LECTURERS[key][0] if key else "Quản trị Học tập (mô phỏng)"
            identity["accounts"].append({"username": username, "role": role, "subject_id": subject, "display_name": name,
                                         "is_synthetic": True, "salt": salt, "password_hash": digest})
            credentials["accounts"].append({"username": username, "password": password, "role": role, "subject_id": subject})
        replace_json(learning_credentials, credentials)
        replace_json(learning_identity, identity)
        print(f"accounts: {len(missing_learning)} learning accounts added to {learning_identity.name}")


def directory_people():
    value = json.loads(DIRECTORY.read_text(encoding="utf-8"))
    by_user = {a["username"]: a for a in value["accounts"]}
    people = [(s, by_user[s.username]) for s in students()]
    staff = [by_user[u] for u, _, _ in sem.STAFF]
    return people, staff


# ----------------------------------------------------------------------------------------------------------- ops
def _check_timetable_clashes() -> None:
    seen = {}
    for class_code, (_, slots) in sem.CLASSES.items():
        for weekday, period, code, room in slots:
            key = (weekday, period, room)
            if key in seen:
                raise ValueError(f"room clash {key}: {seen[key]} and {class_code}")
            seen[key] = class_code


def ops(args) -> None:
    _check_timetable_clashes()
    marker = "seed_batch:" + sem.BATCH
    con = sqlite3.connect(OPS_DB, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    if con.execute("SELECT 1 FROM ops_meta WHERE key=?", (marker,)).fetchone():
        print("ops: already seeded")
        return
    people, staff = directory_people()
    if not args.dry_run:
        backup(OPS_DB)
    rng = random.Random(1121)
    receipt = {"seed_batch": sem.BATCH, "created_at": sem.iso(NOW), "tables": {}}
    audit_rows: list[tuple] = []
    notes: list[tuple] = []

    def keep(table, row_id):
        receipt["tables"].setdefault(table, []).append(row_id)

    def notify(recipient, kind, title, body, link, at, read_ratio=0.85):
        read_at = sem.iso(at + timedelta(hours=rng.randint(1, 30))) if (NOW - at > timedelta(days=2) and rng.random() < read_ratio) else None
        if read_at and read_at > sem.iso(NOW):
            read_at = None
        notes.append((generate_uuid7(), recipient, kind, title, body, link, sem.iso(at), read_at))

    con.execute("BEGIN IMMEDIATE")
    try:
        # Rooms
        existing = {r["code"]: dict(r) for r in con.execute("SELECT * FROM ops_rooms")}
        for entry in sem.EXTRA_ROOMS:
            code, name, building, floor, capacity, kind, features, *status = entry
            if code in existing:
                continue
            room_id = generate_uuid7()
            con.execute("INSERT INTO ops_rooms(id,code,name,building,floor,capacity,kind,features,status,source) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (room_id, code, name, building, floor, capacity, kind, json.dumps(features), status[0] if status else "ACTIVE", "LOCAL_SYNTHETIC"))
            keep("ops_rooms", room_id)
        rooms = {r["code"]: dict(r) for r in con.execute("SELECT * FROM ops_rooms")}
        for class_code, (_, slots) in sem.CLASSES.items():
            for *_, room in slots:
                if room not in rooms:
                    raise ValueError(f"timetable room missing: {room}")

        # Timetables and exams
        created = sem.iso(datetime(2026, 9, 1, 2, 0, tzinfo=timezone.utc))
        timetables = {c: sem.timetable(c) for c in sem.CLASSES}
        personal = [("Họp nhóm đồ án", "Thư viện tầng 2"), ("Làm thêm buổi tối", "Ngoài trường"), ("Câu lạc bộ tiếng Anh", "Nhà sinh viên"),
                    ("Tập thể thao", "Sân vận động"), ("Ôn thi cùng bạn", "Phòng học nhóm Thư viện")]
        for student, account in people:
            for row in timetables[student.class_code]:
                row_id = generate_uuid7()
                con.execute("""INSERT INTO ops_schedule(id,owner_key,kind,course_code,course_name,starts_at,ends_at,location,instructor,note,source,created_at,updated_at)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (row_id, student.student_code, row["kind"], row["course_code"], row["course_name"], row["starts_at"], row["ends_at"],
                             row["location"], row["instructor"], row["note"], "LOCAL_SYNTHETIC", created, created))
                keep("ops_schedule", row_id)
            for n in range(rng.randint(2, 4)):
                title, place = rng.choice(personal)
                day = date(2026, 11, 16) + timedelta(days=rng.randint(0, 20))
                start = time(rng.choice([18, 19]), 0) if title != "Họp nhóm đồ án" else time(rng.choice([14, 16]), 0)
                if day.weekday() < 5 and start.hour < 18 and title == "Họp nhóm đồ án":
                    start = time(18, 30)
                end = (datetime.combine(day, start) + timedelta(minutes=90)).time()
                at = sem.iso(NOW - timedelta(days=rng.randint(1, 20)))
                row_id = generate_uuid7()
                con.execute("""INSERT INTO ops_schedule(id,owner_key,kind,course_code,course_name,starts_at,ends_at,location,instructor,note,source,created_at,updated_at)
                               VALUES(?,?,'PERSONAL','CÁ NHÂN',?,?,?,?,?,?,'USER',?,?)""",
                            (row_id, student.student_code, title, sem.iso(sem.utc(day, start)), sem.iso(sem.utc(day, end)), place,
                             account["display_name"], "", at, at))
                keep("ops_schedule", row_id)
                audit_rows.append((at, account["subject_id"], "schedule.create", row_id, {}))

        # Requests (tickets) with their history
        total = con.execute("SELECT COUNT(*) FROM ops_tickets").fetchone()[0]
        by_unit = {"STUDENT_CERTIFICATE": [staff[0], staff[2]], "GRADE_APPEAL": [staff[0], staff[2]], "GENERAL_SUPPORT": [staff[1], staff[0]]}
        plans = []
        for student, account in people:
            for _ in range(rng.choice([3, 4, 4, 5, 5, 6])):
                plans.append((student, account))
        rng.shuffle(plans)
        start_window = datetime(2026, 9, 10, 1, 0, tzinfo=timezone.utc)
        span = (NOW - start_window).total_seconds()
        tickets = []
        for student, account in plans:
            created_at = start_window + timedelta(seconds=rng.random() ** 0.8 * span)
            created_at = created_at.replace(hour=rng.randint(0, 10), minute=rng.randint(0, 59), second=rng.randint(0, 59))
            if created_at > NOW - timedelta(minutes=30):
                created_at = NOW - timedelta(hours=rng.randint(1, 20))
            tickets.append((created_at, student, account))
        tickets.sort(key=lambda t: t[0])
        for created_at, student, account in tickets:
            kind = rng.choices(list(sem.STAFF_REPLIES), weights=[5, 2, 4])[0]
            age = NOW - created_at
            if age < timedelta(days=1):
                status = rng.choice(["SUBMITTED", "SUBMITTED", "IN_REVIEW"])
            elif age < timedelta(days=6):
                status = rng.choice(["SUBMITTED", "IN_REVIEW", "IN_REVIEW", "NEED_INFO", "RESOLVED"])
            elif age < timedelta(days=8):
                status = rng.choices(["IN_REVIEW", "NEED_INFO", "RESOLVED", "REJECTED", "CANCELLED"], weights=[3, 2, 6, 1, 1])[0]
            else:  # an office that mostly keeps its 7-day promise: only a few old requests are still open
                status = rng.choices(["RESOLVED", "REJECTED", "CANCELLED", "IN_REVIEW", "NEED_INFO"], weights=[80, 8, 7, 2, 2])[0]
            courses = sorted({code for _, _, code, _ in sem.CLASSES[student.class_code][1]})
            if kind == "STUDENT_CERTIFICATE":
                purpose, recipient = rng.choice(sem.CERT_PURPOSES)
                title = "Giấy xác nhận sinh viên đang học"
                summary = f"Mục đích: {purpose}\nĐơn vị nhận: {recipient}\nSố bản: {rng.choice([1, 1, 2])}\nNội dung: Em cần giấy xác nhận đang theo học lớp {student.class_code} để nộp hồ sơ."
                fields = {"purpose": purpose, "recipient": recipient}
            elif kind == "GRADE_APPEAL":
                code = rng.choice(courses)
                title = "Phúc khảo kết quả học tập"
                summary = f"Học phần: {sem.COURSES[code][0]} ({code})\nKỳ thi: Thi giữa kỳ\nNội dung: Em xin phúc khảo vì {rng.choice(sem.APPEAL_REASONS)}."
                fields = {"course": sem.COURSES[code][0], "course_code": code}
            else:
                topic, text = rng.choice(sem.GENERAL_TOPICS)
                title = topic
                summary = f"Nội dung: {text}"
                fields = {"reason": topic}
            officer = rng.choice(by_unit[kind])
            assigned = status not in ("SUBMITTED",) and not (status == "CANCELLED" and rng.random() < 0.6)
            ticket_id = generate_uuid7()
            total += 1
            ticket_code = f"HS-2026-{total:06d}"
            due = created_at + timedelta(days=7)
            events = [(created_at, "STUDENT", account, "CREATED", "Sinh viên gửi hồ sơ.", "PUBLIC")]
            notify(account["subject_id"], "TICKET", f"Đã gửi hồ sơ {ticket_code}", f"{title} — đang chờ cán bộ tiếp nhận.", f"/tickets?id={ticket_id}", created_at)
            audit_rows.append((sem.iso(created_at), account["subject_id"], "ticket.submit", ticket_id, {"code": ticket_code, "kind": kind}))
            moment = created_at
            if assigned:
                moment = moment + timedelta(hours=rng.randint(2, 30))
                if moment > NOW:
                    moment = NOW - timedelta(minutes=rng.randint(5, 50))
                events.append((moment, "SUPPORT_OFFICER", officer, "CLAIMED", "Cán bộ tiếp nhận hồ sơ.", "PUBLIC"))
                notify(account["subject_id"], "TICKET", f"Hồ sơ {ticket_code} đang được xử lý", f"{officer['display_name']} đã tiếp nhận hồ sơ của bạn.", f"/tickets?id={ticket_id}", moment)
                audit_rows.append((sem.iso(moment), officer["subject_id"], "ticket.claim", ticket_id, {}))
                if rng.random() < 0.35:
                    events.append((moment + timedelta(minutes=10), "SUPPORT_OFFICER", officer, "NOTE", rng.choice(sem.STAFF_NOTES), "INTERNAL"))
                replies = sem.STAFF_REPLIES[kind]
                if status in ("NEED_INFO",) or (status in ("RESOLVED", "IN_REVIEW") and rng.random() < 0.3):
                    ask_at = min(moment + timedelta(hours=rng.randint(1, 20)), NOW - timedelta(minutes=20))
                    events.append((ask_at, "SUPPORT_OFFICER", officer, "STAFF_REPLY", replies["NEED_INFO"], "PUBLIC"))
                    events.append((ask_at + timedelta(seconds=1), "SUPPORT_OFFICER", officer, "STATUS_CHANGE", "Trạng thái: IN_REVIEW → NEED_INFO", "PUBLIC"))
                    notify(account["subject_id"], "TICKET", f"Phản hồi mới cho hồ sơ {ticket_code}", replies["NEED_INFO"][:140], f"/tickets?id={ticket_id}", ask_at)
                    moment = ask_at
                    if status != "NEED_INFO":
                        reply_at = min(moment + timedelta(hours=rng.randint(2, 40)), NOW - timedelta(minutes=10))
                        events.append((reply_at, "STUDENT", account, "STUDENT_REPLY", rng.choice(sem.STUDENT_FOLLOWUPS), "PUBLIC"))
                        moment = reply_at
                if status == "IN_REVIEW" and rng.random() < 0.5:
                    at = min(moment + timedelta(hours=rng.randint(1, 10)), NOW - timedelta(minutes=5))
                    events.append((at, "SUPPORT_OFFICER", officer, "STAFF_REPLY", replies["IN_REVIEW"], "PUBLIC"))
                    notify(account["subject_id"], "TICKET", f"Phản hồi mới cho hồ sơ {ticket_code}", replies["IN_REVIEW"][:140], f"/tickets?id={ticket_id}", at)
                    moment = at
                if status in ("RESOLVED", "REJECTED"):
                    at = min(moment + timedelta(hours=rng.randint(4, 70)), NOW - timedelta(minutes=5))
                    events.append((at, "SUPPORT_OFFICER", officer, "STAFF_REPLY", replies[status], "PUBLIC"))
                    events.append((at + timedelta(seconds=1), "SUPPORT_OFFICER", officer, "STATUS_CHANGE",
                                   f"Trạng thái: {'NEED_INFO' if any(e[3] == 'STUDENT_REPLY' for e in events) else 'IN_REVIEW'} → {status}", "PUBLIC"))
                    notify(account["subject_id"], "TICKET", f"Phản hồi mới cho hồ sơ {ticket_code}", replies[status][:140], f"/tickets?id={ticket_id}", at)
                    audit_rows.append((sem.iso(at), officer["subject_id"], "ticket.staff_reply", ticket_id, {"status": status}))
                    moment = at
            if status == "CANCELLED":
                at = min(moment + timedelta(hours=rng.randint(1, 48)), NOW - timedelta(minutes=5))
                events.append((at, "STUDENT", account, "STATUS_CHANGE", "Sinh viên hủy hồ sơ. Lý do: Em đã tự giải quyết được, xin hủy yêu cầu.", "PUBLIC"))
                notify(account["subject_id"], "TICKET", f"Đã hủy hồ sơ {ticket_code}", "Hồ sơ đã được hủy theo yêu cầu của bạn.", f"/tickets?id={ticket_id}", at)
                audit_rows.append((sem.iso(at), account["subject_id"], "ticket.cancel", ticket_id, {}))
                moment = at
            con.execute("""INSERT INTO ops_tickets(id,code,owner_subject_id,owner_display,owner_code,service_kind,title,summary,fields,status,priority,
                           assignee_subject_id,assignee_display,created_at,updated_at,due_at,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (ticket_id, ticket_code, account["subject_id"], account["display_name"], student.student_code, kind, title, summary,
                         json.dumps(fields, ensure_ascii=False), status, "HIGH" if rng.random() < 0.08 else "NORMAL",
                         officer["subject_id"] if assigned else None, officer["display_name"] if assigned else None,
                         sem.iso(created_at), sem.iso(moment), sem.iso(due), f"{sem.BATCH}:{ticket_id}"))
            keep("ops_tickets", ticket_id)
            for at, role, who, ekind, body, visibility in events:
                event_id = generate_uuid7()
                con.execute("INSERT INTO ops_ticket_events(id,ticket_id,actor_subject_id,actor_role,actor_display,kind,body,visibility,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                            (event_id, ticket_id, who["subject_id"], role, who["display_name"], ekind, body, visibility, sem.iso(at)))
                keep("ops_ticket_events", event_id)

        # Room bookings (meeting / study / club rooms only: never over a class or exam)
        bookable = [r for r in rooms.values() if r["kind"] in ("meeting", "study") and r["status"] == "ACTIVE"]
        taken: dict[str, list[tuple[datetime, datetime]]] = {}
        for r in con.execute("SELECT room_id, starts_at, ends_at FROM ops_room_bookings WHERE status='CONFIRMED'"):
            taken.setdefault(r["room_id"], []).append((datetime.fromisoformat(r["starts_at"]), datetime.fromisoformat(r["ends_at"])))
        future_count: dict[str, int] = {}
        bookings = 0
        for student, account in people * 4:
            for _ in range(10):
                room = rng.choice(bookable)
                offset = rng.randint(-60, 13)
                day = (NOW.astimezone(sem.ICT) + timedelta(days=offset)).date()
                if day.weekday() == 6:
                    continue
                start = time(rng.choice([7, 8, 9, 10, 13, 14, 15, 16, 17, 18, 19]), rng.choice([0, 15, 30, 45]))
                minutes = rng.choice([60, 90, 120, 120, 180])
                begin = sem.utc(day, start)
                end = begin + timedelta(minutes=minutes)
                if end.astimezone(sem.ICT).time() > time(21, 0) or end.astimezone(sem.ICT).date() != day:
                    continue
                future = begin > NOW
                if future and future_count.get(account["subject_id"], 0) >= 2:
                    continue
                if any(begin < e and end > s for s, e in taken.get(room["id"], [])):
                    continue
                cancelled = rng.random() < 0.12
                created_at = min(begin - timedelta(days=rng.randint(1, 10), hours=rng.randint(0, 8)), NOW - timedelta(hours=1))
                if not cancelled:
                    taken.setdefault(room["id"], []).append((begin, end))
                if future and not cancelled:
                    future_count[account["subject_id"]] = future_count.get(account["subject_id"], 0) + 1
                booking_id = generate_uuid7()
                code = "BK-" + begin.astimezone(sem.ICT).strftime("%y%m%d") + "-" + secrets.token_hex(2).upper()
                cancel_at = min(created_at + timedelta(hours=rng.randint(2, 48)), begin - timedelta(hours=1), NOW) if cancelled else None
                con.execute("""INSERT INTO ops_room_bookings(id,code,room_id,owner_subject_id,owner_display,starts_at,ends_at,purpose,attendees,status,
                               idempotency_key,created_at,cancelled_at,cancel_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (booking_id, code, room["id"], account["subject_id"], account["display_name"], sem.iso(begin), sem.iso(end),
                             rng.choice(sem.BOOKING_PURPOSES), rng.randint(2, min(room["capacity"], 12)), "CANCELLED" if cancelled else "CONFIRMED",
                             f"{sem.BATCH}:{booking_id}", sem.iso(created_at), sem.iso(cancel_at) if cancel_at else None,
                             rng.choice(sem.CANCEL_REASONS) if cancelled else None))
                keep("ops_room_bookings", booking_id)
                when = begin.astimezone(sem.ICT).strftime("%H:%M %d/%m/%Y")
                notify(account["subject_id"], "ROOM_BOOKING", "Đã đặt phòng " + room["code"], f"Mã {code} · {when}", "/rooms", created_at)
                audit_rows.append((sem.iso(created_at), account["subject_id"], "room.book", booking_id, {"room": room["code"], "code": code}))
                if cancelled:
                    notify(account["subject_id"], "ROOM_BOOKING", "Đã hủy đặt phòng", f"Mã {code} đã được hủy.", "/rooms", cancel_at)
                    audit_rows.append((sem.iso(cancel_at), account["subject_id"], "room.cancel", booking_id, {"code": code}))
                bookings += 1
                break

        # Exam reminders for the coming finals (what the reminder job would have sent)
        for student, account in people:
            for row in timetables[student.class_code]:
                if row["kind"] == "EXAM" and NOW < datetime.fromisoformat(row["starts_at"]) < NOW + timedelta(days=50) and rng.random() < 0.5:
                    when = datetime.fromisoformat(row["starts_at"]).astimezone(sem.ICT).strftime("%H:%M %d/%m/%Y")
                    notify(account["subject_id"], "REMINDER", "Sắp đến lịch thi", f"{row['course_name']} · {when} · phòng {row['location']}",
                           "/schedule", NOW - timedelta(hours=rng.randint(1, 30)), read_ratio=0.3)

        for row in notes:
            con.execute("INSERT INTO ops_notifications(id,recipient_subject_id,kind,title,body,link,created_at,read_at) VALUES(?,?,?,?,?,?,?,?)", row)
            keep("ops_notifications", row[0])
        for at, actor, action, resource, detail in sorted(audit_rows, key=lambda r: r[0]):
            cursor = con.execute("INSERT INTO ops_audit(at,actor,action,resource,detail) VALUES(?,?,?,?,?)",
                                 (at, actor, action, resource, json.dumps(detail, ensure_ascii=False)))
            keep("ops_audit", cursor.lastrowid)
        con.execute("INSERT INTO ops_meta(key,value) VALUES(?,?)", (marker, sem.iso(NOW)))
        counts = {table: len(ids) for table, ids in receipt["tables"].items()}
        if args.dry_run:
            con.execute("ROLLBACK")
            print("ops (dry run, nothing written):", json.dumps(counts))
            return
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    (RECEIPTS / "ops-receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print("ops:", json.dumps(counts))


# -------------------------------------------------------------------------------------------------------- verify
def remove_ops(args) -> None:
    """Delete exactly the rows this batch created (ids from its receipt); nothing else is touched."""
    receipt_path = RECEIPTS / "ops-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt["seed_batch"] != sem.BATCH:
        raise ValueError("receipt of another batch")
    backup(OPS_DB)
    con = sqlite3.connect(OPS_DB, timeout=30, isolation_level=None)
    con.execute("BEGIN IMMEDIATE")
    try:
        removed = {}
        # children before parents (foreign keys)
        for table in ("ops_ticket_events", "ops_notifications", "ops_audit", "ops_room_bookings", "ops_tickets", "ops_schedule", "ops_rooms"):
            ids = receipt["tables"].get(table, [])
            n = 0
            for chunk in range(0, len(ids), 500):
                part = ids[chunk:chunk + 500]
                n += con.execute(f"DELETE FROM {table} WHERE id IN ({','.join('?' * len(part))})", part).rowcount
            removed[table] = n
        con.execute("DELETE FROM ops_meta WHERE key=?", ("seed_batch:" + sem.BATCH,))
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    receipt_path.rename(receipt_path.with_name(f"ops-receipt-removed-{NOW.strftime('%Y%m%dT%H%M%SZ')}.json"))
    print("removed:", json.dumps(removed))


def verify(_args) -> None:
    out = {}
    if DIRECTORY.exists():
        value = json.loads(DIRECTORY.read_text(encoding="utf-8"))
        out["directory_accounts"] = {role: sum(a["role"] == role for a in value["accounts"]) for role in ("STUDENT", "SUPPORT_OFFICER")}
    identity = json.loads((LEARNING / "identity.json").read_text(encoding="utf-8"))
    out["learning_demo_accounts"] = sum(a["username"] in {u for u, _, _ in LEARNING_ACCOUNTS} for a in identity["accounts"])
    con = sqlite3.connect(f"file:{OPS_DB.as_posix()}?mode=ro", uri=True)
    receipt = RECEIPTS / "ops-receipt.json"
    if receipt.exists():
        tables = json.loads(receipt.read_text(encoding="utf-8"))["tables"]
        out["ops_batch"] = {}
        for table, ids in tables.items():
            column = "id"
            present = 0
            for chunk in range(0, len(ids), 500):
                part = ids[chunk:chunk + 500]
                present += con.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IN ({','.join('?' * len(part))})", part).fetchone()[0]
            out["ops_batch"][table] = f"{present}/{len(ids)}"
        out["tickets_by_status"] = dict(con.execute(
            "SELECT status, COUNT(*) FROM ops_tickets WHERE idempotency_key LIKE ? GROUP BY status", (sem.BATCH + ":%",)).fetchall())
    print(json.dumps(out, ensure_ascii=False, indent=1))


def plan(_args) -> None:
    people = students()
    rows = sum(len(sem.timetable(s.class_code)) for s in people)
    print(json.dumps({"students": len(people), "officers": len(sem.STAFF), "learning_accounts": len(LEARNING_ACCOUNTS),
                      "extra_rooms": len(sem.EXTRA_ROOMS), "timetable_rows": rows, "learning_courses": len(sem.LEARNING),
                      "learning_offerings": sum(len(v[1]) for v in sem.LEARNING.values()),
                      "chat_questions": len(sem.CHAT_QUESTIONS)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan").set_defaults(run=plan)
    sub.add_parser("accounts").set_defaults(run=accounts)
    o = sub.add_parser("ops")
    o.add_argument("--dry-run", action="store_true")
    o.set_defaults(run=ops)
    sub.add_parser("verify").set_defaults(run=verify)
    sub.add_parser("remove-ops", help="delete only the rows recorded in this batch's receipt").set_defaults(run=remove_ops)
    parsed = parser.parse_args()
    parsed.run(parsed)
