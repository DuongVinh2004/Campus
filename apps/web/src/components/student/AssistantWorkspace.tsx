"use client";

import { useRef, useState } from "react";
import { ArrowLeft, History, MessageCircle, Plus, X } from "lucide-react";
import { useAssistant } from "@/lib/assistant-context";
import { useVinUniForms } from "@/lib/vinuni-workspace";
import { AccessibleDialog } from "@/components/shared/AccessibleDialog";
import { AssistantConversation } from "./AssistantConversation";
import { VinUniForm } from "./VinUniForm";
import { UnifiedAssistantWorkspace } from "@/features/assistance/UnifiedAssistantWorkspace";

export function AssistantWorkspace() {
  return <ExistingAssistantWorkspace />;
}

function ExistingAssistantWorkspace() {
  const assistant = useAssistant();
  const { state: forms } = useVinUniForms();
  const [historyOpen, setHistoryOpen] = useState(false);
  const [readMessages, setReadMessages] = useState(0);
  const [supportExpanded, setSupportExpanded] = useState(true);
  const chatTab = useRef<HTMLButtonElement>(null);
  const formTab = useRef<HTMLButtonElement>(null);
  const task = assistant.active.formTask;
  const hasForm = Boolean(task);
  // A task remains mounted under mobile tabs so file selection and errors survive.
  const showForm = hasForm && assistant.formExpanded;
  const showSupport = supportExpanded || assistant.tab === "chat";
  const unread = assistant.tab === "form" && assistant.active.exchanges.length > readMessages;
  function choose(tab: "chat" | "form") { assistant.setTab(tab); setReadMessages(assistant.active.exchanges.length); }
  const history = process.env.NEXT_PUBLIC_UNIFIED_AI === "true" ? <p className="text-sm">Dùng lịch sử theo tài khoản trong khung hội thoại chung. Biểu mẫu và nội dung đang điền vẫn được giữ.</p> : <>
    <button type="button" onClick={() => { assistant.chat.start(); assistant.setTab("chat"); assistant.setFormExpanded(true); setHistoryOpen(false); }} className="mb-5 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white"><Plus className="h-4 w-4" />Trò chuyện mới</button>
    <nav aria-label="Lịch sử hội thoại" className="flex-1 space-y-2 overflow-y-auto">{assistant.state.threads.map(thread => <button type="button" key={thread.id} aria-current={thread.id === assistant.active.id ? "true" : undefined} onClick={() => { assistant.selectThread(thread.id); setHistoryOpen(false); }} className={`flex min-h-11 w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm ${thread.id === assistant.active.id ? "bg-blue-50 font-semibold text-blue-800 dark:bg-blue-950 dark:text-blue-200" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`}><MessageCircle className="h-4 w-4 shrink-0" /><span className="min-w-0 break-words">{thread.title}{thread.formTask && <span className="mt-1 block text-xs font-normal text-slate-500">Có biểu mẫu</span>}</span></button>)}</nav>
    <p className="mt-4 text-xs text-slate-500">Hội thoại và bản nháp được đồng bộ bảo mật theo phiên làm việc.</p>
  </>;
  return <div className="flex h-[calc(100dvh-64px)] min-h-0 flex-col overflow-hidden bg-white dark:bg-slate-900">
    <header className="flex min-h-14 shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-1 dark:border-slate-700">
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
        {hasForm && <button type="button" onClick={assistant.returnToStart} className="inline-flex min-h-11 items-center gap-2 rounded-lg px-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"><ArrowLeft className="h-4 w-4" />Trở về</button>}
        <div className="min-w-0"><h1 className="font-semibold">{showForm ? task === "certificate" ? "Yêu cầu cấp giấy tờ học vụ" : "Khiếu nại điểm học phần" : "Trợ lý học vụ"}</h1>{(!showForm || forms[task!].submission) && <p className="text-xs text-slate-600 dark:text-slate-400">{showForm ? `Mã hồ sơ: ${forms[task!].submission!.ticketCode}` : "Hướng dẫn thủ tục và hỗ trợ điền hồ sơ"}</p>}</div>
      </div>
      <div className="flex items-center gap-1"><button type="button" onClick={() => setHistoryOpen(true)} aria-label="Mở lịch sử hội thoại" className="flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"><History className="h-4 w-4" /><span className="hidden sm:inline">Cuộc trò chuyện</span></button>
        {showForm && <button type="button" aria-expanded={showSupport} aria-controls="workspace-chat" onClick={() => { setSupportExpanded(!showSupport); choose("form"); }} className="hidden min-h-11 items-center gap-2 rounded-lg px-3 text-sm text-blue-700 lg:flex dark:text-blue-300"><MessageCircle className="h-4 w-4" />{showSupport ? "Thu gọn trợ lý" : "Hỏi trợ lý"}</button>}
        {hasForm && !showForm && <button type="button" onClick={() => { assistant.setFormExpanded(true); choose("form"); }} className="min-h-11 rounded-lg px-3 text-sm text-blue-700 dark:text-blue-300">Tiếp tục hồ sơ</button>}
      </div>
    </header>
    {showForm && <div role="tablist" aria-label="Chọn vùng làm việc" className="flex shrink-0 border-b border-slate-200 px-4 lg:hidden dark:border-slate-700">
      {(["chat", "form"] as const).map(tab => <button key={tab} ref={tab === "chat" ? chatTab : formTab} id={`workspace-${tab}-tab`} role="tab" aria-selected={assistant.tab === tab} aria-controls={`workspace-${tab}`} tabIndex={assistant.tab === tab ? 0 : -1} onClick={() => choose(tab)} onKeyDown={event => { if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) { event.preventDefault(); const next = event.key === "Home" ? "chat" : event.key === "End" ? "form" : tab === "chat" ? "form" : "chat"; choose(next); (next === "chat" ? chatTab : formTab).current?.focus(); } }} className={`min-h-12 flex-1 border-b-2 px-3 text-sm font-semibold ${assistant.tab === tab ? "border-blue-600 text-blue-700 dark:text-blue-300" : "border-transparent text-slate-500"}`}>{tab === "chat" ? `Hội thoại${unread ? " · Có phản hồi" : ""}` : "Biểu mẫu"}</button>)}
    </div>}
    <div className={`grid min-h-0 flex-1 ${showForm && showSupport ? "lg:grid-cols-[minmax(0,1fr)_380px]" : "grid-cols-1"}`}>
      <section id="workspace-chat" aria-label="Hội thoại với trợ lý" className={`${showForm ? assistant.tab === "form" ? showSupport ? "hidden lg:flex" : "hidden" : "flex" : "flex"} order-2 min-h-0 min-w-0 flex-col border-slate-200 lg:border-l dark:border-slate-700`}>
        {showForm && <div className="flex min-h-14 shrink-0 items-center justify-between border-b border-slate-200 px-4 dark:border-slate-700"><h2 className="text-sm font-semibold">Trợ lý học vụ</h2><button type="button" onClick={() => choose("form")} className="min-h-11 rounded-lg px-3 text-sm text-blue-700 lg:hidden dark:text-blue-300">Trở lại biểu mẫu</button></div>}
        <AssistantConversation compact={showForm} />
      </section>
      {hasForm && <section id="workspace-form" aria-label="Biểu mẫu đang làm" className={`${!showForm ? "hidden" : assistant.tab === "chat" ? "hidden lg:block" : "block"} order-1 min-h-0 min-w-0 overflow-y-auto overscroll-contain bg-slate-50 p-4 sm:p-6 dark:bg-slate-950`}>
        {task && <VinUniForm key={forms[task].id} task={task} embedded />}
      </section>}
    </div>
    <AccessibleDialog open={historyOpen} onClose={() => setHistoryOpen(false)} labelledBy="assistant-history-title" className="fixed inset-y-0 left-0 flex w-[min(340px,90vw)] flex-col bg-white p-4 dark:bg-slate-950"><div className="mb-4 flex items-center justify-between"><h2 id="assistant-history-title" className="font-semibold">Lịch sử hội thoại</h2><button type="button" onClick={() => setHistoryOpen(false)} aria-label="Đóng lịch sử" className="flex h-11 w-11 items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"><X className="h-5 w-5" /></button></div>{history}</AccessibleDialog>
  </div>;
}
