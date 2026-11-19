"use client";

import { createContext, useContext, useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useStore } from "./store";
import { useVinUniForms } from "./vinuni-workspace";
import { createStudentChatStore, type StudentChatExchange } from "./student-chat";
import { guidanceAdapter, isAssistantResult, type AssistantAdapter, type AssistantRequest } from "./assistant-adapter";
import { collectRequests, latestOfficerReply, requestStatusLabel } from "./my-requests";
import type { VinUniTask } from "./vinuni-forms";
import { useOptionalUnifiedAssistant } from "./unified-assistant-runtime";

function subscribeURL(notify: () => void) {
  window.addEventListener("popstate", notify); window.addEventListener("campus-requests-navigation", notify);
  return () => { window.removeEventListener("popstate", notify); window.removeEventListener("campus-requests-navigation", notify); };
}
const readURL = () => window.location.search;
const emptyURL = () => "";

function useAssistantRuntime(adapter: AssistantAdapter) {
  const unified = useOptionalUnifiedAssistant();
  const pathname = usePathname(); const router = useRouter();
  const query = useSyncExternalStore(subscribeURL, readURL, emptyURL);
  const { currentUser, dataConfig, tickets, reviewCases } = useStore();
  const { store: forms, state: formState } = useVinUniForms();
  const [chat] = useState(() => createStudentChatStore(`campus247_chat_ui_v2:${dataConfig?.mode}:${encodeURIComponent(currentUser!.id)}`, `campus247_chat_ui_v1:${dataConfig?.mode}:${encodeURIComponent(currentUser!.id)}`));
  const state = useSyncExternalStore(chat.subscribe, chat.getSnapshot, chat.getSnapshot);
  const active = state.threads.find(thread => thread.id === state.activeId)!;
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"chat" | "form">(active.formTask ? "form" : "chat");
  const [formExpanded, setFormExpanded] = useState(true);
  const [fieldTarget, setFieldTarget] = useState<{ task: VinUniTask; name: string; sequence: number } | null>(null);
  const [pending, setPending] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [composerFocus, setComposerFocus] = useState(0);
  const requests = useRef(new Map<string, AbortController>());
  const isChat = pathname === "/student/assistant";
  const routeTask: VinUniTask | undefined = pathname.includes("certificate") ? "certificate" : pathname.includes("complaint") ? "complaint" : undefined;
  const params = new URLSearchParams(query);
  const conversationRecord = isChat && active.contextKey?.startsWith("request:") ? active.contextKey.split(":") : undefined;
  const selectedId = conversationRecord?.slice(2).join(":") || params.get("review") || params.get("ticket") || (/^\/(?:tickets|reviews)\//.test(pathname) ? pathname.split("/").at(-1) : "");
  const selectedKind = conversationRecord ? conversationRecord[1] : params.has("review") || pathname.startsWith("/reviews/") ? "review" : "ticket";
  const record = collectRequests(tickets, reviewCases, currentUser!.id).find(item => item.id === selectedId && item.kind === selectedKind);
  const supplement = record?.kind === "review" ? [...record.record.supplementRequests].reverse().find(request => request.status === "sent") : undefined;
  const feedback = record ? latestOfficerReply(record) : undefined;
  const task = isChat ? active.formTask : routeTask;
  const context: AssistantRequest["context"] = record
    ? { label: `Hồ sơ ${record.code}`, requestCode: record.code, status: requestStatusLabel(record, dataConfig?.mode === "mock"),
      supplement: supplement ? `Yêu cầu bổ sung đang hiển thị: ${supplement.messageBody.slice(0, 4000)}\nTài liệu được yêu cầu: ${supplement.requestedDocuments.join(", ")}.` : feedback ? `Phản hồi đang hiển thị của cán bộ: ${feedback.slice(0, 4000)}` : undefined }
    : { label: task === "certificate" ? "Yêu cầu tài liệu học vụ" : task === "complaint" ? "Khiếu nại điểm học phần" : pathname === "/my-requests" ? "Danh sách hồ sơ" : "Dịch vụ sinh viên", task };
  const contextKey = record ? `request:${record.kind}:${record.id}` : routeTask ? `draft:${formState[routeTask].id}` : `page:${pathname}`;
  const contextLabel = context.label;
  const routeDraftId = routeTask ? formState[routeTask].id : undefined;

  useEffect(() => () => { requests.current.forEach(controller => controller.abort()); }, []);
  useEffect(() => {
    if (open && !isChat) chat.context(contextKey, contextLabel, routeTask, routeDraftId);
  }, [chat, open, isChat, contextKey, contextLabel, routeTask, routeDraftId]);

  function ensureContext() {
    if (!isChat) chat.context(contextKey, context.label, routeTask, routeTask ? forms.getSnapshot()[routeTask].id : undefined);
  }
  function show() { ensureContext(); setOpen(true); }
  function openForm(formTask: VinUniTask) {
    chat.bindForm(formTask, forms.getSnapshot()[formTask].id);
    setTab("form"); setFormExpanded(true); setError("");
    if (!isChat && routeTask !== formTask) { setOpen(false); router.push(`/student/${formTask}`); }
  }
  function returnToStart() {
    chat.context("page:/student/assistant", "Trợ lý học vụ");
    setTab("chat"); setFormExpanded(true); setError(""); setFieldTarget(null);
    if (!isChat) { setOpen(false); router.push("/student/assistant"); }
  }
  function selectThread(id: string) {
    const thread = state.threads.find(thread => thread.id === id);
    if (thread?.formTask && thread.draftId && !forms.selectDraft(thread.formTask, thread.draftId)) { setError("Chưa thể mở bản nháp này. Hãy chờ yêu cầu đang nộp hoàn tất."); return; }
    chat.select(id); setError(""); setFormExpanded(true); setTab(thread?.formTask ? "form" : "chat");
  }
  async function send(question: string, field?: AssistantRequest["context"]["field"]) {
    if (!question.trim()) return;
    if (unified) {
      if (field) unified.setError("Biểu mẫu này chưa có tham chiếu server đúng phiên bản. Lưu hồ sơ rồi dùng Giải thích tại hồ sơ; dữ liệu đang điền được giữ.");
      else await unified.send(question);
      return;
    }
    ensureContext();
    const threadId = chat.getSnapshot().activeId;
    if (requests.current.has(threadId)) return;
    const controller = new AbortController(); requests.current.set(threadId, controller);
    const draftBefore = task ? forms.getSnapshot()[task] : undefined;
    setPending(previous => [...previous, threadId]); setError("");
    try {
      const result = await adapter.respond({ question: question.trim(), context: { ...context, field } }, controller.signal);
      if (controller.signal.aborted) return;
      if (!isAssistantResult(result)) throw new Error("Invalid assistant response");
      const latest = task ? forms.getSnapshot()[task] : undefined;
      const unchanged = latest?.id === draftBefore?.id && latest?.revision === draftBefore?.revision;
      const change = result.edit && task && unchanged ? forms.propose(task, result.edit.field, result.edit.value) ?? undefined : undefined;
      const reply = result.edit && !change ? { text: "Không thể đề xuất thay đổi cho trường này ở trạng thái hiện tại. Bạn có thể kiểm tra và sửa trực tiếp trong biểu mẫu." } : result.reply;
      chat.send(question, reply, change, threadId);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? "Chưa nhận được phản hồi. Câu hỏi vẫn được giữ; hãy thử gửi lại. Bạn vẫn có thể điền biểu mẫu." : "Trợ lý chưa sẵn sàng. Hãy thử lại.");
    } finally { requests.current.delete(threadId); setPending(previous => previous.filter(id => id !== threadId)); }
  }
  function cancel() { requests.current.get(active.id)?.abort(); }
  function helpField(formTask: VinUniTask, name: string, label: string, hint?: string) {
    if (isChat) { chat.bindForm(formTask, forms.getSnapshot()[formTask].id); setTab("chat"); }
    else show();
    setComposerFocus(previous => previous + 1);
    void send(`Tôi cần điền trường “${label}” thế nào?`, { label, hint });
  }
  function apply(exchange: StudentChatExchange) {
    if (!exchange.change) return;
    const applied = forms.apply(exchange.change);
    chat.exchange(exchange.id, applied ? { applied, error: undefined } : { error: "Bản nháp đã thay đổi hoặc đã nộp. Hãy kiểm tra và yêu cầu đề xuất mới." });
  }
  function undo(exchange: StudentChatExchange) {
    if (!exchange.applied) return;
    const success = forms.undo(exchange.applied);
    chat.exchange(exchange.id, success ? { undone: true, error: undefined } : { error: "Không thể hoàn tác vì bản nháp đã được chỉnh sửa tiếp hoặc đã nộp." });
  }
  function focusField(name: string) {
    if (!task) return;
    const stage = ["receiveMethod", "copies", "recipient", "destinationOrg", "recipientEmail", "delivery", "recipientName", "recipientPhone", "address", "country", "description", "evidenceFiles", "paymentProof", "declaration"].includes(name) ? 1 : 0;
    forms.stage(task, stage); setTab("form"); setFormExpanded(true); setFieldTarget(previous => ({ task, name, sequence: (previous?.sequence ?? 0) + 1 }));
    if (!isChat) setOpen(false);
  }
  return { chat, state, active, open, setOpen, show, isChat, task, context, contextKey, routeTask, tab, setTab, formExpanded, setFormExpanded, fieldTarget,
    pending: pending.includes(active.id), error, send, cancel, openForm, returnToStart, selectThread, apply, undo, focusField, helpField, composerFocus };
}
type Runtime = ReturnType<typeof useAssistantRuntime>;
const Context = createContext<Runtime | null>(null);
export function AssistantProvider({ children, adapter = guidanceAdapter }: { children: ReactNode; adapter?: AssistantAdapter }) {
  const { dataConfig } = useStore();
  const unavailable: AssistantAdapter = { async respond() { throw new Error("API assistant consumer chưa được cấu hình"); } };
  const value = useAssistantRuntime(dataConfig?.mode === "mock" ? adapter : unavailable);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useAssistant() { const value = useContext(Context); if (!value) throw new Error("AssistantProvider required"); return value; }
