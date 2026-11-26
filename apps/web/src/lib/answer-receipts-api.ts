import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient } from "./api/client";

export interface ReceiptStatement {
  index: number;
  checks: { deterministic: string; verbatim: boolean; semantic: string };
  sources: { unit_id: string; path: string | null; doc_title: string | null; page: number | null; status_now: "UNCHANGED" | "CHANGED" | "REMOVED" }[];
}
export interface AnswerReceipt {
  receipt_id: string; created_at: string; release_id: string; outcome_kind: string;
  statements: ReceiptStatement[]; rejected_counts: Record<string, number>;
  now: { release_id: string | null; sources_changed: number; sources_removed: number; impact_run_id: string | null };
}

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });

export const answerReceiptsApi = {
  forMessage: (conversationId: string, messageId: string) =>
    client().get<AnswerReceipt>(`/v1/answer-receipts/by-message/${encodeURIComponent(conversationId)}/${encodeURIComponent(messageId)}`),
};
