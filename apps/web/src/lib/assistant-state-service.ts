import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { ApiClient } from "./api/client";
import type { ResourceRef, DraftProposal } from "./unified-ai-contracts";

export interface AssistantPreferences {
  locale: "vi" | "en";
  reply_style: "concise" | "steps" | "detailed";
  verbosity: "short" | "normal" | "long";
  format: "text" | "markdown";
  display_name: string;
  address_as: string;
  custom_instructions: string;
}
export interface ActorStatePreview { normalized_payload: string; confirmation_token: string; expires_at: string; effect: "actor_state_only" }
export interface ActorStateReceipt { receipt_id: string; client_id: string; namespace: string; key: string; version: number; state: "committed"; is_replay: boolean }
export interface GrantSpec {
  client_id: string; resource: ResourceRef; capability: "read_source" | "read_own_resource" | "prepare_draft";
  purpose: "source_assistance"; lifetime: "once" | "session" | "timed"; lifetime_seconds: number;
}
export interface ScopedContextRequest {
  conversation_id?: string; before_message_id?: string; resource?: ResourceRef; grant_id?: string; operation_id: string;
  memory_terms?: string[];
}
export interface ScopedContext {
  content: Record<string, unknown>;
  manifest: { sha256: string; bytes: number; budget_bytes: number; generated_at: string; expires_at: string; freshness: "revalidate_every_use" };
  receipt: ActorStateReceipt | null;
}

// Read the caller-selected key only. Never migrate, remove or rewrite the
// browser source, and never infer ownership from a key or the current login.
export async function exportLegacyStudentChat(storage: Pick<Storage, "getItem">, key: string) {
  if (!key || key.length > 200) throw new Error("Cần khóa lịch sử cụ thể");
  const source_json = storage.getItem(key);
  if (source_json === null) throw new Error("Không tìm thấy lịch sử trên thiết bị");
  const bytes = new TextEncoder().encode(source_json);
  if (bytes.length > 48000) throw new Error("Snapshot vượt giới hạn import; dữ liệu nguồn được giữ nguyên");
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return { source_json, source_sha256: Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, "0")).join("") };
}

export class AssistantStateService {
  private get client() { return new ApiClient({ baseUrl: CAMPUS_API_BASE_URL }); }
  consumerCapabilities() { return this.client.get<AssistantCapabilities>("/v1/assistant/consumer-capabilities"); }
  consentState() { return this.client.get<{ items: ConsentState[] }>("/v1/assistant/consent-state"); }
  chatPreferences(id: string) { return this.client.get<{ version: number; saved: boolean; override: { enabled: boolean; preferences: AssistantPreferences } | null; effective: AssistantPreferences }>(`/v1/assistant/chats/${encodeURIComponent(id)}/preferences`); }
  grants(cursor = "") { return this.client.get<{ items: AssistantGrant[]; page: { next_cursor: string | null; has_more: boolean } }>(`/v1/assistant/grants?cursor=${encodeURIComponent(cursor)}`); }
  conversations(title = "", cursor = "", archived = false) {
    return this.client.get<{ items: ConversationSummary[]; page: { next_cursor: string | null; has_more: boolean } }>(`/v1/assistant/conversations?title=${encodeURIComponent(title)}&archived=${archived}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
  }
  conversation(id: string) { return this.client.get<ConversationSummary>(`/v1/assistant/conversations/${encodeURIComponent(id)}`); }
  previewConversation(value: ConversationSummary, title: string, pinned: boolean, archived: boolean, client_id: string) {
    return this.client.post<ActorStatePreview>(`/v1/assistant/conversations/${encodeURIComponent(value.id)}:preview`, { title, pinned, archived, expected_version: value.version, client_id });
  }
  resolveSurface(surface: SurfaceContext) {
    return this.client.post<{ audience: "student" | "staff"; action_authority: "none"; context: { guidance?: string; resource?: { id: string; version: number }; evidence?: Array<{ source_id: string; version_id: string; locator: string; sha256: string; classification: string }> }; field_guidance: string | null;
      specialist?: { status: "observed" | "partial" | "abstained"; blockers: string[]; next_action: "read_sources" | "review_resource"; run?: ResourceRunMetadata | null; workflow?: { binding_status: string; binding?: { workflow_version: string; template_version: string }; readiness: string } | null } }>("/v1/assistant/surface:resolve", surface);
  }
  readPreferences() {
    return this.client.get<{ version: number; saved: boolean; preferences: AssistantPreferences; consumer_enabled: boolean }>("/v1/assistant/preferences");
  }
  consentNotice() {
    return this.client.get<{ version: string; status: string; disclaimer: { statement: string }; purposes: string[] }>("/v1/assistant/consent-notice");
  }
  consentHistory(purpose: "OPTIONAL_PERSONALIZATION" | "QUALITY_FEEDBACK" | "CONVERSATION_HISTORY", afterVersion = 0) {
    return this.client.get<{ items: unknown[]; has_more: boolean; next_version: number | null }>(`/v1/assistant/consents/${purpose}?after_version=${encodeURIComponent(afterVersion)}`);
  }
  previewPreferences(preferences: AssistantPreferences, expected_version: number, client_id: string) {
    return this.client.post<ActorStatePreview>("/v1/assistant/preferences:preview", { preferences, expected_version, client_id });
  }
  previewChatPreferences(conversationId: string, preferences: AssistantPreferences, expected_version: number, client_id: string, enabled = true) {
    return this.client.post<ActorStatePreview>(`/v1/assistant/chats/${encodeURIComponent(conversationId)}/preferences:preview`, { preferences, expected_version, client_id, enabled });
  }
  previewConsent(purpose: "OPTIONAL_PERSONALIZATION" | "QUALITY_FEEDBACK" | "CONVERSATION_HISTORY", decision: "GRANTED" | "WITHDRAWN", notice_version: string, expected_version: number, client_id: string) {
    return this.client.post<ActorStatePreview>("/v1/assistant/consents:preview", { purpose, decision, notice_version, expected_version, client_id });
  }
  previewGrant(spec: GrantSpec) { return this.client.post<ActorStatePreview>("/v1/assistant/grants:preview", spec); }
  composeContext(request: ScopedContextRequest) { return this.client.post<ScopedContext>("/v1/assistant/context:compose", request); }
  revalidateContext(request: ScopedContextRequest, expected_sha256: string) {
    return this.client.post<ScopedContext>("/v1/assistant/context:revalidate", { request, expected_sha256 });
  }
  readOwnResource(grant_id: string, resource: ResourceRef, operation_id: string) {
    return this.client.post<{ result: { resource: unknown; fields: Record<string, unknown>; action_authority: "none" }; receipt: ActorStateReceipt }>("/v1/assistant/resources:read", { grant_id, resource, operation_id });
  }
  prepareCandidate(grant_id: string, proposal: DraftProposal, operation_id: string) {
    return this.client.post<{ result: { proposal: DraftProposal; action_authority: "none" }; receipt: ActorStateReceipt }>("/v1/assistant/proposals:prepare", { grant_id, proposal, operation_id });
  }
  previewRevoke(grantId: string, expected_version: number, client_id: string) {
    return this.client.post<ActorStatePreview>(`/v1/assistant/grants/${encodeURIComponent(grantId)}:revoke-preview`, { expected_version, client_id });
  }
  previewImport(source_json: string, client_id: string) {
    return this.client.post<ActorStatePreview | { already_imported: true; record: unknown }>("/v1/assistant/legacy-imports:preview", { source_json, client_id });
  }
  // Explicit caller confirmation, stable preview/client ID for uncertain retry.
  // No autosave, automatic confirmation, source writes or success fallback.
  confirm(kind: "preferences" | "grants" | "legacy-imports" | "conversations", preview: ActorStatePreview, confirmed: true) {
    if (confirmed !== true) throw new Error("Cần xác nhận preview");
    return this.client.post<{ saved: true; receipt: ActorStateReceipt }>(`/v1/assistant/${kind}:confirm`, {
      normalized_payload: preview.normalized_payload, confirmation_token: preview.confirmation_token, confirmed,
    });
  }
  receipt(clientId: string) { return this.client.get<ActorStateReceipt>(`/v1/assistant/receipts/${encodeURIComponent(clientId)}`); }
  resourceRun(id: string) { return this.client.get<{ run: ResourceRunMetadata; continuation: { state: string; next_action: string; blockers: string[] } }>(`/v1/assistant/resource-runs/${encodeURIComponent(id)}`); }
  exportImport(importId: string) { return this.client.get<{ snapshot: { source_json: string; context_eligible: false }; execution_authority: "none" }>(`/v1/assistant/legacy-imports/${encodeURIComponent(importId)}`); }
}

export interface AssistantCapabilities {
  student_preparation?: boolean; student_ocr?: boolean; student_draft_writer?: string | null;
  tenant_id: string;
  audience: "student" | "staff";
  history: boolean; history_metadata: boolean; stable_create: boolean; stable_turns: boolean;
  temporary_chat?: boolean;
  student_model_chat: boolean; staff_model_chat: boolean; model_preferences: boolean;
  resource_context: boolean; account_preferences: boolean; chat_preferences: boolean; grants: boolean;
  memory: boolean; tools: boolean; templates: boolean; quality_training: boolean;
  locked_reasons: Record<string, string>;
  coordination?: { profile: "coordination-checkpoint.v1" | null; read: boolean; resume: boolean; transition_receipts: boolean; writer: string };
  resource_runs?: boolean;
}
export interface ResourceRunMetadata { id: string; version: number; state: "partial" | "interrupted"; receipt_id: string; is_replay: boolean }
export interface ConsentState {
  purpose: "OPTIONAL_PERSONALIZATION" | "CONVERSATION_HISTORY" | "QUALITY_FEEDBACK";
  version: number; decision: "GRANTED" | "WITHDRAWN"; notice_version: string | null; current_notice_consented: boolean; consumer: string;
}
export interface AssistantGrant {
  id: string; version: number; capability: GrantSpec["capability"]; lifetime: GrantSpec["lifetime"];
  resource: ResourceRef; expires_at: string; state: "active" | "consumed" | "revoked" | "expired";
  last_used_at: string | null; use_count: number; locked_reason: string | null; action_authority: "read_or_prepare_only";
}
export interface ConversationSummary {
  mode?: "persistent" | "temporary" | null;
  id: string; conversation_id: string; title: string; pinned: boolean; archived: boolean; version: number;
  audience: "student"; history_version: number; retention_state: "available" | "expired"; retention_expires_at: string;
  can_continue: boolean; saved: boolean; created_at: string; updated_at: string;
}
export interface SurfaceContext {
  surface: "chat" | "student_home" | "staff_queue" | "settings" | "certificate" | "service";
  resource?: ResourceRef;
  operation_id?: string;
  staff_surface?: "queue" | "detail" | "checklist" | "editor" | "error" | "handover" | "admin";
  staff_intent?: "read" | "review" | "prepare" | "retry" | "route" | "publish";
  field?: "reason" | "course_record_id" | "contact_preference" | "purpose" | "recipient" | "quantity" | "delivery_method";
}

/** UUIDv7 for stable client operations; random tail contains no actor data. */
export function assistantClientId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  let time = Date.now();
  for (let i = 5; i >= 0; i--) { bytes[i] = time % 256; time = Math.floor(time / 256); }
  bytes[6] = (bytes[6] & 15) | 112; bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
