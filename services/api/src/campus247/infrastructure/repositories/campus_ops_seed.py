"""Synthetic local seed for rooms and a sample student timetable.

Everything here is invented for the local campus workspace. It is labelled ``LOCAL_SYNTHETIC`` in the
store and the UI says so; it is not data from HUCE systems.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

ICT = timezone(timedelta(hours=7))

_CLASSROOM_FEATURES = ["WIFI", "MAY_CHIEU", "DIEU_HOA"]


def _room(code, name, building, floor, capacity, kind, features, status="ACTIVE"):
    return dict(code=code, name=name, building=building, floor=floor, capacity=capacity, kind=kind,
                features=features, status=status)


def _build_rooms():
    rooms = [
        _room("H1-301", "Phòng 301 - Giảng đường H1", "Giảng đường H1", 3, 50, "lecture", _CLASSROOM_FEATURES),
        _room("H1-302", "Phòng 302 - Giảng đường H1", "Giảng đường H1", 3, 25, "lecture", ["WIFI", "DIEU_HOA"]),
        _room("H2-HT", "Hội trường H2", "Hội trường H2", 1, 150, "hall", ["MAY_CHIEU", "MICRO", "SAN_KHAU", "DIEU_HOA"]),
    ]
    for n in (201, 202, 203, 204, 205, 206):
        rooms.append(_room(f"H3-{n}", f"Phòng {n} - Giảng đường H3", "Giảng đường H3", n // 100, 60, "lecture", _CLASSROOM_FEATURES))
    for n in (301, 302, 303, 304):
        rooms.append(_room(f"H3-{n}", f"Phòng {n} - Giảng đường H3", "Giảng đường H3", n // 100, 80 if n == 301 else 60, "lecture", _CLASSROOM_FEATURES))
    for n in (101, 102, 103):
        rooms.append(_room(f"H5-{n}", f"Phòng {n} - Giảng đường H5", "Giảng đường H5", 1, 45, "lecture", ["WIFI", "MAY_CHIEU"]))
    for n in (201, 202, 203, 204, 205, 206):
        rooms.append(_room(f"A1-{n}", f"Phòng {n} - Nhà A1", "Nhà A1", 2, 40, "lecture", ["WIFI", "MAY_CHIEU"]))
    for n in (401, 402, 403):
        rooms.append(_room(f"A2-{n}", f"Phòng {n} - Nhà A2", "Nhà A2", 4, 70, "lecture", _CLASSROOM_FEATURES))
    for n in (1, 2, 3, 4):
        status = "MAINTENANCE" if n == 4 else "ACTIVE"
        rooms.append(_room(f"L2-0{n}", f"Phòng máy tính L2-0{n}", "Nhà thực hành L2", 1, 40, "lab",
                           ["MAY_TINH", "WIFI", "MAY_CHIEU", "DIEU_HOA"], status))
    rooms += [
        _room("A1-M01", "Phòng họp nhóm A1-M01", "Nhà A1", 1, 12, "meeting", ["WIFI", "MAN_HINH", "DIEU_HOA"]),
        _room("A1-M02", "Phòng họp nhóm A1-M02", "Nhà A1", 1, 12, "meeting", ["WIFI", "MAN_HINH", "DIEU_HOA"]),
        _room("TV-01", "Phòng học nhóm Thư viện 01", "Thư viện", 2, 8, "study", ["WIFI", "BANG_TRANG"]),
        _room("TV-02", "Phòng học nhóm Thư viện 02", "Thư viện", 2, 8, "study", ["WIFI", "BANG_TRANG"]),
        _room("TV-03", "Phòng học nhóm Thư viện 03", "Thư viện", 2, 10, "study", ["WIFI", "BANG_TRANG", "MAN_HINH"]),
    ]
    return rooms


ROOMS = _build_rooms()

# (weekday 0=Mon, period, code, name, location, instructor)
_PERIODS = {1: (time(7, 0), time(9, 25)), 2: (time(9, 35), time(11, 55)),
            3: (time(13, 0), time(15, 25)), 4: (time(15, 35), time(17, 55))}
_WEEKLY = [
    (0, 1, "IT3080", "Mạng máy tính", "H3-301", "ThS. Trần Quang Huy"),
    (1, 1, "IT3090", "Cơ sở dữ liệu", "H3-204", "TS. Lê Minh Châu"),
    (1, 3, "MI2020", "Xác suất thống kê", "A2-402", "TS. Vũ Hồng Nhung"),
    (2, 1, "IT3095", "Thực hành cơ sở dữ liệu", "L2-01", "ThS. Bùi Gia Bảo"),
    (2, 3, "IT3120", "Trí tuệ nhân tạo", "H3-301", "TS. Phạm Thu Hà"),
    (3, 1, "IT3150", "Kỹ thuật phần mềm", "H5-102", "ThS. Đỗ Anh Tuấn"),
    (4, 2, "EN2010", "Tiếng Anh chuyên ngành", "A1-205", "ThS. Ngô Lan Phương"),
]
_FIRST_MONDAY = date(2026, 9, 7)
_WEEKS = 15
_EXAMS = [
    # (date, start, end, code, name, location, note)
    (date(2026, 10, 17), time(8, 0), time(9, 30), "IT3080", "Thi giữa kỳ — Mạng máy tính", "H3-204", "Mang theo thẻ sinh viên."),
    (date(2026, 10, 24), time(8, 0), time(9, 30), "IT3090", "Thi giữa kỳ — Cơ sở dữ liệu", "H3-301", "Được dùng tài liệu in một mặt A4."),
    (date(2027, 1, 5), time(7, 30), time(9, 30), "IT3090", "Thi cuối kỳ — Cơ sở dữ liệu", "H3-301", "Có mặt trước giờ thi 15 phút."),
    (date(2027, 1, 7), time(13, 0), time(15, 0), "IT3120", "Thi cuối kỳ — Trí tuệ nhân tạo", "H3-204", "Thi viết, không dùng tài liệu."),
    (date(2027, 1, 9), time(7, 30), time(9, 30), "IT3080", "Thi cuối kỳ — Mạng máy tính", "A2-402", "Có mặt trước giờ thi 15 phút."),
]


def _utc(day: date, at: time) -> str:
    return datetime.combine(day, at, tzinfo=ICT).astimezone(timezone.utc).isoformat(timespec="seconds")


def student_timetable(owner_key: str) -> list[dict]:
    """Weekly classes for 15 teaching weeks plus mid-term and final exams (all synthetic)."""
    rows: list[dict] = []
    for week in range(_WEEKS):
        monday = _FIRST_MONDAY + timedelta(weeks=week)
        for weekday, period, code, name, location, instructor in _WEEKLY:
            if code == "IT3095" and week % 2 == 1:  # lab sessions every other week
                continue
            start, end = _PERIODS[period]
            day = monday + timedelta(days=weekday)
            rows.append(dict(kind="CLASS", course_code=code, course_name=name, starts_at=_utc(day, start),
                             ends_at=_utc(day, end), location=location, instructor=instructor,
                             note=f"Tuần {week + 1} · Lịch mô phỏng học kỳ 1 năm học 2026–2027"))
    for day, start, end, code, name, location, note in _EXAMS:
        rows.append(dict(kind="EXAM", course_code=code, course_name=name, starts_at=_utc(day, start),
                         ends_at=_utc(day, end), location=location, instructor="Phòng Đào tạo (mô phỏng)", note=note))
    return rows
