import { describe, expect, it } from "vitest";
import { buildIcs, escapeIcsText, foldIcsLine } from "./ics";

const NOW = new Date("2026-11-17T03:00:00Z");

/** Minimal RFC 5545 reader used only to check the output: unfold, then split into properties per component. */
function parse(text: string) {
  expect(text.endsWith("\r\n")).toBe(true);
  expect(text.replace(/\r\n/g, "")).not.toMatch(/[\r\n]/); // only CRLF line breaks
  const unfolded = text.replace(/\r\n[ \t]/g, "").split("\r\n").filter(Boolean);
  const events: Record<string, string>[] = [];
  let current: Record<string, string> | null = null;
  for (const line of unfolded) {
    if (line === "BEGIN:VEVENT") current = {};
    else if (line === "END:VEVENT" && current) {
      events.push(current);
      current = null;
    } else if (current) {
      const at = line.indexOf(":");
      current[line.slice(0, at)] = line.slice(at + 1);
    }
  }
  return { unfolded, events };
}

describe("buildIcs", () => {
  it("emits the properties Google and Apple Calendar need to import an event", () => {
    const { text, skipped } = buildIcs(
      [
        {
          id: "abc-1",
          title: "Mạng máy tính (IT3080)",
          startsAt: "2026-11-16T09:35:00+07:00",
          endsAt: "2026-11-16T11:55:00+07:00",
          location: "H3-204",
          description: "Giảng viên: TS. Trần Văn Minh",
        },
      ],
      { now: NOW },
    );
    const { unfolded, events } = parse(text);
    expect(skipped).toBe(0);
    expect(unfolded[0]).toBe("BEGIN:VCALENDAR");
    expect(unfolded[1]).toBe("VERSION:2.0");
    expect(unfolded.at(-1)).toBe("END:VCALENDAR");
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({
      UID: "abc-1@campus247.local",
      DTSTAMP: "20261117T030000Z",
      DTSTART: "20261116T023500Z",
      DTEND: "20261116T045500Z",
      SUMMARY: "Mạng máy tính (IT3080)",
      LOCATION: "H3-204",
    });
  });

  it("escapes commas, semicolons, backslashes and newlines", () => {
    expect(escapeIcsText("A, B; C\\D\nE")).toBe("A\\, B\\; C\\\\D\\nE");
    const { text } = buildIcs(
      [{ id: "x", title: "Toán, rời rạc; nhóm 1", startsAt: "2026-11-16T00:00:00Z", endsAt: "2026-11-16T01:00:00Z" }],
      { now: NOW },
    );
    expect(parse(text).events[0].SUMMARY).toBe("Toán\\, rời rạc\\; nhóm 1");
  });

  it("folds long lines at 75 octets without splitting a UTF-8 character, and unfolding restores the text", () => {
    const title = "Phương pháp luận nghiên cứu khoa học và kỹ năng viết báo cáo kỹ thuật bằng tiếng Việt có dấu đầy đủ";
    const { text } = buildIcs(
      [{ id: "long", title, startsAt: "2026-11-16T00:00:00Z", endsAt: "2026-11-16T01:00:00Z" }],
      { now: NOW },
    );
    const raw = text.split("\r\n").filter(Boolean);
    for (const line of raw) expect(new TextEncoder().encode(line).length).toBeLessThanOrEqual(75);
    expect(raw.some((line) => line.startsWith(" "))).toBe(true);
    expect(parse(text).events[0].SUMMARY).toBe(title);
  });

  it("skips events whose time range is unreadable or not positive and reports the count", () => {
    const { text, skipped } = buildIcs(
      [
        { id: "ok", title: "Có giờ", startsAt: "2026-11-16T00:00:00Z", endsAt: "2026-11-16T01:00:00Z" },
        { id: "bad", title: "Sai giờ", startsAt: "chưa rõ", endsAt: "2026-11-16T01:00:00Z" },
        { id: "neg", title: "Âm", startsAt: "2026-11-16T02:00:00Z", endsAt: "2026-11-16T01:00:00Z" },
      ],
      { now: NOW },
    );
    expect(skipped).toBe(2);
    expect(parse(text).events.map((e) => e.UID)).toEqual(["ok@campus247.local"]);
  });

  it("makes the UID safe for ids with unusual characters", () => {
    const { text } = buildIcs(
      [{ id: "a b/c:d", title: "T", startsAt: "2026-11-16T00:00:00Z", endsAt: "2026-11-16T01:00:00Z" }],
      { now: NOW },
    );
    expect(parse(text).events[0].UID).toBe("a-b-c-d@campus247.local");
  });
});

describe("foldIcsLine", () => {
  it("leaves short lines alone", () => {
    expect(foldIcsLine("SUMMARY:ngắn")).toBe("SUMMARY:ngắn");
  });
});
