"use client";

import { useCallback, useEffect, useRef, useSyncExternalStore } from "react";
import Link from "next/link";
import { MessageCircle, X } from "lucide-react";
import { useAssistant } from "@/lib/assistant-context";
import { AccessibleDialog } from "@/components/shared/AccessibleDialog";
import { AssistantConversation } from "./AssistantConversation";

const subscribe = (notify: () => void) => { const media = window.matchMedia("(min-width: 1024px)"); media.addEventListener("change", notify); return () => media.removeEventListener("change", notify); };
const read = () => window.matchMedia("(min-width: 1024px)").matches;

export function AssistantSurface() {
  const assistant = useAssistant();
  const { setOpen } = assistant;
  const desktop = useSyncExternalStore(subscribe, read, () => false);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  const close = useCallback(() => { setOpen(false); requestAnimationFrame(() => trigger.current?.focus()); }, [setOpen]);
  useEffect(() => {
    if (!assistant.open || !desktop) return;
    panel.current?.querySelector<HTMLElement>("button")?.focus();
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape" && !event.defaultPrevented && !document.querySelector('[role="dialog"][aria-modal="true"]')) { event.preventDefault(); close(); } };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [assistant.open, desktop, close]);
  useEffect(() => {
    if (!assistant.open || desktop) return;
    const previous = document.body.style.overflow; document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [assistant.open, desktop]);
  const contents = <>
    <header className="flex shrink-0 items-start justify-between gap-2 border-b border-slate-200 px-4 py-3 dark:border-slate-700">
      <button type="button" onClick={close} aria-label="Quay lại tác vụ và đóng trợ lý" className="order-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"><X className="h-5 w-5" /></button>
      <div className="order-1"><h2 id="context-assistant-title" className="font-semibold">Trợ lý học vụ</h2><Link href="/student/assistant" onClick={() => assistant.setOpen(false)} className="inline-flex min-h-11 items-center text-xs font-medium text-blue-700 dark:text-blue-300">Tiếp tục trong trang chatbot →</Link></div>
    </header><AssistantConversation compact />
  </>;
  return <>
    <button ref={trigger} type="button" onClick={assistant.show} aria-expanded={assistant.open} aria-controls="context-assistant" className={`${assistant.open ? "sr-only" : "fixed bottom-4 right-4 z-30"} inline-flex min-h-12 items-center gap-2 rounded-full border border-blue-200 bg-white px-4 py-3 text-sm font-semibold text-blue-700 shadow-lg dark:border-blue-800 dark:bg-slate-900 dark:text-blue-300`}><MessageCircle className="h-5 w-5" />Hỏi trợ lý</button>
    {desktop ? assistant.open && <aside id="context-assistant" ref={panel} aria-labelledby="context-assistant-title" className="fixed bottom-0 right-0 top-0 z-40 flex w-[380px] flex-col border-l border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">{contents}</aside>
      : <AccessibleDialog open={assistant.open} onClose={close} labelledBy="context-assistant-title" className="fixed inset-0 flex min-h-0 flex-col bg-white dark:bg-slate-900"><div id="context-assistant" className="flex min-h-0 flex-1 flex-col">{contents}</div></AccessibleDialog>}
  </>;
}
