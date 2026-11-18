"use client";

import { useEffect, useRef } from "react";

/**
 * Runs `task` now, then every `intervalMs` while the tab is visible, and once more when the tab becomes visible again.
 * A hidden tab makes no requests, so a page left open in the background costs the server nothing.
 */
export function usePolling(task: () => void | Promise<void>, intervalMs: number, deps: ReadonlyArray<unknown> = []): void {
  const latest = useRef(task);
  latest.current = task;
  useEffect(() => {
    const run = () => { void Promise.resolve(latest.current()).catch(() => undefined); };
    run();
    const timer = window.setInterval(() => { if (!document.hidden) run(); }, intervalMs);
    const onVisible = () => { if (!document.hidden) run(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => { window.clearInterval(timer); document.removeEventListener("visibilitychange", onVisible); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, ...deps]);
}
