import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { ApiClient } from "./api/client";
import type { ResourceRef } from "./unified-ai-contracts";
import type { PersonalPreview, PersonalReceipt } from "./assistant-memory";

export type TrackingTrigger = "feedback" | "supplement" | "status" | "deadline";
export interface SubscriptionSpec { resource: ResourceRef; trigger: TrackingTrigger; channel: "in_app"; expires_at: string; permission_id: string; permission_version: number; quiet_start_hour: number; quiet_end_hour: number; utc_offset_minutes: number }
export interface Subscription { key: string; version: number; payload: { state: "active" | "stopped"; spec: SubscriptionSpec } }
export interface Notification { id: string; event_id: string; subscription_id: string; subscription_version: number; recipient_id: string; audience: "student" | "staff"; resource: ResourceRef; reason: string; source_id: string; source_sha256: string; updated_at: string; next_action: string; classification: "public_student" | "internal_staff"; action_authority: "none" }
export class AssistantTrackingClient {
  private get client() { return new ApiClient({ baseUrl: CAMPUS_API_BASE_URL }); }
  subscriptions() { return this.client.get<{ items: Subscription[]; configured: boolean }>("/v1/assistant/tracking/subscriptions"); }
  notifications(cursor = "") { return this.client.get<{ items: Notification[]; next_cursor: string | null }>(`/v1/assistant/tracking/notifications?cursor=${encodeURIComponent(cursor)}`); }
  preview(subscription_id: string, spec: SubscriptionSpec | null, expected_version: number, client_id: string) { return this.client.post<PersonalPreview>("/v1/assistant/tracking/preview", { operation: spec ? "subscribe" : "stop", spec, subscription_id, expected_version, client_id }); }
  confirm(preview: PersonalPreview) { return this.client.post<PersonalReceipt>("/v1/assistant/tracking/confirm", { normalized_payload: preview.normalized_payload, confirmation_token: preview.confirmation_token, confirmed: true }); }
  receipt(id: string) { return this.client.get<PersonalReceipt>(`/v1/assistant/tracking/receipts/${encodeURIComponent(id)}`); }
  open(event_id: string) { return this.client.post<{ resource: ResourceRef; projection_hash: string; open_path: string; handover: Array<{ version: number; queue: string; summary: { visibility: "public" | "internal"; done: string[]; open: string[]; next_action: string } }>; action_authority: "none" }>("/v1/assistant/cases/notification:open", { event_id }); }
}
