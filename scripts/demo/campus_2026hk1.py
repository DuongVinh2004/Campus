"""Simulated semester "HK1 2026-2027" for the local Campus 24/7 runtime.

Everything here is invented for demos and tests: people, codes, timetable, rooms, requests and lecture text. It is
not HUCE data. Faculty names are the public names of HUCE faculties so the demo reads naturally; nothing claims to be a
real record. Generation is deterministic (fixed seed) so a rerun produces the same people and the same content.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

BATCH = "DEMO-2026HK1-01"
ICT = timezone(timedelta(hours=7))
SEMESTER_START = date(2026, 9, 7)  # Monday of week 1
WEEKS = 15
TERM_NAME = "Học kỳ 1 năm học 2026–2027"
TERM_START, TERM_END = date(2026, 9, 7), date(2027, 1, 24)

PERIODS = {1: (time(7, 0), time(9, 25)), 2: (time(9, 35), time(11, 55)),
           3: (time(13, 0), time(15, 25)), 4: (time(15, 35), time(17, 55))}

FACULTIES = {
    "CNTT": "Khoa Công nghệ thông tin",
    "XD": "Khoa Xây dựng Dân dụng và Công nghiệp",
    "KT": "Khoa Kiến trúc và Quy hoạch",
    "KX": "Khoa Kinh tế và Quản lý xây dựng",
}

# Course code -> (name, credits)
COURSES = {
    "IT3090": ("Cơ sở dữ liệu", 3), "IT3080": ("Mạng máy tính", 3), "IT3120": ("Trí tuệ nhân tạo", 3),
    "IT3150": ("Kỹ thuật phần mềm", 3), "MI2020": ("Xác suất thống kê", 3), "EN2010": ("Tiếng Anh chuyên ngành", 2),
    "XD3010": ("Sức bền vật liệu", 3), "XD3020": ("Cơ học kết cấu", 3), "XD3030": ("Kết cấu bê tông cốt thép", 3),
    "XD3040": ("Vật liệu xây dựng", 2), "KT3010": ("Lịch sử kiến trúc", 2), "KT3020": ("Cấu tạo kiến trúc", 3),
    "KT3030": ("Đồ án kiến trúc nhà ở", 4), "KT3040": ("Vẽ ghi kiến trúc", 2), "MI2010": ("Hình học họa hình", 2),
    "KX3010": ("Kinh tế xây dựng", 3), "KX3020": ("Dự toán công trình", 3), "KX3030": ("Quản lý dự án xây dựng", 3),
    "KX3040": ("Pháp luật xây dựng", 2),
}

# Lecturers (schedule + learning). key -> (display name, faculty)
LECTURERS = {
    "gv01": ("TS. Lê Minh Châu", "CNTT"), "gv02": ("ThS. Trần Quang Huy", "CNTT"), "gv03": ("TS. Phạm Thu Hà", "CNTT"),
    "gv04": ("PGS.TS. Nguyễn Văn Khải", "XD"), "gv05": ("TS. Hoàng Thị Lan", "KT"), "gv06": ("TS. Vũ Đức Thành", "KX"),
}
OTHER_INSTRUCTORS = {
    "IT3150": "ThS. Đỗ Anh Tuấn", "MI2020": "TS. Vũ Hồng Nhung", "EN2010": "ThS. Ngô Lan Phương",
    "XD3020": "TS. Bùi Văn Tiến", "XD3040": "ThS. Đinh Thị Hương", "KT3010": "PGS.TS. Lương Minh Đức",
    "KT3030": "ThS. KTS. Mai Thanh Tùng", "KT3040": "ThS. KTS. Phan Ngọc Ánh", "MI2010": "ThS. Lại Thị Thu",
    "KX3010": "TS. Đào Quang Vinh", "KX3020": "ThS. Tạ Thị Mai", "KX3040": "ThS. Kiều Văn Sơn",
}
COURSE_LECTURER = {"IT3090": "gv01", "IT3080": "gv02", "IT3120": "gv03", "XD3010": "gv04", "XD3030": "gv04",
                   "KT3020": "gv05", "KX3030": "gv06"}


def instructor(code: str) -> str:
    return LECTURERS[COURSE_LECTURER[code]][0] if code in COURSE_LECTURER else OTHER_INSTRUCTORS[code]


# Class -> weekly slots (weekday 0=Mon, period, course, room). Rooms do not clash across classes.
CLASSES = {
    "66IT1": ("CNTT", [(0, 1, "IT3080", "H3-301"), (1, 1, "IT3090", "H3-204"), (1, 3, "MI2020", "A2-402"),
                       (2, 1, "IT3090", "L2-01"), (2, 3, "IT3120", "H3-301"), (3, 1, "IT3150", "H5-102"),
                       (4, 2, "EN2010", "A1-205")]),
    "66IT2": ("CNTT", [(0, 2, "IT3090", "H3-204"), (1, 2, "IT3080", "H3-301"), (2, 2, "IT3090", "L2-02"),
                       (3, 3, "MI2020", "A2-402"), (3, 2, "IT3150", "H5-103"), (4, 1, "EN2010", "A1-206"),
                       (4, 3, "IT3120", "H3-302")]),
    "66XD1": ("XD", [(0, 1, "XD3010", "H1-301"), (0, 3, "XD3030", "H6-201"), (1, 1, "XD3020", "H6-202"),
                     (2, 2, "MI2020", "A2-401"), (3, 1, "XD3040", "TN-01"), (3, 3, "XD3010", "H6-203"),
                     (4, 2, "EN2010", "A1-204")]),
    "66XD2": ("XD", [(0, 2, "XD3020", "H6-201"), (1, 3, "XD3010", "H1-301"), (2, 1, "MI2020", "A2-403"),
                     (2, 3, "XD3030", "H6-202"), (3, 2, "XD3040", "TN-01"), (4, 1, "EN2010", "A1-203"),
                     (4, 3, "XD3010", "H6-203")]),
    "66KT1": ("KT", [(0, 1, "KT3020", "H4-301"), (0, 3, "KT3030", "XK-01"), (1, 1, "KT3010", "H4-302"),
                     (2, 1, "MI2010", "H4-303"), (2, 3, "KT3030", "XK-01"), (3, 2, "KT3040", "XK-02"),
                     (4, 2, "EN2010", "A1-202")]),
    "66KT2": ("KT", [(0, 2, "KT3010", "H4-302"), (1, 2, "KT3020", "H4-301"), (1, 3, "KT3030", "XK-02"),
                     (2, 2, "MI2010", "H4-303"), (3, 3, "KT3040", "XK-01"), (4, 1, "EN2010", "A1-201"),
                     (4, 3, "KT3030", "XK-02")]),
    "66KX1": ("KX", [(0, 1, "KX3010", "H5-101"), (1, 1, "KX3020", "L2-03"), (1, 3, "KX3030", "H5-102"),
                     (2, 2, "MI2020", "A2-402"), (3, 1, "KX3040", "H5-103"), (3, 3, "KX3030", "H5-101"),
                     (4, 2, "EN2010", "A1-203")]),
    "66KX2": ("KX", [(0, 2, "KX3020", "L2-03"), (1, 2, "KX3010", "H5-101"), (2, 1, "KX3030", "H5-102"),
                     (2, 3, "MI2020", "A2-401"), (3, 2, "KX3040", "H5-201"), (4, 1, "EN2010", "A1-202"),
                     (4, 3, "KX3030", "H5-101")]),
}
STUDENTS_PER_CLASS = 5

# Exams: course -> (midterm date or None, final date, period start/end, room, note)
EXAMS = {
    "IT3090": (date(2026, 10, 24), date(2027, 1, 5)), "IT3080": (date(2026, 10, 17), date(2027, 1, 9)),
    "IT3120": (None, date(2027, 1, 7)), "IT3150": (None, date(2027, 1, 12)), "MI2020": (date(2026, 10, 31), date(2027, 1, 6)),
    "EN2010": (None, date(2027, 1, 14)), "XD3010": (date(2026, 10, 22), date(2027, 1, 8)), "XD3020": (None, date(2027, 1, 11)),
    "XD3030": (date(2026, 10, 29), date(2027, 1, 13)), "XD3040": (None, date(2027, 1, 15)), "KT3010": (None, date(2027, 1, 7)),
    "KT3020": (date(2026, 10, 23), date(2027, 1, 12)), "KT3030": (None, date(2027, 1, 16)), "KT3040": (None, date(2027, 1, 9)),
    "MI2010": (None, date(2027, 1, 5)), "KX3010": (None, date(2027, 1, 8)), "KX3020": (date(2026, 10, 28), date(2027, 1, 11)),
    "KX3030": (date(2026, 10, 21), date(2027, 1, 13)), "KX3040": (None, date(2027, 1, 14)),
}
EXAM_ROOMS = ["H3-204", "H3-301", "A2-402", "H6-201", "H4-301", "H5-101", "A2-401"]
EXAM_NOTES = ["Có mặt trước giờ thi 15 phút, mang theo thẻ sinh viên.", "Thi viết, không dùng tài liệu.",
              "Được dùng một tờ tài liệu A4 viết tay.", "Mang máy tính cầm tay không có chức năng lưu trữ văn bản."]

# Extra rooms on top of the 34 already seeded by campus_ops_seed.
EXTRA_ROOMS = (
    [(f"H4-{n}", f"Phòng {n} - Giảng đường H4", "Giảng đường H4", n // 100, 60, "lecture", ["WIFI", "MAY_CHIEU", "DIEU_HOA"])
     for n in (201, 202, 301, 302, 303)]
    + [(f"H6-{n}", f"Phòng {n} - Giảng đường H6", "Giảng đường H6", n // 100, 90, "lecture", ["WIFI", "MAY_CHIEU", "MICRO", "DIEU_HOA"])
       for n in (201, 202, 203, 301, 302)]
    + [(f"H5-{n}", f"Phòng {n} - Giảng đường H5", "Giảng đường H5", 2, 45, "lecture", ["WIFI", "MAY_CHIEU"]) for n in (201, 202)]
    + [("TN-01", "Phòng thí nghiệm Vật liệu xây dựng", "Trung tâm thí nghiệm", 1, 30, "lab", ["MAY_THI_NGHIEM", "DIEU_HOA"]),
       ("TN-02", "Phòng thí nghiệm Kết cấu", "Trung tâm thí nghiệm", 1, 30, "lab", ["MAY_THI_NGHIEM"]),
       ("TN-03", "Phòng thí nghiệm Cơ học đất", "Trung tâm thí nghiệm", 2, 25, "lab", ["MAY_THI_NGHIEM", "DIEU_HOA"]),
       ("XK-01", "Xưởng đồ án Kiến trúc 01", "Nhà xưởng Kiến trúc", 1, 40, "studio", ["BAN_VE", "WIFI", "DIEU_HOA"]),
       ("XK-02", "Xưởng đồ án Kiến trúc 02", "Nhà xưởng Kiến trúc", 1, 40, "studio", ["BAN_VE", "WIFI"]),
       ("XK-03", "Xưởng mô hình Kiến trúc", "Nhà xưởng Kiến trúc", 2, 20, "studio", ["MAY_CAT_LASER", "WIFI"], "MAINTENANCE"),
       ("L2-05", "Phòng máy tính L2-05", "Nhà thực hành L2", 2, 40, "lab", ["MAY_TINH", "WIFI", "MAY_CHIEU", "DIEU_HOA"]),
       ("L2-06", "Phòng máy tính L2-06", "Nhà thực hành L2", 2, 40, "lab", ["MAY_TINH", "WIFI", "MAY_CHIEU", "DIEU_HOA"]),
       ("TV-04", "Phòng học nhóm Thư viện 04", "Thư viện", 3, 8, "study", ["WIFI", "BANG_TRANG"]),
       ("TV-05", "Phòng học nhóm Thư viện 05", "Thư viện", 3, 8, "study", ["WIFI", "BANG_TRANG", "MAN_HINH"]),
       ("TV-06", "Phòng đọc yên tĩnh Thư viện", "Thư viện", 3, 30, "study", ["WIFI"]),
       ("A1-M03", "Phòng họp nhóm A1-M03", "Nhà A1", 1, 12, "meeting", ["WIFI", "MAN_HINH", "DIEU_HOA"]),
       ("A1-M04", "Phòng họp nhóm A1-M04", "Nhà A1", 1, 16, "meeting", ["WIFI", "MAN_HINH", "DIEU_HOA"]),
       ("CLB-01", "Phòng sinh hoạt câu lạc bộ 01", "Nhà sinh viên", 1, 30, "meeting", ["WIFI", "LOA"]),
       ("CLB-02", "Phòng sinh hoạt câu lạc bộ 02", "Nhà sinh viên", 1, 30, "meeting", ["WIFI", "LOA", "MAY_CHIEU"]),
       ("HT-A2", "Hội trường A2", "Nhà A2", 1, 250, "hall", ["MAY_CHIEU", "MICRO", "SAN_KHAU", "DIEU_HOA"])]
)

_SURNAMES = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Ngô", "Dương", "Lý", "Phan", "Đinh", "Trịnh"]
_MIDDLE_M = ["Văn", "Đức", "Minh", "Quang", "Hữu", "Thành", "Tiến", "Công", "Gia", "Hoàng"]
_MIDDLE_F = ["Thị", "Thu", "Ngọc", "Thanh", "Phương", "Minh", "Khánh", "Hồng", "Mai", "Bảo"]
_GIVEN_M = ["An", "Bình", "Cường", "Dũng", "Đạt", "Hiếu", "Hùng", "Khoa", "Long", "Nam", "Phúc", "Quân", "Sơn", "Thắng", "Trung", "Tú", "Việt"]
_GIVEN_F = ["Anh", "Chi", "Dung", "Giang", "Hà", "Hạnh", "Hoa", "Hương", "Lan", "Linh", "Ly", "Mai", "Ngân", "Nhung", "Quyên", "Trang", "Vy"]

STAFF = [
    ("nv.demo01", "Nguyễn Thị Hồng Nhung", "Phòng Đào tạo"),
    ("nv.demo02", "Trần Văn Hải", "Phòng Công tác sinh viên"),
    ("nv.demo03", "Lê Thị Thanh Bình", "Phòng Đào tạo"),
    ("nv.demo04", "Phạm Quốc Toản", "Phòng Quản trị thiết bị"),
]


@dataclass
class Student:
    username: str
    display_name: str
    student_code: str
    class_code: str
    faculty: str
    gender: str
    birth_year: int = 2006
    phone_tail: str = ""


@dataclass
class Semester:
    students: list[Student] = field(default_factory=list)


def build_students(rng: random.Random) -> list[Student]:
    people, used = [], set()
    index = 0
    for class_code, (faculty, _) in CLASSES.items():
        for _ in range(STUDENTS_PER_CLASS):
            index += 1
            while True:
                female = rng.random() < 0.45
                name = " ".join([rng.choice(_SURNAMES), rng.choice(_MIDDLE_F if female else _MIDDLE_M),
                                 rng.choice(_GIVEN_F if female else _GIVEN_M)])
                if name not in used:
                    used.add(name)
                    break
            people.append(Student(f"sv.demo{index:02d}", name, f"SIM-{class_code}-{index:03d}", class_code, faculty,
                                  "F" if female else "M", 2006 + (rng.random() < 0.15), f"{rng.randrange(1000):03d}"))
    return people


def utc(day: date, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=ICT).astimezone(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def timetable(class_code: str) -> list[dict]:
    """Weekly classes for the 15 weeks plus midterm and final exams, as ops_schedule rows (without owner)."""
    faculty, slots = CLASSES[class_code]
    rows = []
    for week in range(WEEKS):
        for weekday, period, code, room in slots:
            day = SEMESTER_START + timedelta(weeks=week, days=weekday)
            start, end = PERIODS[period]
            note = "Nghỉ học bù ngày lễ, lịch học bù do giảng viên thông báo." if day == date(2026, 11, 20) else ""
            rows.append({"kind": "CLASS", "course_code": code, "course_name": COURSES[code][0],
                         "starts_at": iso(utc(day, start)), "ends_at": iso(utc(day, end)), "location": room,
                         "instructor": instructor(code), "note": note})
    courses = sorted({code for _, _, code, _ in slots})
    for n, code in enumerate(courses):
        midterm, final = EXAMS[code]
        room = EXAM_ROOMS[(n + len(class_code)) % len(EXAM_ROOMS)]
        start = time(7, 30) if n % 2 == 0 else time(13, 30)
        for day, label in ((midterm, "Thi giữa kỳ"), (final, "Thi cuối kỳ")):
            if day is None:
                continue
            rows.append({"kind": "EXAM", "course_code": code, "course_name": f"{label} — {COURSES[code][0]}",
                         "starts_at": iso(utc(day, start)), "ends_at": iso(utc(day, (datetime.combine(day, start) + timedelta(minutes=90)).time())),
                         "location": room, "instructor": instructor(code), "note": EXAM_NOTES[(n + day.day) % len(EXAM_NOTES)]})
    return rows


# --------------------------------------------------------------------------------------------- requests (tickets)
CERT_PURPOSES = [
    ("Xin tạm hoãn nghĩa vụ quân sự", "Ban Chỉ huy quân sự quận nơi cư trú"),
    ("Làm hồ sơ vay vốn sinh viên", "Ngân hàng Chính sách xã hội"),
    ("Bổ sung hồ sơ xin học bổng doanh nghiệp", "Quỹ học bổng của doanh nghiệp tài trợ"),
    ("Xác nhận cho gia đình hưởng chế độ trợ cấp", "UBND phường nơi gia đình cư trú"),
    ("Đăng ký tạm trú", "Công an phường nơi ở trọ"),
    ("Nộp hồ sơ thực tập tại doanh nghiệp", "Công ty nhận sinh viên thực tập"),
    ("Làm thủ tục xin thị thực đi trao đổi ngắn hạn", "Đại sứ quán nước tiếp nhận"),
]
GENERAL_TOPICS = [
    ("Đăng ký học phần muộn", "Em muốn hỏi thủ tục đăng ký học phần sau hạn vì trùng lịch thực tập tại công trường."),
    ("Xin bảo lưu kết quả học tập", "Em xin hướng dẫn thủ tục bảo lưu kết quả học tập một học kỳ vì lý do sức khỏe."),
    ("Cấp lại thẻ sinh viên", "Em bị mất thẻ sinh viên, xin hướng dẫn thủ tục cấp lại và thời gian nhận thẻ."),
    ("Điều chỉnh thông tin cá nhân", "Thông tin ngày sinh trên hệ thống bị sai một chữ số so với giấy khai sinh, em xin điều chỉnh."),
    ("Miễn giảm học phí", "Em thuộc diện hộ cận nghèo, xin hỏi hồ sơ cần nộp để được xét giảm học phí học kỳ này."),
    ("Rút bớt học phần", "Em đăng ký quá số tín chỉ, xin rút học phần tự chọn trước hạn có được hoàn học phí không."),
    ("Xác nhận lịch thi trùng", "Hai học phần của em có lịch thi cuối kỳ trùng giờ, em xin được bố trí thi ở ca khác."),
    ("Học cải thiện điểm", "Em muốn học lại một học phần để cải thiện điểm, xin hỏi cách đăng ký và lớp mở trong kỳ."),
    ("Chuyển lớp học phần", "Lịch học lớp hiện tại trùng với giờ làm thêm, em xin chuyển sang lớp học phần khác cùng môn."),
    ("Cấp bảng điểm tạm thời", "Em cần bảng điểm tạm thời có dấu để nộp hồ sơ xin học bổng trao đổi."),
]
APPEAL_REASONS = [
    "điểm câu tự luận cuối chưa khớp với đáp án công bố",
    "tổng điểm thành phần trên hệ thống thấp hơn điểm giảng viên đã báo trên lớp",
    "em nghĩ bài làm bị chấm sót một trang",
    "điểm chuyên cần chưa được cập nhật dù em đi học đủ buổi",
]
STAFF_REPLIES = {
    "STUDENT_CERTIFICATE": {
        "RESOLVED": "Đã cấp giấy xác nhận. Bạn nhận bản giấy tại Bộ phận Một cửa (tầng 1 nhà A1) trong giờ hành chính, mang theo thẻ sinh viên.",
        "NEED_INFO": "Bạn bổ sung giúp số căn cước và tên đơn vị nhận đầy đủ để in trên giấy xác nhận.",
        "REJECTED": "Hồ sơ trùng với yêu cầu đã cấp trong tuần; bạn dùng bản đã nhận hoặc gửi lại nếu cần thêm bản.",
        "IN_REVIEW": "Đã tiếp nhận, giấy xác nhận đang chờ ký, dự kiến có sau 2 ngày làm việc.",
    },
    "GRADE_APPEAL": {
        "RESOLVED": "Bộ môn đã chấm phúc khảo. Kết quả được cập nhật trên hệ thống trong 3 ngày làm việc.",
        "NEED_INFO": "Bạn cho biết mã lớp học phần và ngày thi để phòng chuyển đúng bộ môn chấm phúc khảo.",
        "REJECTED": "Đơn phúc khảo gửi sau thời hạn 10 ngày kể từ ngày công bố điểm nên không được tiếp nhận.",
        "IN_REVIEW": "Đã chuyển đơn tới bộ môn, thời gian chấm phúc khảo tối đa 15 ngày.",
    },
    "GENERAL_SUPPORT": {
        "RESOLVED": "Đã hướng dẫn và cập nhật trên hệ thống. Bạn kiểm tra lại trên cổng sinh viên, nếu còn vướng hãy phản hồi tại đây.",
        "NEED_INFO": "Bạn gửi kèm ảnh chụp giấy tờ liên quan (đơn có chữ ký, minh chứng) để phòng xử lý.",
        "REJECTED": "Yêu cầu chưa thuộc thẩm quyền của bộ phận; bạn liên hệ trực tiếp khoa quản lý để được hướng dẫn.",
        "IN_REVIEW": "Đã tiếp nhận, phòng đang kiểm tra hồ sơ và sẽ phản hồi trong tuần.",
    },
}
STUDENT_FOLLOWUPS = ["Em đã bổ sung thông tin, mong phòng xem giúp em ạ.", "Em gửi kèm minh chứng như phòng yêu cầu.",
                     "Em cảm ơn, khi nào em có thể nhận kết quả ạ?", "Em xin bổ sung: em cần gấp trước thứ Sáu tuần này."]
STAFF_NOTES = ["Đã đối chiếu danh sách lớp, thông tin khớp.", "Chờ bộ môn phản hồi bằng văn bản.",
               "Sinh viên đã gọi điện hỏi, hẹn trả kết quả đúng hạn.", "Ưu tiên vì sinh viên cần nộp trước hạn."]

BOOKING_PURPOSES = ["Họp nhóm đồ án môn học", "Ôn thi giữa kỳ theo nhóm", "Sinh hoạt câu lạc bộ học thuật",
                    "Chuẩn bị báo cáo seminar", "Tập thuyết trình bảo vệ đồ án", "Họp ban cán sự lớp",
                    "Làm bài tập lớn theo nhóm", "Phỏng vấn thành viên mới câu lạc bộ"]
CANCEL_REASONS = ["Nhóm đổi lịch họp", "Giảng viên đổi lịch học bù trùng giờ", "Đặt nhầm phòng", "Thành viên nhóm bận đột xuất"]


# ---------------------------------------------------------------------------------------------------- learning
# Learning courses: code -> (lecturer key, classes with an offering, syllabus goals, lectures [(title, [points])])
LEARNING = {
    "IT3090": ("gv01", ["66IT1", "66IT2"], [
        "Hiểu mô hình dữ liệu quan hệ và các ràng buộc toàn vẹn.",
        "Thiết kế lược đồ cơ sở dữ liệu đạt dạng chuẩn 3NF.",
        "Viết truy vấn SQL từ cơ bản đến nâng cao, có kết nối và gom nhóm.",
        "Hiểu giao dịch, khóa và phục hồi trong hệ quản trị cơ sở dữ liệu."], [
        ("Mô hình quan hệ và khóa", ["Quan hệ là một bảng gồm các bộ (hàng) có cùng tập thuộc tính (cột).",
            "Khóa chính xác định duy nhất mỗi bộ; khóa ngoại tham chiếu khóa chính của quan hệ khác.",
            "Ràng buộc toàn vẹn thực thể yêu cầu khóa chính không được rỗng.",
            "Ví dụ: SINHVIEN(MaSV, HoTen, MaLop) có khóa ngoại MaLop tham chiếu LOP(MaLop)."]),
        ("Truy vấn SQL cơ bản", ["Câu lệnh SELECT gồm các mệnh đề SELECT, FROM, WHERE, ORDER BY.",
            "Toán tử LIKE dùng ký tự đại diện % và _ để tìm theo mẫu.",
            "Giá trị NULL phải kiểm tra bằng IS NULL, không dùng dấu bằng.",
            "Ví dụ: SELECT HoTen FROM SINHVIEN WHERE MaLop = '66IT1' ORDER BY HoTen;"]),
        ("Kết nối bảng và gom nhóm", ["INNER JOIN chỉ giữ các cặp bộ thỏa điều kiện nối.",
            "LEFT JOIN giữ mọi bộ của bảng trái, thiếu ghép thì cột bảng phải nhận NULL.",
            "GROUP BY gom các bộ cùng giá trị; HAVING lọc trên kết quả gom nhóm.",
            "Ví dụ: đếm số sinh viên mỗi lớp bằng COUNT(*) kết hợp GROUP BY MaLop."]),
        ("Chuẩn hóa lược đồ", ["Phụ thuộc hàm X → Y nghĩa là X xác định duy nhất Y.",
            "Dạng chuẩn 2NF loại bỏ phụ thuộc bộ phận vào khóa.",
            "Dạng chuẩn 3NF loại bỏ phụ thuộc bắc cầu giữa các thuộc tính không khóa.",
            "Chuẩn hóa giảm dư thừa và bất thường khi thêm, sửa, xóa dữ liệu."])]),
    "IT3080": ("gv02", ["66IT1", "66IT2"], [
        "Hiểu mô hình phân tầng OSI và TCP/IP.", "Phân tích hoạt động của các giao thức tầng ứng dụng và giao vận.",
        "Chia mạng con và định tuyến cơ bản với IPv4.", "Nhận biết các nguy cơ an ninh mạng phổ biến."], [
        ("Mô hình phân tầng", ["Mô hình OSI có bảy tầng, TCP/IP thực tế dùng bốn tầng.",
            "Mỗi tầng cung cấp dịch vụ cho tầng trên và dùng dịch vụ của tầng dưới.",
            "Đóng gói: dữ liệu được thêm tiêu đề khi đi xuống từng tầng.",
            "Ví dụ: một yêu cầu HTTP được bọc trong đoạn TCP, gói IP rồi khung Ethernet."]),
        ("Tầng giao vận", ["TCP là giao thức hướng kết nối, bảo đảm thứ tự và độ tin cậy.",
            "Bắt tay ba bước SYN, SYN-ACK, ACK thiết lập kết nối TCP.",
            "UDP không kết nối, độ trễ thấp, phù hợp truyền âm thanh và hình ảnh trực tiếp.",
            "Cổng (port) phân biệt các ứng dụng trên cùng một máy."]),
        ("Địa chỉ IPv4 và chia mạng con", ["Địa chỉ IPv4 dài 32 bit, viết thành bốn số thập phân.",
            "Mặt nạ /24 cho 254 địa chỉ máy dùng được trong mạng con.",
            "Chia mạng con bằng cách mượn bit phần máy để tạo thêm mạng.",
            "Ví dụ: 192.168.10.0/26 chia được bốn mạng con, mỗi mạng 62 máy."]),
        ("An ninh mạng cơ bản", ["Tường lửa lọc gói tin theo địa chỉ, cổng và giao thức.",
            "Tấn công từ chối dịch vụ làm cạn tài nguyên của máy chủ.",
            "HTTPS dùng TLS để mã hóa và xác thực máy chủ.",
            "Mật khẩu mạnh và xác thực hai lớp giảm nguy cơ chiếm tài khoản."])]),
    "IT3120": ("gv03", ["66IT1"], [
        "Hiểu các phương pháp tìm kiếm trong không gian trạng thái.", "Biểu diễn tri thức và suy diễn logic.",
        "Nắm nguyên lý học máy có giám sát.", "Đánh giá mô hình bằng các độ đo phù hợp."], [
        ("Tìm kiếm mù", ["Bài toán tìm kiếm gồm trạng thái đầu, hành động, hàm chuyển và trạng thái đích.",
            "Tìm kiếm theo chiều rộng tìm được lời giải nông nhất.",
            "Tìm kiếm theo chiều sâu tốn ít bộ nhớ nhưng có thể không tối ưu.",
            "Ví dụ: tìm đường trong mê cung bằng hàng đợi các ô chưa thăm."]),
        ("Tìm kiếm có thông tin", ["Hàm heuristic ước lượng chi phí từ trạng thái hiện tại tới đích.",
            "Thuật toán A* chọn nút có f(n) = g(n) + h(n) nhỏ nhất.",
            "Heuristic chấp nhận được không bao giờ đánh giá quá chi phí thực.",
            "Ví dụ: khoảng cách Manhattan cho bài toán 8 ô số."]),
        ("Học có giám sát", ["Dữ liệu huấn luyện gồm đầu vào và nhãn đúng.",
            "Hồi quy dự đoán giá trị liên tục, phân lớp dự đoán nhãn rời rạc.",
            "Quá khớp xảy ra khi mô hình học thuộc dữ liệu huấn luyện.",
            "Chia dữ liệu thành tập huấn luyện, kiểm định và kiểm tra để đánh giá khách quan."]),
        ("Đánh giá mô hình", ["Ma trận nhầm lẫn thống kê dự đoán đúng và sai theo từng lớp.",
            "Độ chính xác (precision) là tỉ lệ dự đoán dương đúng trong các dự đoán dương.",
            "Độ phủ (recall) là tỉ lệ mẫu dương thật được tìm ra.",
            "F1 là trung bình điều hòa của precision và recall."])]),
    "XD3010": ("gv04", ["66XD1", "66XD2"], [
        "Xác định nội lực trong thanh chịu kéo, nén, xoắn, uốn.", "Tính ứng suất và biến dạng của thanh.",
        "Kiểm tra điều kiện bền và điều kiện cứng.", "Vận dụng vào tính toán cấu kiện đơn giản."], [
        ("Nội lực và phương pháp mặt cắt", ["Nội lực là lực tương tác giữa các phần của vật thể khi chịu tải.",
            "Phương pháp mặt cắt: cắt thanh, xét cân bằng một phần để tìm nội lực.",
            "Thanh phẳng có ba thành phần nội lực: lực dọc N, lực cắt Q, mô men uốn M.",
            "Biểu đồ nội lực cho biết vị trí nội lực lớn nhất để kiểm tra bền."]),
        ("Kéo nén đúng tâm", ["Ứng suất pháp σ = N / A phân bố đều trên mặt cắt.",
            "Định luật Hooke: σ = E·ε trong giới hạn đàn hồi.",
            "Độ giãn dài của thanh ΔL = N·L / (E·A).",
            "Điều kiện bền: |σ| không vượt quá ứng suất cho phép [σ]."]),
        ("Đặc trưng hình học mặt cắt", ["Mô men tĩnh dùng để xác định trọng tâm mặt cắt.",
            "Mô men quán tính chữ nhật đối với trục trung tâm Ix = b·h³ / 12.",
            "Công thức chuyển trục song song: I = Ic + A·d².",
            "Mặt cắt chữ I chịu uốn hiệu quả vì vật liệu tập trung xa trục trung hòa."]),
        ("Uốn phẳng", ["Ứng suất pháp khi uốn σ = M·y / I, lớn nhất ở thớ xa trục trung hòa.",
            "Liên hệ vi phân: dM/dz = Q và dQ/dz = q.",
            "Ứng suất tiếp khi uốn tính theo công thức Zhuravskii.",
            "Kiểm tra bền dầm theo cả ứng suất pháp lớn nhất và ứng suất tiếp lớn nhất."])]),
    "XD3030": ("gv04", ["66XD1"], [
        "Hiểu tính năng cơ học của bê tông và cốt thép.", "Tính toán cấu kiện chịu uốn theo trạng thái giới hạn.",
        "Bố trí cốt thép đúng yêu cầu cấu tạo.", "Đọc bản vẽ kết cấu bê tông cốt thép."], [
        ("Vật liệu bê tông cốt thép", ["Bê tông chịu nén tốt, chịu kéo kém; cốt thép bù khả năng chịu kéo.",
            "Cấp độ bền chịu nén của bê tông ký hiệu B, ví dụ B20, B25.",
            "Lực dính giữa bê tông và cốt thép giúp hai vật liệu cùng làm việc.",
            "Lớp bê tông bảo vệ chống ăn mòn cốt thép và chống cháy."]),
        ("Nguyên lý tính theo trạng thái giới hạn", ["Trạng thái giới hạn thứ nhất liên quan tới khả năng chịu lực.",
            "Trạng thái giới hạn thứ hai liên quan tới võng và nứt khi sử dụng.",
            "Tải trọng tính toán bằng tải trọng tiêu chuẩn nhân hệ số độ tin cậy.",
            "Cường độ tính toán của vật liệu nhỏ hơn cường độ tiêu chuẩn."]),
        ("Cấu kiện chịu uốn tiết diện chữ nhật", ["Giả thiết vùng nén bê tông có ứng suất phân bố hình chữ nhật.",
            "Chiều cao vùng nén x phải nhỏ hơn giới hạn ξR·h0 để tránh phá hoại giòn.",
            "Diện tích cốt thép chịu kéo xác định từ cân bằng mô men.",
            "Hàm lượng cốt thép phải nằm trong khoảng tối thiểu và tối đa cho phép."]),
        ("Cấu tạo cốt thép dầm", ["Cốt dọc chịu kéo đặt ở vùng có mô men dương lớn nhất.",
            "Cốt đai chịu lực cắt và giữ ổn định cốt dọc.",
            "Khoảng hở giữa các thanh cốt thép bảo đảm đổ và đầm bê tông được.",
            "Neo và nối cốt thép phải đủ chiều dài theo tiêu chuẩn thiết kế."])]),
    "KT3020": ("gv05", ["66KT1", "66KT2"], [
        "Hiểu cấu tạo các bộ phận chính của nhà dân dụng.", "Lựa chọn giải pháp cấu tạo phù hợp khí hậu nhiệt đới.",
        "Thể hiện chi tiết cấu tạo trên bản vẽ.", "Liên hệ cấu tạo với công năng và thẩm mỹ."], [
        ("Tổng quan cấu tạo nhà", ["Nhà gồm móng, khung chịu lực, tường, sàn, mái, cầu thang và cửa.",
            "Bộ phận chịu lực truyền tải trọng từ mái xuống móng.",
            "Bộ phận bao che bảo vệ không gian bên trong khỏi mưa, nắng, gió.",
            "Giải pháp cấu tạo phải cân bằng giữa bền vững, kinh tế và thẩm mỹ."]),
        ("Cấu tạo tường", ["Tường chịu lực đỡ sàn và mái; tường ngăn chỉ phân chia không gian.",
            "Tường gạch cần giằng tường và lanh tô ở đầu cửa.",
            "Chống thấm chân tường bằng lớp vữa xi măng có phụ gia chống thấm.",
            "Ở khí hậu nóng ẩm nên dùng tường hai lớp có khe thông gió."]),
        ("Cấu tạo sàn và mái", ["Sàn gồm lớp kết cấu chịu lực, lớp cách âm và lớp hoàn thiện.",
            "Mái bằng cần độ dốc thoát nước tối thiểu khoảng 2 phần trăm.",
            "Mái dốc lợp ngói có độ dốc lớn để thoát nước mưa nhanh.",
            "Lớp chống nóng trên mái giảm nhiệt truyền vào phòng tầng trên."]),
        ("Cầu thang và cửa", ["Bậc thang thoải mái khi 2h + b nằm trong khoảng 60 đến 64 cm.",
            "Chiếu nghỉ đặt sau tối đa khoảng 18 bậc liên tiếp.",
            "Cửa sổ bố trí đón gió chủ đạo để thông gió tự nhiên.",
            "Ô văng và lam che nắng giảm bức xạ trực tiếp ở hướng tây."])]),
    "KX3030": ("gv06", ["66KX1"], [
        "Hiểu vòng đời và các bên tham gia dự án xây dựng.", "Lập kế hoạch tiến độ bằng sơ đồ mạng.",
        "Quản lý chi phí và chất lượng dự án.", "Nhận diện và ứng phó rủi ro dự án."], [
        ("Tổng quan dự án xây dựng", ["Dự án xây dựng có mục tiêu, thời hạn và ngân sách xác định.",
            "Các bên tham gia gồm chủ đầu tư, tư vấn, nhà thầu và cơ quan quản lý.",
            "Vòng đời dự án: chuẩn bị, thực hiện và kết thúc đưa vào sử dụng.",
            "Ban quản lý dự án điều phối các bên để đạt mục tiêu."]),
        ("Lập tiến độ bằng sơ đồ mạng", ["Sơ đồ mạng biểu diễn công việc và quan hệ trước sau.",
            "Đường găng là chuỗi công việc dài nhất quyết định thời gian hoàn thành.",
            "Công việc trên đường găng có thời gian dự trữ bằng không.",
            "Rút ngắn tiến độ bằng cách tăng nguồn lực cho công việc găng."]),
        ("Quản lý chi phí", ["Tổng mức đầu tư là chi phí dự tính của toàn bộ dự án.",
            "Phương pháp giá trị thu được so sánh giá trị kế hoạch, giá trị thực hiện và chi phí thực tế.",
            "Chỉ số CPI nhỏ hơn 1 cho thấy dự án đang vượt chi phí.",
            "Kiểm soát thay đổi giúp tránh phát sinh chi phí ngoài kế hoạch."]),
        ("Quản lý rủi ro", ["Rủi ro là sự kiện không chắc chắn ảnh hưởng tới mục tiêu dự án.",
            "Đánh giá rủi ro theo xác suất xảy ra và mức độ tác động.",
            "Các chiến lược ứng phó: né tránh, chuyển giao, giảm thiểu, chấp nhận.",
            "Sổ đăng ký rủi ro được cập nhật định kỳ trong suốt dự án."])]),
    "MI2020": ("gv03", ["66IT1", "66KX1"], [
        "Nắm các khái niệm xác suất cơ bản.", "Làm việc với biến ngẫu nhiên và các phân phối thông dụng.",
        "Ước lượng tham số và kiểm định giả thuyết.", "Vận dụng thống kê vào dữ liệu kỹ thuật."], [
        ("Xác suất và biến cố", ["Xác suất của biến cố nằm trong đoạn từ 0 đến 1.",
            "Công thức cộng: P(A ∪ B) = P(A) + P(B) − P(A ∩ B).",
            "Hai biến cố độc lập khi P(A ∩ B) = P(A)·P(B).",
            "Công thức Bayes cập nhật xác suất khi có thông tin mới."]),
        ("Biến ngẫu nhiên", ["Biến ngẫu nhiên rời rạc mô tả bằng bảng phân phối xác suất.",
            "Kỳ vọng là giá trị trung bình theo xác suất của biến ngẫu nhiên.",
            "Phương sai đo mức phân tán quanh kỳ vọng.",
            "Phân phối nhị thức mô tả số lần thành công trong n phép thử độc lập."]),
        ("Phân phối chuẩn", ["Phân phối chuẩn có đồ thị hình chuông đối xứng quanh kỳ vọng.",
            "Khoảng 95 phần trăm giá trị nằm trong μ ± 1,96σ.",
            "Chuẩn hóa Z = (X − μ) / σ đưa về phân phối chuẩn tắc.",
            "Định lý giới hạn trung tâm giải thích vì sao trung bình mẫu xấp xỉ chuẩn."]),
        ("Ước lượng và kiểm định", ["Ước lượng khoảng cho biết miền chứa tham số với độ tin cậy cho trước.",
            "Giả thuyết H0 được bác bỏ khi giá trị p nhỏ hơn mức ý nghĩa α.",
            "Sai lầm loại I là bác bỏ H0 khi H0 đúng.",
            "Cỡ mẫu lớn hơn làm khoảng ước lượng hẹp hơn."])]),
}

# Class questions (student asks on a lecture page; lecturer replies). course -> [(lecture index, question, reply)]
LEARNING_QA = {
    "IT3090": [(1, "Thầy ơi, sao so sánh với NULL bằng dấu = lại không ra kết quả ạ?",
                "Vì NULL nghĩa là chưa biết giá trị, mọi phép so sánh với NULL đều cho UNKNOWN. Em dùng IS NULL nhé."),
               (2, "LEFT JOIN và RIGHT JOIN có thể thay nhau được không ạ?",
                "Được, A LEFT JOIN B tương đương B RIGHT JOIN A. Thường dùng LEFT JOIN cho dễ đọc."),
               (3, "Bảng đạt 3NF thì có chắc đạt 2NF không ạ?", "Có. Mỗi dạng chuẩn cao hơn đều bao hàm các dạng chuẩn thấp hơn.")],
    "IT3080": [(1, "Vì sao bắt tay TCP cần ba bước mà không phải hai ạ?",
                "Bước thứ ba xác nhận rằng phía khách đã nhận được số thứ tự của máy chủ, tránh kết nối cũ bị mở lại."),
               (2, "Mạng /26 có 64 địa chỉ, sao chỉ dùng được 62 ạ?", "Hai địa chỉ dành cho địa chỉ mạng và địa chỉ quảng bá.")],
    "IT3120": [(1, "A* có luôn nhanh hơn tìm kiếm theo chiều rộng không ạ?",
                "Không luôn luôn; A* nhanh khi heuristic tốt. Heuristic bằng 0 thì A* thành tìm kiếm chi phí đều.")],
    "XD3010": [(1, "Thầy cho em hỏi đơn vị của E trong công thức ΔL ạ?",
                "E có đơn vị ứng suất, thường dùng MPa hoặc kN/cm². Em nhớ đổi đơn vị thống nhất trước khi tính."),
               (3, "Ứng suất tiếp lớn nhất của dầm chữ nhật nằm ở đâu ạ?", "Ở trục trung hòa, bằng 1,5 lần ứng suất tiếp trung bình.")],
    "XD3030": [(2, "Nếu x vượt quá ξR·h0 thì xử lý thế nào ạ?",
                "Có thể tăng tiết diện, tăng cấp độ bền bê tông hoặc đặt thêm cốt thép chịu nén.")],
    "KT3020": [(1, "Cô ơi khe thông gió giữa hai lớp tường nên rộng bao nhiêu ạ?",
                "Thường từ 3 đến 5 cm, có lỗ thoát ở chân và đỉnh tường để không khí lưu thông."),
               (3, "Công thức 2h + b áp dụng cho cả cầu thang ngoài trời không ạ?", "Có, nhưng cầu thang ngoài trời nên thoải hơn và chống trơn.")],
    "KX3030": [(1, "Một dự án có thể có hai đường găng không ạ?", "Có, khi hai chuỗi công việc dài bằng nhau. Cả hai đều cần theo dõi sát.")],
    "MI2020": [(0, "Biến cố độc lập và xung khắc khác nhau thế nào ạ?",
                "Xung khắc là không thể cùng xảy ra; độc lập là xảy ra cái này không ảnh hưởng xác suất cái kia."),
               (3, "Giá trị p bằng 0,05 thì có bác bỏ H0 ở mức 5% không ạ?", "Quy ước thường dùng là bác bỏ khi p < α, nên p = 0,05 là ca biên, nên báo cáo rõ.")],
}

# Questions students ask the assistant (answered live by the real RAG over public HUCE sources).
CHAT_QUESTIONS = [
    "Điều kiện để được xét học bổng khuyến khích học tập là gì?",
    "Sinh viên bị cảnh báo học tập khi nào?",
    "Thủ tục xin bảo lưu kết quả học tập như thế nào?",
    "Điểm học phần được tính theo thang điểm chữ ra sao?",
    "Sinh viên được đăng ký tối đa bao nhiêu tín chỉ một học kỳ?",
    "Làm thế nào để phúc khảo bài thi?",
    "Điều kiện xét tốt nghiệp đại học gồm những gì?",
    "Chuẩn đầu ra tiếng Anh của sinh viên đại học chính quy là gì?",
    "Sinh viên nghỉ học quá bao nhiêu buổi thì bị cấm thi?",
    "Học phí được miễn giảm cho những đối tượng nào?",
    "Cách tính điểm trung bình chung tích lũy?",
    "Khi nào sinh viên bị buộc thôi học?",
    "Sinh viên có được học cùng lúc hai chương trình không?",
    "Quy định về học lại và học cải thiện điểm?",
    "Thời gian tối đa hoàn thành khóa học là bao lâu?",
    "Xếp loại rèn luyện của sinh viên dựa trên tiêu chí nào?",
    "Sinh viên được miễn học phần tiếng Anh khi có chứng chỉ gì?",
    "Thủ tục chuyển ngành học trong trường?",
    "Đồ án tốt nghiệp được đăng ký khi nào?",
    "Xếp hạng tốt nghiệp loại giỏi cần điểm trung bình bao nhiêu?",
    "Sinh viên năm nhất cần làm gì khi nhập học?",
    "Quy định về thi lại kết thúc học phần?",
    "Sinh viên vắng thi có lý do chính đáng thì xử lý thế nào?",
    "Điều kiện để được giao đồ án tốt nghiệp ngành kiến trúc?",
    "Ký túc xá của trường đăng ký ở đâu?",
    "Thực tập tốt nghiệp kéo dài bao lâu?",
    "Sinh viên được rút học phần đã đăng ký trước thời hạn nào?",
    "Quy định về trang phục và thẻ sinh viên khi đi thi?",
    "Học bổng cho sinh viên có hoàn cảnh khó khăn xét như thế nào?",
    "Có những ngành đào tạo nào tại Khoa Công nghệ thông tin?",
    "Sinh viên được bảo lưu tối đa bao nhiêu học kỳ?",
    "Điểm rèn luyện ảnh hưởng thế nào đến học bổng?",
    "Lịch nghỉ Tết của sinh viên được thông báo ở đâu?",
    "Sinh viên muốn tạm ngừng học vì đi nghĩa vụ quân sự cần thủ tục gì?",
    "Quy định đánh giá học phần đồ án môn học?",
    "Sinh viên đạt chuẩn đầu ra tin học như thế nào?",
    "Trường có hỗ trợ vay vốn cho sinh viên không?",
    "Kỳ học hè dành cho sinh viên học lại có không?",
    "Cách đăng ký học phần trên cổng thông tin sinh viên?",
    "Sinh viên nước ngoài muốn trao đổi ngắn hạn tại trường cần gì?",
]
