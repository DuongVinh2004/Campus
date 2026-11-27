import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient } from "./api/client";

export type AnnouncementPriority = "NORMAL" | "IMPORTANT" | "URGENT";

export interface AnnouncementSummary {
  id: string; code: string; title: string; category: string; priority: AnnouncementPriority; issuer_unit: string; status: string;
  revision: number; expires_at: string; requires_ack: boolean; ack_deadline: string | null; published_at: string | null; row_version: number;
  read?: boolean; acked?: boolean;
}
export interface AnnouncementDetail extends AnnouncementSummary {
  body: string; links: { label: string; url?: string }[]; source_ref: { document_no?: string };
  viewer: "recipient" | "manager"; needs_ack?: boolean; revisions?: { revision: number; change_note: string; material: number; at: string }[];
}
export interface AudienceGroup { roles?: string[]; faculty_codes?: string[]; cohorts?: string[]; class_codes?: string[]; offering_ids?: string[]; subjects?: string[] }
export interface Audience { groups: AudienceGroup[]; include_guests?: boolean }
export interface AudienceCount { total: number; by_role: { key: string; n: number }[]; by_faculty: { key: string; n: number }[]; by_cohort: { key: string; n: number }[]; warnings: string[] }
export interface DraftInput {
  title: string; body: string; category: string; priority: AnnouncementPriority; audience: Audience; expires_at: string;
  publish_at?: string | null; requires_ack?: boolean; ack_deadline?: string | null;
}
export interface StatsGroup { key: string; delivered: number; read: number; acked: number }
export interface AnnouncementStats { delivered: number; read: number; acked: number; read_rate: number; by_faculty: StatsGroup[]; by_cohort: StatsGroup[]; timeline: { hour: string; reads: number }[] }
export interface WithdrawPreview { preview_id: string; confirmation_token: string; expires_at: string; summary: { delivered: number; knowledge_revoked: boolean } }
export interface PublishPreview { preview_id: string; confirmation_token: string; summary: { total: number; needs_approval: boolean; knowledge_sync: boolean; publish_at: string | null }; warnings: string[] }

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });
const newKey = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `k-${Date.now()}-${Math.random().toString(16).slice(2)}`);

export const announcementsApi = {
  mine: (filter: "active" | "unread" | "all" = "active") => client().get<{ items: AnnouncementSummary[]; next_offset: number | null }>(`/v1/announcements/mine?filter=${filter}`),
  publicList: () => client().get<{ items: AnnouncementSummary[] }>("/v1/announcements/public"),
  get: (id: string) => client().get<AnnouncementDetail>(`/v1/announcements/${encodeURIComponent(id)}`),
  ack: (id: string) => client().post<{ acked: boolean }>(`/v1/announcements/${encodeURIComponent(id)}/ack`),
  authored: () => client().get<{ items: AnnouncementSummary[] }>("/v1/announcements/authored"),
  createDraft: (input: DraftInput) => client().post<{ id: string; row_version: number }>("/v1/announcements/drafts", input),
  audienceCount: (audience: Audience) => client().post<AudienceCount>("/v1/announcements:audience-preview", { audience }),
  publishPreview: (id: string) => client().post<PublishPreview>(`/v1/announcements/${encodeURIComponent(id)}:publish-preview`),
  publishConfirm: (previewId: string, token: string) =>
    client().post<{ id: string; status: string }>("/v1/announcements:publish-confirm", { preview_id: previewId, confirmation_token: token }, { "Idempotency-Key": newKey() }),
  stats: (id: string) => client().get<AnnouncementStats>(`/v1/announcements/${encodeURIComponent(id)}/stats`),
  approvals: () => client().get<{ items: AnnouncementSummary[] }>("/v1/announcements/approvals"),
  approve: (id: string, note: string, rowVersion: number) => client().post(`/v1/announcements/${encodeURIComponent(id)}:approve`, { note, row_version: rowVersion }),
  reject: (id: string, note: string, rowVersion: number) => client().post(`/v1/announcements/${encodeURIComponent(id)}:reject`, { note, row_version: rowVersion }),
  revisionPreview: (id: string, changes: { title?: string; body?: string; change_note: string; material: boolean }) =>
    client().post<{ preview_id: string; confirmation_token: string; expires_at: string; summary: { material: boolean; revision: number } }>(
      `/v1/announcements/${encodeURIComponent(id)}:revision-preview`, changes),
  revisionConfirm: (previewId: string, token: string) =>
    client().post<{ id: string; revision: number }>("/v1/announcements:revision-confirm", { preview_id: previewId, confirmation_token: token }, { "Idempotency-Key": newKey() }),
  withdrawPreview: (id: string, reason: string) => client().post<WithdrawPreview>(`/v1/announcements/${encodeURIComponent(id)}:withdraw-preview`, { reason }),
  withdrawConfirm: (previewId: string, token: string) =>
    client().post<{ id: string; status: string }>("/v1/announcements:withdraw-confirm", { preview_id: previewId, confirmation_token: token }, { "Idempotency-Key": newKey() }),
};
