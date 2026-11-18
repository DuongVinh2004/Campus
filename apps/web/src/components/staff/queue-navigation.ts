interface QueuePosition {
  url: string;
  scrollY: number;
  focusId: string;
}

const key = (accountId: string) => `campus247_staff_queue_position_v1:${accountId}`;

export function queuePosition(accountId: string): QueuePosition | null {
  try {
    const saved = sessionStorage.getItem(key(accountId));
    if (!saved) return null;
    const value = JSON.parse(saved) as QueuePosition;
    const url = new URL(value.url, window.location.origin);
    if (url.origin !== window.location.origin || url.pathname !== "/dashboard") return null;
    if (!Number.isFinite(value.scrollY) || value.scrollY < 0 || typeof value.focusId !== "string") return null;
    return { ...value, url: url.pathname + url.search };
  } catch { return null; }
}

export function rememberQueuePosition(accountId: string, focusId: string) {
  try {
    sessionStorage.setItem(key(accountId), JSON.stringify({
      url: window.location.pathname + window.location.search,
      scrollY: window.scrollY,
      focusId,
    } satisfies QueuePosition));
  } catch { /* Navigation works even when position storage is unavailable. */ }
}
