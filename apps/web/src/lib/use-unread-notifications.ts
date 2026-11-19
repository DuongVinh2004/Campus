"use client";
import { useEffect, useState } from "react";
import { notificationsApi } from "./campus-ops-api";

/** Unread notification count for the signed-in actor; refreshes every minute and when the tab regains focus. */
export function useUnreadNotifications(enabled: boolean): number {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const load = () => { notificationsApi.list({ unreadOnly: true, limit: 1 }).then(r => { if (active) setCount(r.unread_count); }).catch(() => undefined); };
    load();
    const timer = window.setInterval(load, 60_000);
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    window.addEventListener("campus:notifications-changed", onFocus);
    return () => { active = false; window.clearInterval(timer); window.removeEventListener("focus", onFocus); window.removeEventListener("campus:notifications-changed", onFocus); };
  }, [enabled]);
  return count;
}
