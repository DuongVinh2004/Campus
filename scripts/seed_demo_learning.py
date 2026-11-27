"""Seed the simulated semester's learning area through the RUNNING runtime's own API (as real users would).

    python scripts/seed_demo_learning.py pdfs        # render the simulated lecture PDFs (local Chrome)
    python scripts/seed_demo_learning.py classes     # term, courses, class sections, members (admin, preview+confirm)
    python scripts/seed_demo_learning.py materials   # sessions, uploads (ClamAV scan), publication (lecturers)
    python scripts/seed_demo_learning.py activity    # reading progress, bookmarks, notes, class questions and replies

Each step records what it created in infra/local/seed-demo-2026hk1/learning-receipt.json and skips what is already
there, so a rerun continues where it stopped. Nothing existing is changed. Credentials are read from the local
credentials files and never printed. All content is simulated (see scripts/demo/campus_2026hk1.py).
"""
from __future__ import annotations

import argparse
import html
import json
import random
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts")]
from demo import campus_2026hk1 as sem  # noqa: E402

BASE = "http://127.0.0.1:8015"
RECEIPTS = ROOT / "infra/local/seed-demo-2026hk1"
RECEIPT = RECEIPTS / "learning-receipt.json"
PDF_DIR = ROOT / ".tooling/demo-learning-pdfs-2026hk1"
LEARNING_CREDENTIALS = ROOT / "infra/local/learning-materials-20261104-01/credentials.json"
DIRECTORY = ROOT / "infra/local/knowledge-platform-20261023/campus-directory.json"
DIRECTORY_CREDENTIALS = ROOT / "infra/local/knowledge-platform-20261023/campus-directory-credentials.json"


def load_receipt() -> dict:
    if RECEIPT.exists():
        return json.loads(RECEIPT.read_text(encoding="utf-8"))
    return {"seed_batch": sem.BATCH, "courses": {}, "offerings": {}, "members": {}, "sessions": {}, "materials": {}, "activity": {}}


def save(receipt: dict) -> None:
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(RECEIPT)


class Api:
    """One signed-in person. Learning writes need the marker header the web client sends."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.client = httpx.Client(base_url=BASE, trust_env=False, timeout=60,
                                   headers={"Origin": BASE, "X-Campus-Request": "learning"})
        reply = self.client.post("/v1/knowledge/platform/session", json={"username": username, "password": password})
        if reply.status_code != 200:
            raise SystemExit(f"sign-in refused for {username} (HTTP {reply.status_code})")

    def call(self, method: str, path: str, **kw) -> dict:
        headers = kw.pop("headers", {})
        if method in {"POST", "PUT", "PATCH"}:
            headers = {"Idempotency-Key": str(uuid.uuid4())} | headers
        for attempt in range(8):
            reply = self.client.request(method, "/v1/learning" + path, headers=headers, **kw)
            if reply.status_code == 429:
                time.sleep(int(reply.headers.get("Retry-After", "5")) + 1)
                continue
            if reply.status_code >= 400:
                raise RuntimeError(f"{self.username} {method} {path}: HTTP {reply.status_code} {reply.text[:300]}")
            return reply.json() if reply.content else {}
        raise RuntimeError(f"{self.username} {method} {path}: still rate limited")

    def confirmed(self, action: str, target: str | None, payload: dict) -> dict:
        preview = self.call("POST", "/action-previews", json={"action": action, "target_id": target, "payload": payload})
        return payload | {k: preview[k] for k in ("preview_id", "confirmation_token")}


def items(value):
    return value["items"] if isinstance(value, dict) and "items" in value else value


def learning_accounts() -> dict:
    return {a["username"]: a for a in json.loads(LEARNING_CREDENTIALS.read_text(encoding="utf-8"))["accounts"]}


def directory() -> tuple[dict, dict]:
    accounts = {a["username"]: a for a in json.loads(DIRECTORY.read_text(encoding="utf-8"))["accounts"]}
    passwords = {a["username"]: a["password"] for a in json.loads(DIRECTORY_CREDENTIALS.read_text(encoding="utf-8"))["accounts"]}
    return accounts, passwords


def class_students(class_code: str) -> list[dict]:
    accounts, _ = directory()
    return [a for a in accounts.values() if a.get("class_code") == class_code]


# ------------------------------------------------------------------------------------------------------------ pdfs
STYLE = """<style>body{font-family:Arial,sans-serif;font-size:12.5pt;color:#1b1b1b;line-height:1.5}
h1{font-size:22pt;color:#163b67;margin:0 0 6pt}h2{font-size:15pt;color:#163b67;border-bottom:1px solid #c9d6e6;padding-bottom:3pt;margin-top:18pt}
.meta{color:#555;font-size:10.5pt}.cover{height:240mm;display:flex;flex-direction:column;justify-content:center;break-after:page}
.cover h1{font-size:28pt}.box{background:#f1f6fc;border-left:4px solid #163b67;padding:8pt 12pt;margin:10pt 0}
table{border-collapse:collapse;width:100%;font-size:11pt}td,th{border:1px solid #9aa9bb;padding:5pt 7pt;text-align:left}th{background:#e6eef8}
section{break-after:page}section:last-child{break-after:auto}.sim{color:#8a4b00;font-size:10pt}</style>"""


def page(title: str, body: str) -> str:
    return f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>{html.escape(title)}</title>{STYLE}</head><body>{body}</body></html>'


def syllabus_html(code: str) -> str:
    lecturer_key, classes, goals, lectures = sem.LEARNING[code]
    name, credits = sem.COURSES[code]
    teacher = sem.LECTURERS[lecturer_key][0]
    rows = "".join(f"<tr><td>{w}</td><td>{html.escape(t)}</td><td>Đọc tài liệu buổi {w}, làm bài tập cuối chương</td></tr>"
                   for w, (t, _) in enumerate(lectures, start=1))
    goals_html = "".join(f"<li>{html.escape(g)}</li>" for g in goals)
    body = f"""<section class="cover"><p class="meta">{html.escape(sem.TERM_NAME)}</p><h1>Đề cương học phần {code}<br>{html.escape(name)}</h1>
<p>Số tín chỉ: {credits} · Giảng viên: {html.escape(teacher)}</p><p>Lớp học phần: {", ".join(classes)}</p>
<p class="sim">Tài liệu mô phỏng phục vụ chạy thử Campus 24/7; không phải đề cương chính thức của trường.</p></section>
<section><h2>1. Mục tiêu học phần</h2><ul>{goals_html}</ul>
<h2>2. Kế hoạch giảng dạy</h2><table><tr><th>Buổi</th><th>Nội dung</th><th>Chuẩn bị của sinh viên</th></tr>{rows}</table>
<h2>3. Đánh giá</h2><table><tr><th>Thành phần</th><th>Trọng số</th><th>Hình thức</th></tr>
<tr><td>Chuyên cần</td><td>10%</td><td>Điểm danh, tham gia trên lớp</td></tr><tr><td>Giữa kỳ</td><td>30%</td><td>Bài kiểm tra viết 60 phút</td></tr>
<tr><td>Cuối kỳ</td><td>60%</td><td>Thi viết 90 phút</td></tr></table>
<h2>4. Quy định lớp học</h2><p>Sinh viên vắng quá 20% số buổi không được dự thi cuối kỳ. Câu hỏi về bài giảng đặt trực tiếp trên trang tài liệu để cả lớp cùng xem.</p></section>"""
    return page(f"Đề cương {code}", body)


def lecture_html(code: str, index: int) -> str:
    lecturer_key, _, _, lectures = sem.LEARNING[code]
    title, points = lectures[index]
    name = sem.COURSES[code][0]
    example = next((p for p in points if p.startswith("Ví dụ")), None)
    keys = [p for p in points if p is not example][:2]
    sections = "<h2>Ghi nhớ</h2>" + "".join(f'<div class="box">{html.escape(p)}</div>' for p in keys)
    if example:
        sections += f"<h2>Ví dụ minh họa</h2><p>{html.escape(example)}</p>"
    body = f"""<section class="cover"><p class="meta">{code} · {html.escape(name)} · {html.escape(sem.TERM_NAME)}</p>
<h1>Bài {index + 1}: {html.escape(title)}</h1><p>Giảng viên: {html.escape(sem.LECTURERS[lecturer_key][0])}</p>
<p class="sim">Tài liệu mô phỏng phục vụ chạy thử Campus 24/7.</p></section>
<section><h2>Nội dung chính</h2><ol>{"".join(f"<li>{html.escape(p)}</li>" for p in points)}</ol>{sections}</section>
<section><h2>Câu hỏi ôn tập</h2><ol>{"".join(f"<li>Giải thích bằng lời của bạn: {html.escape(p)}</li>" for p in points[:3])}</ol>
<p>Chuẩn bị cho buổi sau: đọc lại bài này và ghi câu hỏi trên trang tài liệu.</p></section>"""
    return page(f"{code} bài {index + 1}", body)


def pdf_name(code: str, index: int | None) -> str:
    return f"{code}-de-cuong.pdf" if index is None else f"{code}-bai-{index + 1:02d}.pdf"


def pdfs(_args) -> None:
    specs = []
    for code, (_, _, _, lectures) in sem.LEARNING.items():
        specs.append({"file": pdf_name(code, None), "html": syllabus_html(code)})
        specs += [{"file": pdf_name(code, i), "html": lecture_html(code, i)} for i in range(len(lectures))]
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    spec_path = PDF_DIR / "specs.json"
    spec_path.write_text(json.dumps(specs, ensure_ascii=False), encoding="utf-8")
    subprocess.run(["node", str(ROOT / "scripts/demo/render_pdfs.mjs"), str(spec_path), str(PDF_DIR)], check=True, cwd=ROOT)


# --------------------------------------------------------------------------------------------------------- classes
def classes(_args) -> None:
    receipt = load_receipt()
    creds = learning_accounts()
    admin = Api("qt.hoctap.demo", creds["qt.hoctap.demo"]["password"])
    if "term" not in receipt:
        receipt["term"] = admin.call("POST", "/terms", json=admin.confirmed("term-create", None, {
            "name": sem.TERM_NAME, "start_date": sem.TERM_START.isoformat(), "end_date": sem.TERM_END.isoformat()}))["id"]
        save(receipt)
    for code in sem.LEARNING:
        if code not in receipt["courses"]:
            receipt["courses"][code] = admin.call("POST", "/courses", json=admin.confirmed("course-create", None, {
                "code": code, "name": sem.COURSES[code][0]}))["id"]
            save(receipt)
    for code, (lecturer_key, class_codes, _, _) in sem.LEARNING.items():
        lecturer = creds[f"gv.demo{list(sem.LECTURERS).index(lecturer_key) + 1:02d}"]
        for class_code in class_codes:
            key = f"{code}/{class_code}"
            if key not in receipt["offerings"]:
                payload = {"course_id": receipt["courses"][code], "term_id": receipt["term"], "section_code": class_code,
                           "title": f"{sem.COURSES[code][0]} — {class_code}"}
                receipt["offerings"][key] = admin.call("POST", "/offerings", json=admin.confirmed("offering-create", None, payload))["id"]
                save(receipt)
            offering = receipt["offerings"][key]
            people = [(lecturer["subject_id"], "INSTRUCTOR")] + [(s["subject_id"], "STUDENT") for s in class_students(class_code)]
            done = set(receipt["members"].get(key, []))
            for subject, role in people:
                if subject in done:
                    continue
                payload = {"actor_subject_id": subject, "role": role}
                admin.call("POST", f"/offerings/{offering}/members", json=admin.confirmed("member-create", offering, payload))
                done.add(subject)
                receipt["members"][key] = sorted(done)
                save(receipt)
    print(json.dumps({"term": 1, "courses": len(receipt["courses"]), "offerings": len(receipt["offerings"]),
                      "memberships": sum(len(v) for v in receipt["members"].values())}))


# ------------------------------------------------------------------------------------------------------- materials
def lecturer_for(code: str) -> Api:
    creds = learning_accounts()
    username = f"gv.demo{list(sem.LECTURERS).index(sem.LEARNING[code][0]) + 1:02d}"
    return Api(username, creds[username]["password"])


def wait_ready(api: Api, version_id: str, limit_s: int = 240) -> dict:
    deadline = time.monotonic() + limit_s
    while time.monotonic() < deadline:
        version = api.call("GET", f"/versions/{version_id}")
        version = version.get("version", version)
        state = version.get("processing_state")
        if state == "READY":
            return version
        if state in {"REJECTED", "FAILED", "QUARANTINED", "INFECTED"}:
            raise RuntimeError(f"version {version_id} ended in {state}")
        time.sleep(3)
    raise RuntimeError(f"version {version_id} not ready after {limit_s}s")


def materials(args) -> None:
    receipt = load_receipt()
    for key, offering in receipt["offerings"].items():
        code, class_code = key.split("/")
        lectures = sem.LEARNING[code][3]
        first = sem.LEARNING[code][1][0] == class_code
        count = len(lectures) if first else 2  # second sections get the syllabus and the first two lectures
        api = lecturer_for(code)
        plan = [(None, "Giới thiệu học phần và đề cương", "Đề cương học phần " + code)] + [
            (i, f"Buổi {i + 1}: {lectures[i][0]}", f"Bài {i + 1}: {lectures[i][0]}") for i in range(count)]
        for n, (index, session_title, material_title) in enumerate(plan):
            mkey = f"{key}/{n}"
            entry = receipt["materials"].get(mkey, {})
            if entry.get("published"):
                continue
            if "session" not in entry:
                start = datetime.combine(sem.SEMESTER_START + timedelta(weeks=2 * n), datetime.min.time(), tzinfo=sem.ICT) + timedelta(hours=7)
                entry["session"] = api.call("POST", f"/offerings/{offering}/sessions", json={
                    "title": session_title, "description": f"{sem.COURSES[code][0]} · {class_code}", "starts_at": start.isoformat()})["id"]
                receipt["materials"][mkey] = entry
                save(receipt)
            if "material" not in entry:
                entry["material"] = api.call("POST", f"/offerings/{offering}/materials", json={
                    "title": material_title, "description": "Tài liệu mô phỏng", "session_id": entry["session"]})["id"]
                save(receipt)
            for _ in range(2):
                if "version" not in entry:
                    upload_version(api, entry, code, index, mkey)
                    save(receipt)
                try:
                    wait_ready(api, entry["version"], 120)
                    break
                except RuntimeError:
                    # a version that ran out of automatic attempts never becomes ready; upload the file again
                    entry.setdefault("abandoned_versions", []).append(entry.pop("version"))
                    save(receipt)
            else:
                raise RuntimeError(f"{mkey}: no version became ready")
            preview = api.call("POST", f"/versions/{entry['version']}/publication-preview", json={"action": "publish"})
            api.call("POST", f"/versions/{entry['version']}/publish", json={k: preview[k] for k in ("preview_id", "confirmation_token")})
            entry["published"] = True
            save(receipt)
            print(f"published {mkey}", flush=True)
    print(json.dumps({"materials": len(receipt["materials"]),
                      "published": sum(1 for v in receipt["materials"].values() if v.get("published"))}))


def upload_version(api: Api, entry: dict, code: str, index: int | None, mkey: str) -> None:
    data = (PDF_DIR / pdf_name(code, index)).read_bytes()
    intent = api.call("POST", f"/materials/{entry['material']}/upload-intents", json={
        "filename": pdf_name(code, index), "byte_size": len(data), "content_type": "application/pdf"})
    sent = api.client.put(f"/v1/learning/upload-intents/{intent['id']}/content", content=data,
                          headers={"Content-Type": "application/pdf"})
    if sent.status_code != 200:
        raise RuntimeError(f"upload {mkey}: HTTP {sent.status_code} {sent.text[:200]}")
    entry["version"] = api.call("POST", f"/upload-intents/{intent['id']}/complete", json={})["id"]




# -------------------------------------------------------------------------------------------------------- activity
def activity(_args) -> None:
    receipt = load_receipt()
    rng = random.Random(1104)
    accounts, passwords = directory()
    by_subject = {a["subject_id"]: a for a in accounts.values()}
    done = receipt.setdefault("activity", {})
    sessions: dict[str, Api] = {}

    def as_student(account) -> Api:
        if account["username"] not in sessions:
            sessions[account["username"]] = Api(account["username"], passwords[account["username"]])
        return sessions[account["username"]]

    for key, offering in receipt["offerings"].items():
        code, class_code = key.split("/")
        students = [s for s in class_students(class_code)]
        versions = [(int(m.split("/")[-1]), v["version"]) for m, v in receipt["materials"].items()
                    if m.startswith(key + "/") and v.get("published")]
        for n, version in versions:
            for student in students:
                if rng.random() < 0.25:
                    continue  # not everyone has opened every file
                tag = f"read/{version}/{student['username']}"
                if tag in done:
                    continue
                api = as_student(student)
                pages = max(1, int(api.call("GET", f"/versions/{version}").get("page_count") or 1))
                page_no = rng.randint(1, pages)
                api.call("PUT", f"/me/reader-state/{version}", json={"page_no": page_no})
                if rng.random() < 0.3:
                    api.call("POST", "/me/bookmarks", json={"version_id": version, "page_no": page_no, "label": "Xem lại trước khi thi"})
                if rng.random() < 0.25:
                    api.call("POST", "/me/annotations", json={"version_id": version, "page_no": min(2, pages), "body": rng.choice([
                        "Phần này hay vào đề thi giữa kỳ.", "Cần hỏi lại ví dụ trên lớp.", "Đã hiểu, làm thêm bài tập cuối chương.",
                        "Ghi chú: so sánh với bài trước."])})
                done[tag] = True
                save(receipt)
        # Class questions with the lecturer's reply
        lecturer = lecturer_for(code)
        for index, question, reply in sem.LEARNING_QA.get(code, []):
            n = index + 1
            mkey = f"{key}/{n}"
            if mkey not in receipt["materials"] or not receipt["materials"][mkey].get("published"):
                continue
            tag = f"qa/{mkey}/{question[:30]}"
            if tag in done or not students:
                continue
            version = receipt["materials"][mkey]["version"]
            asker = as_student(students[(index + len(question)) % len(students)])
            created = asker.call("POST", f"/versions/{version}/questions", json={"page_no": 2, "body": question, "visibility": "CLASS"})
            question_id = created.get("id") or created.get("question", {}).get("id")
            revision = created.get("revision") or created.get("question", {}).get("revision", 1)
            answered = lecturer.call("POST", f"/questions/{question_id}/replies", json={"body": reply, "question_revision": revision})
            reply_id = answered.get("id") or answered.get("reply", {}).get("id")
            if reply_id and rng.random() < 0.6:
                lecturer.call("POST", f"/replies/{reply_id}/endorse", json={})
            done[tag] = True
            save(receipt)
    print(json.dumps({"activity_records": len(done)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, run in (("pdfs", pdfs), ("classes", classes), ("materials", materials), ("activity", activity)):
        sub.add_parser(name).set_defaults(run=run)
    parsed = parser.parse_args()
    parsed.run(parsed)
