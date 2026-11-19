import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient } from "./api/client";

export type GapAction = "NEEDS_SOURCE" | "SOURCE_OUTDATED" | "OUT_OF_SCOPE" | "RESOLVED";

export interface RatedSource {
  version_id: string; title: string | null; owner_unit: string | null; in_current_release: boolean;
  helpful: number; not_helpful: number; share_not_helpful: number;
}

export interface GapCluster {
  cluster_key: string; reason: string; version_ids: string[]; count: number; count_7d: number; previous_7d: number; is_new_trend: boolean; last_at: string;
  sources: { version_id: string; title: string | null; owner_unit: string | null }[];
  decision: { at: string; action: GapAction; note: string; release_ref: string; actor: string } | null;
}

export interface AnswerQualityReport {
  days: number; minimum_votes: number; ratings: number; sources: RatedSource[];
  gaps: { days: number; minimum_count: number; clusters: GapCluster[] };
}

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });

export const answerQualityApi = {
  report: (days = 30) => client().get<AnswerQualityReport>(`/v1/knowledge/answer-quality?days=${days}`),
  decide: (clusterKey: string, body: { action: GapAction; note: string; release_ref?: string }) =>
    client().post<{ cluster_key: string; action: GapAction }>(`/v1/knowledge/answer-quality/gaps/${encodeURIComponent(clusterKey)}/decision`, body),
};
