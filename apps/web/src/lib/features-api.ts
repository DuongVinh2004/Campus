import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient } from "./api/client";

export interface FeatureSnapshot {
  version: number;
  features: Record<string, boolean | string>;
}

export interface FeatureItem {
  key: string;
  title: string;
  area: string;
  kind: string;
  locked: boolean;
  startup_wired: boolean;
  variants: string[];
  depends_on: string[];
  dependents: string[];
  configured: { value: boolean | string; source: string; expires_at?: string | null; reason?: string; by?: string; at?: string };
  effective_for_all: boolean;
  off_reasons: string[];
  entry_points: { api: string[]; pages: string[]; jobs: string[]; tools: string[] };
  cost: string;
}

export interface FeatureAdminList {
  version: number;
  profile: string;
  store_error: boolean;
  items: FeatureItem[];
}

export interface FeaturePreview {
  preview_id: string;
  confirmation_token: string;
  expires_at: string;
  change: { key: string; from: boolean | string; to: boolean | string | null; remove: boolean };
  impact: { also_off: string[]; api_prefixes: string[]; pages: string[]; jobs: string[]; restart_required: boolean; data_kept: boolean };
}

export interface FeatureAuditRow {
  id: number;
  at: string;
  by: string;
  key: string;
  before: unknown;
  after: { value?: boolean | string; removed?: boolean };
  reason: string;
}

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });

export const featuresApi = {
  snapshot: () => client().get<FeatureSnapshot>("/v1/features"),
  adminList: () => client().get<FeatureAdminList>("/v1/admin/features"),
  audit: (key?: string) => client().get<{ items: FeatureAuditRow[]; next_cursor: number | null }>(
    "/v1/admin/features/audit" + (key ? `?key=${encodeURIComponent(key)}` : "")),
  preview: (key: string, body: { value?: boolean | string; reason: string; expected_version: number; expires_at?: string | null; remove?: boolean; audience?: object }) =>
    client().post<FeaturePreview>(`/v1/admin/features/${encodeURIComponent(key)}/preview`, body),
  confirm: (previewId: string, token: string, idempotencyKey: string) =>
    client().post<{ receipt_id: string; key: string; version: number }>(
      "/v1/admin/features/confirm", { preview_id: previewId, confirmation_token: token }, { "Idempotency-Key": idempotencyKey }),
};
