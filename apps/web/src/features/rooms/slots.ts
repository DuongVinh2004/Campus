const HCM_OFFSET_MS = 7 * 60 * 60 * 1000; // Vietnam has no daylight saving
const OPEN_MIN = 7 * 60;
const CLOSE_MIN = 21 * 60;
const DEFAULT_LENGTH_MIN = 120;
const LEAD_MIN = 15;
const STEP_MIN = 30;

function hhmm(minutes: number): string {
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
}

/**
 * The slot the booking page opens with: the next half hour at least 15 minutes from now, two hours long, inside the 07:00-21:00
 * opening hours. Late in the evening it moves to 07:00 tomorrow, so a first booking with the defaults is never "in the past".
 */
export function defaultBookingSlot(now: Date = new Date()): { date: string; start: string; end: string } {
  const local = new Date(now.getTime() + HCM_OFFSET_MS);
  let minutes = local.getUTCHours() * 60 + local.getUTCMinutes() + LEAD_MIN;
  minutes = Math.ceil(minutes / STEP_MIN) * STEP_MIN;
  let dayShift = 0;
  if (minutes < OPEN_MIN) minutes = OPEN_MIN;
  if (minutes + DEFAULT_LENGTH_MIN > CLOSE_MIN) {
    minutes = OPEN_MIN;
    dayShift = 1;
  }
  const day = new Date(local.getTime() + dayShift * 24 * 60 * 60 * 1000);
  return { date: day.toISOString().slice(0, 10), start: hhmm(minutes), end: hhmm(minutes + DEFAULT_LENGTH_MIN) };
}

/** "Giữ chỗ đến 18:16 (còn 15 phút)" for a preview that expires at the given instant. */
export function formatHold(expiresAt: string, now: Date = new Date()): string {
  const at = new Date(expiresAt);
  if (Number.isNaN(at.getTime())) return "";
  const local = new Date(at.getTime() + HCM_OFFSET_MS);
  const clock = hhmm(local.getUTCHours() * 60 + local.getUTCMinutes());
  const left = Math.max(0, Math.round((at.getTime() - now.getTime()) / 60000));
  return `Giữ chỗ đến ${clock} (còn ${left} phút)`;
}
