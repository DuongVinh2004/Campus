"use client";
import { useState } from "react";
import Link from "next/link";
import { useUnifiedAssistant } from "@/lib/unified-assistant-runtime";
import { assistantClientId } from "@/lib/assistant-state-service";
import { prepareStudent, saveStudentDraft, type StudentPreparationState, type StudentWorkflow } from "@/lib/student-preparation";
import type { ResourceRef } from "@/lib/unified-ai-contracts";
import { ApiClientError } from "@/lib/api/client";

const names: Record<string, string> = { purpose: "Mục đích", recipient: "Đơn vị nhận", reason: "Lý do", course_record_id: "Mã học phần từ danh sách của bạn", quantity: "Số bản", delivery_method: "Cách nhận", contact_preference: "Kênh thông báo" };
const defaults: StudentPreparationState = { goal: "", workflow: "", statements: {} };
const path = (r: ResourceRef) => `${r.kind === "certificate_request" ? "/tickets" : "/services"}?request=${r.id}`;
export function StudentPreparationPanel() {
  const runtime = useUnifiedAssistant(), state = runtime.active?.studentPreparation || defaults;
  const [busy, setBusy] = useState(false), [reviewed, setReviewed] = useState(false), [error, setError] = useState("");
  if (runtime.capabilities?.audience !== "student") return null;
  const set = (value: StudentPreparationState) => { runtime.setStudentPreparation(value); setReviewed(false); };
  const edit = (patch: Partial<StudentPreparationState>) => set({ ...state, ...patch, prepared: undefined, request: undefined, saved: undefined });
  async function prepare(resource = state.resource) {
    if (busy) return; setBusy(true); setError("");
    const request = { goal: state.goal, ...(state.workflow ? { workflow: state.workflow } : {}), resource,
      statements: state.statements, constraints: [], operation_id: assistantClientId() };
    try { await runtime.guard(); const prepared = await prepareStudent(request); await runtime.guard();
      set({ ...state, resource, request, prepared, saved: undefined, uncertain: false });
    } catch (e) { setError(e instanceof Error ? e.message : "Chưa chuẩn bị được; nội dung được giữ."); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!reviewed || !state.prepared?.sha256 || !state.request || busy) return;
    setBusy(true); setError("");
    try { await runtime.guard(); const result = await saveStudentDraft(state.request, state.prepared.sha256); await runtime.guard();
      if (result.receipt.effect !== "draft_saved" || result.receipt.document_request_id !== result.document_request.id || result.document_request.version < result.receipt.version) throw new Error("Chưa xác nhận được receipt lưu nháp");
      set({ ...state, saved: { kind: result.document_request.document_type === "STUDENT_CERTIFICATE" ? "certificate_request" : "service_request", id: result.document_request.id, expected_version: result.document_request.version }, uncertain: false });
    } catch (e) { runtime.setStudentPreparation({ ...state, uncertain: !(e instanceof ApiClientError && e.problem.status >= 400 && e.problem.status < 500) }); setError(e instanceof Error ? e.message : "Chưa rõ kết quả; thử lại cùng mã lưu để đọc receipt."); }
    finally { setBusy(false); }
  }
  const fields = state.workflow === "STUDENT_CERTIFICATE" ? ["purpose", "recipient"] : state.workflow === "GRADE_APPEAL" ? ["course_record_id", "reason"] : state.workflow ? ["reason"] : [];
  return <details className="max-h-[55dvh] overflow-y-auto border-b p-3 text-sm">
    <summary className="min-h-11 cursor-pointer font-semibold">Chuẩn bị thủ tục sinh viên</summary>
    {runtime.capabilities?.student_preparation !== true ? <p>Chức năng chuẩn bị nháp chưa có ở bản đang phục vụ. <Link href="/tickets">Mở giấy xác nhận</Link> hoặc <Link href="/services">phúc khảo và hỗ trợ</Link>.</p> : <div className="space-y-3">
      <p>Nội dung khai dưới đây dùng để chuẩn bị nháp. Trường đã lưu được đọc theo quyền hiện tại; nội dung chưa lưu ở biểu mẫu khác vẫn được giữ tại đó.</p>
      <fieldset disabled={busy || state.uncertain} className="space-y-3">
        <label className="block">Kết quả mong muốn<textarea className="fluent-input w-full" maxLength={2000} value={state.goal} onChange={e => edit({ goal: e.target.value })} /></label>
        <label className="block">Thủ tục<select className="fluent-input w-full" value={state.workflow} onChange={e => edit({ workflow: e.target.value as StudentWorkflow | "" })}><option value="">Cần làm rõ</option><option value="STUDENT_CERTIFICATE">Giấy xác nhận</option><option value="GRADE_APPEAL">Phúc khảo</option><option value="GENERAL_SUPPORT">Hỗ trợ chung</option></select></label>
        {fields.map(field => <label key={field} className="block">{names[field]}<input className="fluent-input w-full" maxLength={2000} value={state.statements[field] ?? ""} placeholder={state.resource ? "Để trống để giữ trường đã lưu" : ""} onChange={e => { const statements = { ...state.statements }; if (e.target.value) statements[field] = e.target.value; else delete statements[field]; edit({ statements }); }} /></label>)}
        {state.workflow === "GRADE_APPEAL" && <Link href="/services">Xem danh sách học phần được cấp</Link>}
        {runtime.surface.resource && <button type="button" onClick={() => edit({ resource: runtime.surface.resource })}>Dùng hồ sơ đang mở</button>}
        {state.resource && <p>Hồ sơ {state.resource.id} · v{state.resource.expected_version} <button type="button" onClick={() => edit({ resource: undefined })}>Bỏ chọn tham chiếu</button></p>}
        <button type="button" className="fluent-btn-primary" disabled={!state.goal.trim()} onClick={() => void prepare()}>Chuẩn bị đề xuất</button>
      </fieldset>
      {state.prepared && <section aria-live="polite" className="space-y-2">
        <p>{state.prepared.intent.clarification}</p>
        {state.prepared.candidates.map(r => <div key={r.id}><Link href={path(r)}>Mở {r.id} · {r.status}</Link>{r.status === "DRAFT" && <button type="button" disabled={busy || state.uncertain} className="ml-2 min-h-11" onClick={() => void prepare({ kind: r.kind, id: r.id, expected_version: r.expected_version })}>Chọn nháp</button>}</div>)}
        {state.prepared.field_errors.map(e => <p key={e.field} role="alert">{names[e.field] || e.field}: {e.detail}</p>)}
        {state.prepared.diff.map(c => <p key={c.field}>{names[c.field]}: <del>{String(c.before ?? "")}</del> → <ins>{String(c.candidate)}</ins></p>)}
        {state.prepared.form && !state.prepared.diff.length && <dl>{Object.entries(state.prepared.form).filter(([k]) => names[k]).map(([k, v]) => <div key={k}><dt>{names[k]}</dt><dd className="break-words">{String(v ?? "")}</dd></div>)}</dl>}
        {state.prepared.binding && <p className="break-words text-xs">Quy trình {state.prepared.binding.workflow_version} · mẫu {state.prepared.binding.template_version} · {state.prepared.binding.queue}. Quy định chính thức chưa được xác minh.</p>}
        {state.prepared.sha256 && !state.saved && <><label className="block"><input type="checkbox" checked={reviewed} disabled={busy} onChange={e => setReviewed(e.target.checked)} /> Tôi đã xem các thay đổi nháp trên</label><button type="button" className="fluent-btn-primary" disabled={!reviewed || busy} onClick={() => void save()}>{state.uncertain ? "Thử lại cùng mã lưu / đọc receipt" : "Lưu nháp đã xem"}</button></>}
      </section>}
      {state.saved && <p role="status">Đã xác nhận receipt lưu nháp. <Link className="underline" href={path(state.saved)}>Mở nháp để xem trước và xác nhận gửi</Link>.</p>}
      <p className="text-xs">OCR chưa có consumer. Tệp và trích xuất không xác thực giấy tờ.</p>
      {busy && <p role="status">Đang kiểm tra…</p>}{error && <p role="alert">{error}</p>}
    </div>}
  </details>;
}
