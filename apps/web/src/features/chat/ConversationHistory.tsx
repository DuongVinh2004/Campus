"use client";

import { useT } from "@/lib/i18n";
import React, { useEffect, useRef, useState } from "react";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { sessionLoginHref } from "./local-session";

interface ConversationSummary { id: string; title: string }
const UUID7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export function ConversationHistory({ activeId, revision, onSelect }: { activeId: string | null; revision: number; onSelect?: (id: string) => void }) {
  const t = useT();
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [state, setState] = useState<"loading" | "success" | "error" | "expired" | "forbidden">("loading");
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState(false);
  const loadMore = useRef<() => void>(() => {});
  useEffect(() => {
    let active = true;
    let loading = false;
    let controller: AbortController | null = null;
    let timeout: number | undefined;
    let cursor: string | null = null;
    const seenCursors = new Set<string>();
    const seenIds = new Set<string>();
    setItems([]); setState("loading");
    setNextCursor(null); setLoadingMore(false); setMoreError(false);
    async function load(append: boolean) {
      if (!active || loading || (append && !cursor)) return;
      loading = true;
      controller = new AbortController();
      timeout = window.setTimeout(() => controller?.abort(), 10000);
      setMoreError(false);
      if (append) setLoadingMore(true);
      try {
        const response = await fetch(`${CAMPUS_API_BASE_URL}/v1/assistant/conversations?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, {
          credentials: "include", cache: "no-store", signal: controller.signal,
        });
        if (!active) return;
        if (response.status === 401 || response.status === 403) {
          setItems([]); setNextCursor(null);
          setState(response.status === 401 ? "expired" : "forbidden"); return;
        }
        if (!response.ok) throw new Error();
        const value = await response.json();
        if (!Array.isArray(value?.items) || value.items.length > 20 || !value.items.every((item: ConversationSummary) =>
          item && UUID7.test(item.id) && typeof item.title === "string" && item.title.length <= 2000)
          || new Set(value.items.map((item: ConversationSummary) => item.id)).size !== value.items.length) throw new Error();
        const next = value.page?.has_more === true ? value.page.next_cursor : null;
        if (next !== null && (typeof next !== "string" || !next || next.length > 1000 || seenCursors.has(next))) throw new Error();
        if (value.items.some((item: ConversationSummary) => seenIds.has(item.id))) throw new Error();
        if (active && !controller.signal.aborted) {
          for (const item of value.items) seenIds.add(item.id);
          if (next) seenCursors.add(next);
          cursor = next;
          setItems(previous => append ? [...previous, ...value.items] : value.items);
          setNextCursor(next); setState("success");
        }
      } catch {
        if (active) {
          if (append) setMoreError(true);
          else { setItems([]); setState("error"); }
        }
      } finally {
        window.clearTimeout(timeout); loading = false;
        if (active) setLoadingMore(false);
      }
    }
    loadMore.current = () => { void load(true); };
    void load(false);
    return () => { active = false; controller?.abort(); window.clearTimeout(timeout); };
  }, [revision]);

  return <section data-conversation-history className="mb-4 min-w-0">
    <h2 className="mb-1 px-3 text-xs font-semibold text-slate-500 dark:text-slate-400">{t("c3ConversationHistory.7")}</h2>
    <nav aria-label={t("c3ConversationHistory.8")} className="space-y-1">
      {items.map(item => <a key={item.id} href={`/chat?conversation_id=${encodeURIComponent(item.id)}`}
        onClick={event => {
          if (!onSelect || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
          event.preventDefault(); onSelect(item.id);
        }}
        aria-current={item.id === activeId ? "page" : undefined}
        className={`block min-h-11 break-words rounded-xl px-3 py-2 text-sm ${item.id === activeId
          ? "bg-slate-200/70 font-semibold text-slate-900 dark:bg-slate-800 dark:text-slate-100"
          : "text-slate-600 hover:bg-slate-200/50 dark:text-slate-400 dark:hover:bg-slate-800/50"}`}>
        {item.title.trim() || t("c3ConversationHistory.9")}
      </a>)}
    </nav>
    {state === "loading" && <p role="status" className="px-3 text-xs">{t("c3ConversationHistory.10")}</p>}
    {state === "success" && !items.length && <p className="px-3 text-xs">{t("c3ConversationHistory.11")}</p>}
    {state === "error" && <p role="status" className="px-3 text-xs">{t("c3ConversationHistory.12")}</p>}
    {state === "forbidden" && <p role="status" className="px-3 text-xs">{t("c3ConversationHistory.13")}</p>}
    {state === "expired" && <p role="status" className="px-3 text-xs">{t("sess.1")} <a className="underline" href={sessionLoginHref()}>{t("sess.2")}</a>.</p>}
    {moreError && <p role="status" className="px-3 text-xs">{t("c3ConversationHistory.14")}</p>}
    {nextCursor && <button type="button" disabled={loadingMore} onClick={() => loadMore.current()}
      className="min-h-11 rounded-xl px-3 py-2 text-sm underline">{loadingMore ? t("c3ConversationHistory.15") : t("c3ConversationHistory.16")}</button>}
    {/* Quick prompts are suggestions; selection belongs to conversation links. */}
    <style>{`.campus-chat-history [data-conversation-history] ~ div > button {
      background-color: transparent; font-weight: 400; color: var(--color-text-muted);
    }`}</style>
  </section>;
}
