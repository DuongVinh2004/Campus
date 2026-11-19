import { describe, expect, it } from "vitest";
import { defaultBookingSlot, formatHold } from "./slots";

// Vietnam is UTC+7: 17:50 there is 10:50 UTC.
describe("defaultBookingSlot", () => {
  it("opens on the next half hour that is still ahead (never a slot in the past)", () => {
    expect(defaultBookingSlot(new Date("2026-11-18T10:50:00Z"))).toEqual({ date: "2026-11-18", start: "18:30", end: "20:30" });
    expect(defaultBookingSlot(new Date("2026-11-18T02:00:00Z"))).toEqual({ date: "2026-11-18", start: "09:30", end: "11:30" });
  });

  it("starts at 07:00 before opening hours", () => {
    expect(defaultBookingSlot(new Date("2026-11-17T22:00:00Z"))).toEqual({ date: "2026-11-18", start: "07:00", end: "09:00" });
  });

  it("moves to 07:00 tomorrow when two hours no longer fit before 21:00", () => {
    expect(defaultBookingSlot(new Date("2026-11-18T13:10:00Z"))).toEqual({ date: "2026-11-19", start: "07:00", end: "09:00" });
    expect(defaultBookingSlot(new Date("2026-11-18T16:30:00Z"))).toEqual({ date: "2026-11-19", start: "07:00", end: "09:00" });
  });
});

describe("formatHold", () => {
  it("shows the Vietnam clock time and the minutes left, not an ISO string", () => {
    const text = formatHold("2026-11-18T11:01:15+00:00", new Date("2026-11-18T10:46:15Z"));
    expect(text).toBe("Giữ chỗ đến 18:01 (còn 15 phút)");
    expect(text).not.toContain("T11:");
  });
});
