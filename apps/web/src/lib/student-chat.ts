import { lookupStudentGuidance, type AssistantReply } from "./student-assistant";
import { VINUNI_SOURCES } from "./vinuni-forms";
import type { VinUniTask } from "./vinuni-forms";
import type { FormChange } from "./vinuni-form-store";

export interface StudentChatExchange { id: string; question: string; reply: AssistantReply; change?: FormChange; applied?: FormChange; undone?: boolean; error?: string }
export interface StudentChatThread { id: string; title: string; input: string; exchanges: StudentChatExchange[]; contextKey?: string; formTask?: VinUniTask; draftId?: string }
interface ChatSnapshot { threads: StudentChatThread[]; activeId: string; issue: string | null }

export function createStudentChatStore(key: string, legacyKey?: string) {
  const fresh = (): StudentChatThread => ({ id: crypto.randomUUID(), title: "Cuộc trò chuyện mới", input: "", exchanges: [] });
  const first = fresh();
  let snapshot: ChatSnapshot = { threads: [first], activeId: first.id, issue: null };
  let preserveSaved = false;
  try {
    const saved = localStorage.getItem(key) ?? (legacyKey ? localStorage.getItem(legacyKey) : null);
    if (saved) {
      const value = JSON.parse(saved);
      if (![1, 2].includes(value.version) || !Array.isArray(value.threads) || !value.threads.length ||
        !value.threads.every((thread: StudentChatThread) => typeof thread.id === "string" && typeof thread.title === "string" && typeof thread.input === "string" && Array.isArray(thread.exchanges) && thread.exchanges.every((item) => typeof item.id === "string" && typeof item.question === "string" && typeof item.reply?.text === "string" && !item.reply.proposal &&
          (!item.reply.source || (typeof item.reply.source.title === "string" && typeof item.reply.source.section === "string" && typeof item.reply.source.quote === "string" && (!item.reply.source.href || Object.values(VINUNI_SOURCES).includes(item.reply.source.href)))) &&
          (!item.reply.action || (typeof item.reply.action.label === "string" && ["/student/certificate", "/student/complaint", "/my-requests"].includes(item.reply.action.href))) &&
          (!item.change || validChange(item.change)) && (!item.applied || validChange(item.applied)))) ||
        !value.threads.every((thread: StudentChatThread) => (!thread.formTask || ["certificate", "complaint"].includes(thread.formTask)) && (!thread.draftId || typeof thread.draftId === "string") && (!thread.contextKey || typeof thread.contextKey === "string"))) throw new Error("Invalid history");
      snapshot = { threads: value.threads, activeId: value.threads.some((thread: StudentChatThread) => thread.id === value.activeId) ? value.activeId : value.threads[0].id, issue: null };
    }
  } catch {
    preserveSaved = true;
    snapshot.issue = "Không đọc được lịch sử đã lưu. Dữ liệu cũ được giữ nguyên; cuộc trò chuyện mới chỉ lưu trong phiên này.";
  }
  const listeners = new Set<() => void>();
  function update(next: ChatSnapshot) {
    snapshot = next;
    if (!preserveSaved) {
      try { localStorage.setItem(key, JSON.stringify({ version: 2, threads: next.threads, activeId: next.activeId })); snapshot = { ...next, issue: null }; }
      catch { snapshot = { ...next, issue: "Chưa lưu được hội thoại trên thiết bị. Hãy giữ trang này mở để tiếp tục." }; }
    }
    listeners.forEach((listener) => listener());
  }
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    select(id: string) { if (snapshot.threads.some((thread) => thread.id === id)) update({ ...snapshot, activeId: id }); },
    start() { const thread = fresh(); update({ ...snapshot, threads: [thread, ...snapshot.threads], activeId: thread.id }); },
    context(contextKey: string, title: string, formTask?: VinUniTask, draftId?: string) {
      const existing = snapshot.threads.find(thread => thread.contextKey === contextKey);
      if (existing) { if (existing.id !== snapshot.activeId) update({ ...snapshot, activeId: existing.id }); return; }
      const thread = { ...fresh(), title, contextKey, formTask, draftId };
      update({ ...snapshot, threads: [thread, ...snapshot.threads], activeId: thread.id });
    },
    bindForm(formTask: VinUniTask, draftId: string) {
      const active = snapshot.threads.find(thread => thread.id === snapshot.activeId)!;
      // Preserve an existing task's conversation when switching to another draft.
      if (active.draftId && active.draftId !== draftId) { this.context(`draft:${draftId}`, formTask === "certificate" ? "Yêu cầu tài liệu" : "Khiếu nại điểm học phần", formTask, draftId); return; }
      update({ ...snapshot, threads: snapshot.threads.map(thread => thread.id === snapshot.activeId ? { ...thread, formTask, draftId, contextKey: `draft:${draftId}` } : thread) });
    },
    exchange(id: string, fields: Partial<Pick<StudentChatExchange, "applied" | "undone" | "error">>) {
      update({ ...snapshot, threads: snapshot.threads.map(thread => ({ ...thread, exchanges: thread.exchanges.map(item => item.id === id ? { ...item, ...fields } : item) })) });
    },
    input(value: string) { update({ ...snapshot, threads: snapshot.threads.map((thread) => thread.id === snapshot.activeId ? { ...thread, input: value } : thread) }); },
    send(question: string, answer?: AssistantReply, change?: FormChange, threadId = snapshot.activeId) {
      const value = question.trim();
      if (!value) return;
      const reply = answer ?? (/^(xin chào|chào|hello|hi)[!.\s]*$/i.test(value)
        ? { text: "Chào bạn! Tôi có thể hướng dẫn xin giấy xác nhận, tra cứu hướng dẫn dịch vụ, khiếu nại điểm thi và theo dõi hồ sơ. Bạn muốn bắt đầu từ việc nào?" }
        : lookupStudentGuidance(value));
      update({ ...snapshot, threads: snapshot.threads.map((thread) => thread.id === threadId ? {
        ...thread, title: thread.exchanges.length ? thread.title : value.slice(0, 64), input: "",
        exchanges: [...thread.exchanges, { id: crypto.randomUUID(), question: value, reply, change }],
      } : thread) });
    },
  };
}

function validChange(change: FormChange) {
  return ["certificate", "complaint"].includes(change.task) && typeof change.draftId === "string" && Number.isSafeInteger(change.revision) && change.revision >= 0 && typeof change.label === "string" &&
    [change.before, change.after].every(values => values && typeof values === "object" && !Array.isArray(values) && Object.values(values).every(value => typeof value === "string" && value.length <= 4000));
}
