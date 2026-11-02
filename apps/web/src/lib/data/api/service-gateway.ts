import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { ApiClient } from "../../api/client";
import { ApiCertificateGateway, type CertificateActor } from "./certificate-gateway";

export const SERVICE_DEMO = process.env.NEXT_PUBLIC_SERVICE_DEMO === "true";
const baseUrl = CAMPUS_API_BASE_URL;
export type ServiceKind = "GRADE_APPEAL" | "GENERAL_SUPPORT";
export interface ServiceForm {
  kind: ServiceKind; course_record_id: string | null; reason: string; contact_preference: "PORTAL" | "EMAIL";
  attachments: Array<{ name: string; content: string; media_type?: "text/plain" }>;
  question: string; unresolved: string; evidence_refs: string[];
}
export interface CourseRecord { id: string; course_code: string; semester: string; score: string; deadline: string | null;
  eligibility: string; eligibility_reason?: string; source_locator: string; is_simulation: boolean }
export interface ServiceRecord {
  id: string; document_type: ServiceKind; student_user_id: string; status: string; version: number; queue: string;
  payload: ServiceForm; assigned_user_id: string | null; supplement_request: string | null; disclaimer: string;
  profile: { display_name: string; student_code: string }; snapshot: { guidance: { text?: string; unverified?: string; version_id?: string; source_sha256?: string } };
  history: Array<{ id: string; action: string; status: string; occurred_at: string; note: string; actor_role: string }>;
  messages: Array<{ action: string; text: string; at: string }>;
  result: { title: string; outcome: string; note: string; checksum: string; template_version: string } | null;
}
export interface ServicePreview { document_request: ServiceRecord; form: ServiceForm; preview_id: string;
  confirmation_token: string; operation: string; note: string; expires_at: string; disclaimer: string }
export interface StaffEntry { user_id: string; display_name: string; queues: string[] }
export interface KnowledgeSource { id: string; title: string; filename: string; locator: string;
  original_base64: string; original_sha256: string; created_by: string }
export interface KnowledgeVersion {
  id: string; source_id: string; procedure: ServiceKind; text: string; mapping: string; candidate_text: string;
  source_sha256: string; rendition_sha256: string; created_by: string; revision: number; state: string;
  effective_from: string; effective_until: string | null; reviews: Array<{ reviewer: string; verdict: string; note: string }>;
  build: { error: string | null; checksum: string; compatibility: string } | null;
}
export interface KnowledgeState { sources: KnowledgeSource[]; versions: KnowledgeVersion[];
  active: Array<{ id: string; version_id: string | null; generation: number }>;
  history: Array<{ id: string; target: string; action: string; note: string; occurred_at: string }> }
export interface PublicationPreview { preview_id: string; confirmation_token: string; expires_at: string; payload: { operation: string; version_id: string } }

function record(v: ServiceRecord) {
  if (!v || !["GRADE_APPEAL", "GENERAL_SUPPORT"].includes(v.document_type) || !Number.isInteger(v.version)
      || !v.payload || !Array.isArray(v.history)) throw new Error("Phản hồi hồ sơ không hợp lệ");
  return v;
}

export class ApiServiceGateway {
  private client() { return new ApiClient({ baseUrl }); }
  me(): Promise<CertificateActor> { return new ApiCertificateGateway().me(); }
  async list(staff: boolean) {
    const items: ServiceRecord[] = [];
    let cursor: string | null = null;
    for (let pages = 0; pages < 20; pages++) {
      const result: { items: ServiceRecord[]; page: { next_cursor: string | null } } = await this.client().get(
        `/v1/${staff ? "staff/" : ""}service-requests?limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
      items.push(...result.items.map(record)); cursor = result.page.next_cursor;
      if (!cursor) return items;
    }
    throw new Error("Danh sách vượt giới hạn trang; cần thu hẹp truy vấn");
  }
  async read(id: string, staff = false) { return record(await this.client().get<ServiceRecord>(`/v1/${staff ? "staff/" : ""}service-requests/${encodeURIComponent(id)}`)); }
  courses() { return this.client().get<{ items: CourseRecord[] }>("/v1/service-course-records"); }
  directory() { return this.client().get<{ items: StaffEntry[] }>("/v1/service-staff-directory"); }
  guidance(kind: ServiceKind) { return this.client().get<{ text: string; source_sha256: string; rendition_sha256: string; locator: string; version_id: string }>(`/v1/service-guidance/${kind}`); }
  propose(message: string) { return this.client().post<{ intent: ServiceKind | null; message: string; effect: string; missing_fields: string[] }>("/v1/service-assistant", { message }); }
  async save(form: ServiceForm, current: ServiceRecord | null) {
    return record(await this.client().post<ServiceRecord>("/v1/service-requests/drafts", { form,
      ...(current ? { document_id: current.id, expected_version: current.version } : {}) }));
  }
  preview(current: ServiceRecord, form?: ServiceForm, note?: string) {
    return this.client().post<ServicePreview>(`/v1/service-requests/${current.id}/preview`, { expected_version: current.version,
      ...(form ? { form, note } : {}) });
  }
  resume(id: string) { return this.client().get<ServicePreview>(`/v1/service-requests/${encodeURIComponent(id)}/preview`); }
  async confirm(p: ServicePreview) {
    const receipt = await this.client().post<{ document_request_id: string; status: string; queue: string }>(`/v1/service-requests/${p.document_request.id}/confirm`, {
      preview_id: p.preview_id, confirmation_token: p.confirmation_token, idempotency_key: `service-submit:${p.preview_id}`, form: p.form });
    if (receipt.document_request_id !== p.document_request.id || !["SUBMITTED", "VALIDATING"].includes(receipt.status) || !receipt.queue)
      throw new Error("Chưa xác minh được kết quả gửi");
    return receipt;
  }
  async act(r: ServiceRecord, action: string, note: string, extra: Record<string, unknown> = {}) {
    const result = await this.client().post<{ document_request: ServiceRecord }>(`/v1/staff/service-requests/${r.id}/${action}`, {
      expected_version: r.version, idempotency_key: `service:${r.id}:${r.version}:${action}`, note, ...extra });
    return record(result.document_request);
  }
  async download(id: string, suffix: string) {
    const response = await fetch(`${baseUrl}/v1/service-requests/${encodeURIComponent(id)}/${suffix}`, {
      credentials: "include", cache: "no-store" });
    if (!response.ok) throw new Error("Chưa tải được tài liệu. Kiểm tra quyền/trạng thái hồ sơ.");
    return response.text();
  }
  knowledge() { return this.client().get<KnowledgeState>("/v1/knowledge-operations"); }
  source(id: string) { return this.client().get<KnowledgeSource>(`/v1/knowledge-operations/sources/${encodeURIComponent(id)}`); }
  upload(value: { title: string; filename: string; content: string; locator: string }) { return this.client().post<KnowledgeSource>("/v1/knowledge-operations/sources", value); }
  version(value: { source_id: string; procedure: ServiceKind; text: string; mapping: string; effective_from: string; effective_until?: string | null; candidate_text: string }) {
    return this.client().post<KnowledgeVersion>("/v1/knowledge-operations/versions", value);
  }
  review(v: KnowledgeVersion, verdict: string, note: string) { return this.client().post<KnowledgeVersion>(`/v1/knowledge-operations/versions/${v.id}/review`, { expected_version: v.revision, verdict, note }); }
  build(v: KnowledgeVersion) { return this.client().post<KnowledgeVersion>(`/v1/knowledge-operations/versions/${v.id}/build`, { expected_version: v.revision }); }
  publicationPreview(v: KnowledgeVersion, operation: string) { return this.client().post<PublicationPreview>(`/v1/knowledge-operations/versions/${v.id}/${operation}/preview`, { expected_version: v.revision }); }
  publish(p: PublicationPreview) { return this.client().post(`/v1/knowledge-operations/versions/${p.payload.version_id}/confirm`, {
    preview_id: p.preview_id, confirmation_token: p.confirmation_token, idempotency_key: `knowledge:${p.preview_id}`, confirmed: true }); }
}
