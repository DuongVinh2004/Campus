"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { useStore } from "./store";
import { AssistantStateService, assistantClientId, type AssistantCapabilities, type ConversationSummary, type SurfaceContext, type ResourceRunMetadata } from "./assistant-state-service";
import { ApiClient, ApiClientError } from "./api/client";
import { ChatStream, SseParser, type StreamCitation, type StreamSnapshot } from "@/features/chat/sse";
import { decodeHistoryPage } from "@/features/chat/history";
import type { ChatMessage } from "@/features/chat/ChatPanel";
import type { CoordinationRun } from "./unified-ai-contracts";
import type { StudentPreparationState } from "./student-preparation";

const base = CAMPUS_API_BASE_URL;
const service = new AssistantStateService();
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
interface Actor { user_id: string; roles: string[]; display_name?: string; student_code?: string; is_synthetic?: boolean }
interface TurnReceipt { client_id: string; state: "pending" | "interrupted" | "completed"; assistant_message_id: string | null }
interface Session {
  mode?: "persistent" | "temporary";
  studentPreparation?: StudentPreparationState;
  localId: string; id: string | null; input: string; messages: ChatMessage[]; citations: Record<string, StreamCitation[]>;
  summary?: ConversationSummary; cursor: string | null; sequence: number; loaded: boolean;
  saveState: "local" | "pending" | "saved" | "error" | "interrupted"; receipt?: TurnReceipt; turnId?: string;
  uncertain?: boolean; pendingText?: string;
  waitingRunId?: string;
  runId?: string; run?: CoordinationRun;
  resourceRequest?: string; resourceOperationId?: string; resourceWork?: ResourceRunMetadata;
}
const fresh = (): Session => ({ localId: assistantClientId(), id: null, input: "", messages: [], citations: {}, cursor: null, sequence: 0, loaded: true, saveState: "local" });
// Retain unsaved text during account switches, and reveal it only after the
// same server tenant/actor/role has been authenticated again. No token stored.
const retained = new Map<string, { sessions: Session[]; activeKey: string }>();

function useRuntime() {
  const { dataConfig } = useStore();
  const pathname = usePathname();
  const [actor, setActor] = useState<Actor | null>(null);
  const [capabilities, setCapabilities] = useState<AssistantCapabilities | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeKey, setActiveKey] = useState("");
  const [catalog, setCatalog] = useState<ConversationSummary[]>([]);
  const [catalogCursor, setCatalogCursor] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [archived, setArchived] = useState(false);
  const [error, setError] = useState("");
  const [authenticationRequired, setAuthenticationRequired] = useState(false);
  const [bootAttempt, setBootAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [surface, setSurface] = useState<SurfaceContext>({ surface: "chat" });
  const sessionValid = useRef(true);
  const identity = useRef<Actor | null>(null);
  const alive = useRef(true);
  const activeRef = useRef<Session | undefined>(undefined);
  const work = useRef<AbortController | null>(null);
  const catalogEpoch = useRef(0);
  const retainedKey = useRef("");
  const active = sessions.find(item => item.localId === activeKey);
  activeRef.current = active;
  if (retainedKey.current && activeKey) retained.set(retainedKey.current, { sessions, activeKey });

  function current() { return alive.current && sessionValid.current; }
  function update(key: string, apply: (item: Session) => Session) {
    if (current()) setSessions(previous => previous.map(item => item.localId === key ? apply(item) : item));
  }
  async function guard() {
    if (!current() || !identity.current) {
      work.current?.abort(); setActor(null); setCapabilities(null); setCatalog([]); setActiveKey("");
      throw new Error("Phiên tài khoản đã thay đổi; nội dung soạn được giữ theo tài khoản cũ.");
    }
    let value: Actor;
    try { value = await new ApiClient({ baseUrl: base }).get<Actor>("/v1/users/me"); }
    catch (failure) {
      if (failure instanceof ApiClientError && failure.problem.status === 401) {
        sessionValid.current = false;
        work.current?.abort(); setAuthenticationRequired(true); setActor(null); setCapabilities(null);
        setCatalog([]); setActiveKey("");
      }
      throw failure;
    }
    if (!current() || !Array.isArray(value.roles) || value.user_id !== identity.current.user_id || JSON.stringify([...value.roles].sort()) !== JSON.stringify([...identity.current.roles].sort())) {
      sessionValid.current = false;
      work.current?.abort(); setActor(null); setCapabilities(null); setCatalog([]); setActiveKey("");
      throw new Error("Vai trò hoặc tài khoản đã thay đổi; nội dung đang soạn được giữ trong phiên cũ.");
    }
    return value;
  }
  async function refreshCatalog(title = query, onlyArchived = archived, cursor = "") {
    const epoch = ++catalogEpoch.current;
    try {
      await guard();
      const page = await service.conversations(title, cursor, onlyArchived);
      if (!current() || epoch !== catalogEpoch.current) return;
      if (!Array.isArray(page.items) || page.items.some(item => !uuid.test(item.id) || item.audience !== "student")) throw new Error("Danh sách hội thoại không hợp lệ");
      setCatalog(previous => cursor ? [...previous.filter(item => !page.items.some(row => row.id === item.id)), ...page.items] : page.items);
      setCatalogCursor(page.page.next_cursor); setError("");
    } catch (failure) { if (current() && epoch === catalogEpoch.current) setError(failure instanceof Error ? failure.message : "Chưa đọc được lịch sử."); }
  }
  useEffect(() => {
    alive.current = true;
    sessionValid.current = true;
    const controller = new AbortController();
    async function boot() {
      try {
        setError(""); setAuthenticationRequired(false);
        const value = await new ApiClient({ baseUrl: base }).get<Actor>("/v1/users/me");
        if (!current() || controller.signal.aborted) return;
        if (!uuid.test(value.user_id) || !Array.isArray(value.roles)) throw new Error("Danh tính server không hợp lệ");
        identity.current = value; setActor(value);
        const caps = await service.consumerCapabilities();
        if (!current() || controller.signal.aborted) return;
        if (!["student", "staff"].includes(caps.audience)) throw new Error("Capability không hợp lệ");
        setCapabilities(caps);
        retainedKey.current = `${base}:${dataConfig?.mode}:${caps.tenant_id}:${value.user_id}:${[...value.roles].sort().join(",")}`;
        const existing = retained.get(retainedKey.current);
        const session = fresh(); setSessions(existing?.sessions.length ? existing.sessions : [session]); setActiveKey(existing?.activeKey || session.localId);
        if (caps.history) await refreshCatalog("", false);
      } catch (failure) { if (alive.current && !controller.signal.aborted) {
        setAuthenticationRequired(failure instanceof ApiClientError && failure.problem.status === 401);
        setError(failure instanceof Error ? failure.message : "Trợ lý chưa sẵn sàng.");
      } }
    }
    void boot();
    return () => { alive.current = false; controller.abort(); work.current?.abort(); };
    // Provider is keyed by account/mode/role and every operation revalidates identity.
  }, [bootAttempt]);
  useEffect(() => { setSurface({ surface: pathname === "/privacy" ? "settings" : pathname.startsWith("/student") ? "student_home" : pathname.startsWith("/reviews") || pathname.startsWith("/tickets") ? "staff_queue" : "chat" }); }, [pathname]);
  useEffect(() => {
    const changed = () => { if (identity.current) void guard().catch(failure => setError(failure.message)); };
    window.addEventListener("focus", changed); return () => window.removeEventListener("focus", changed);
  }, []);

  function rememberConversation(id: string | null) {
    if (pathname !== "/chat") return;
    const url = new URL(window.location.href);
    url.searchParams.delete("q");
    if (id) url.searchParams.set("conversation_id", id); else url.searchParams.delete("conversation_id");
    window.history.replaceState(window.history.state, "", url);
  }
  function createChat(mode: "persistent" | "temporary") {
    if (busy) return;
    const value = { ...fresh(), mode }; setSessions(previous => [...previous, value]); setActiveKey(value.localId); setError("");
    rememberConversation(null);
  }
  function newChat() { createChat("persistent"); }
  function temporaryChat() { if (capabilities?.temporary_chat) createChat("temporary"); }
  async function restore(key: string, id: string, append = false) {
    if (work.current) return;
    const controller = new AbortController(); work.current = controller; setBusy(true); setError("");
    try {
      await guard();
      const summary = await service.conversation(id);
      update(key, item => ({ ...item, mode: summary.mode || undefined }));
      const old = activeRef.current;
      const cursor = append && old?.localId === key ? old.cursor : null;
      const after = append && old?.localId === key ? old.sequence : 0;
      const response = await fetch(`${base}/v1/conversations/${encodeURIComponent(id)}/messages?limit=50${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, { credentials: "include", cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error("Chưa đọc được messages; lịch sử và nội dung đang soạn được giữ.");
      const page = decodeHistoryPage(await response.json(), id, after);
      const sets: Record<string, StreamCitation[]> = {};
      const messages = page.messages.map(message => {
        sets[message.id] = message.final?.citations || [];
        return { id: message.id, role: message.role, content: message.content,
          ...(message.role === "assistant" ? { status: !message.final ? "unknown" : message.final.phase === "abstained" ? "abstained" : message.final.phase === "failed" ? "failed" : "success",
            responseClass: message.final?.responseClass, citations: sets[message.id].map(c => ({ id: c.citation.citation_id, title: c.citation.source_title, index: Number(c.turn_citation_id.slice(4)) })) } : {}) } as ChatMessage;
      });
      if (!current() || controller.signal.aborted) return;
      update(key, item => ({ ...item, id, summary, messages: append ? [...item.messages, ...messages.filter(m => !item.messages.some(old => old.id === m.id))] : item.uncertain ? [...messages, ...item.messages.filter(m => !messages.some(saved => saved.id === m.id))] : messages,
        citations: append || item.uncertain ? { ...item.citations, ...sets } : sets, cursor: page.nextCursor, sequence: page.messages.at(-1)?.sequence ?? after,
        waitingRunId: !page.nextCursor && page.messages.at(-1)?.final?.responseClass === "clarification_request" ? page.messages.at(-1)?.final?.runId : undefined,
        runId: page.messages.at(-1)?.final?.runId || item.runId,
        loaded: true, saveState: item.uncertain ? item.saveState : "saved" }));
    } catch (failure) { if (current()) { setError(failure instanceof Error ? failure.message : "Khôi phục bị gián đoạn; trang đã đọc được giữ."); update(key, item => ({ ...item, saveState: "error" })); } }
    finally { if (work.current === controller) { work.current = null; if (alive.current) setBusy(false); } }
  }
  async function select(id: string) {
    if (busy) return;
    const existing = sessions.find(item => item.id === id);
    const value = existing || { ...fresh(), id, loaded: false };
    if (!existing) setSessions(previous => [...previous, value]);
    setActiveKey(value.localId);
    await restore(value.localId, id);
    if (current()) rememberConversation(id);
  }
  function snapshot(key: string, value: StreamSnapshot) {
    update(key, session => ({ ...session, messages: [...session.messages.filter(m => m.id !== value.messageId), {
      id: value.messageId || "provisional", role: "assistant", content: value.text, responseClass: value.responseClass,
      status: value.phase === "completed" ? "success" : value.phase === "abstained" ? "abstained" : value.phase === "failed" ? "failed" : "streaming",
      agentProgress: value.agentProgress,
      citations: value.citations.map(c => ({ id: c.citation.citation_id, title: c.citation.source_title, index: Number(c.turn_citation_id.slice(4)) })),
    }], waitingRunId: value.responseClass === "clarification_request" ? value.runId : value.phase === "streaming" ? session.waitingRunId : undefined,
      runId: value.runId || session.runId,
      citations: { ...session.citations, [value.messageId || "provisional"]: value.citations } }));
  }
  async function send(content: string, selectedSurface = surface) {
    const session = activeRef.current;
    if (!session || work.current || !content.trim() || !capabilities) return;
    if (!selectedSurface.resource && ["/schedule", "/rooms"].includes(pathname)) {
      setError("Chức năng cá nhân trên trang này chưa kết nối. Mở Hỏi đáp để tra nguồn công khai hoặc Hỗ trợ để chuẩn bị yêu cầu; chưa có thao tác lịch/phòng nào được thực hiện.");
      return;
    }
    const controller = new AbortController(); work.current = controller; setBusy(true); setError("");
    const key = session.localId;
    let stream: ChatStream | undefined;
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    try {
      await guard();
      if (capabilities.audience === "staff") {
        const result = await new ApiClient({ baseUrl: base }).post<{ action_authority: string; support: string; guidance: string; status: string }>("/v1/assistant/cases/intent:resolve", {
          resources: selectedSurface.resource ? [selectedSurface.resource] : [],
          surface: selectedSurface.staff_surface || (selectedSurface.resource ? "detail" : selectedSurface.surface === "settings" ? "admin" : "queue"),
          intent: selectedSurface.staff_intent || "read",
        });
        await guard();
        if (!current() || controller.signal.aborted) return;
        if (result.action_authority !== "none") throw new Error("Trợ lý không có quyền thực hiện nghiệp vụ");
        update(key, item => ({ ...item, saveState: "local", messages: [...item.messages,
          { id: assistantClientId(), role: "user", content }, { id: assistantClientId(), role: "assistant", content: result.guidance,
            blocks: [{ type: "status", state: result.support === "supported" ? "completed" : "pending", text: `${result.support} · ${result.status}. Context chỉ dùng reference hồ sơ/action đã chọn; nội dung biểu mẫu riêng không được đọc.` }] }] }));
        return;
      }
      if (selectedSurface.resource) {
        const resource = selectedSurface.resource;
        const resourceRequest = JSON.stringify(selectedSurface);
        const operationId = session.resourceRequest === resourceRequest && session.resourceOperationId ? session.resourceOperationId : assistantClientId();
        if (capabilities.resource_runs === true) update(key, item => ({ ...item, resourceRequest, resourceOperationId: operationId }));
        const result = await service.resolveSurface({ ...selectedSurface, ...(capabilities.resource_runs === true ? { operation_id: operationId } : {}) });
        await guard();
        if (!current() || controller.signal.aborted) return;
        if (result.action_authority !== "none" || result.audience !== capabilities.audience || result.context.resource?.id !== resource.id || result.context.resource.version !== resource.expected_version) throw new Error("Context không khớp hồ sơ đang mở");
        const reply = [result.field_guidance, result.context.guidance].filter(Boolean).join("\n\n");
        update(key, item => ({ ...item, saveState: "local", resourceWork: result.specialist?.run || item.resourceWork, messages: [...item.messages,
          { id: assistantClientId(), role: "user", content }, { id: assistantClientId(), role: "assistant", content: reply,
            blocks: [{ type: "status", state: "completed", text: `Projection hồ sơ ${resource.id}, phiên bản ${resource.expected_version}, đã đọc theo quyền hiện tại; trao đổi này chỉ giữ trong phiên, chưa lưu vào chat model.` },
              ...(result.specialist ? [{ type: "status" as const, state: result.specialist.status === "observed" ? "completed" as const : "pending" as const,
                text: result.specialist.status === "observed" ? "Đã đối chiếu nguồn và mẫu áp dụng; kiểm tra bắt buộc của cán bộ vẫn cần thực hiện." : `Đối chiếu còn thiếu: ${result.specialist.blockers.join(", ")}. Mở nguồn của hồ sơ để kiểm tra.` }] : []),
              ...(result.specialist?.run ? [{ type: "status" as const, state: "pending" as const, text: "Checkpoint đối chiếu hồ sơ đã lưu với receipt. Hiệu lực quy định chính thức và các kiểm tra cán bộ còn cần đối chiếu; công việc này không gửi hồ sơ." }] : []),
              ...(result.context.evidence?.length ? [{ type: "table" as const, columns: ["Nguồn", "Phiên bản", "Locator", "Hash"], rows: result.context.evidence.map(item => [item.classification, item.version_id, item.locator, item.sha256]) }] : [])] }] }));
        return;
      }
      if (!capabilities.student_model_chat || capabilities.audience !== "student") throw new Error("Chat model cho cán bộ chưa được cấu hình; dùng đối chiếu hồ sơ có phạm vi.");
      if (!session.loaded || session.cursor || session.summary && !session.summary.can_continue) throw new Error("Đọc hết lịch sử hoặc mở hội thoại mới trước khi tiếp tục.");
      if (session.uncertain) throw new Error("Cần kiểm tra receipt/lịch sử của lượt trước; không tự tạo lại câu trả lời. Có thể mở hội thoại mới, bản soạn cũ được giữ.");
      let id = session.id;
      if (!id) {
        const created = await new ApiClient({ baseUrl: base }).post<{ id: string; mode?: string }>("/v1/conversations", capabilities.stable_create ? { client_id: session.localId, mode: session.mode || "persistent" } : undefined);
        if (!current() || controller.signal.aborted) return;
        if (!uuid.test(created.id)) throw new Error("Conversation ID không hợp lệ");
        if (session.mode === "temporary" && created.mode !== "temporary") throw new Error("Server chưa xác nhận chat tạm thời; chưa gửi nội dung.");
        id = created.id; update(key, item => ({ ...item, id })); rememberConversation(id);
      }
      const clientId = assistantClientId();
      update(key, item => ({ ...item, saveState: "pending", uncertain: true, pendingText: content, input: item.input || content, turnId: capabilities.stable_turns && !session.waitingRunId ? clientId : undefined,
        messages: [...item.messages, { id: clientId, role: "user", content }] }));
      if (session.waitingRunId) {
        if (capabilities.coordination?.resume !== true || capabilities.coordination.profile !== "coordination-checkpoint.v1") throw new Error("Writer đang phục vụ chưa có hợp đồng tiếp tục U3; đọc lịch sử hoặc mở chat mới. Nội dung đang soạn được giữ.");
        const path = `/v1/conversations/${id}/agent-runs/${session.waitingRunId}`;
        const api = new ApiClient({ baseUrl: base });
        const run = await api.get<{ status: string; version: number }>(path);
        if (run.status !== "waiting_user" || !Number.isSafeInteger(run.version) || run.version < 1) throw new Error("Run đang chờ đã đổi; đọc lại lịch sử.");
        const resumed = await api.post<{ run: { id: string }; message: { message_id: string } }>(path+":resume", { expected_version: run.version, content });
        await guard(); if (controller.signal.aborted) return;
        const restored = new ChatStream(id);
        restored.accept({ id: resumed.message.message_id, event: "message.started", data: JSON.stringify({ conversation_id: id, message_id: resumed.message.message_id }) });
        const final = restored.accept({ id: resumed.run.id, event: "message.completed", data: JSON.stringify(resumed.message) });
        snapshot(key, final);
        update(key, item => ({ ...item, saveState: "saved", uncertain: false, pendingText: undefined, input: item.input === content ? "" : item.input }));
        void refreshCatalog(); return;
      }
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      const response = await fetch(`${base}/v1/conversations/${id}/messages:stream`, { method: "POST", credentials: "include", headers, signal: controller.signal,
        body: JSON.stringify({ content, ...(capabilities.stable_turns ? { client_id: clientId } : {}) }) });
      if (!response.ok || !response.body) throw new Error(response.status === 409 ? "Lượt đã được tiếp nhận hoặc state đã đổi; kiểm tra receipt/lịch sử." : "API chưa hoàn tất lượt này; câu hỏi vẫn được giữ.");
      reader = response.body.getReader(); stream = new ChatStream(id, response.headers.get("X-Request-Id") || undefined);
      const parser = new SseParser(), decoder = new TextDecoder("utf-8", { fatal: true });
      function accept(frames: ReturnType<SseParser["push"]>) { for (const frame of frames) { if (stream!.terminal || !current()) break; snapshot(key, stream!.accept(frame)); } }
      while (!stream.terminal) {
        const value = await reader.read();
        if (!current()) return;
        if (value.done) { accept(parser.push(decoder.decode())); accept(parser.finish()); stream.finish(); break; }
        accept(parser.push(decoder.decode(value.value, { stream: true })));
      }
      const final = stream.snapshot;
      if (!["completed", "abstained"].includes(final.phase)) throw new Error("Chưa nhận final đã xác nhận; kiểm tra receipt/lịch sử.");
      update(key, item => ({ ...item, saveState: "saved", uncertain: false, pendingText: undefined, input: item.input === content ? "" : item.input }));
      void refreshCatalog();
    } catch (failure) {
      if (current()) { update(key, item => ({ ...item, saveState: controller.signal.aborted ? "interrupted" : "error" })); setError(controller.signal.aborted ? "Đã dừng luồng; kiểm tra receipt/lịch sử trước khi gửi lại." : failure instanceof Error ? failure.message : "Trợ lý chưa sẵn sàng."); }
    } finally { if (reader) { void reader.cancel().catch(() => {}); reader.releaseLock(); } if (work.current === controller) { work.current = null; if (alive.current) setBusy(false); } }
  }
  async function readReceipt() {
    const session = activeRef.current; if (!session?.id || !session.turnId) return;
    try { await guard(); const receipt = await new ApiClient({ baseUrl: base }).get<TurnReceipt>(`/v1/conversations/${session.id}/receipts/${session.turnId}`);
      if (!current() || receipt.client_id !== session.turnId || !["pending", "interrupted", "completed"].includes(receipt.state)) throw new Error("Receipt chưa thể xác nhận");
      update(session.localId, item => ({ ...item, receipt, uncertain: receipt.state !== "completed", saveState: receipt.state === "completed" ? "saved" : receipt.state === "interrupted" ? "interrupted" : "pending" }));
      if (receipt.state === "completed") await restore(session.localId, session.id);
    } catch (failure) { if (current()) setError(failure instanceof Error ? failure.message : "Chưa đọc được receipt."); }
  }
  async function readRun() {
    const session = activeRef.current;
    if (!session?.id || !session.runId || capabilities?.coordination?.read !== true) return;
    try {
      await guard();
      const api = new ApiClient({ baseUrl: base });
      const run = await api.get<CoordinationRun>(`/v1/conversations/${session.id}/agent-runs/${session.runId}`);
      await guard();
      if (!current() || run.id !== session.runId || !Number.isSafeInteger(run.version) || run.version < 1 || run.continuation?.schema_version !== "coordination-checkpoint.v1") throw new Error("Checkpoint chưa thể xác nhận");
      if (run.status === "completed") {
        const receipt = await api.get<NonNullable<CoordinationRun["transition_receipt"]>>(`/v1/conversations/${session.id}/agent-runs/${session.runId}/receipt`);
        await guard();
        if (receipt.id !== run.continuation.receipt_id || receipt.run_id !== run.id || receipt.state !== "completed" || receipt.version !== run.version) throw new Error("Kết quả chưa có receipt khớp checkpoint");
      }
      update(session.localId, item => ({ ...item, run, waitingRunId: run.status === "waiting_user" ? run.id : undefined }));
    } catch (failure) { if (current()) setError(failure instanceof Error ? failure.message : "Chưa xác nhận được run; dữ liệu đã lưu được giữ."); }
  }
  async function readResourceWork() {
    const session = activeRef.current;
    if (!session?.resourceWork || capabilities?.resource_runs !== true) return;
    try {
      await guard(); const value = await service.resourceRun(session.resourceWork.id); await guard();
      if (value.run.id !== session.resourceWork.id || value.run.receipt_id !== session.resourceWork.receipt_id || value.run.version !== session.resourceWork.version) throw new Error("Receipt công việc hồ sơ đã đổi; cần đối chiếu lại");
      update(session.localId, item => ({ ...item, resourceWork: value.run }));
    } catch (failure) { if (current()) setError(failure instanceof Error ? failure.message : "Chưa đọc được công việc hồ sơ."); }
  }
  return { actor, capabilities, active, catalog, catalogCursor, query, setQuery, archived, setArchived, error, setError, busy,
    authenticationRequired, retrySession: () => setBootAttempt(value => value + 1),
    guard, refreshCatalog, select, newChat, temporaryChat, send, surface, setSurface, readReceipt, readRun, readResourceWork,
    loadMore: () => active?.id ? restore(active.localId, active.id, true) : Promise.resolve(),
    reload: () => active?.id ? restore(active.localId, active.id) : Promise.resolve(),
    input: (value: string) => active && update(active.localId, item => ({ ...item, input: value })),
    setStudentPreparation: (value: StudentPreparationState) => active && update(active.localId, item => ({ ...item, studentPreparation: value })),
    stop: () => work.current?.abort(), service };
}
const Context = createContext<ReturnType<typeof useRuntime> | null>(null);
function ScopedRuntime({ children }: { children: ReactNode }) { const value = useRuntime(); return <Context.Provider value={value}>{children}</Context.Provider>; }
export function UnifiedAssistantProvider({ children }: { children: ReactNode }) {
  const { currentUser, dataConfig } = useStore();
  return <ScopedRuntime key={`${dataConfig?.mode}:${currentUser?.id}:${currentUser?.role}`}>{children}</ScopedRuntime>;
}
export function useUnifiedAssistant() { const value = useContext(Context); if (!value) throw new Error("UnifiedAssistantProvider required"); return value; }
export function useOptionalUnifiedAssistant() { return useContext(Context); }
