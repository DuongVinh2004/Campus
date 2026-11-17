import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient } from "./api/client";

export type FreshnessState = "EXPIRED" | "OVERDUE" | "DUE_SOON" | "OK";

export interface FreshnessItem {
  source_id: string;
  version_id: string;
  title: string;
  owner_unit: string;
  version_label: string | null;
  state: FreshnessState;
  due_at: string | null;
  reason: "EFFECTIVE_UNTIL" | "REVIEW_INTERVAL" | null;
  days_left: number | null;
  applicability_unknown: boolean;
  last_review: { reviewed_at: string; note: string } | null;
}

export interface FreshnessReport {
  generated_at: string;
  summary: Record<FreshnessState, number> & { applicability_unknown: number };
  items: FreshnessItem[];
}

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });

export const freshnessApi = {
  report: () => client().get<FreshnessReport>("/v1/knowledge/freshness"),
  reviewed: (sourceId: string, note: string) =>
    client().post<{ source_id: string; reviewed_at: string }>(`/v1/knowledge/freshness/${encodeURIComponent(sourceId)}/reviewed`, { note }),
};
