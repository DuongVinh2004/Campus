"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowUp, Check, MessageCircle, X } from "lucide-react";
import { AccessibleDialog } from "@/components/shared/AccessibleDialog";
import { answerStudentQuestion, receiveMethodLabel, type AssistantReply } from "@/lib/student-assistant";
import type { StudentTask, StudentDraft, CertificateData } from "@/lib/student-workspace";
import { useVinUniForms } from "@/lib/vinuni-workspace";
import { fieldClass, secondaryButton } from "./StudentFlowUI";

interface Exchange { id: string; question: string; reply: AssistantReply; applied?: boolean; error?: string }

const suggestions: Record<StudentTask, string[]> = {
  home: ["Xin giấy xác nhận cần thông tin gì?", "Theo dõi hồ sơ ở đâu?"],
  certificate: ["Mục đích và nơi nhận điền thế nào?", "Đổi sang bản giấy"],
  complaint: ["Khiếu nại cần thông tin gì?", "Theo dõi phản hồi ở đâu?"],
  lookup: ["Xin giấy xác nhận cần thông tin gì?", "Cách nhận bản điện tử?"],
};

export function AssistantDrawer({ task }: { task: StudentTask }) {
  const { state, store } = useVinUniForms();
  const certificate: StudentDraft<CertificateData> = { id: "vinuni-certificate", step: "details", updatedAt: "", data: {
    purpose: state.certificate.values.purpose || "", destinationOrg: state.certificate.values.destinationOrg || "",
    receiveMethod: state.certificate.values.receiveMethod === "paper_stamped" ? "paper_stamped" : "digital_pdf",
  } };
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, [open]);

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ block: "nearest" });
  }, [open, exchanges]);

  function send(question: string) {
    const value = question.trim();
    if (!value) return;
    const reply = answerStudentQuestion(value, task, certificate);
    setExchanges((current) => [...current, { id: crypto.randomUUID(), question: value, reply }]);
    setInput("");
    inputRef.current?.focus();
  }

  function apply(exchange: Exchange) {
    if (!exchange.reply.proposal) return;
    const proposal = exchange.reply.proposal;
    const applied = proposal.draftId === certificate.id && certificate.data[proposal.field] === proposal.before;
    if (applied) store.update("certificate", { [proposal.field]: proposal.value });
    setExchanges((current) => current.map((item) => item.id === exchange.id
                    ? { ...item, applied, error: applied ? undefined : "Không thể áp dụng đề xuất này vì bản nháp đã thay đổi. Hãy hỏi lại sau khi kiểm tra biểu mẫu." }
      : item));
  }

  return <>
    <button type="button" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-expanded={open}
      className="fixed bottom-5 right-4 z-30 inline-flex min-h-12 items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50 sm:bottom-6 sm:right-6 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800">
      <MessageCircle className="h-5 w-5" />Hỏi trợ lý
    </button>
    <AccessibleDialog open={open} onClose={() => setOpen(false)} labelledBy="student-assistant-title"
      className="fixed inset-x-0 bottom-0 flex h-[85dvh] max-h-[900px] flex-col rounded-t-2xl bg-white shadow-xl sm:inset-x-auto sm:bottom-0 sm:right-0 sm:top-0 sm:h-dvh sm:max-h-none sm:w-[420px] sm:rounded-none dark:bg-slate-900">
      <div className="flex shrink-0 items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-700">
        <div>
          <h2 id="student-assistant-title" className="text-base font-semibold">Trợ lý học vụ</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Hỗ trợ bạn hoàn thành tác vụ</p>
          <Link href="/student/assistant" onClick={() => setOpen(false)} className="mt-1 inline-flex min-h-11 items-center text-sm font-medium text-blue-600 dark:text-blue-300">Mở trang chatbot →</Link>
        </div>
        <button type="button" onClick={() => setOpen(false)} aria-label="Đóng trợ lý" className="flex h-11 w-11 items-center justify-center rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800"><X className="h-5 w-5" /></button>
      </div>
      <div className="flex-1 space-y-6 overflow-y-auto overscroll-contain p-5">
        {exchanges.length === 0 && <p className="text-base text-slate-600 dark:text-slate-300">Bạn đang cần hướng dẫn ở bước nào?</p>}
        <div className="flex flex-wrap gap-2" aria-label="Câu hỏi gợi ý">
          {suggestions[task].map((question) => <button key={question} type="button" onClick={() => send(question)}
            className="min-h-11 rounded-xl border border-slate-200 px-3 py-2 text-left text-sm hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800">{question}</button>)}
        </div>
        <div role="log" aria-label="Trao đổi với trợ lý" aria-live="polite" aria-relevant="additions" className="space-y-6">
          {exchanges.map((exchange) => <div key={exchange.id} className="space-y-3">
            <p className="ml-8 rounded-2xl bg-slate-100 px-4 py-3 text-base dark:bg-slate-800"><span className="sr-only">Bạn: </span>{exchange.question}</p>
            <div className="space-y-3 pr-2 text-base leading-relaxed"><p><span className="sr-only">Trợ lý: </span>{exchange.reply.text}</p>
              {exchange.reply.source && <details className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700">
                <summary className="cursor-pointer font-medium">Nguồn hướng dẫn · {exchange.reply.source.section}</summary>
                <p className="mt-3 text-slate-500 dark:text-slate-400">{exchange.reply.source.title}</p>
                <blockquote className="mt-2 border-l-2 border-slate-300 pl-3 dark:border-slate-600">{exchange.reply.source.quote}</blockquote>
                {exchange.reply.source.href && <a href={exchange.reply.source.href} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex min-h-11 items-center text-blue-700 underline dark:text-blue-300">Mở liên kết quy chế học vụ</a>}
              </details>}
              {exchange.reply.proposal && <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
                <p className="text-sm font-semibold">{exchange.reply.proposal.label}</p>
                <dl className="mt-3 space-y-2 text-sm">
                  <div><dt className="text-slate-500 dark:text-slate-400">Hiện tại</dt><dd className="break-words">{receiveMethodLabel(exchange.reply.proposal.before) || "Chưa điền"}</dd></div>
                  <div><dt className="text-slate-500 dark:text-slate-400">Đề xuất</dt><dd className="break-words font-medium">{receiveMethodLabel(exchange.reply.proposal.value)}</dd></div>
                </dl>
                <button type="button" onClick={() => apply(exchange)} disabled={exchange.applied}
                  className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold hover:bg-slate-50 disabled:cursor-default disabled:text-emerald-700 dark:border-slate-600 dark:hover:bg-slate-800 dark:disabled:text-emerald-400">
                  {exchange.applied ? <><Check className="h-4 w-4" />Đã áp dụng</> : "Áp dụng thay đổi"}
                </button>
                {exchange.error && <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">{exchange.error}</p>}
              </div>}
              {exchange.reply.action && <Link href={exchange.reply.action.href} onClick={() => setOpen(false)} className={`${secondaryButton} border border-slate-200 dark:border-slate-700`}>{exchange.reply.action.label}</Link>}
            </div>
          </div>)}
        </div>
        <div ref={endRef} />
      </div>
      <form onSubmit={(event) => { event.preventDefault(); send(input); }} className="shrink-0 border-t border-slate-200 p-4 pb-[max(1rem,env(safe-area-inset-bottom))] dark:border-slate-700">
        <label htmlFor="assistant-question" className="sr-only">Câu hỏi cho trợ lý</label>
        <div className="flex gap-2">
          <input ref={inputRef} id="assistant-question" value={input} onChange={(event) => setInput(event.target.value)} maxLength={2000} placeholder="Nhập câu hỏi của bạn…" className={`${fieldClass} min-w-0 flex-1`} />
          <button type="submit" aria-label="Gửi câu hỏi" disabled={!input.trim()} className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40"><ArrowUp className="h-5 w-5" /></button>
        </div>
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Hướng dẫn theo quy chế học vụ. Kiểm tra thông tin trước khi xác nhận hồ sơ.</p>
      </form>
    </AccessibleDialog>
  </>;
}
