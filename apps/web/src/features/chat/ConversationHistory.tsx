"use client";

import React, { useEffect, useState } from "react";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { sessionLoginHref } from "./local-session";

interface ConversationSummary { id: string; title: string }
const UUID7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export function ConversationHistory({ activeId, revision }: { activeId: string | null; revision: number }) {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [state, setState] = useState<"loading" | "success" | "error" | "expired">("loading");
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    setItems([]); setState("loading");
    void (async () => {
      try {
        const response = await fetch(`${CAMPUS_API_BASE_URL}/v1/assistant/conversations?limit=20`, {
          credentials: "include", cache: "no-store", signal: controller.signal,
        });
        if (!active) return;
        if (response.status === 401) { setState("expired"); return; }
        if (!response.ok) throw new Error();
        const value = await response.json();
        if (!Array.isArray(value?.items) || value.items.length > 20 || !value.items.every((item: ConversationSummary) =>
          item && UUID7.test(item.id) && typeof item.title === "string" && item.title.length <= 2000)
          || new Set(value.items.map((item: ConversationSummary) => item.id)).size !== value.items.length) throw new Error();
        if (active && !controller.signal.aborted) { setItems(value.items); setState("success"); }
      } catch { if (active) { setItems([]); setState("error"); } }
      finally { window.clearTimeout(timeout); }
    })();
    return () => { active = false; controller.abort(); window.clearTimeout(timeout); };
  }, [revision]);

  return <section data-conversation-history className="mb-4 min-w-0">
    <h2 className="mb-1 px-3 text-xs font-semibold text-slate-500 dark:text-slate-400">Lịch sử</h2>
    <nav aria-label="Lịch sử hội thoại" className="space-y-1">
      {items.map(item => <a key={item.id} href={`/chat?conversation_id=${encodeURIComponent(item.id)}`}
        aria-current={item.id === activeId ? "page" : undefined}
        className={`block min-h-11 break-words rounded-xl px-3 py-2 text-sm ${item.id === activeId
          ? "bg-slate-200/70 font-semibold text-slate-900 dark:bg-slate-800 dark:text-slate-100"
          : "text-slate-600 hover:bg-slate-200/50 dark:text-slate-400 dark:hover:bg-slate-800/50"}`}>
        {item.title.trim() || "Hội thoại chưa có tiêu đề"}
      </a>)}
    </nav>
    {state === "loading" && <p role="status" className="px-3 text-xs">Đang tải lịch sử…</p>}
    {state === "success" && !items.length && <p className="px-3 text-xs">Chưa có hội thoại đã lưu.</p>}
    {state === "error" && <p role="status" className="px-3 text-xs">Chưa tải được lịch sử. Bạn vẫn có thể trò chuyện.</p>}
    {state === "expired" && <p role="status" className="px-3 text-xs">Phiên đăng nhập đã hết hạn. <a className="underline" href={sessionLoginHref()}>Đăng nhập lại</a>.</p>}
    {/* Quick prompts are suggestions; selection belongs to conversation links. */}
    <style>{`.campus-chat-history [data-conversation-history] ~ div > button {
      background-color: transparent; font-weight: 400; color: var(--color-text-muted);
    }`}</style>
  </section>;
}
