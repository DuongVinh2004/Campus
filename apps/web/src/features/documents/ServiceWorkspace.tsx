"use client";

import React, { useEffect, useState } from "react";
import { FileAttachmentInput } from "../../components/shared/FileAttachmentInput";
import { DecisionSheet } from "../../components/shared/DecisionSheet";
import { RecordInventory } from "../../components/shared/RecordInventory";
import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { ApiServiceGateway, type ServiceForm, type ServiceKind, type ServiceRecord, type ServicePreview, type CourseRecord, type StaffEntry } from "../../lib/data/api/service-gateway";
import { type CertificateActor } from "../../lib/data/api/certificate-gateway";
import { AssistanceContextPanel } from "../assistance/AssistanceContextPanel";
import { BaselineRecorder, useBaselineMeasurement } from "../assistance/BaselineRecorder";
import { StaffDraftEditor } from "../assistance/StaffDraftEditor";
import { StaffWorkspacePanel } from "../assistance/StaffWorkspacePanel";
import { CaseWorkflowPanel } from "../assistance/CaseWorkflowPanel";
import { CaseSupplementPanel } from "../assistance/CaseSupplementPanel";
import { StaffCaseInsights } from "../assistance/StaffCaseInsights";
import { CaseProjectionPanel } from "../assistance/CaseProjectionPanel";
import { StudentFieldHelp, MissingFields, formErrors, readTextAttachment } from "./StudentFieldHelp";
import { ServiceCatalog } from "./ServiceCatalog";

const api = new ApiServiceGateway();
const labels: Record<string, string> = { DRAFT: "Bản nháp", PENDING_CONFIRMATION: "Chờ xác nhận", SUBMITTED: "Đã gửi vào hàng đợi",
  VALIDATING: "Đã tiếp nhận", PROCESSING: "Đang xử lý", WAITING_STUDENT: "Cần bổ sung", READY: "Có kết quả", REJECTED: "Đã từ chối" };
const kindLabel = (kind: string) => kind === "GRADE_APPEAL" ? "Phúc khảo" : "Hỗ trợ chung";
const empty = (kind: ServiceKind = "GRADE_APPEAL"): ServiceForm => ({ kind, course_record_id: null, reason: "", contact_preference: "PORTAL", attachments: [], question: "", unresolved: "", evidence_refs: [] });
const panel = "campus-panel";
const input = "fluent-input w-full text-sm";

export function ServiceWorkspace() {
  const [actor, setActor] = useState<CertificateActor | null>(null);
  const [rows, setRows] = useState<ServiceRecord[]>([]);
  const [courses, setCourses] = useState<CourseRecord[]>([]);
  const [directory, setDirectory] = useState<StaffEntry[]>([]);
  const [selected, setSelected] = useState<ServiceRecord | null>(null);
  const [form, setForm] = useState<ServiceForm>(empty());
  const [preview, setPreview] = useState<ServicePreview | null>(null);
  const [note, setNote] = useState("");
  const [target, setTarget] = useState("");
  const [outcome, setOutcome] = useState("UNCHANGED");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [guidance, setGuidance] = useState("");
  const [result, setResult] = useState("");
  const [creating, setCreating] = useState(false);
  const [staffDetail, setStaffDetail] = useState(false);
  const queueScroll = React.useRef(0);
  const staff = !!actor?.roles.includes("SUPPORT_OFFICER");
  const student = !!actor?.roles.includes("STUDENT");
  const measurement = useBaselineMeasurement(process.env.NEXT_PUBLIC_UNIFIED_AI === "true" ? actor?.user_id : undefined);

  async function load() {
    setBusy(true); setError("");
    try {
      const user = await api.me(); setActor(user);
      const isStaff = user.roles.includes("SUPPORT_OFFICER");
      if (!isStaff && !user.roles.includes("STUDENT")) throw new Error("Vai trò này dùng không gian quản trị nguồn");
      const items = await api.list(isStaff); setRows(items);
      if (isStaff) setDirectory((await api.directory()).items);
      else setCourses((await api.courses()).items);
      const params = new URL(window.location.href).searchParams;
      if (params.has("kind") || params.has("request")) setCreating(true);
      const identifier = params.get("request");
      if (identifier) setStaffDetail(true);
      if (identifier) { const row = await api.read(identifier, isStaff); setSelected(row); setForm(row.payload); }
      else if (params.get("kind") === "GENERAL_SUPPORT") setForm(empty("GENERAL_SUPPORT"));
    } catch (e) { setError(e instanceof Error ? e.message : "Không thể tải hồ sơ"); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []);

  async function run(fn: () => Promise<void>) {
    measurement.record("manual_action");
    setBusy(true); setError(""); setNotice(""); setFieldErrors({});
    try { await fn(); setRows(await api.list(staff)); }
    catch (e) { setFieldErrors(formErrors(e)); setError(`${e instanceof Error ? e.message : "Chưa hoàn tất"}. Nội dung đang soạn được giữ. Nếu kết quả gửi chưa rõ, thử lại cùng preview để đối chiếu receipt.`); }
    finally { setBusy(false); }
  }
  function choose(r: ServiceRecord) { void run(async () => {
    queueScroll.current = window.scrollY;
    setStaffDetail(true);
    const latest = await api.read(r.id, staff); setSelected(latest); setForm(latest.payload); setPreview(null); setResult(""); setNote("");
    const url = new URL(window.location.href); url.searchParams.set("request", r.id); window.history.replaceState(window.history.state, "", url);
  }); }
  async function prepare() {
    if (selected?.status === "WAITING_STUDENT") {
      const p = await api.preview(selected, form, note); setSelected(p.document_request); setPreview(p); return;
    }
    const r = await api.save(form, selected); setSelected(r);
    const p = await api.preview(r); setSelected(p.document_request); setPreview(p);
  }
  async function submit() {
    if (!preview) throw new Error("Cần xem trước");
    const receipt = await api.confirm(preview);
    const row = await api.read(receipt.document_request_id); setSelected(row); setForm(row.payload); setPreview(null);
    setNotice(`Đã ghi hồ sơ ${row.id} vào ${receipt.queue}`);
    const url = new URL(window.location.href); url.searchParams.set("request", row.id); window.history.replaceState(window.history.state, "", url);
  }
  async function act(action: string) {
    if (!selected) return;
    const recipient = directory.find(d => d.user_id === target);
    const extra = action === "transfer" ? { target_user_id: target, target_queue: recipient?.queues[0] }
      : action === "assign" ? { target_user_id: target } : action === "resolve" && selected.document_type === "GRADE_APPEAL" ? { outcome } : {};
    const updated = await api.act(selected, action, note, extra);
    if (action === "transfer" && recipient?.queues[0] !== selected.queue) { setSelected(null); setNotice("Đã chuyển tới hàng đợi được cấp quyền"); }
    else { setSelected(updated); setForm(updated.payload); setNotice("Đã cập nhật hồ sơ"); }
    setNote(""); setPreview(null);
  }
  async function attach(file?: File) {
    if (!file) return;
    try { const attachment = await readTextAttachment(file, form.attachments.length);
      setForm(current => current.attachments.length < 3 ? { ...current, attachments: [...current.attachments, { ...attachment, media_type: "text/plain" }] } : current);
    } catch (e) { setError(e instanceof Error ? e.message : "Chưa đọc được tệp; bản nháp được giữ."); }
  }
  const editing = student && (!selected || ["DRAFT", "PENDING_CONFIRMATION", "WAITING_STUDENT"].includes(selected.status));
  return <AppShell activeNav={staff ? "staff" : "services"} userRole={staff ? "staff" : "student"}>
    <main className="campus-workflow space-y-5">
      <header className="campus-page-heading"><div><h1 className="text-2xl font-semibold">{staff ? "Hàng đợi dịch vụ" : creating || selected ? "Phúc khảo & hỗ trợ" : "Danh mục dịch vụ"}</h1>
        <p className="mt-2 text-sm">Mô phỏng local · Phí, hạn và mẫu chính thức của trường chưa được xác minh.</p></div>
        <nav className="flex flex-wrap gap-4 text-sm"><Link href="/tickets">Giấy xác nhận</Link><Link href="/chat">Hỏi đáp có nguồn</Link><Link href="/knowledge/sources">Quản trị nguồn</Link><Link href="/login">Đổi tài khoản</Link></nav></header>
      {actor && <p>{actor.display_name} · {staff ? "Cán bộ" : student ? "Sinh viên" : "Quản trị"}</p>}
      {busy && <p role="status">Đang tải hoặc xử lý…</p>}
      {error && <div role="alert" className="rounded-xl border border-[var(--color-danger-subtle)] bg-[var(--surface-subtle)] p-3 text-xs text-[var(--color-danger)]">{error} <button disabled={busy} className="ml-2 font-semibold underline cursor-pointer" onClick={() => void load()}>Tải lại hồ sơ</button></div>}
      {notice && <p role="status" className="rounded-xl border border-[var(--color-success-subtle)] bg-[var(--surface-subtle)] p-3 text-xs text-[var(--color-success)]">{notice}</p>}
      {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && staff && <StaffCaseInsights key={actor?.user_id} kind="service_request" onCommitted={async () => {
        setRows(await api.list(true)); if (selected) { try { setSelected(await api.read(selected.id, true)); } catch { setSelected(null); } }
      }} />}
      {!staff && !creating && !selected && <ServiceCatalog authenticated={student} onChoose={kind => { setForm(empty(kind)); setCreating(true); }} onHistory={() => setCreating(true)} />}
      {student && creating && !selected && <button type="button" className="fluent-btn-secondary" onClick={() => setCreating(false)}>← Danh mục dịch vụ</button>}
      {staff && <div hidden={staffDetail}><RecordInventory busy={busy} selectedId={selected?.id} records={rows.map(record => ({ id: record.id, title: kindLabel(record.document_type), description: record.profile.display_name, status: record.status, statusLabel: labels[record.status] || record.status, updatedAt: record.history.at(-1)?.occurred_at, group: record.status === "WAITING_STUDENT" ? "waiting" as const : ["READY", "REJECTED"].includes(record.status) ? "completed" as const : "active" as const }))} onOpen={id => { const record = rows.find(record => record.id === id); if (record) choose(record); }} /></div>}
      {staff && staffDetail && <button type="button" className="fluent-btn-secondary" onClick={() => { setStaffDetail(false); requestAnimationFrame(() => window.scrollTo({ top: queueScroll.current })); }}>← Quay lại hàng đợi</button>}
      {(staff && staffDetail || student && (creating || selected)) && <div className={`campus-workflow-grid ${staff ? "" : "campus-form-layout"}`}><aside className={panel}>
        <h2 className="font-semibold">{staff ? "Hàng đợi theo quyền" : "Hồ sơ của tôi"}</h2>
        {student && <button disabled={busy} className="fluent-btn-primary my-3" onClick={() => {
          setSelected(null); setForm(empty()); setPreview(null); setResult(""); setNotice(""); setNote("");
          window.history.replaceState(window.history.state, "", window.location.pathname);
        }}>Hồ sơ mới</button>}
        {!busy && !rows.length && <p className="my-3 text-sm">Chưa có hồ sơ.</p>}
        <ul className="space-y-3">{rows.map(r => <li key={r.id}><button aria-pressed={selected?.id === r.id} className="campus-record-option w-full rounded-xl border p-3 text-left text-sm" disabled={busy} onClick={() => choose(r)}>
          <strong>{kindLabel(r.document_type)} · {r.id.slice(-8)}</strong><span className="block">{labels[r.status] || r.status}</span><span>{r.queue}</span></button></li>)}</ul>
      </aside><section className={panel}>
        <h2 className="font-semibold">{selected ? `${kindLabel(selected.document_type)} · ${selected.id}` : staff ? "Chọn hồ sơ để xử lý" : "Chuẩn bị bản nháp"}</h2>
        {selected && <p className="my-3 text-sm">{labels[selected.status]} · Phiên bản {selected.version} · {selected.profile.display_name}</p>}
        {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && selected && <CaseProjectionPanel key={`projection:${actor?.user_id}:${selected.id}`} resource={{ kind: "service_request", id: selected.id, expected_version: selected.version }} />}
        {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && selected && <AssistanceContextPanel key={`context:${actor?.user_id}:${selected.id}`} id={selected.id} version={selected.version} />}
        <MissingFields errors={fieldErrors} />
        {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && student && selected?.status === "WAITING_STUDENT" &&
          <CaseSupplementPanel key={`supplement:${actor?.user_id}:${selected.id}`} resource={{ kind: "service_request", id: selected.id, expected_version: selected.version }} onCommitted={async () => {
            const latest = await api.read(selected.id); setSelected(latest); setForm(latest.payload); setRows(await api.list(false));
          }} />}
        {editing && <ol className="campus-stepper my-5" aria-label="Tiến trình hồ sơ"><li aria-current={!preview ? "step" : undefined}><span>1</span>Điền thông tin</li><li aria-current={preview ? "step" : undefined}><span>2</span>Xem trước & xác nhận</li><li><span>3</span>Kết quả</li></ol>}
        {editing && !preview && <form className="mt-4 space-y-4" onSubmit={e => { e.preventDefault(); void run(prepare); }}>
          <fieldset id="student-field-form" disabled={busy} className="space-y-4">
            <label className="block text-sm">Loại yêu cầu<select className={input} value={form.kind} disabled={!!selected} onChange={e => setForm(empty(e.target.value as ServiceKind))}>
              <option value="GRADE_APPEAL">Phúc khảo</option><option value="GENERAL_SUPPORT">Hỗ trợ chung</option></select></label>
            {form.kind === "GRADE_APPEAL" && <label className="block text-sm">Học phần mô phỏng<select id="student-field-course_record_id" aria-label="Học phần mô phỏng" aria-describedby="student-help-course_record_id" aria-invalid={!!fieldErrors.course_record_id} required className={input} value={form.course_record_id || ""} disabled={selected?.status === "WAITING_STUDENT"} onChange={e => { setForm({ ...form, course_record_id: e.target.value }); measurement.markField("course_record_id"); measurement.flushField("course_record_id"); }}>
              <option value="">Chọn học phần</option>{courses.map(c => <option key={c.id} value={c.id} disabled={c.eligibility !== "ELIGIBLE_DEMO"}>{c.course_code} · {c.semester} · {c.eligibility === "ELIGIBLE_DEMO" ? c.score : c.eligibility_reason}</option>)}</select></label>}
            {form.course_record_id && <p className="text-sm">Nguồn: {courses.find(c => c.id === form.course_record_id)?.source_locator} · Hạn demo: {courses.find(c => c.id === form.course_record_id)?.deadline}</p>}
            <button type="button" onClick={() => void run(async () => { const g = await api.guidance(form.kind); setGuidance(`${g.text}\nLocator: ${g.locator}\nSource SHA256: ${g.source_sha256}\nRendition SHA256: ${g.rendition_sha256}`); })}>Đọc hướng dẫn và nguồn</button>
            <label className="block text-sm">Lý do<textarea id="student-field-reason" aria-describedby="student-help-reason" aria-invalid={!!fieldErrors.reason} required maxLength={2000} className={input} value={form.reason} onChange={e => { setForm({ ...form, reason: e.target.value }); measurement.markField("reason"); }} onBlur={() => measurement.flushField("reason")} /></label>
            <StudentFieldHelp field="reason" hint="Nêu lý do của bạn. Khoảng trắng đầu/cuối được máy chủ chuẩn hóa; nội dung không được tự viết lại." error={fieldErrors.reason} resource={selected ? { kind: "service_request", id: selected.id, expected_version: selected.version } : undefined} />
            {form.kind === "GRADE_APPEAL" && <StudentFieldHelp field="course_record_id" hint="Chọn đúng học phần từ nguồn được cấp. Thiếu hoặc quá hạn cần đối chiếu với cán bộ." error={fieldErrors.course_record_id} resource={selected ? { kind: "service_request", id: selected.id, expected_version: selected.version } : undefined} />}
            {form.kind === "GENERAL_SUPPORT" && <><label className="block text-sm">Câu hỏi được chia sẻ<textarea maxLength={2000} className={input} value={form.question} onChange={e => setForm({ ...form, question: e.target.value })} /></label>
              <label className="block text-sm">Phần chưa giải quyết<textarea className={input} maxLength={1000} value={form.unresolved} onChange={e => setForm({ ...form, unresolved: e.target.value })} /></label></>}
            <label className="block text-sm">Kênh nhận thông tin<select className={input} value={form.contact_preference} onChange={e => { setForm({ ...form, contact_preference: e.target.value as "PORTAL" | "EMAIL" }); measurement.markField("contact_preference"); measurement.flushField("contact_preference"); }}><option value="PORTAL">Cổng demo</option><option value="EMAIL">Email mô phỏng (không gửi email thật)</option></select></label>
            <div><label htmlFor="student-field-attachments" className="block text-sm">Tệp minh họa (.txt, 16 KB)</label><FileAttachmentInput id="student-field-attachments" invalid={!!fieldErrors.attachments} disabled={busy} onFile={file => void attach(file)} /></div>
            {form.attachments.map((a, i) => <p key={i}>{a.name} <button type="button" onClick={() => setForm({ ...form, attachments: form.attachments.filter((_, j) => i !== j) })}>Bỏ khỏi bản nháp</button></p>)}
            <p className="text-xs">Chưa có OCR. Nội dung tệp là dữ liệu khai báo, không xác thực giấy tờ.</p>
            {selected?.status === "WAITING_STUDENT" && <><p>Yêu cầu bổ sung: {selected.supplement_request}</p><label className="block text-sm">Nội dung bổ sung<textarea required maxLength={1000} className={input} value={note} onChange={e => setNote(e.target.value)} /></label></>}
          </fieldset>
          <div className="flex flex-wrap gap-3">{selected?.status !== "WAITING_STUDENT" && <button type="button" disabled={busy} onClick={() => void run(async () => { const r = await api.save(form, selected); setSelected(r); setNotice("Đã lưu bản nháp; chưa gửi"); })}>Lưu bản nháp</button>}
            <button className="fluent-btn-primary" disabled={busy} type="submit">Xem trước {selected?.status === "WAITING_STUDENT" ? "bổ sung" : "hồ sơ"}</button>
            {selected?.status === "PENDING_CONFIRMATION" && <button type="button" disabled={busy} onClick={() => void run(async () => setPreview(await api.resume(selected.id)))}>Tiếp tục preview đang chờ</button>}</div>
        </form>}
        {preview && <div className="mt-5 space-y-4"><h3 className="font-semibold">Xem trước — chưa gửi</h3><p className="text-sm">{preview.disclaimer}</p>
          <p>{kindLabel(preview.form.kind)} · {preview.form.course_record_id}</p><p>Lý do: {preview.form.reason}</p>
          {preview.form.question && <p>Câu hỏi chia sẻ: {preview.form.question}</p>}{preview.form.unresolved && <p>Chưa giải quyết: {preview.form.unresolved}</p>}
          <p>Tệp: {preview.form.attachments.map(a => a.name).join(", ") || "Không có"}</p><p>Nội dung bổ sung: {preview.note || "Không có"}</p>
          <p className="text-sm">Hết hạn: {new Date(preview.expires_at).toLocaleString("vi-VN")}</p>
          <button disabled={busy} onClick={() => setPreview(null)}>Quay lại sửa</button> <button disabled={busy} className="fluent-btn-primary" onClick={() => void run(submit)}>Xác nhận gửi</button></div>}
        {selected && !editing && <div className="mt-4 space-y-3"><p>Lý do: {selected.payload.reason}</p><p>Học phần: {selected.payload.course_record_id || "Không áp dụng"}</p>
          {selected.payload.question && <p>{selected.payload.question}</p>}{selected.payload.unresolved && <p>Chưa giải quyết: {selected.payload.unresolved}</p>}
          <p className="text-sm">{selected.disclaimer}</p>{selected.payload.attachments.map((a, i) => <button key={i} className="mr-3" disabled={busy} onClick={() => void run(async () => setGuidance(await api.download(selected.id, `attachments/${i}`)))}>Mở {a.name}</button>)}</div>}
        {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && staff && selected && actor &&
          <StaffWorkspacePanel key={`dossier:${actor.user_id}:${selected.id}`} actorId={actor.user_id} studentId={selected.student_user_id}
            resource={{ kind: "service_request", id: selected.id, expected_version: selected.version }} />}
        {process.env.NEXT_PUBLIC_UNIFIED_DURABLE_DRAFTS === "true" && staff && selected && actor && selected.assigned_user_id === actor.user_id &&
          <StaffDraftEditor key={`private-draft:${actor.user_id}:${selected.id}`} actorId={actor.user_id}
            resource={{ kind: "service_request", id: selected.id, expected_version: selected.version }} onUse={setNote} />}
        {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && staff && selected && actor && selected.assigned_user_id === actor.user_id &&
          <CaseWorkflowPanel key={`case-workflow:${actor.user_id}:${selected.id}`} studentId={selected.student_user_id}
            resource={{ kind: "service_request", id: selected.id, expected_version: selected.version }} onCommitted={async () => {
              try { const latest = await api.read(selected.id, true); setSelected(latest); } catch { setSelected(null); }
              setRows(await api.list(true));
            }} />}
        {staff && selected && !["READY", "REJECTED"].includes(selected.status) && <DecisionSheet busy={busy} version={selected.version}><fieldset disabled={busy} className="mt-5 space-y-3">
          <label className="block text-sm">Lý do / phản hồi cán bộ<textarea className={input} maxLength={1000} value={note} onChange={e => { setNote(e.target.value); measurement.markField("staff_note"); }} onBlur={() => measurement.flushField("staff_note")} /></label>
          <label className="block text-sm">Cán bộ nhận<select className={input} value={target} onChange={e => setTarget(e.target.value)}><option value="">Chọn người nhận</option>{directory.map(d => <option key={d.user_id} value={d.user_id}>{d.display_name} · {d.queues.join(", ")}</option>)}</select></label>
          {selected.document_type === "GRADE_APPEAL" && <label className="block text-sm">Kết luận demo<select className={input} value={outcome} onChange={e => setOutcome(e.target.value)}><option value="UNCHANGED">Không thay đổi</option><option value="CORRECTED">Đã đối chiếu, điều chỉnh demo (không ghi điểm trường)</option><option value="UNABLE_TO_REVIEW">Chưa thể phúc khảo</option></select></label>}
          <div className="flex flex-wrap gap-3">{selected.status === "SUBMITTED" && <button disabled={!note.trim()} className="fluent-btn-primary" onClick={() => void run(() => act("claim"))}>Tiếp nhận</button>}
            <button disabled={!target || !note.trim()} onClick={() => void run(() => act("assign"))}>Giao cán bộ trong queue</button>
            {selected.assigned_user_id === actor?.user_id && <><button disabled={!target || !note.trim()} onClick={() => void run(() => act("transfer"))}>Chuyển queue</button>
              {["VALIDATING", "PROCESSING"].includes(selected.status) && <><button disabled={!note.trim()} onClick={() => void run(() => act("respond"))}>Trả lời</button><button disabled={!note.trim()} onClick={() => void run(() => act("request_information"))}>Yêu cầu bổ sung</button>
                <button disabled={!note.trim()} className="fluent-btn-primary" onClick={() => void run(() => act("resolve"))}>Trả kết quả demo</button><button disabled={!note.trim()} onClick={() => void run(() => act("reject"))}>Từ chối có lý do</button></>}</>}</div>
        </fieldset></DecisionSheet>}
        {selected?.result && <div className="mt-5"><p>{selected.result.title} · {selected.result.outcome}</p><p>{selected.result.note}</p>
          <button disabled={busy} className="fluent-btn-primary mt-3" onClick={() => void run(async () => setResult(await api.download(selected.id, "result")))}>Mở kết quả</button><p className="mt-2 break-all text-xs">{selected.result.template_version} · SHA256 {selected.result.checksum}</p></div>}
        {result && <iframe sandbox="" title="Kết quả dịch vụ mô phỏng" srcDoc={result} className="mt-4 min-h-[440px] w-full border" />}
        {selected && <details open className="mt-6"><summary className="font-semibold">Lịch sử xử lý</summary><ol className="mt-3 space-y-3 text-sm">{selected.history.map(e => <li key={e.id}>{new Date(e.occurred_at).toLocaleString("vi-VN")} · {e.action} · {labels[e.status]}<p>{e.note}</p></li>)}</ol></details>}
      </section></div>}
      {guidance && <section className={panel}><h2 className="font-semibold">Nội dung nguồn / tệp đã kiểm quyền</h2><pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-words text-sm">{guidance}</pre><button onClick={() => setGuidance("")}>Đóng nguồn</button></section>}
      {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && actor && <BaselineRecorder key={actor.user_id} measurement={measurement} />}
    </main>
  </AppShell>;
}
