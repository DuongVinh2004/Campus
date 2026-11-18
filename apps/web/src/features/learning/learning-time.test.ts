import { describe, expect, it } from "vitest";
import { CAMPUS_TIMEZONE, classDateTime, classDateTimeCandidates, classDateTimeToUtc, utcOffsetLabel } from "./learning-time";

describe("class-local learning dates", () => {
  it("converts Vietnamese class time without relying on the browser's timezone", () => {
    expect(classDateTimeToUtc("2026-11-06T00:30", CAMPUS_TIMEZONE)).toBe("2026-11-05T17:30:00.000Z");
    expect(classDateTime("2026-11-05T17:30:00Z", CAMPUS_TIMEZONE)).toBe("2026-11-06T00:30");
  });

  it("rejects ambiguous and missing wall times across daylight saving changes", () => {
    expect(() => classDateTimeToUtc("2026-03-08T02:30", "America/New_York")).toThrow(/bị trùng hoặc không tồn tại/);
    expect(() => classDateTimeToUtc("2026-11-01T01:30", "America/New_York")).toThrow(/bị trùng hoặc không tồn tại/);
    expect(classDateTimeToUtc("2026-11-01T02:30", "America/New_York")).toBe("2026-11-01T07:30:00.000Z");
  });

  it("returns both valid offsets for an exit ticket at a repeated class wall time", () => {
    expect(classDateTimeCandidates("2026-11-01T01:30", "America/New_York")).toEqual([
      { utc: "2026-11-01T05:30:00.000Z", offsetMinutes: -240 },
      { utc: "2026-11-01T06:30:00.000Z", offsetMinutes: -300 },
    ]);
    expect(classDateTimeCandidates("2026-03-08T02:30", "America/New_York")).toEqual([]);
    expect(utcOffsetLabel(630)).toBe("UTC+10:30");
  });
});
