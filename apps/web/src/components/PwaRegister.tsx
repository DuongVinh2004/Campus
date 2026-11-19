"use client";

import { useEffect } from "react";

/** Asks every service worker of this site to forget its caches. Call it when a person signs out. */
export function clearPwaCaches(): void {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  navigator.serviceWorker.getRegistration().then((registration) => registration?.active?.postMessage({ type: "campus247:clear-caches" })).catch(() => undefined);
}

/** Registers the service worker once the page has loaded, only in a secure context (https or localhost). Renders nothing. */
export function PwaRegister() {
  useEffect(() => {
    if (typeof window === "undefined" || !window.isSecureContext || !("serviceWorker" in navigator)) return;
    const register = () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined); // a failed registration only means no offline page
    };
    if (document.readyState === "complete") register();
    else window.addEventListener("load", register, { once: true });
    return () => window.removeEventListener("load", register);
  }, []);
  return null;
}
