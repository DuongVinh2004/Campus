import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { ApiClient } from "./api/client";
import type { ResourceRef } from "./unified-ai-contracts";

export interface PersonalPreview { normalized_payload: string; confirmation_token: string; expires_at: string; effect: "personal_state_only" }
export interface PersonalReceipt { client_id: string; key: string; version: number; state: "committed"; is_replay: boolean }
export interface MemoryValue {
  kind: "preference" | "goal" | "confirmed_fact"; topic: string; text: string;
  valid_until: string; purpose?: "personal_assistance"; scope?: "actor" | "resource";
  resource?: ResourceRef; grant_id?: string;
}
export interface MemoryItem { key: string; version: number; updated_at: string; state: "active" | "suppressed"; value?: MemoryValue; locked_reason?: string }
export interface MemoryPage { items: MemoryItem[]; control: { version: number; payload: { enabled: boolean } } | null; next_cursor: string | null; disclosure: string; physical_erasure: "not_performed" }
export type MemoryChange = { operation: "save"; value: MemoryValue } | { operation: "forget"; key: string } | { operation: "control"; enabled: boolean };

export class AssistantMemoryClient {
  private get client() { return new ApiClient({ baseUrl: CAMPUS_API_BASE_URL }); }
  read(cursor = "") { return this.client.get<MemoryPage>(`/v1/assistant/memory?cursor=${encodeURIComponent(cursor)}`); }
  exportPage(cursor = "") { return this.client.get<MemoryPage>(`/v1/assistant/memory/export?cursor=${encodeURIComponent(cursor)}`); }
  preview(change: MemoryChange, expected_version: number, client_id: string) {
    return this.client.post<PersonalPreview>("/v1/assistant/memory/preview", { ...change, expected_version, client_id });
  }
  confirm(preview: PersonalPreview) { return this.client.post<PersonalReceipt>("/v1/assistant/memory/confirm", { normalized_payload: preview.normalized_payload, confirmation_token: preview.confirmation_token, confirmed: true }); }
  receipt(id: string) { return this.client.get<PersonalReceipt>(`/v1/assistant/memory/receipts/${encodeURIComponent(id)}`); }
}
