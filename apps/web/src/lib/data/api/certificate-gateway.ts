import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { ApiClient } from "../../api/client";

export const CERTIFICATE_DEMO = process.env.NEXT_PUBLIC_CERTIFICATE_DEMO === "true";
const baseUrl = CAMPUS_API_BASE_URL;
export type CertificateStatus = "DRAFT" | "PENDING_CONFIRMATION" | "SUBMITTED" | "VALIDATING" | "PROCESSING" | "WAITING_STUDENT" | "READY" | "FULFILLED" | "REJECTED" | "CANCELLED";
export interface CertificateFormData {
  purpose: string; recipient: string; quantity: number; delivery_method: "DIGITAL" | "PICKUP";
  attachments: Array<{ name: string; content: string }>;
}
export interface CertificateActor {
  user_id: string; display_name: string; roles: string[]; student_code?: string;
  profile?: { display_name: string; student_code: string; program_code: string; cohort_year: number };
}
export interface CertificateRecord {
  id: string; student_user_id: string; status: CertificateStatus; version: number; disclaimer: string;
  payload: CertificateFormData; profile: NonNullable<CertificateActor["profile"]>;
  assigned_user_id: string | null; supplement_request: string | null;
  history: Array<{ id: string; action: string; status: CertificateStatus; occurred_at: string; note: string; actor_role: string }>;
  result: { title: string; disclaimer: string } | null;
}
export interface CertificatePreview {
  document_request: CertificateRecord; preview_id: string; confirmation_token: string; expires_at: string;
}
export interface GuidanceSource { id: string; title: string; locator: string; url: string; content_text: string; content_sha256: string }
export interface CertificateGuidance { summary: string; demo_configuration: string; sources: GuidanceSource[] }
export interface CertificateProposal { intent: "STUDENT_CERTIFICATE" | null; message?: string; missing_fields: string[] }

function record(value: CertificateRecord): CertificateRecord {
  const statuses: string[] = ["DRAFT", "PENDING_CONFIRMATION", "SUBMITTED", "VALIDATING", "PROCESSING", "WAITING_STUDENT", "READY", "FULFILLED", "REJECTED", "CANCELLED"];
  if (!value || typeof value.id !== "string" || !statuses.includes(value.status) || !Number.isInteger(value.version)
    || !value.payload || !value.profile || !Array.isArray(value.history)) throw new Error("Phản hồi hồ sơ không hợp lệ");
  return value;
}

export class ApiCertificateGateway {
  private client() { return new ApiClient({ baseUrl }); }
  async me() { return this.client().get<CertificateActor>("/v1/users/me"); }
  async login(account: string) {
    const result = await this.client().post<{ user: CertificateActor }>("/v1/auth/demo-login", { account });
    if (!result.user?.user_id) throw new Error("Phản hồi đăng nhập không hợp lệ");
    return result.user;
  }
  async logout() {
    await this.client().post("/v1/auth/logout");
  }
  async list(staff = false) {
    const items: CertificateRecord[] = [];
    let cursor: string | null = null;
    for (let i = 0; i < 20; i++) {
      const page: { items: CertificateRecord[]; page: { next_cursor: string | null } } = await this.client().get(
        `${staff ? "/v1/staff" : "/v1"}/document-requests?limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
      items.push(...page.items.map(record));
      cursor = page.page.next_cursor;
      if (!cursor) return items;
    }
    throw new Error("Danh sách vượt giới hạn trang; cần thu hẹp truy vấn");
  }
  async read(id: string, staff = false) {
    return record(await this.client().get<CertificateRecord>(`${staff ? "/v1/staff" : "/v1"}/document-requests/${encodeURIComponent(id)}`));
  }
  async save(form: CertificateFormData, current?: CertificateRecord | null) {
    return record(await this.client().post<CertificateRecord>("/v1/document-requests/drafts", {
      form, ...(current ? { document_id: current.id, expected_version: current.version } : {}),
    }));
  }
  async preview(current: CertificateRecord) {
    const p = await this.client().post<CertificatePreview>(`/v1/document-requests/${current.id}/preview`, { expected_version: current.version });
    record(p.document_request);
    if (!p.preview_id || !p.confirmation_token || !Number.isFinite(Date.parse(p.expires_at))) throw new Error("Bản xem trước không hợp lệ");
    return p;
  }
  async resume(id: string) { return this.client().get<CertificatePreview>(`/v1/document-requests/${encodeURIComponent(id)}/preview`); }
  async confirm(p: CertificatePreview) {
    const result = await this.client().post<{ document_request_id: string; status: string; tracking_url: string; is_replay: boolean }>(
      `/v1/document-requests/${p.document_request.id}/confirm`, { preview_id: p.preview_id, confirmation_token: p.confirmation_token,
        idempotency_key: `certificate-submit:${p.preview_id}`, form: p.document_request.payload });
    if (result.document_request_id !== p.document_request.id || result.status !== "SUBMITTED" || !result.tracking_url) throw new Error("Chưa xác minh được kết quả gửi");
    return result;
  }
  async act(current: CertificateRecord, action: string, note: string, form?: CertificateFormData) {
    const prefix = action === "supplement" ? "/v1" : "/v1/staff";
    const result = await this.client().post<{ document_request: CertificateRecord; is_replay: boolean }>(
      `${prefix}/document-requests/${current.id}/${action}`, { expected_version: current.version,
        idempotency_key: `certificate:${current.id}:${current.version}:${action}`, note, ...(form ? { form } : {}) });
    return record(result.document_request);
  }
  guidance() { return this.client().get<CertificateGuidance>("/v1/certificate-guidance"); }
  source(id: string) { return this.client().get<GuidanceSource>(`/v1/certificate-guidance/sources/${encodeURIComponent(id)}`); }
  propose(message: string) { return this.client().post<CertificateProposal>("/v1/document-assistant", { message }); }
  async result(id: string) {
    const response = await fetch(`${baseUrl}/v1/document-requests/${encodeURIComponent(id)}/result`, {
      credentials: "include", cache: "no-store" });
    if (!response.ok) throw new Error("Không thể tải kết quả. Hãy tải lại hồ sơ.");
    return response.text();
  }
}
