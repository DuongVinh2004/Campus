const MINUTE_MS = 60_000;
const DAY_MS = 24 * 60 * MINUTE_MS;

export const CAMPUS_TIMEZONE = "Asia/Bangkok";

export function classTimeZone(value = CAMPUS_TIMEZONE): string {
  try { new Intl.DateTimeFormat("vi-VN", { timeZone: value }); return value; }
  catch { return CAMPUS_TIMEZONE; }
}

export function classDateTime(instant: string | number, timeZone: string): string {
  const formatter = new Intl.DateTimeFormat("sv-SE", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  const parts = Object.fromEntries(formatter.formatToParts(new Date(instant)).map(({ type, value }) => [type, value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function classDateTimeCandidates(local: string, timeZone: string): { utc: string; offsetMinutes: number }[] {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(local)) return [];
  const wallTime = Date.parse(`${local}Z`);
  if (!Number.isFinite(wallTime)) return [];
  const candidates = new Set<number>();
  for (const sample of [wallTime - DAY_MS, wallTime, wallTime + DAY_MS]) {
    const localSample = Date.parse(`${classDateTime(sample, timeZone)}Z`);
    const instant = wallTime - (localSample - sample);
    if (classDateTime(instant, timeZone) === local) candidates.add(instant);
  }
  return [...candidates].sort((a, b) => a - b).map(instant => ({
    utc: new Date(instant).toISOString(), offsetMinutes: (wallTime - instant) / MINUTE_MS,
  }));
}

export function classDateTimeToUtc(local: string, timeZone: string): string {
  if (!Number.isFinite(Date.parse(`${local}Z`))) throw new Error("Nhập ngày giờ theo múi giờ của lớp.");
  const candidates = classDateTimeCandidates(local, timeZone);
  if (candidates.length !== 1) throw new Error("Giờ này bị trùng hoặc không tồn tại trong múi giờ của lớp. Hãy chọn giờ khác.");
  return candidates[0].utc;
}

export function utcOffsetLabel(minutes: number): string {
  const absolute = Math.abs(minutes);
  return `UTC${minutes < 0 ? "−" : "+"}${String(Math.floor(absolute / 60)).padStart(2, "0")}:${String(absolute % 60).padStart(2, "0")}`;
}
