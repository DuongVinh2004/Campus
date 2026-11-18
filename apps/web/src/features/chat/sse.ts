// P-CONTRACT-STREAM-001: parse framing separately from validated message lifecycle.
export interface SseFrame { id: string; event: string; data: string }
export type FinishStatus = "answered" | "abstained" | "completed" | "cancelled" | "handed_over";
export type ResponseClass = "grounded_answer" | "tool_result" | "action_preview" | "action_result" |
  "handover_notice" | "clarification_request" | "safe_refusal" | "system_error" | "partial_answer";
export interface StreamCitation {
  turn_citation_id: string;
  citation: {
    citation_id: string; source_id: string; document_version_id: string; chunk_id?: string;
    source_title: string; canonical_uri: string; version_label: string;
    source_status: "CURRENT" | "SUPERSEDED" | "EXPIRED" | "SYNTHETIC";
    locator: { section_path?: string; page_start?: number; page_end?: number; paragraph_id?: string };
    quote?: string;
    release_id?: string;
    release_generation?: number;
    evidence_sha256?: string;
    unit_id?: string;
  };
}

export const FAILED_GUIDANCE = "Không thể xác nhận câu trả lời. Vui lòng kiểm tra lịch sử hoặc gửi yêu cầu hỗ trợ; hệ thống không tự gửi lại thao tác.";
export const DEPENDENCY_GUIDANCE = "Dịch vụ hỗ trợ trả lời đang phản hồi chậm hoặc tạm thời không khả dụng. Câu hỏi chưa có kết quả được xác nhận; bạn có thể thử lại sau. Hệ thống không tự gửi lại câu hỏi.";
export const UNKNOWN_GUIDANCE = "UNKNOWN — Luồng trả lời có dữ liệu chưa được hỗ trợ. Nội dung tạm đã được thu hồi; bạn có thể gửi yêu cầu hỗ trợ.";
export class ChatStreamError extends Error {
  constructor(public readonly code: "MALFORMED_STREAM" | "UNKNOWN_STREAM" | "INCOMPLETE_STREAM") {
    super(code === "UNKNOWN_STREAM" ? UNKNOWN_GUIDANCE : FAILED_GUIDANCE);
    Object.setPrototypeOf(this, ChatStreamError.prototype);
  }
}
const malformed = (): never => { throw new ChatStreamError("MALFORMED_STREAM"); };
const unknown = (): never => { throw new ChatStreamError("UNKNOWN_STREAM"); };

/** Decoded UTF-8 chunks may end anywhere, including inside CRLF or a JSON line. */
export class SseParser {
  private buffer = "";
  private event = "";
  private id = "";
  private data: string[] = [];
  private size = 0;
  private beginning = true;

  push(chunk: string, eof = false): SseFrame[] {
    this.buffer += chunk;
    if (this.beginning && this.buffer.length) {
      this.beginning = false;
      if (this.buffer[0] === "\uFEFF") this.buffer = this.buffer.slice(1);
    }
    const frames: SseFrame[] = [];
    while (true) {
      const boundary = this.buffer.search(/[\r\n]/);
      if (boundary < 0) break;
      if (!eof && this.buffer[boundary] === "\r" && boundary === this.buffer.length - 1) break;
      const line = this.buffer.slice(0, boundary);
      const width = this.buffer[boundary] === "\r" && this.buffer[boundary + 1] === "\n" ? 2 : 1;
      this.buffer = this.buffer.slice(boundary + width);
      this.size += line.length + width;
      if (this.size > 128000) malformed();
      if (!line) {
        if (this.data.length) frames.push({ id: this.id, event: this.event || "message", data: this.data.join("\n") });
        this.event = ""; this.id = ""; this.data = []; this.size = 0;
        continue;
      }
      if (line.startsWith(":")) continue;
      const colon = line.indexOf(":");
      const field = colon < 0 ? line : line.slice(0, colon);
      let value = colon < 0 ? "" : line.slice(colon + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (field === "event") this.event = value;
      if (field === "data") this.data.push(value);
      if (field === "id" && !value.includes("\0")) this.id = value;
    }
    if (this.buffer.length + this.size > 128000) malformed();
    // SSE requires a blank line to dispatch. An unfinished record at EOF is discarded.
    return frames;
  }

  finish(): SseFrame[] { return this.push("", true); }
}

export interface StreamSnapshot {
  messageId: string | null;
  text: string;
  phase: "streaming" | "completed" | "abstained" | "failed";
  citations: StreamCitation[];
  finishStatus?: FinishStatus;
  responseClass?: ResponseClass;
  problemCode?: string;
  agentProgress?: AgentProgress;
  runId?: string;
}
export interface AgentProgress {
  version: 1;
  runId: string;
  phase: "planning" | "researching" | "verifying" | "reviewing" | "synthesizing" | "waiting_user" | "failed" | "completed" | "cancelled" | "partial" | "interrupted" | "uncertain";
  tasks: { id: string; role: "research" | "verifier"; status: "pending" | "running" | "succeeded" | "partial" | "failed" | "cancelled" }[];
  sourceCount: number;
}

export function agentProgress(value: unknown): AgentProgress {
  const data = record(value);
  if (Object.keys(data).sort().join(",") !== "phase,run_id,source_count,tasks,version" || data.version !== 1) return malformed();
  const phase = text(data.phase, 32);
  if (!["planning", "researching", "verifying", "reviewing", "synthesizing", "waiting_user", "failed", "completed", "cancelled", "partial", "interrupted", "uncertain"].includes(phase)) return unknown();
  if (!Array.isArray(data.tasks) || data.tasks.length > 8 || typeof data.source_count !== "number" ||
    !Number.isSafeInteger(data.source_count) || data.source_count < 0 || data.source_count > 6) return malformed();
  const tasks = data.tasks.map((value) => {
    const task = record(value);
    if (Object.keys(task).sort().join(",") !== "id,role,status" || typeof task.id !== "string" || !/^T[1-8]$/.test(task.id)) return malformed();
    if (!["research", "verifier"].includes(String(task.role)) ||
      !["pending", "running", "succeeded", "partial", "failed", "cancelled"].includes(String(task.status))) return unknown();
    return { id: task.id, role: task.role, status: task.status } as AgentProgress["tasks"][number];
  });
  if (new Set(tasks.map(task => task.id)).size !== tasks.length) return malformed();
  return { version: 1, runId: uuid(data.run_id), phase: phase as AgentProgress["phase"], tasks, sourceCount: data.source_count };
}
const UUID7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return malformed();
  return value as Record<string, unknown>;
}
function text(value: unknown, max: number, nonempty = true): string {
  if (typeof value !== "string" || value.length > max || (nonempty && !value.trim())) return malformed();
  return value;
}
function uuid(value: unknown): string {
  if (typeof value !== "string" || !UUID7.test(value)) return malformed();
  return value;
}
function positiveInteger(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1) return malformed();
  return value;
}

function citation(value: unknown): StreamCitation {
  const mapping = record(value);
  const localId = text(mapping.turn_citation_id, 32);
  if (!/^CIT-[0-9]{3,}$/.test(localId)) return malformed();
  return { turn_citation_id: localId, citation: normalizeCitation(mapping.citation) };
}

export function normalizeCitation(value: unknown): StreamCitation["citation"] {
  const raw = record(value);
  const sourceStatus = text(raw.source_status, 32);
  if (!["CURRENT", "SUPERSEDED", "EXPIRED", "SYNTHETIC"].includes(sourceStatus)) return unknown();
  const locator = record(raw.locator);
  const normalizedLocator: StreamCitation["citation"]["locator"] = {};
  if (locator.section_path !== undefined) normalizedLocator.section_path = text(locator.section_path, 500);
  if (locator.paragraph_id !== undefined) normalizedLocator.paragraph_id = text(locator.paragraph_id, 100);
  if (locator.page_start !== undefined) normalizedLocator.page_start = positiveInteger(locator.page_start);
  if (locator.page_end !== undefined) normalizedLocator.page_end = positiveInteger(locator.page_end);
  if (!Object.keys(normalizedLocator).length || (normalizedLocator.page_end !== undefined &&
    (normalizedLocator.page_start === undefined || normalizedLocator.page_end < normalizedLocator.page_start))) return malformed();
  const canonicalUri = text(raw.canonical_uri, 2000);
  try { new URL(canonicalUri); } catch { return malformed(); }
  if (raw.release_generation !== undefined && (typeof raw.release_generation !== "number" || !Number.isSafeInteger(raw.release_generation) || raw.release_generation < 0)) return malformed();
  if (raw.evidence_sha256 !== undefined && (typeof raw.evidence_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(raw.evidence_sha256))) return malformed();
  return {
    citation_id: uuid(raw.citation_id), source_id: uuid(raw.source_id),
    document_version_id: uuid(raw.document_version_id),
    ...(raw.chunk_id !== undefined ? { chunk_id: uuid(raw.chunk_id) } : {}),
    source_title: text(raw.source_title, 300), canonical_uri: canonicalUri,
    version_label: text(raw.version_label, 64), source_status: sourceStatus as StreamCitation["citation"]["source_status"],
    locator: normalizedLocator, ...(raw.quote !== undefined ? { quote: text(raw.quote, 500, false) } : {}),
    ...(raw.release_id !== undefined ? { release_id: uuid(raw.release_id) } : {}),
    ...(raw.release_generation !== undefined ? { release_generation: raw.release_generation as number } : {}),
    ...(raw.evidence_sha256 !== undefined ? { evidence_sha256: raw.evidence_sha256 as string } : {}),
    ...(raw.unit_id !== undefined ? { unit_id: text(raw.unit_id, 256) } : {}),
  };
}

const PROBLEM_CODES = new Set([
  "AUTHENTICATION_REQUIRED", "IDENTITY_PROVIDER_NOT_ALLOWED", "ROLE_MAPPING_FAILED", "FORBIDDEN", "RESOURCE_NOT_FOUND",
  "VALIDATION_FAILED", "UNSUPPORTED_MEDIA_TYPE", "PAYLOAD_TOO_LARGE", "VERSION_CONFLICT", "INVALID_STATE_TRANSITION",
  "IDEMPOTENCY_KEY_REQUIRED", "IDEMPOTENCY_KEY_REUSED", "IDEMPOTENCY_IN_PROGRESS", "ACTION_PREVIEW_EXPIRED",
  "ACTION_PREVIEW_ALREADY_USED", "ACTION_CONFIRMATION_INVALID", "POLICY_DENIED", "ROOM_SLOT_UNAVAILABLE",
  "CITATION_UNRESOLVABLE", "RATE_LIMITED", "DEPENDENCY_UNAVAILABLE", "INTEGRATION_NOT_ENABLED", "EVENT_PUBLISH_FAILED", "INTERNAL_ERROR",
]);

/** One instance belongs to one response attempt; it never changes another message. */
export class ChatStream {
  private seen = new Set<string>();
  private lastSequence = 0;
  private started = false;
  private state: StreamSnapshot = { messageId: null, text: "", phase: "streaming", citations: [] };
  constructor(private readonly conversationId: string, private readonly requestId?: string | null) {}

  get terminal(): boolean { return this.state.phase !== "streaming"; }
  get snapshot(): StreamSnapshot { return this.state; }

  accept(frame: SseFrame): StreamSnapshot {
    if (this.terminal) return this.state;
    uuid(frame.id);
    if (this.seen.has(frame.id)) return this.state;
    this.seen.add(frame.id);
    if (this.seen.size > 20000) malformed();
    if (!["message.started", "agent.status", "message.delta", "citation.added", "message.completed", "message.failed"].includes(frame.event)) return unknown();
    let value: unknown;
    try { value = JSON.parse(frame.data); } catch { return malformed(); }
    const data = record(value);
    if (frame.event === "message.started") {
      if (this.started || data.conversation_id !== this.conversationId) return malformed();
      this.started = true;
      this.state = { ...this.state, messageId: uuid(data.message_id) };
      return this.state;
    }
    if (!this.started) return malformed();
    if (frame.event === "agent.status") {
      const progress = agentProgress(data);
      if (this.state.agentProgress && this.state.agentProgress.runId !== progress.runId) return malformed();
      this.state = { ...this.state, agentProgress: progress };
      return this.state;
    }
    if (frame.event === "message.failed") {
      const code = text(data.code, 64);
      if (!PROBLEM_CODES.has(code)) return unknown();
      if (typeof data.status !== "number" || !Number.isInteger(data.status) || data.status < 400 || data.status > 599 ||
        typeof data.retryable !== "boolean") return malformed();
      if (data.type !== `https://campus247.example/problems/${code.toLowerCase().replaceAll("_", "-")}`) return malformed();
      text(data.title, 160); text(data.detail, 1000); text(data.instance, 300); uuid(data.request_id);
      if (this.requestId && data.request_id !== this.requestId) return malformed();
      // User guidance comes from a fixed safe copy, never an exception/body reflected by a peer.
      this.state = { ...this.state, text: code === "DEPENDENCY_UNAVAILABLE" ? DEPENDENCY_GUIDANCE : FAILED_GUIDANCE,
        phase: "failed", citations: [], problemCode: code };
      return this.state;
    }
    if (frame.event === "message.delta") {
      const sequence = positiveInteger(data.seq);
      const delta = text(data.delta, 20000, false);
      if (sequence <= this.lastSequence) return this.state;
      this.lastSequence = sequence;
      if (this.state.text.length + delta.length > 20000) return malformed();
      this.state = { ...this.state, text: this.state.text + delta };
      return this.state;
    }
    if (data.message_id !== this.state.messageId) return malformed();
    if (frame.event === "citation.added") {
      citation(data.citation); // Validate but keep provisional citations unavailable to the UI.
      return this.state;
    }
    if (data.conversation_id !== this.conversationId) return malformed();
    const status = text(data.status, 32);
    const responseClass = text(data.response_class, 32);
    const classes: Record<string, string[]> = {
      answered: ["grounded_answer", "partial_answer", "tool_result"], abstained: ["safe_refusal", "clarification_request", "system_error"],
      completed: ["tool_result", "action_preview", "action_result"], cancelled: ["safe_refusal"], handed_over: ["handover_notice"],
    };
    if (!Object.prototype.hasOwnProperty.call(classes, status) ||
      !Object.values(classes).some((values) => values.includes(responseClass))) return unknown();
    if (!classes[status].includes(responseClass)) return malformed();
    if (!Array.isArray(data.citations) || data.citations.length > 20) return malformed();
    const citations = data.citations.map(citation);
    if (new Set(citations.map((item) => item.turn_citation_id)).size !== citations.length ||
      new Set(citations.map((item) => item.citation.citation_id)).size !== citations.length ||
      (["abstained", "cancelled"].includes(status) && citations.length) ||
      (["grounded_answer", "partial_answer"].includes(responseClass) && !citations.length)) return malformed();
    this.state = {
      messageId: this.state.messageId, text: text(data.content, 20000), citations,
      ...(this.state.agentProgress ? { agentProgress: this.state.agentProgress } : {}),
      ...(data.run_id !== undefined ? { runId: uuid(data.run_id) } : {}),
      phase: responseClass === "system_error" ? "failed" : status === "abstained" ? "abstained" : "completed",
      finishStatus: status as FinishStatus, responseClass: responseClass as ResponseClass,
    };
    return this.state;
  }

  finish(): StreamSnapshot {
    if (!this.terminal) throw new ChatStreamError("INCOMPLETE_STREAM");
    return this.state;
  }
}
