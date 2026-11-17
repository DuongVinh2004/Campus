import { describe, expect, it } from "vitest";
import { isExamTitle, vnTimeRange, vnWeekday } from "./schedule-time";

describe("vnWeekday", () => {
  it("uses Vietnam time even when UTC is still the previous day", () => {
    // Monday 2026-11-16 07:00 in Vietnam is Sunday 2026-11-15 in UTC-evening zones.
    expect(vnWeekday("2026-11-16T00:00:00Z")).toBe("Thứ Hai");
    expect(vnWeekday("2026-11-15T17:30:00Z")).toBe("Thứ Hai");
    expect(vnWeekday("2026-11-15T16:30:00Z")).toBe("Chủ nhật");
  });

  it("does not depend on the process time zone", () => {
    const saved = process.env.TZ;
    try {
      for (const tz of ["America/New_York", "Pacific/Kiritimati", "UTC"]) {
        process.env.TZ = tz;
        expect(vnWeekday("2026-11-15T20:00:00Z")).toBe("Thứ Hai");
      }
    } finally {
      if (saved === undefined) delete process.env.TZ;
      else process.env.TZ = saved;
    }
  });

  it("falls back for an invalid date", () => {
    expect(vnWeekday("not a date")).toBe("Chung");
  });
});

describe("vnTimeRange", () => {
  it("formats the range as 24-hour Vietnam time", () => {
    expect(vnTimeRange("2026-11-16T00:00:00Z", "2026-11-16T02:25:00Z")).toBe("07:00 - 09:25");
    expect(vnTimeRange("2026-11-16T06:00:00Z", "2026-11-16T08:25:00Z")).toBe("13:00 - 15:25");
  });

  it("returns an empty string for invalid input", () => {
    expect(vnTimeRange("x", "2026-11-16T02:25:00Z")).toBe("");
  });
});

describe("isExamTitle", () => {
  it.each([
    "Thi giữa kỳ — Mạng máy tính",
    "Thi cuối kỳ Cơ sở dữ liệu",
    "Kiểm tra giữa kỳ Giải tích",
    "Mạng máy tính (thi)",
    "THI HỌC KỲ",
  ])("treats %s as an exam", (title) => expect(isExamTitle(title)).toBe(true));

  it.each([
    "Thiết kế hệ thống",
    "Thiết kế web",
    "Kiến trúc máy tính",
    "Trí tuệ nhân tạo",
    "Lý thuyết đồ thị",
    "Phương pháp luận nghiên cứu khoa học",
  ])("does not treat %s as an exam", (title) => expect(isExamTitle(title)).toBe(false));

  it("works on decomposed Unicode input", () => {
    expect(isExamTitle("Kiểm tra giữa kỳ".normalize("NFD"))).toBe(true);
  });
});
