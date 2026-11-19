/** Schedule time helpers. Everything is computed in Asia/Ho_Chi_Minh, never in the browser's time zone. */

export const SCHEDULE_TIME_ZONE = "Asia/Ho_Chi_Minh";

const WEEKDAYS_VI = ["Chủ nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"] as const;
const WEEKDAY_INDEX: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };

const weekdayFormat = new Intl.DateTimeFormat("en-US", { timeZone: SCHEDULE_TIME_ZONE, weekday: "short" });
const clockFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: SCHEDULE_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function vnWeekday(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Chung";
  return WEEKDAYS_VI[WEEKDAY_INDEX[weekdayFormat.format(date)] ?? 1];
}

/** "07:00 - 09:25" in Vietnam time. */
export function vnTimeRange(startIso: string, endIso: string): string {
  const start = new Date(startIso);
  const end = new Date(endIso);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return "";
  return `${clockFormat.format(start)} - ${clockFormat.format(end)}`;
}

const EXAM_WORD = /(^|[\s\-–—:(])(thi|kiểm tra)(?=$|[\s\-–—:)])/iu;

/**
 * Whether a course title names an exam. Matches the word "thi" / "kiểm tra" on its own, so
 * "Thi giữa kỳ - Mạng máy tính" is an exam but "Thiết kế hệ thống" is not.
 * Temporary until the schedule source carries an explicit event type.
 */
export function isExamTitle(title: string): boolean {
  return EXAM_WORD.test(title.normalize("NFC"));
}
