import { ApiClient } from "./api/client";
import { CAMPUS_API_BASE_URL } from "./api/base-url";

export type RuleStatus = "PUBLISHED" | "STALE" | "RETIRED";
export interface RuleRow { rule_id: string; version: number; topic: string; status: RuleStatus; label: string; release_id: string | null; published_at: string | null; published_by: string | null }
export interface DraftRow { id: string; rule_id: string; topic: string | null; origin: "MANUAL" | "MODEL_CANDIDATE"; row_version: number; author: string; updated_at: string }
export interface RuleList { rules: RuleRow[]; drafts: DraftRow[]; stale: number }
export interface Review { verdict: "approved" | "rejected" | "needs_source"; note: string; reviewer: string; at: string }
export interface DraftView extends DraftRow { body: Record<string, unknown>; reviews: Review[]; issues: { code: string; detail?: string }[] | string[]; vector_count: number; mismatches: unknown[] }
export interface RuleView { rule_id: string; current: { version: number; status: RuleStatus; body: Record<string, unknown>; published_at: string | null; published_by: string | null; release_id: string | null }; versions: { version: number; status: RuleStatus; published_at: string | null }[] }
export interface Preview { preview_id: string; confirmation_token: string; expires_at: string; change: Record<string, unknown> }

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });
const id = (value: string) => encodeURIComponent(value);

export const policyRulesApi = {
  list: () => client().get<RuleList>("/v1/policy-rules"),
  draft: (draftId: string) => client().get<DraftView>(`/v1/policy-rules/drafts/${id(draftId)}`),
  rule: (ruleId: string) => client().get<RuleView>(`/v1/policy-rules/rules/${id(ruleId)}`),
  createDraft: (body: Record<string, unknown>) => client().post<{ id: string; row_version: number }>("/v1/policy-rules/drafts", { body, origin: "MANUAL" }),
  updateDraft: (draftId: string, body: Record<string, unknown>, rowVersion: number) =>
    client().put<{ id: string; row_version: number }>(`/v1/policy-rules/drafts/${id(draftId)}`, { body, row_version: rowVersion }),
  validate: (draftId: string) => client().post<{ issues: unknown[]; vector_count: number; mismatches: unknown[]; next_version: number }>(`/v1/policy-rules/drafts/${id(draftId)}/validate`, {}),
  review: (draftId: string, verdict: Review["verdict"], note: string) => client().post(`/v1/policy-rules/drafts/${id(draftId)}/review`, { verdict, note }),
  publishPreview: (draftId: string) => client().post<Preview>(`/v1/policy-rules/drafts/${id(draftId)}/publish-preview`, {}),
  retirePreview: (ruleId: string) => client().post<Preview>(`/v1/policy-rules/rules/${id(ruleId)}/retire-preview`, {}),
  confirm: (preview: Preview) => client().post<{ rule_id: string; version: number; status: string }>("/v1/policy-rules/confirm",
    { preview_id: preview.preview_id, confirmation_token: preview.confirmation_token }, { "Idempotency-Key": crypto.randomUUID() }),
};
