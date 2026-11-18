"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { ArrowUp, FileText, Sparkles } from "lucide-react";
import { useAssistant } from "@/lib/assistant-context";
import { useVinUniForms } from "@/lib/vinuni-workspace";
import { validateForm } from "@/lib/vinuni-forms";
import { receiveMethodLabel } from "@/lib/student-assistant";
import { secondaryButton } from "./StudentFlowUI";
import { UnifiedAssistantWorkspace } from "@/features/assistance/UnifiedAssistantWorkspace";
import { AssistantContent } from "@/features/chat/ChatPanel";

export function AssistantConversation({ compact = false }: { compact?: boolean }) {
  return process.env.NEXT_PUBLIC_UNIFIED_AI === "true" ? <UnifiedAssistantWorkspace compact={compact} /> : <ExistingAssistantConversation compact={compact} />;
}

function ExistingAssistantConversation({ compact = false }: { compact?: boolean }) {
  const assistant = useAssistant();
  const { active, chat, context, task, pending, error } = assistant;
  const { state: forms, store } = useVinUniForms();
  const draft = task ? forms[task] : undefined;
  const scrollRef = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const follow = useRef(true);
  useEffect(() => {
    if (assistant.composerFocus > 0 && composer.current?.getClientRects().length) composer.current.focus();
  }, [assistant.composerFocus]);
  useEffect(() => {
    if (follow.current && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [active.id, active.exchanges.length, pending]);
  const suggestions = draft?.stage === 2 ? ["Tôi còn thiếu thông tin gì?"] : task === "certificate" ? draft?.stage === 1 ? ["PDF và bản giấy khác nhau thế nào?", "Đổi sang bản giấy"] : ["Xin giấy xác nhận cần thông tin gì?", "Mục đích sử dụng cần điền gì?"]
    : task === "complaint" ? draft?.stage === 1 ? ["Tôi cần chuẩn bị minh chứng gì?"] : ["Khiếu nại cần thông tin gì?"]
      : context.requestCode ? ["Giải thích trạng thái hồ sơ", "Tôi cần bổ sung gì?"] : ["Xin giấy xác nhận cần thông tin gì?", "Khiếu nại điểm thi thế nào?"];
  function send(question: string) {
    follow.current = true;
    if (question === "Tôi còn thiếu thông tin gì?" && task && draft) {
      const missing = Object.values(validateForm(task, draft.values, [0, 1], store.getFiles(task)));
      void assistant.send(question, { label: "Kiểm tra hồ sơ", hint: missing.length ? missing.join("\n") : "Các trường bắt buộc đã đầy đủ. Bạn cần kiểm tra nội dung ở bước cuối và xác nhận; trợ lý không xác minh thay nhà trường." });
    } else void assistant.send(question);
    composer.current?.focus();
  }
  return <div className="flex min-h-0 flex-1 flex-col">
    <div className="border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
      Đang hỗ trợ: <span className="font-semibold">{draft ? draft.submission ? "Xem hồ sơ đã lưu" : draft.stage === 2 ? "Kiểm tra thông tin" : draft.stage === 1 ? task === "certificate" ? "Chọn cách nhận" : "Chuẩn bị minh chứng" : task === "certificate" ? "Chọn tài liệu" : "Thông tin học phần" : context.label}</span>
    </div>
    {(assistant.state.issue || error) && <p role="alert" className="border-b border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">{error || assistant.state.issue}</p>}
    <div ref={scrollRef} onScroll={() => { const el = scrollRef.current; if (el) follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100; }} className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5 sm:px-5">
      {!active.exchanges.length && <div className="mx-auto max-w-2xl pb-6">
        <Sparkles className="mb-3 h-7 w-7 text-blue-600" />
        <h2 className={`${compact ? "text-lg" : "text-2xl sm:text-3xl"} font-semibold tracking-tight`}>Bạn cần hỗ trợ gì?</h2>
        <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-300">{context.requestCode ? "Bạn có thể hỏi về trạng thái, yêu cầu bổ sung và phản hồi đang hiển thị của hồ sơ này." : task ? "Hỏi về bước đang làm hoặc chọn Giải thích cạnh trường bạn cần hỗ trợ." : "Hỏi về thủ tục hoặc mở biểu mẫu để điền và kiểm tra cùng trợ lý."}</p>
        {!task && !context.requestCode && <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" onClick={() => assistant.openForm("certificate")} className={`${secondaryButton} border border-slate-300 dark:border-slate-600`}><FileText className="h-4 w-4" />Mở yêu cầu tài liệu</button>
          <button type="button" onClick={() => assistant.openForm("complaint")} className={`${secondaryButton} border border-slate-300 dark:border-slate-600`}>Mở khiếu nại điểm</button>
        </div>}
      </div>}
      <div className="mx-auto mb-5 flex max-w-2xl flex-wrap gap-2" aria-label="Câu hỏi gợi ý">{suggestions.map(question => <button type="button" key={question} disabled={pending} onClick={() => send(question)} className="min-h-11 rounded-xl border border-slate-200 px-3 py-2 text-left text-xs hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800">{question}</button>)}</div>
      <div role="log" aria-label="Trao đổi với trợ lý" aria-live="polite" aria-relevant="additions" className="mx-auto max-w-2xl space-y-7">
        {active.exchanges.map(exchange => <article key={exchange.id} className="space-y-4">
          <div className="flex justify-end"><p className="max-w-[90%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-sm bg-blue-600 px-4 py-3 text-sm leading-relaxed text-white"><span className="sr-only">Bạn: </span>{exchange.question}</p></div>
          <div className="space-y-3 text-sm leading-7"><p className="text-xs font-semibold text-blue-700 dark:text-blue-300">Trợ lý học vụ</p><AssistantContent content={exchange.reply.text} audience="student" />
            {exchange.reply.source && <details className="rounded-xl border border-slate-200 px-3 dark:border-slate-700"><summary className="min-h-11 cursor-pointer py-2 text-xs font-medium">Nguồn hướng dẫn · {exchange.reply.source.section}</summary><p className="text-xs text-slate-500">{exchange.reply.source.title}</p><blockquote className="my-3 border-l-2 border-blue-200 pl-3">{exchange.reply.source.quote}</blockquote>{exchange.reply.source.href && <a href={exchange.reply.source.href} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center text-blue-700 underline dark:text-blue-300">Mở liên kết quy chế học vụ</a>}</details>}
            {exchange.change && <div className="rounded-xl border border-blue-200 bg-blue-50/40 p-4 dark:border-blue-900 dark:bg-blue-950/30">
              <p className="font-semibold">Đề xuất: {exchange.change.label}</p>
              <dl className="mt-3 space-y-2"><div><dt className="text-xs text-slate-500">Hiện tại</dt><dd className="break-words">{receiveMethodLabel(Object.values(exchange.change.before)[0]) || "Chưa điền"}</dd></div><div><dt className="text-xs text-slate-500">Thay bằng</dt><dd className="break-words font-medium">{receiveMethodLabel(Object.values(exchange.change.after)[0])}</dd></div></dl>
              <div className="mt-3 flex flex-wrap gap-2">{!exchange.applied ? <button type="button" onClick={() => assistant.apply(exchange)} className={`${secondaryButton} border border-blue-300 dark:border-blue-700`}>Áp dụng</button> : <><span role="status" className="inline-flex min-h-11 items-center text-emerald-700 dark:text-emerald-300">{exchange.undone ? "Đã hoàn tác" : "Đã áp dụng"}</span>{!exchange.undone && <button type="button" onClick={() => assistant.undo(exchange)} className={secondaryButton}>Hoàn tác</button>}</>}
                <button type="button" onClick={() => assistant.focusField(Object.keys(exchange.change!.after)[0])} className={secondaryButton}>Xem trường</button>
              </div>
              {exchange.error && <p role="alert" className="mt-2 text-red-700 dark:text-red-300">{exchange.error}</p>}
            </div>}
            {exchange.reply.action && (exchange.reply.action.href === "/student/certificate" || exchange.reply.action.href === "/student/complaint"
              ? <button type="button" onClick={() => assistant.openForm(exchange.reply.action!.href.endsWith("certificate") ? "certificate" : "complaint")} className={`${secondaryButton} border border-blue-200 dark:border-blue-800`}>{task === (exchange.reply.action.href.endsWith("certificate") ? "certificate" : "complaint") ? "Tiếp tục hồ sơ" : "Mở biểu mẫu"} · {exchange.reply.action.href.endsWith("certificate") ? "Yêu cầu tài liệu" : "Khiếu nại điểm"}</button>
              : <Link href={exchange.reply.action.href} onClick={() => assistant.setOpen(false)} className={`${secondaryButton} border border-slate-200 dark:border-slate-700`}>{exchange.reply.action.label}</Link>)}
          </div>
        </article>)}
      </div>
      {pending && <p role="status" className="mx-auto mt-5 max-w-2xl text-sm text-slate-500">Đang chuẩn bị phản hồi…</p>}
    </div>
    <footer className="shrink-0 border-t border-slate-200 bg-white px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 dark:border-slate-700 dark:bg-slate-900">
      <form onSubmit={event => { event.preventDefault(); send(active.input); }} className="mx-auto max-w-2xl rounded-xl border border-slate-300 p-3 focus-within:border-blue-500 dark:border-slate-600">
        <label htmlFor={compact ? "assistant-question" : "chatbot-question"} className="sr-only">Câu hỏi cho trợ lý</label>
        <textarea ref={composer} id={compact ? "assistant-question" : "chatbot-question"} value={active.input} onChange={event => chat.input(event.target.value)} maxLength={2000} rows={2} placeholder="Nhập câu hỏi của bạn…" onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!pending) send(active.input); } }} className="min-h-12 w-full resize-none bg-transparent text-sm outline-none" />
        <div className="flex items-center justify-between gap-2"><span className="text-[11px] text-slate-500">Enter để gửi · Shift + Enter xuống dòng</span>{pending ? <button type="button" onClick={assistant.cancel} className={secondaryButton}>Dừng</button> : <button type="submit" disabled={!active.input.trim()} aria-label="Gửi câu hỏi" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white disabled:opacity-40"><ArrowUp className="h-4 w-4" /></button>}</div>
      </form>
      <p className="mx-auto mt-2 max-w-2xl text-xs leading-relaxed text-slate-500">Trợ lý hướng dẫn thủ tục theo quy chế học vụ. Sinh viên kiểm tra thông tin và xác nhận trước khi nộp hồ sơ.</p>
    </footer>
  </div>;
}
