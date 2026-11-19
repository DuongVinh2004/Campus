"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { ApiCertificateGateway, CERTIFICATE_DEMO } from "../../lib/data/api/certificate-gateway";
import { CertificateWorkspace } from "../../features/documents/CertificateWorkspace";
import { ApiServiceGateway, SERVICE_DEMO, type ServiceKind } from "../../lib/data/api/service-gateway";
import Link from "next/link";

import React, { useState, useCallback, useRef, useEffect } from "react";
import { AccessibleDialog } from "../../components/shared/AccessibleDialog";
import { AppShell } from "../../components/AppShell";
import { type ChatMessage } from "../../features/chat/ChatPanel";
import { type FeedbackRating } from "../../features/chat/AnswerFeedback";
import { RouteDraftChatPanel, type DraftSendLifecycle } from "../../features/chat/route-drafts";
import { CitationDrawer, type CitationItem } from "../../features/chat/CitationDrawer";
import { AsyncState, type AsyncStatus } from "../../components/AsyncState";
import { FileText } from "lucide-react";
import { ChatStream, ChatStreamError, SseParser, FAILED_GUIDANCE,
  type StreamCitation, type StreamSnapshot } from "../../features/chat/sse";
import { decodeHistoryPage } from "../../features/chat/history";
import { clearLegacyLocalToken, sessionLoginHref } from "../../features/chat/local-session";
import { ConversationHistory } from "../../features/chat/ConversationHistory";
import { assistantClientId } from "../../lib/assistant-state-service";
import { useOptionalUnifiedAssistant } from "@/lib/unified-assistant-runtime";
import { UnifiedAssistantWorkspace } from "@/features/assistance/UnifiedAssistantWorkspace";

const BUSY_GUIDANCE = "Hệ thống đang bận, thử lại sau ít giây. Câu hỏi của bạn chưa được gửi đi.";

const API_BASE_URL = CAMPUS_API_BASE_URL;
const MULTI_AGENT = process.env.NEXT_PUBLIC_MULTI_AGENT === "true";
const UUID7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

function rememberConversation(id: string | null, mode: "push" | "replace" = "replace") {
  const url = new URL(window.location.href);
  if (id && UUID7.test(id)) url.searchParams.set("conversation_id", id);
  else url.searchParams.delete("conversation_id");
  url.searchParams.delete("q");
  if (url.href !== window.location.href) window.history[mode === "push" ? "pushState" : "replaceState"](window.history.state, "", url);
}

function citationItems(citations: StreamCitation[], conversationId?: string | null, messageId?: string | null): CitationItem[] {
  return citations.map(({ citation }) => ({
    id: citation.citation_id, sourceId: citation.source_id, title: citation.source_title, documentRef: citation.version_label,
    quote: citation.quote || "", isSimulation: citation.source_status === "SYNTHETIC",
    validityStatus: ["CURRENT", "SYNTHETIC"].includes(citation.source_status) ? "active" : "stale",
    locator: citation.locator.section_path || citation.locator.paragraph_id || `Trang ${citation.locator.page_start}`,
    canonicalUrl: citation.canonical_uri.startsWith("https://") ? citation.canonical_uri : undefined,
    ...(conversationId && messageId && UUID7.test(conversationId) && UUID7.test(messageId)
      ? { sourceBinding: { conversationId, messageId, citation } } : {}),
  }));
}

export default function ChatPage() {
  return process.env.NEXT_PUBLIC_UNIFIED_AI === "true" ? <UnifiedChatPage /> : <ExistingChatPage />;
}

function UnifiedChatPage() {
  const runtime = useOptionalUnifiedAssistant();
  return <AppShell activeNav="chat" userRole={runtime?.capabilities?.audience === "staff" ? "staff" : "student"} publicKnowledge={!runtime?.actor}><UnifiedAssistantWorkspace /></AppShell>;
}

function ExistingChatPage() {
  const [initialDraft, setInitialDraft] = useState("");
  const [certificateIntent, setCertificateIntent] = useState(false);
  const [certificateOpen, setCertificateOpen] = useState(false);
  const [certificateError, setCertificateError] = useState("");
  const [serviceIntent, setServiceIntent] = useState<ServiceKind | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [citations, setCitations] = useState<CitationItem[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [status, setStatus] = useState<AsyncStatus>("success");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [historyRevision, setHistoryRevision] = useState(0);
  const [historyTarget, setHistoryTarget] = useState<string | null | undefined>(undefined);
  const [restoreRevision, setRestoreRevision] = useState(0);

  // Persistent conversation ID for the active session
  const conversationIdRef = useRef<string | null>(null);
  const attemptRef = useRef<symbol | null>(null);
  const sequenceRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const citationSetsRef = useRef<Record<string, CitationItem[]>>({});
  const historyControllerRef = useRef<AbortController | null>(null);
  const historyBlockedRef = useRef(false);
  const unlistedConversationRef = useRef(false);
  const waitingRunRef = useRef<string | null>(null);
  const [waitingClarification, setWaitingClarification] = useState(false);

  /** Rates a saved answer. Only answers the server has stored (their id is the server's message id) can be rated. */
  const submitFeedback = useCallback(async (answerId: string, rating: FeedbackRating) => {
    const conversationId = conversationIdRef.current;
    if (!conversationId || !UUID7.test(conversationId) || !UUID7.test(answerId)) throw new Error("Answer is not stored yet");
    const response = await fetch(`${API_BASE_URL}/v1/conversations/${conversationId}/messages/${answerId}/feedback`, {
      method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating: rating === "helpful" ? "HELPFUL" : "NOT_HELPFUL", client_id: assistantClientId() }),
    });
    if (!response.ok) throw new Error("Feedback was not saved");
  }, []);

  const switchConversation = useCallback((id: string | null, navigate = true) => {
    attemptRef.current = null;
    const previousStream = controllerRef.current; controllerRef.current = null;
    const previousHistory = historyControllerRef.current; historyControllerRef.current = null;
    previousStream?.abort(); previousHistory?.abort();
    historyBlockedRef.current = id !== null;
    conversationIdRef.current = null; sequenceRef.current = 0; citationSetsRef.current = {};
    waitingRunRef.current = null;
    setWaitingClarification(false); setIsStreaming(false); setMessages([]); setCitations([]); setIsDrawerOpen(false);
    setCertificateIntent(false); setCertificateError(""); setServiceIntent(null);
    setActiveConversationId(id); setHistoryTarget(id); setRestoreRevision(value => value + 1);
    setInitialDraft(""); setStatus(id === null ? "success" : "loading"); setErrorMessage("");
    if (unlistedConversationRef.current) { unlistedConversationRef.current = false; setHistoryRevision(value => value + 1); }
    if (navigate) rememberConversation(id, "push");
  }, []);

  useEffect(() => {
    clearLegacyLocalToken();
    const restoreLocation = () => {
      const params = new URL(window.location.href).searchParams;
      const id = params.get("conversation_id");
      switchConversation(id, false);
      if (!id) setInitialDraft(params.get("q")?.trim() || "");
    };
    restoreLocation(); window.addEventListener("popstate", restoreLocation);
    return () => window.removeEventListener("popstate", restoreLocation);
  }, [switchConversation]);

  useEffect(() => {
    if (historyTarget === undefined || historyTarget === null) return;
    const conversationId = historyTarget;
    const controller = new AbortController();
    historyControllerRef.current = controller;
    const current = () => historyControllerRef.current === controller && !controller.signal.aborted;
    const deadline = window.setTimeout(() => controller.abort(), 10000);
    setStatus("loading");
    const restore = async () => {
      try {
        if (!UUID7.test(conversationId)) throw new Error("Invalid conversation");
        const restored: ChatMessage[] = [];
        const sets: Record<string, CitationItem[]> = {};
        let cursor: string | null = null;
        let lastSequence = 0;
        // An interrupted or oversized restore never publishes a partial page set.
        for (let pages = 0; pages < 20; pages++) {
          const query = new URLSearchParams({ limit: "100" });
          if (cursor) query.set("cursor", cursor);
          const response = await fetch(`${API_BASE_URL}/v1/conversations/${conversationId}/messages?${query}`, {
            credentials: "include", cache: "no-store", signal: controller.signal,
          });
          if (!current()) return;
          if (response.status === 401) {
            setStatus("unauthorized"); setErrorMessage("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
            return;
          }
          if (!response.ok) throw new Error("History unavailable");
          const page = decodeHistoryPage(await response.json(), conversationId, lastSequence);
          if (!current()) return;
          for (const message of page.messages) {
            if (restored.some((item) => item.id === message.id)) throw new Error("Duplicate history identity");
            const mapped = citationItems(message.final?.citations || [], conversationId, message.id);
            if (message.final) sets[message.id] = mapped;
            restored.push({ id: message.id, role: message.role, content: message.content,
              timestamp: new Date(message.createdAt).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }),
              ...(message.role === "assistant" ? {
                status: !message.final ? "unknown" : message.final.finishStatus === "cancelled" ? "stopped"
                  : message.final.phase === "failed" ? "failed" : message.final.phase === "abstained" ? "abstained" : "success",
                responseClass: message.final?.responseClass,
                citations: mapped.map((item, index) => ({ id: item.id, title: item.title,
                  index: Number(message.final!.citations[index].turn_citation_id.slice(4)) })),
              } : {}),
            });
            lastSequence = message.sequence;
          }
          cursor = page.nextCursor;
          if (!cursor) {
            const last = page.messages[page.messages.length - 1];
            if (MULTI_AGENT && last?.final?.responseClass === "clarification_request" && last.final.runId) {
              waitingRunRef.current = last.final.runId;
              setWaitingClarification(true);
            }
            conversationIdRef.current = conversationId;
            citationSetsRef.current = sets;
            sequenceRef.current = lastSequence;
            const latestAssistant = [...restored].reverse().find(message => message.role === "assistant");
            setMessages(restored); setCitations(latestAssistant ? sets[latestAssistant.id] || [] : []);
            setStatus("success"); setErrorMessage("");
            historyBlockedRef.current = false;
            return;
          }
        }
        throw new Error("History page limit");
      } catch {
        if (historyControllerRef.current === controller) {
          setStatus("error"); setErrorMessage("Không thể khôi phục lịch sử đã xác nhận. Hãy tải lại hoặc mở cuộc trò chuyện mới.");
        }
      } finally {
        window.clearTimeout(deadline);
      }
    };
    void restore();
    return () => {
      historyControllerRef.current = null;
      controller.abort(); window.clearTimeout(deadline);
    };
  }, [historyTarget, restoreRevision]);

  useEffect(() => () => {
    attemptRef.current = null;
    controllerRef.current?.abort();
  }, []);

  const handleSendMessage = useCallback(async (content: string, draft?: DraftSendLifecycle) => {
    if (!content.trim() || attemptRef.current || historyBlockedRef.current) return;
    if (SERVICE_DEMO) {
      void new ApiServiceGateway().propose(content).then(proposal => {
        if (proposal.intent) setServiceIntent(proposal.intent);
      }).catch(() => setCertificateError("Chưa thể chuẩn bị dịch vụ. Kiểm tra phiên đăng nhập hoặc mở Phúc khảo & hỗ trợ."));
    }
    if (CERTIFICATE_DEMO) {
      setCertificateError("");
      void new ApiCertificateGateway().propose(content).then(proposal => {
        if (proposal.intent === "STUDENT_CERTIFICATE") setCertificateIntent(true);
      }).catch(() => setCertificateError("Chưa thể chuẩn bị hồ sơ. Hãy kiểm tra đăng nhập hoặc mở mục Thủ tục & Yêu cầu."));
    }
    const attempt = Symbol("chat-attempt");
    attemptRef.current = attempt;
    const controller = new AbortController();
    controllerRef.current = controller;
    const current = () => attemptRef.current === attempt;
    const sequence = ++sequenceRef.current;

    const userMessage: ChatMessage = {
      id: `user-${sequence}`,
      role: "user",
      content,
      timestamp: new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsStreaming(true);
    setStatus("success");
    setErrorMessage("");
    setCitations([]);
    setIsDrawerOpen(false);

    let assistantMsgId = `assistant-${sequence}`;
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    let stream: ChatStream | undefined;
    let createdConversation = false;
    const showAssistant = (text: string, messageStatus: ChatMessage["status"],
      mapped: CitationItem[] = [], finalId?: string, references: StreamCitation[] = [], responseClass?: string,
      agentProgress?: StreamSnapshot["agentProgress"]) => {
      if (!current()) return;
      const targetId = assistantMsgId;
      const nextId = finalId || targetId;
      const message: ChatMessage = {
        id: nextId, role: "assistant", content: text, status: messageStatus, timestamp: userMessage.timestamp,
        responseClass,
        agentProgress,
        citations: mapped.map((item, index) => ({
          id: item.id, title: item.title,
          index: references[index] ? Number(references[index].turn_citation_id.slice(4)) : index + 1,
        })),
      };
      setMessages((previous) => previous.some((item) => item.id === targetId)
        ? previous.map((item) => item.id === targetId ? message : item) : [...previous, message]);
      assistantMsgId = nextId;
    };
    const showSnapshot = (snapshot: StreamSnapshot) => {
      if (!current()) return;
      if (snapshot.phase === "failed") {
        showAssistant(snapshot.text, "failed", [], snapshot.messageId || undefined, [], snapshot.responseClass);
        setStatus("error"); setErrorMessage(snapshot.text); setCitations([]);
        return;
      }
      if (snapshot.phase === "streaming") {
        showAssistant(snapshot.text, "streaming", [], undefined, [], undefined, snapshot.agentProgress);
        return;
      }
      if (snapshot.responseClass === "clarification_request" && (snapshot.agentProgress?.runId || snapshot.runId)) {
        waitingRunRef.current = snapshot.agentProgress?.runId || snapshot.runId || null;
        setWaitingClarification(true);
      }
      const mapped = citationItems(snapshot.citations, conversationIdRef.current, snapshot.messageId);
      showAssistant(snapshot.text, snapshot.phase === "abstained" ? "abstained"
        : snapshot.finishStatus === "cancelled" ? "stopped" : "success", mapped,
        snapshot.messageId || undefined, snapshot.citations, snapshot.responseClass);
      if (snapshot.messageId) citationSetsRef.current[snapshot.messageId] = mapped;
      setCitations(mapped);
    };

    const stopAttempt = () => {
      if (!current() || stream?.terminal) return;
      showAssistant("Đã dừng — câu trả lời chưa được xác nhận. Kiểm tra lịch sử trước khi gửi thao tác mới.", "stopped");
      setCitations([]);
      setIsDrawerOpen(false);
      attemptRef.current = null;
      controllerRef.current = null;
      setIsStreaming(false);
      // UI cancellation must not wait for transport or its cleanup promise.
      if (reader) void reader.cancel().catch(() => { /* Connection may already be closed. */ });
    };
    controller.signal.addEventListener("abort", stopAttempt, { once: true });

    try {
      const authHeaders: Record<string, string> = {
        "Content-Type": "application/json",
      };

      // 2. Ensure active conversation session exists
      let convId = conversationIdRef.current;
      if (!convId) {
        const convRes = await fetch(`${API_BASE_URL}/v1/conversations`, {
          method: "POST",
          headers: authHeaders,
          credentials: "include",
          body: JSON.stringify({}),
          signal: controller.signal,
        });

        if (!current()) return;

        if (convRes.status === 401) {
          setStatus("unauthorized");
          setErrorMessage("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
          return;
        }

        if (!convRes.ok) {
          throw new Error(`Không thể khởi tạo phiên trò chuyện (Mã lỗi ${convRes.status})`);
        }

        const convData = await convRes.json();
        if (!current()) return;
        convId = convData.id;
        if (!convId || !UUID7.test(convId)) throw new Error("Invalid created conversation");
        if (draft && !draft.created(convId)) throw new Error("Private draft binding conflict");
        conversationIdRef.current = convId;
        if (convId && UUID7.test(convId)) {
          rememberConversation(convId); setActiveConversationId(convId); createdConversation = true;
          unlistedConversationRef.current = true;
        }
      }

      if (MULTI_AGENT && waitingRunRef.current && convId) {
        const pendingPath = `${API_BASE_URL}/v1/conversations/${convId}/agent-runs/${waitingRunRef.current}`;
        const pending = await fetch(pendingPath, { headers: authHeaders, credentials: "include", cache: "no-store", signal: controller.signal });
        if (!current()) return;
        if (pending.status === 401) {
          setStatus("unauthorized"); setErrorMessage("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."); return;
        }
        if (pending.ok) {
          const run = await pending.json();
          if (run.status !== "waiting_user" || !Number.isSafeInteger(run.version) || run.version < 1) throw new Error("Run changed");
          const resumed = await fetch(`${pendingPath}:resume`, { method: "POST", headers: authHeaders, credentials: "include",
            body: JSON.stringify({ expected_version: run.version, content }), signal: controller.signal });
          if (!current()) return;
          if (resumed.status === 401) {
            setStatus("unauthorized"); setErrorMessage("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."); return;
          }
          if (!resumed.ok) throw new Error("Resume unavailable");
          const data = await resumed.json();
          const resumedStream = new ChatStream(convId);
          resumedStream.accept({ id: data.message.message_id, event: "message.started", data: JSON.stringify({ conversation_id: convId, message_id: data.message.message_id }) });
          const snapshot = resumedStream.accept({ id: data.run.id, event: "message.completed", data: JSON.stringify(data.message) });
          resumedStream.finish();
          draft?.accepted();
          waitingRunRef.current = data.run.status === "waiting_user" ? data.run.id : null;
          setWaitingClarification(data.run.status === "waiting_user");
          showSnapshot(snapshot);
          return;
        }
        if (pending.status !== 404) throw new Error("Current run access unavailable");
        // Older conversations may have a clarification without a run record.
        // A new explicit user message follows the established stream contract.
        waitingRunRef.current = null;
        setWaitingClarification(false);
      }

      // 3. Stream message from backend
      const response = await fetch(
        `${API_BASE_URL}/v1/conversations/${convId}/messages:stream`,
        {
          method: "POST",
          headers: authHeaders,
          credentials: "include",
          body: JSON.stringify({ content, client_id: assistantClientId() }),
          signal: controller.signal,
        }
      );

      if (!current()) return;

      if (response.status === 401) {
        setStatus("unauthorized");
        setErrorMessage("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
        return;
      }

      if (response.status === 503 && response.headers?.get("Retry-After")) {
        // Admission control: the server refused the turn before saving anything, so nothing was sent and
        // retrying the same question is safe.
        setStatus("error");
        setErrorMessage(BUSY_GUIDANCE);
        setCitations([]);
        showAssistant(BUSY_GUIDANCE, "failed");
        return;
      }

      if (!response.ok) {
        throw new Error(`Máy chủ phản hồi lỗi: ${response.status}`);
      }

      if (!response.body) {
        throw new Error("Không nhận được luồng dữ liệu từ máy chủ");
      }

      reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8", { fatal: true });
      const parser = new SseParser();
      stream = new ChatStream(convId!, response.headers?.get("X-Request-Id"));
      const acceptFrames = (frames: ReturnType<SseParser["push"]>) => {
        for (const frame of frames) {
          if (stream!.terminal || !current()) break;
          const snapshot = stream!.accept(frame);
          // The API persists the user message before emitting message.started.
          if (frame.event === "message.started") draft?.accepted();
          showSnapshot(snapshot);
        }
      };

      while (!stream.terminal) {
        const { value, done } = await reader.read();
        if (!current()) return;
        if (done) {
          acceptFrames(parser.push(decoder.decode()));
          acceptFrames(parser.finish());
          stream.finish();
          break;
        }
        acceptFrames(parser.push(decoder.decode(value, { stream: true })));
      }
    } catch (err: unknown) {
      if (!current() || stream?.terminal) return;
      if (controller.signal.aborted) {
        showAssistant("Đã dừng — câu trả lời chưa được xác nhận. Kiểm tra lịch sử trước khi gửi thao tác mới.", "stopped");
        setCitations([]);
        return;
      }
      const msg = err instanceof ChatStreamError ? err.message : FAILED_GUIDANCE;
      if (err instanceof ChatStreamError) console.warn("chat_stream_protocol", err.code);
      setStatus("error");
      setErrorMessage(msg);
      setCitations([]);
      showAssistant(msg, err instanceof ChatStreamError && err.code === "UNKNOWN_STREAM" ? "unknown" : "failed");
    } finally {
      controller.signal.removeEventListener("abort", stopAttempt);
      if (current()) {
        if (createdConversation) { unlistedConversationRef.current = false; setHistoryRevision(value => value + 1); }
        attemptRef.current = null;
        controllerRef.current = null;
        setIsStreaming(false);
      }
      if (reader) {
        void reader.cancel().catch(() => { /* Connection may already be closed. */ });
        reader.releaseLock();
      }
    }
  }, []);

  return (
    <AppShell activeNav="chat" publicKnowledge>
      <div className="flex flex-col h-full w-full relative overflow-hidden bg-white dark:bg-[#212121]">
        {waitingClarification && <p role="status" className="border-b bg-blue-50 px-3 py-2 text-sm text-blue-800 dark:bg-blue-950/40 dark:text-blue-200">Thông tin bạn gửi tiếp sẽ dùng để làm rõ yêu cầu đang chờ.</p>}
        {SERVICE_DEMO && serviceIntent && <div className="p-3 border-b text-sm"><p>Đề xuất dịch vụ chưa gửi. Chọn thông tin cần chia sẻ, sửa bản nháp rồi xem trước và xác nhận.</p>
          <Link className="fluent-btn-primary mt-2" href={`/services?kind=${serviceIntent}`}>Chuẩn bị {serviceIntent === "GRADE_APPEAL" ? "phúc khảo" : "hỗ trợ chung"} từ hội thoại</Link></div>}
        {CERTIFICATE_DEMO && (certificateIntent || certificateError) && <div className="p-3 border-b text-sm">
          {certificateError && <p role="alert">{certificateError}</p>}
          {certificateIntent && <><p>Bạn cần giấy xác nhận để làm gì và nộp cho đơn vị nào? Chuẩn bị bản nháp để xem và sửa trước khi gửi.</p>
            <button className="fluent-btn-primary mt-2" onClick={() => setCertificateOpen(true)}>Chuẩn bị hồ sơ từ hội thoại</button></>}
        </div>}
        {certificateOpen && <AccessibleDialog open onClose={() => setCertificateOpen(false)} labelledBy="chat-certificate-title" className="campus-request-dialog"><h2 id="chat-certificate-title" className="sr-only">Chuẩn bị hồ sơ giấy xác nhận</h2>
          <button className="fluent-btn-secondary m-4" onClick={() => setCertificateOpen(false)}>Quay lại hội thoại</button>
          <CertificateWorkspace embedded />
        </AccessibleDialog>}

        {(status === "unauthorized" || status === "loading" || (status === "error" && historyBlockedRef.current)) && (
          <div className="p-3 bg-amber-50 dark:bg-amber-950/60 border-b border-amber-200 dark:border-amber-900 shrink-0">
            {status === "unauthorized" ? <p role="alert" className="text-sm">
              {errorMessage} <a className="underline" href={sessionLoginHref()}>Đăng nhập lại</a>
            </p> : <AsyncState
              status={status}
              errorMessage={errorMessage || "Phiên đăng nhập không hợp lệ hoặc đã hết hạn."}
              onRetry={() => {
                if (historyBlockedRef.current) switchConversation(activeConversationId, false);
                else { setStatus("success"); conversationIdRef.current = null; }
              }}
            />}
          </div>
        )}

        <div className="flex-1 min-h-0 w-full h-full">
          <RouteDraftChatPanel
            draftId={activeConversationId || "new"}
            initialDraft={activeConversationId ? "" : initialDraft}
            retainUntilAcknowledged
            disabled={historyBlockedRef.current || status === "unauthorized"}
            historyContent={<ConversationHistory activeId={activeConversationId} revision={historyRevision} onSelect={id => switchConversation(id)} />}
            messages={messages}
            isStreaming={isStreaming}
            onSendMessage={handleSendMessage}
            onStopStreaming={() => controllerRef.current?.abort()}
            citationCount={citations.length}
            onOpenCitations={() => setIsDrawerOpen(true)}
            onClearMessages={() => switchConversation(null)}
            onFeedbackSubmit={submitFeedback}
            onCitationClick={(citationId) => {
              const selected = Object.values(citationSetsRef.current).find((items) => items.some((item) => item.id === citationId));
              if (selected) { setCitations(selected); setIsDrawerOpen(true); }
            }}
            onRetry={() => {
              const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
              if (lastUserMsg) {
                void handleSendMessage(lastUserMsg.content);
              }
            }}
          />
        </div>

        <CitationDrawer
          isOpen={isDrawerOpen}
          citations={citations}
          onClose={() => setIsDrawerOpen(false)}
        />
      </div>
    </AppShell>
  );
}
