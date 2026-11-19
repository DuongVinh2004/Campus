import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ScheduleView, type ScheduleEntry } from "./ScheduleView";

const entries: ScheduleEntry[] = [
  {
    id: "e1",
    courseCode: "IT3080",
    courseName: "Mạng máy tính",
    dayOfWeek: "Thứ Hai",
    time: "09:35 - 11:55",
    startsAt: "2026-11-16T02:35:00Z",
    endsAt: "2026-11-16T04:55:00Z",
    room: "H3-204",
    lecturer: "TS. Trần Văn Minh",
    type: "class",
  },
  // No ISO times (fallback data): it cannot become a valid VEVENT, so it must not be exported.
  { id: "e2", courseCode: "IT1", courseName: "Không có giờ", dayOfWeek: "Thứ Ba", time: "07:00 - 09:25", room: "A1", lecturer: "X", type: "class" },
];

afterEach(() => {
  vi.restoreAllMocks();
  delete (URL as Partial<typeof URL>).createObjectURL;
  delete (URL as Partial<typeof URL>).revokeObjectURL;
});

describe("ScheduleView .ics export", () => {
  it("downloads a calendar file with real start and end times", async () => {
    let blob: Blob | undefined;
    // jsdom does not implement these two; install fakes and remove them afterwards.
    Object.assign(URL, {
      createObjectURL: (value: Blob) => {
        blob = value;
        return "blob:test";
      },
      revokeObjectURL: () => {},
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(<ScheduleView entries={entries} />);
    fireEvent.click(screen.getByRole("button", { name: /Xuất lịch iCal/i }));

    expect(blob).toBeDefined();
    const text = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsText(blob!);
    });
    expect(text).toContain("DTSTART:20261116T023500Z");
    expect(text).toContain("DTEND:20261116T045500Z");
    expect(text).toContain("UID:e1@campus247.local");
    expect(text).toContain("SUMMARY:Mạng máy tính (IT3080)");
    expect(text).not.toContain("Không có giờ");
    expect(text.split("BEGIN:VEVENT")).toHaveLength(2);
    expect(text).toContain("\r\n");
  });
});
