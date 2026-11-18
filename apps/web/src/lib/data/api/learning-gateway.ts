/** Authenticated learning API. All calls stay on the Campus entry origin. */
export interface LearningPage<T> { items: T[]; page?: { next_cursor: string | null; has_more?: boolean; limit?: number } }
export interface LearningOffering { id: string; course_id: string; term_id: string; section_code: string; title: string; status: string; revision: number; timezone?: string; member_role: string | null; capabilities: { read: boolean; manage: boolean; page_feedback?: boolean; page_explanations?: boolean; exit_tickets?: boolean } }
export interface LearningSession { id: string; offering_id: string; sequence_no: number; title: string; description: string; starts_at: string | null; revision: number }
export type LearningSessionContext = Pick<LearningSession, "id" | "offering_id" | "sequence_no" | "title">;
export interface LearningVersion { id: string; version_id?: string; rendition_id?: string | null; source_media_type?: string; error_detail?: string; version_no: number; processing_state: string; publication_state: string; page_count: number; has_text_layer: boolean; revision: number; schedule_error?: string; capabilities?: { version_changes?: boolean } }
export type LearningUploadAttempt = {intentKey:string;contentKey:string;completeKey:string;started?:boolean;intentId?:string;materialId?:string;file?:File};
export const newLearningUploadAttempt = ():LearningUploadAttempt=>({intentKey:crypto.randomUUID(),contentKey:crypto.randomUUID(),completeKey:crypto.randomUUID()});
export interface LearningMaterial { id: string; offering_id: string; title: string; description: string; visibility: string; current_published_version_id: string | null; revision: number; versions: LearningVersion[] }
export interface LearningReaderMetadata extends LearningVersion { version_id: string; material_id: string; offering_id: string; title: string; content_path: string; current_published_version_id?: string|null; capabilities: { read: boolean; download: boolean; manage: boolean; explain?: boolean; page_feedback?: boolean; version_changes?: boolean; idea_cards?: boolean; accessible_text?: boolean; manage_accessible_text?: boolean } }
export interface LearningPreview {
  preview_id: string; confirmation_token: string; payload: Record<string, unknown>; expires_at: string;
  retraction?: { is_current: boolean; candidates: { id: string; version_no: number }[] };
  page_explanation?: LearningPageExplanation;
  change_set?: LearningVersionChangeSet;
  exit_ticket?: LearningExitTicket & { students: number; submissions: number };
  exit_review?: { explanation: string; revision: number };
  idea_share?: LearningIdeaSharePreview;
  ocr_release?: { id: string; operation: "PUBLISH" | "WITHDRAW"; version_id: string; revision: number; pages: number[]; page_count: number };
}
export interface LearningOcrAnchor { x: number; y: number; width: number; height: number }
export type LearningOcrBlockType = "PARAGRAPH" | "HEADING" | "LIST" | "TABLE" | "FORMULA" | "FIGURE" | "PLACEHOLDER";
export interface LearningOcrDecision {
  id: string; type: LearningOcrBlockType; text?: string; level?: number; items?: string[]; ordered?: boolean;
  headers?: string[]; rows?: string[][]; risk_verified?: boolean;
}
export type LearningOcrBlock = LearningOcrDecision & { anchor: LearningOcrAnchor };
export interface LearningOcrCandidateBlock {
  id: string; order: number; text: string; anchor: LearningOcrAnchor; confidence: number | null;
  provenance: "NATIVE" | "OCR"; review_reasons: string[];
}
export interface LearningOcrRelease {
  id: string; version_id: string; revision: number; state: "DRAFT" | "PUBLISHED" | "WITHDRAWN" | "SUPERSEDED";
  page_count: number; available_pages: number[]; missing_page_count: number;
}
export interface LearningOcrReviewRelease extends LearningOcrRelease {
  current_release_id: string | null; requested_pages: number[]; reviewed_pages: number[];
  candidate?: { sha256: string; blocks: LearningOcrCandidateBlock[] } | null;
  review?: { page_no: number; blocks: LearningOcrBlock[] } | null;
}
export interface LearningOcrJob {
  id: string; version_id: string; release_id: string; revision: number; pages: number[];
  state: "QUEUED" | "RUNNING" | "PAUSED" | "CANCELLED" | "FAILED" | "NEEDS_REVIEW";
  errors: Record<string, { code: string; permanent: boolean }>; completed_pages: number; requested_pages: number;
}
export interface LearningOcrJobs {
  jobs: LearningOcrJob[]; releases: LearningOcrReviewRelease[];
  daily_pages_remaining: number; max_pages_per_job: number; storage_available_bytes: number;
}
export type LearningIdeaProse = { problem: string; idea: string; verification: string; source_description: string };
export type LearningIdeaSource = {
  offering_id: string; version_id: string; page_no: number; title: string; version_no: number;
  kind: "PAGE" | "TEXT" | "REGION"; quote: string | null; rects: { x: number; y: number; width: number; height: number }[];
};
export type LearningIdeaCard = LearningIdeaProse & {
  id: string; topic_id: string | null; revision: number; status: "ACTIVE" | "ARCHIVED"; source: LearningIdeaSource | null;
};
export type LearningIdeaRecipient = { id: string; label: string };
export type LearningIdeaSharePreview = { card: LearningIdeaCard; recipients: LearningIdeaRecipient[] };
export interface LearningExitWallInput { local: string; offset_minutes?: number }
export interface LearningExitWallTime extends LearningExitWallInput { offset_minutes: number; utc: string }
export interface LearningReadingInstructionRef { id: string; revision: number }
export interface LearningExitInstruction extends LearningReadingInstructionRef { purpose: string; page_ranges: { start: number; end: number }[] }
export interface LearningExitDraft {
  version_id: string; page_no: number; question: string; opens: LearningExitWallInput; closes: LearningExitWallInput;
  instruction: LearningReadingInstructionRef | null;
}
interface LearningExitTicketBase { id: string; session_id: string; revision: number }
export interface LearningVisibleExitTicket extends LearningExitTicketBase {
  state: "DRAFT" | "SCHEDULED" | "OPEN" | "CLOSED" | "CANCELLED";
  version_id: string; page_no: number; question: string; zone_id: string;
  opens: LearningExitWallTime; closes: LearningExitWallTime; instruction: LearningExitInstruction | null;
}
export type LearningExitTicket = LearningVisibleExitTicket | (LearningExitTicketBase & { state: "SOURCE_UNAVAILABLE" });
export interface LearningExitReceipt { ticket_id: string; answer: string; revision: number; receipt_id: string; submitted_at: string }
export interface LearningExitSubmission extends LearningExitReceipt { history?: LearningExitReceipt[] }
export interface LearningExitStaffSubmission extends LearningExitReceipt { id: string; student_id: string; student_name?: string }
export interface LearningExitReview {
  revision?: number; topics?: string; next_plan?: string; explanation?: string;
  published: { explanation: string; published_at: string } | null;
}
export type LearningChangeMode = "PAGE_MAP" | "WHOLE_DOCUMENT" | "UNSPECIFIED";
export type LearningChangeItem = {
  kind?: "EDITED" | "MOVED" | "ADDED" | "REMOVED"; old_page?: number | null; new_page?: number | null;
  description?: string; guidance?: string;
};
export interface LearningVersionChangeSet {
  revision: number; mode: LearningChangeMode; target_version_id: string; target_version_no: number;
  target_media_type: string; target_guidance: string; base_available: boolean; base_version_id?: string;
  base_version_no?: number; base_media_type?: string; reason?: string; items: LearningChangeItem[];
}
export interface LearningPageExplanation {
  id: string; session_id: string; version_id: string; page_no: number; body: string;
  category: "RETEACH" | "ADD_EXAMPLE" | "CORRECTION"; status: "DRAFT" | "PUBLISHED";
  revision: number; published_at: string | null;
}
export interface LearningCapabilities { enabled?: boolean; available?: boolean; can_administer?: boolean; roles?: string[]; max_file_bytes?: number; limits?: { max_file_bytes?: number }; [key: string]: unknown }
export class LearningApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) { super(message); this.name = "LearningApiError"; }
}
type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
const ROOT = "/v1/learning";
export function learningId(value: string): string {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value)) throw new Error("Mã học liệu không hợp lệ.");
  return value;
}
export function learningContentPath(path: string, versionId: string): string {
  const expected = `${ROOT}/versions/${learningId(versionId)}/content`;
  if (path !== expected) throw new Error("Đường dẫn tài liệu không hợp lệ.");
  return path;
}
export class LearningGateway {
  constructor(private readonly transport: Fetcher = (input, init) => fetch(input, init), private readonly actorId?: string) {}
  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    if (!path.startsWith("/") || path.startsWith("//") || path.includes("..")) throw new Error("Đường dẫn API không hợp lệ.");
    const headers = new Headers(init.headers); headers.set("Accept", "application/json, application/problem+json");
    if (this.actorId) {
      const expected = headers.get("X-Campus-Reader-Actor");
      if (expected && expected !== this.actorId) throw new LearningApiError(401, "READER_SESSION_CHANGED", "Tài khoản đọc đã thay đổi. Hãy kiểm tra lại phiên đăng nhập.");
      headers.set("X-Campus-Reader-Actor", this.actorId);
    }
    let response: Response;
    try { response = await this.transport(`${ROOT}${path}`, { ...init, headers, credentials: "include", cache: "no-store", redirect: "error" }); }
    catch (error) { if (error && typeof error === "object" && "name" in error && error.name === "AbortError") throw error; throw new LearningApiError(0, "NETWORK_ERROR", "Mất kết nối. Chưa xác định được kết quả; hãy tải lại trạng thái trước khi gửi lại."); }
    if (!response.ok) {
      let code = "HTTP_ERROR";
      try { const data = await response.json(); if (typeof data.code === "string") code = data.code; } catch { /* Safe fallback without private server details. */ }
      const message = response.status === 401 ? "Phiên đăng nhập hết hạn. Hãy đăng nhập lại."
        : code === "UPLOAD_EXPIRED" ? "Lượt tải đã hết hạn. Chọn tệp và bắt đầu lượt tải mới."
        : code === "UPLOAD_LIMIT" ? "Bạn có quá nhiều lượt tải chưa hoàn tất. Hãy hoàn tất hoặc hủy lượt tải đang mở."
        : response.status === 409 ? "Dữ liệu đã thay đổi hoặc thao tác chưa hợp lệ. Hãy tải lại trạng thái."
        : response.status === 404 ? "Không tìm thấy học liệu được phép truy cập."
        : response.status === 413 ? "Tệp vượt giới hạn dung lượng."
        : response.status === 422 || response.status === 415 ? "Kiểm tra thông tin và định dạng tệp học liệu."
        : response.status === 403 ? "Bạn không có quyền thực hiện thao tác này."
        : "Dịch vụ học liệu chưa sẵn sàng. Hãy thử lại.";
      throw new LearningApiError(response.status, code, message);
    }
    if (response.status === 204) return undefined as T;
    try { return await response.json() as T; } catch { throw new LearningApiError(0, "INVALID_RESPONSE", "Phản hồi học liệu không hợp lệ."); }
  }
  async list<T>(path: string, signal?: AbortSignal, headers?: Record<string, string>): Promise<T[]> {
    const items: T[] = []; let cursor: string | null = null;
    for (let pages = 0; pages < 20; pages++) {
      const page: LearningPage<T> = await this.request(`${path}${path.includes("?") ? "&" : "?"}limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, { signal, headers });
      if (!page || !Array.isArray(page.items)) throw new LearningApiError(0, "INVALID_RESPONSE", "Danh sách học liệu không hợp lệ.");
      items.push(...page.items); cursor = page.page?.next_cursor ?? null;
      if (!cursor) return items;
    }
    throw new Error("Danh sách quá dài. Hãy thu hẹp phạm vi.");
  }
  write<T>(path: string, value: unknown, method = "POST", key = crypto.randomUUID(), extraHeaders: Record<string, string> = {}, signal?: AbortSignal): Promise<T> {
    return this.request(path, { method, headers: { ...extraHeaders, "Content-Type": "application/json", "Idempotency-Key": key, "X-Campus-Request": "learning" }, body: JSON.stringify(value), signal });
  }
  capabilities(signal?: AbortSignal) { return this.request<LearningCapabilities>("/capabilities", { signal }); }
  offerings(admin = false, signal?: AbortSignal) { return this.list<LearningOffering>(admin ? "/admin/offerings" : "/offerings", signal); }
  sessions(offeringId: string, signal?: AbortSignal) { return this.list<LearningSession>(`/offerings/${learningId(offeringId)}/sessions`, signal); }
  sessionContexts(versionId: string, signal?: AbortSignal, actorId?: string) {
    return this.list<LearningSessionContext>(`/versions/${learningId(versionId)}/session-contexts`, signal,
      actorId ? { "X-Campus-Reader-Actor": actorId } : undefined);
  }
  materials(sessionId: string, signal?: AbortSignal) { return this.list<LearningMaterial>(`/sessions/${learningId(sessionId)}/materials`, signal); }
  async reader(versionId: string, signal?: AbortSignal) {
    const value = await this.request<LearningReaderMetadata>(`/versions/${learningId(versionId)}`, { signal });
    if ((value.version_id || value.id) !== versionId || !Number.isInteger(value.page_count) || value.page_count < 1) throw new Error("Phiên bản tài liệu không hợp lệ.");
    learningContentPath(value.content_path, versionId); return value;
  }
  async upload(materialId: string, file: File, signal?: AbortSignal, onIntent?: (id: string) => void, attempt:LearningUploadAttempt=newLearningUploadAttempt()): Promise<LearningVersion> {
    if(signal?.aborted) throw new DOMException("Aborted", "AbortError");
    if((attempt.materialId&&attempt.materialId!==materialId)||(attempt.file&&attempt.file!==file))throw new Error("Lượt tải không khớp tài liệu hoặc tệp đã chọn.");
    attempt.materialId=materialId;attempt.file=file;
    const resuming=attempt.started===true;attempt.started=true;
    const contentType=/\.pptx$/i.test(file.name)?"application/vnd.openxmlformats-officedocument.presentationml.presentation":"application/pdf";
    const intent = attempt.intentId?{id:attempt.intentId}:await this.write<{ id: string }>(`/materials/${learningId(materialId)}/upload-intents`, { filename: file.name, byte_size: file.size, content_type: contentType }, "POST", attempt.intentKey, undefined, signal);
    attempt.intentId=learningId(intent.id);
    onIntent?.(intent.id);
    if(signal?.aborted) throw new DOMException("Aborted", "AbortError");
    let received=false;
    if(resuming){
      const status=await this.request<{id:string;material_id:string;state:string;version_id?:string}>(`/upload-intents/${learningId(intent.id)}`,{signal});
      if(signal?.aborted)throw new DOMException('Aborted','AbortError');
      if(status.id!==intent.id||status.material_id!==materialId)throw new Error("Trạng thái lượt tải không khớp tài liệu.");
      if(status.version_id){
        const recovered=await this.request<LearningVersion>(`/versions/${learningId(status.version_id)}`,{signal});
        if(signal?.aborted)throw new DOMException('Aborted','AbortError');
        if((recovered.version_id||recovered.id)!==status.version_id)throw new Error('Biên nhận phiên bản không khớp lượt tải.');
        return recovered;
      }
      if(status.state==='RECEIVING')throw new LearningApiError(409,'UPLOAD_IN_PROGRESS','Máy chủ vẫn đang nhận tệp. Hãy kiểm tra lại trước khi thử tiếp.');
      if(status.state==='ABORTED'||status.state==='EXPIRED')throw new LearningApiError(409,'UPLOAD_'+status.state,'Lượt tải đã dừng hoặc hết hạn. Tệp đang chọn vẫn được giữ.');
      if(!['CREATED','RECEIVED'].includes(status.state))throw new Error("Chưa xác minh được trạng thái lượt tải.");
      received=status.state==='RECEIVED';
    }
    if(!received)await this.request(`/upload-intents/${learningId(intent.id)}/content`, { method: "PUT", headers: { "Content-Type": contentType, "Idempotency-Key": attempt.contentKey, "X-Campus-Request": "learning" }, body: file, signal });
    if(signal?.aborted) throw new DOMException("Aborted", "AbortError");
    const completed=await this.write<LearningVersion>(`/upload-intents/${intent.id}/complete`, {}, "POST", attempt.completeKey, undefined, signal);
    if(signal?.aborted)throw new DOMException('Aborted','AbortError');
    learningId(completed.version_id||completed.id);
    return completed;
  }
  preview(versionId: string, action: "publish" | "retract" | "cancel-publication", scheduledAt?: string, replacementId?: string, changeRevision?: number) {
    return this.write<LearningPreview>(`/versions/${learningId(versionId)}/publication-preview`, {
      action,
      ...(scheduledAt ? { scheduled_at: scheduledAt } : {}),
      ...(replacementId ? { replacement_version_id: learningId(replacementId) } : {}),
      ...(changeRevision === undefined ? {} : { change_set_revision: changeRevision }),
    });
  }
}
