"use client";

import React, { useEffect, useState } from "react";

interface InstallEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export function isIos(userAgent: string): boolean {
  return /iphone|ipad|ipod/i.test(userAgent);
}

export function isStandalone(): boolean {
  return typeof window !== "undefined" && (window.matchMedia?.("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true);
}

/** "Install the app": a button where the browser offers it, and a short how-to on iPhone/iPad, which has no install prompt. Hidden once installed. */
export function InstallPrompt() {
  const [event, setEvent] = useState<InstallEvent | null>(null);
  const [installed, setInstalled] = useState(false);
  const [ios, setIos] = useState(false);

  useEffect(() => {
    setInstalled(isStandalone());
    setIos(isIos(navigator.userAgent));
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setEvent(e as InstallEvent);
    };
    const onInstalled = () => setInstalled(true);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (installed) return null;
  if (event) {
    return (
      <button type="button" className="min-h-[44px] rounded-lg border px-4 text-sm font-medium"
              onClick={async () => { await event.prompt(); await event.userChoice; setEvent(null); }}>
        Cài ứng dụng Campus 24/7
      </button>
    );
  }
  if (ios) {
    return <p data-testid="ios-install-hint" className="text-sm">Để cài ứng dụng: bấm nút Chia sẻ trong Safari, rồi chọn “Thêm vào MH chính”.</p>;
  }
  return null;
}
