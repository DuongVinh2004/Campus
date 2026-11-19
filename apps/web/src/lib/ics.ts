/** iCalendar (RFC 5545) builder for the student's schedule. Pure functions, no DOM. */

export interface IcsEvent {
  id: string;
  title: string;
  startsAt: string; // ISO 8601 with offset
  endsAt: string;
  location?: string;
  description?: string;
}

export interface BuildIcsOptions {
  now?: Date;
  prodId?: string;
  calendarName?: string;
}

const CRLF = "\r\n";
const encoder = new TextEncoder();

/** RFC 5545 section 3.3.11: escape backslash, semicolon, comma and line breaks in TEXT values. */
export function escapeIcsText(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r\n|\r|\n/g, "\\n");
}

/** Section 3.1: lines are folded at 75 octets; a fold is CRLF plus one space, and never splits a UTF-8 character. */
export function foldIcsLine(line: string): string {
  if (encoder.encode(line).length <= 75) return line;
  const parts: string[] = [];
  let current = "";
  let currentBytes = 0;
  let limit = 75;
  for (const char of line) {
    const size = encoder.encode(char).length;
    if (currentBytes + size > limit) {
      parts.push(current);
      current = "";
      currentBytes = 0;
      limit = 74; // continuation lines start with one space
    }
    current += char;
    currentBytes += size;
  }
  parts.push(current);
  return parts.join(CRLF + " ");
}

function utcStamp(date: Date): string {
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function uidFor(id: string): string {
  return `${id.replace(/[^A-Za-z0-9._-]/g, "-")}@campus247.local`;
}

/** Events with an unreadable or non-positive time range are skipped; `skipped` says how many. */
export function buildIcs(events: IcsEvent[], options: BuildIcsOptions = {}): { text: string; skipped: number } {
  const now = options.now ?? new Date();
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    `PRODID:${options.prodId ?? "-//Campus 24/7//Schedule//VI"}`,
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    `X-WR-CALNAME:${escapeIcsText(options.calendarName ?? "Lịch học Campus 24/7")}`,
    "X-WR-TIMEZONE:Asia/Ho_Chi_Minh",
  ];
  let skipped = 0;
  for (const event of events) {
    const start = new Date(event.startsAt);
    const end = new Date(event.endsAt);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
      skipped += 1;
      continue;
    }
    lines.push(
      "BEGIN:VEVENT",
      `UID:${uidFor(event.id)}`,
      `DTSTAMP:${utcStamp(now)}`,
      `DTSTART:${utcStamp(start)}`,
      `DTEND:${utcStamp(end)}`,
      `SUMMARY:${escapeIcsText(event.title)}`,
    );
    if (event.location) lines.push(`LOCATION:${escapeIcsText(event.location)}`);
    if (event.description) lines.push(`DESCRIPTION:${escapeIcsText(event.description)}`);
    lines.push("END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  return { text: lines.map(foldIcsLine).join(CRLF) + CRLF, skipped };
}
