"use client";
import { RefreshCw } from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";

import React, { useCallback, useEffect, useState } from "react";
import { FileAttachmentInput } from "../../components/shared/FileAttachmentInput";
import { DecisionSheet } from "../../components/shared/DecisionSheet";
import { RecordInventory } from "../../components/shared/RecordInventory";
import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { AuthLayout } from "../../components/AuthLayout";
import { AssistanceContextPanel } from "../assistance/AssistanceContextPanel";
import { StaffDraftEditor } from "../assistance/StaffDraftEditor";
import { CaseWorkflowPanel } from "../assistance/CaseWorkflowPanel";
import { CaseSupplementPanel } from "../assistance/CaseSupplementPanel";
import { StaffCaseInsights } from "../assistance/StaffCaseInsights";
import { CaseProjectionPanel } from "../assistance/CaseProjectionPanel";
import { StaffWorkspacePanel } from "../assistance/StaffWorkspacePanel";
import { StudentFieldHelp, MissingFields, formErrors, readTextAttachment } from "./StudentFieldHelp";
import type { ResourceRef } from "../../lib/unified-ai-contracts";
import { SERVICE_DEMO } from "../../lib/data/api/service-gateway";
import { ApiCertificateGateway, type CertificateActor, type CertificateRecord, type CertificateFormData,
  type CertificatePreview, type CertificateGuidance, type GuidanceSource } from "../../lib/data/api/certificate-gateway";

const gateway = new ApiCertificateGateway();
const emptyForm: CertificateFormData = { purpose: "", recipient: "", quantity: 1, delivery_method: "DIGITAL", attachments: [] };
const labels: Record<string, string> = { DRAFT: "Bản nháp", PENDING_CONFIRMATION: "Chờ xác nhận gửi", SUBMITTED: "Đã gửi",
  VALIDATING: "Đã tiếp nhận", PROCESSING: "Đang xử lý", WAITING_STUDENT: "Cần bổ sung", READY: "Có kết quả",
  REJECTED: "Đã từ chối", FULFILLED: "Đã nhận", CANCELLED: "Đã hủy" };
const panel = "campus-panel";
const input = "fluent-input w-full text-sm";

export function CertificateLogin() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [account, setAccount] = useState("");
  const login = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const user = await gateway.login(account.trim());
      window.location.assign(user.roles.some(role => role === "KNOWLEDGE_ADMIN" || role === "SYSTEM_ADMIN")
        ? SERVICE_DEMO ? "/knowledge/sources" : "/knowledge/policy-graph" : user.roles.includes("SUPPORT_OFFICER") ? SERVICE_DEMO ? "/services" : "/staff"
          : new URLSearchParams(window.location.search).get("next") === "/chat" ? "/chat" : SERVICE_DEMO ? "/services" : "/tickets");
    } catch (e) { setError(e instanceof Error ? e.message : "Không thể đăng nhập"); setBusy(false); }
  };
  return <AuthLayout>
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-[var(--text-primary)]">Đăng nhập</h1>
      <p className="my-2 text-xs text-[var(--text-secondary)]">Truy cập hồ sơ và các dịch vụ của bạn.</p>
      <form className="space-y-4" onSubmit={e => void login(e)}>
        <label className="block text-xs font-semibold text-[var(--text-secondary)]">Mã tài khoản<input required autoComplete="username" className={`${input} mt-1`} value={account} onChange={e => setAccount(e.target.value)} /></label>
        <button disabled={busy} className="fluent-btn-primary w-full text-sm font-semibold shadow-xs" type="submit">Đăng nhập</button>
      </form>
      {busy && <p role="status" className="text-xs text-[var(--text-secondary)]">Đang đăng nhập…</p>}
      {error && <p role="alert" className="rounded-xl border border-[var(--color-danger-subtle)] bg-[var(--surface-subtle)] p-3 text-xs text-[var(--color-danger)]">{error}</p>}
    </div>
  </AuthLayout>;
}

function FormFields({ form, onChange, disabled, resource, errors }: { form: CertificateFormData; onChange: React.Dispatch<React.SetStateAction<CertificateFormData>>; disabled: boolean; resource?: ResourceRef; errors: Record<string, string> }) {
  const [attachmentError, setAttachmentError] = useState("");
  const upload = async (file: File | undefined) => {
    if (!file) return;
    try { const attachment = await readTextAttachment(file, form.attachments.length); setAttachmentError(""); onChange(current => current.attachments.length < 3 ? { ...current, attachments: [...current.attachments, attachment] } : current); }
    catch (e) { setAttachmentError(e instanceof Error ? e.message : "Chưa đọc được tệp; bản nháp được giữ."); }
  };
  return <fieldset id="student-field-form" disabled={disabled} className="space-y-4">
    <label className="block text-sm">Mục đích xin giấy xác nhận<textarea id="student-field-purpose" aria-describedby="student-help-purpose" aria-invalid={!!errors.purpose} required maxLength={500} className={input} value={form.purpose}
      onChange={e => onChange({ ...form, purpose: e.target.value })} /></label>
    <StudentFieldHelp field="purpose" resource={resource} error={errors.purpose} hint="Nêu mục đích sử dụng theo thông tin của bạn." />
    <label className="block text-sm">Nơi nộp giấy xác nhận<input id="student-field-recipient" aria-describedby="student-help-recipient" aria-invalid={!!errors.recipient} required maxLength={200} className={input} value={form.recipient}
      onChange={e => onChange({ ...form, recipient: e.target.value })} /></label>
    <StudentFieldHelp field="recipient" resource={resource} error={errors.recipient} hint="Ghi đúng đơn vị nhận; trợ lý không tự suy nơi nộp." />
    <div className="flex flex-wrap gap-4"><label className="text-sm">Số bản<input type="number" min={1} max={3} className={input} value={form.quantity}
      onChange={e => onChange({ ...form, quantity: Number(e.target.value) })} /></label>
      <label className="text-sm">Cách nhận<select className={input} value={form.delivery_method} onChange={e => onChange({ ...form, delivery_method: e.target.value as "DIGITAL" | "PICKUP" })}>
        <option value="DIGITAL">Bản điện tử</option><option value="PICKUP">Nhận trực tiếp</option></select></label></div>
    <div><label htmlFor="student-field-attachments" className="block text-sm">Tệp đính kèm</label><FileAttachmentInput id="student-field-attachments" invalid={!!errors.attachments} disabled={disabled} onFile={file => void upload(file)} /></div>
    {form.attachments.map((a, i) => <p key={i} className="text-sm">{a.name} <button type="button" onClick={() => onChange({ ...form, attachments: form.attachments.filter((_, j) => j !== i) })}>Bỏ khỏi bản nháp</button></p>)}
    {attachmentError && <p role="alert">{attachmentError}</p>}
    <p className="text-xs">Chưa có OCR. Nội dung tệp là dữ liệu khai báo, không xác thực giấy tờ.</p>
  </fieldset>;
}

export function CertificateWorkspace({ staff = false, embedded = false }: { staff?: boolean; embedded?: boolean }) {
  const [actor, setActor] = useState<CertificateActor | null>(null);
  const [rows, setRows] = useState<CertificateRecord[]>([]);
  const [selected, setSelected] = useState<CertificateRecord | null>(null);
  const [form, setForm] = useState<CertificateFormData>(emptyForm);
  const [preview, setPreview] = useState<CertificatePreview | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [guidance, setGuidance] = useState<CertificateGuidance | null>(null);
  const [source, setSource] = useState<GuidanceSource | null>(null);
  const [result, setResult] = useState("");
  const [view, setView] = useState<"list" | "form">(embedded ? "form" : "list");
  const listScroll = React.useRef(0);
  const load = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const user = await gateway.me(); setActor(user);
      const [items, guide] = await Promise.all([gateway.list(staff), gateway.guidance()]);
      setRows(items); setGuidance(guide);
      const params = new URL(window.location.href).searchParams;
      const id = params.get("request");
      if (id || params.get("new") === "1") setView("form");
      if (id) { const r = await gateway.read(id, staff); setSelected(r); setForm(r.payload); }
    } catch (e) { setError(e instanceof Error ? e.message : "Không thể tải hồ sơ"); }
    finally { setBusy(false); }
  }, [staff]);
  useEffect(() => { void load(); }, [load]);
  const select = async (r: CertificateRecord) => {
    listScroll.current = window.scrollY;
    setView("form");
    setBusy(true); setError(""); setNotice(""); setPreview(null); setNote(""); setResult("");
    try { const latest = await gateway.read(r.id, staff); setSelected(latest); setForm(latest.payload);
      const url = new URL(window.location.href); url.searchParams.set("request", r.id);
      window.history.replaceState(window.history.state, "", url);
    }
    catch (e) { setError(e instanceof Error ? e.message : "Không thể mở hồ sơ"); }
    finally { setBusy(false); }
  };
  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError(""); setNotice(""); setFieldErrors({});
    try { await fn(); setRows(await gateway.list(staff)); }
    catch (e) { setFieldErrors(formErrors(e)); setError(`${e instanceof Error ? e.message : "Lỗi xử lý"}. Nội dung đang soạn được giữ. Nếu kết quả gửi chưa rõ, thử lại với cùng bản xem trước.`); }
    finally { setBusy(false); }
  };
  const save = () => run(async () => { const saved = await gateway.save(form, selected); setSelected(saved); setPreview(null); setNotice("Đã lưu bản nháp"); });
  const prepare = () => run(async () => {
    const saved = await gateway.save(form, selected); setSelected(saved);
    const p = await gateway.preview(saved); setSelected(p.document_request); setPreview(p);
  });
  const submit = () => run(async () => {
    if (!preview) throw new Error("Cần xem trước");
    const sent = await gateway.confirm(preview);
    const readback = await gateway.read(sent.document_request_id);
    setSelected(readback); setPreview(null);
    setNotice(`Đã gửi hồ sơ ${sent.document_request_id}`);
    const url = new URL(window.location.href); url.searchParams.set("request", sent.document_request_id);
    window.history.replaceState(window.history.state, "", url);
  });
  const act = (action: string) => run(async () => {
    if (!selected) return;
    const r = await gateway.act(selected, action, note, action === "supplement" ? form : undefined);
    setSelected(r); setForm(r.payload); setNote(""); setNotice("Đã cập nhật hồ sơ");
  });
  const editing = !staff && (!selected || ["DRAFT", "PENDING_CONFIRMATION", "WAITING_STUDENT"].includes(selected.status));
  const content = <div className={embedded ? "campus-workflow p-4 space-y-4" : "campus-workflow space-y-5"}>
    <div className="campus-page-heading"><div><h1 className="text-xl font-bold">{staff ? "Hàng đợi giấy xác nhận" : view === "list" ? "Hồ sơ của tôi" : "Xin giấy xác nhận sinh viên"}</h1>
      <p className="text-sm mt-1">Chuẩn bị hồ sơ, theo dõi xử lý và nhận kết quả.</p></div>
      <div className="flex flex-wrap gap-3 items-center text-sm">{!staff && view === "list" && <button type="button" className="fluent-btn-primary" disabled={busy} onClick={() => setView("form")}>Tạo yêu cầu mới</button>}<Link href="/chat">Hỏi hướng dẫn có nguồn</Link>{SERVICE_DEMO && <Link href="/services">Phúc khảo & hỗ trợ</Link>}<Link href="/login">Đổi tài khoản</Link>
        {actor && <button disabled={busy} onClick={() => void run(async () => { await gateway.logout(); window.location.assign("/login"); })}>Đăng xuất</button>}</div></div>
    {actor && <p className="text-sm">{actor.display_name} · {actor.roles.includes("SUPPORT_OFFICER") ? "Cán bộ" : "Sinh viên"}</p>}
    {busy && <p role="status">Đang tải hoặc xử lý…</p>}
    {error && <div role="alert" className="rounded-xl bg-red-50 text-red-800 p-3">{error} <button onClick={() => void load()}>Tải lại</button> · <Link href="/login">Đăng nhập</Link></div>}
    {notice && <p role="status" className="rounded-xl bg-green-50 text-green-800 p-3">{notice}</p>}
    {!embedded && <div hidden={view !== "list"}><RecordInventory busy={busy} selectedId={selected?.id} records={rows.map(record => ({ id: record.id, title: "Giấy xác nhận sinh viên", description: staff ? record.profile.display_name : record.payload.purpose, status: record.status, statusLabel: labels[record.status], updatedAt: record.history.at(-1)?.occurred_at, group: record.status === "WAITING_STUDENT" ? "waiting" as const : ["READY", "FULFILLED", "REJECTED", "CANCELLED"].includes(record.status) ? "completed" as const : "active" as const }))} onOpen={id => { const record = rows.find(record => record.id === id); if (record) void select(record); }} onCreate={staff ? undefined : () => setView("form")} /></div>}
    {!embedded && view === "form" && <button type="button" className="fluent-btn-secondary" onClick={() => { setView("list"); requestAnimationFrame(() => window.scrollTo({ top: listScroll.current })); }}>← {staff ? "Quay lại hàng đợi" : "Danh sách hồ sơ"}</button>}
    {guidance && <details className={panel}><summary className="font-semibold cursor-pointer">Hướng dẫn và căn cứ công khai</summary><p className="text-sm my-3">{guidance.summary}</p>
      <p className="text-sm">Biểu mẫu, lệ phí và thời gian trả kết quả được xác định theo hướng dẫn của đơn vị tiếp nhận.</p><div className="flex gap-4 mt-3">{guidance.sources.map(s => <button key={s.id} onClick={() => void run(async () => setSource(await gateway.source(s.id)))}>{s.locator} — mở nguồn</button>)}</div></details>}
    {source && <section className={panel}><h2 className="font-semibold">{source.title} · {source.locator}</h2><a href={source.url} target="_blank" rel="noreferrer" className="text-blue-600">Trang phát hành nguồn</a>
      <pre className="whitespace-pre-wrap max-h-80 overflow-auto text-xs mt-3">{source.content_text}</pre><button onClick={() => setSource(null)}>Đóng nguồn</button></section>}
    {actor && view === "form" && <div className={`campus-workflow-grid ${staff ? "" : "campus-form-layout"}`}><aside className={panel}><div className="flex justify-between"><h2 className="font-bold">{staff ? "Hồ sơ đã gửi" : "Hồ sơ của tôi"}</h2><IconButton label="Làm mới" variant="outline" disabled={busy} onClick={() => void load()} icon={<RefreshCw size={18} />} /></div>
      {!staff && <button disabled={busy} className="fluent-btn-primary mt-3 w-full" onClick={() => { setSelected(null); setForm(emptyForm); setPreview(null); setResult(""); setNote(""); setNotice(""); window.history.replaceState(window.history.state, "", window.location.pathname); }}>Chuẩn bị hồ sơ mới</button>}
      {rows.length === 0 && !busy && <p className="text-sm mt-4">Chưa có hồ sơ.</p>}
      <ul className="space-y-3 mt-4">{rows.map(r => <li key={r.id}><button disabled={busy} onClick={() => void select(r)} aria-pressed={selected?.id === r.id} className="campus-record-option text-left w-full rounded-lg border p-3 text-sm">
        <strong>{r.id.slice(-8).toUpperCase()}</strong><span className="block">{labels[r.status]}</span>{staff && <span>{r.profile.display_name}</span>}</button></li>)}</ul></aside>
      <section className={panel}><h2 className="font-bold mb-3">{selected ? `Hồ sơ ${selected.id}` : staff ? "Chọn hồ sơ trong hàng đợi" : "Chuẩn bị bản nháp"}</h2>
        {selected && <p className="text-sm mb-3">Trạng thái: {labels[selected.status]}</p>}
        {selected && process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && <AssistanceContextPanel id={selected.id} version={selected.version} surface="certificate" />}
        <section className="campus-student-profile" aria-label="Thông tin sinh viên"><strong>Thông tin sinh viên</strong><dl><div><dt>Họ và tên</dt><dd>{(selected?.profile || actor.profile)?.display_name || "Chưa có thông tin"}</dd></div><div><dt>Mã sinh viên</dt><dd>{(selected?.profile || actor.profile)?.student_code || "Chưa có thông tin"}</dd></div><div><dt>Chương trình đào tạo</dt><dd>{(selected?.profile || actor.profile)?.program_code || "Chưa có thông tin"}</dd></div></dl></section>
        <MissingFields errors={fieldErrors} />
        {!staff && editing && <ol className="campus-stepper mb-5" aria-label="Tiến trình hồ sơ"><li aria-current={!preview ? "step" : undefined}><span>1</span>Điền thông tin</li><li aria-current={preview ? "step" : undefined}><span>2</span>Xem trước & xác nhận</li><li><span>3</span>Kết quả</li></ol>}
        {!preview && editing && <form onSubmit={e => { e.preventDefault(); void prepare(); }}><FormFields form={form} onChange={setForm} disabled={busy} errors={fieldErrors} resource={selected ? { kind: "certificate_request", id: selected.id, expected_version: selected.version } : undefined} />
          {selected?.status === "WAITING_STUDENT" ? <div className="mt-4 space-y-3"><p>Yêu cầu bổ sung: {selected.supplement_request}</p>
            <label className="block text-sm">Nội dung bổ sung<textarea className={input} value={note} onChange={e => setNote(e.target.value)} /></label>
            <button type="button" disabled={busy || !note.trim()} className="fluent-btn-primary" onClick={() => void act("supplement")}>Xác nhận gửi bổ sung</button></div>
            : <div className="flex flex-wrap gap-3 mt-5"><button type="button" disabled={busy} className="fluent-btn-secondary" onClick={() => void save()}>Lưu bản nháp</button>
              <button type="submit" disabled={busy} className="fluent-btn-primary">Xem trước hồ sơ</button>
              {selected?.status === "PENDING_CONFIRMATION" && <button type="button" disabled={busy} onClick={() => void run(async () => setPreview(await gateway.resume(selected.id)))}>Tiếp tục xác nhận đang chờ</button>}</div>}</form>}
        {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && !staff && selected?.status === "WAITING_STUDENT" &&
          <CaseSupplementPanel key={`supplement:${actor?.user_id}:${selected.id}`} resource={{ kind: "certificate_request", id: selected.id, expected_version: selected.version }} onCommitted={async () => {
            const latest = await gateway.read(selected.id); setSelected(latest); setForm(latest.payload); setRows(await gateway.list(false));
          }} />}
        {preview && <div className="space-y-4"><h3 className="font-bold">Xem trước — chưa gửi</h3><dl className="text-sm space-y-2"><dt>Mục đích</dt><dd>{preview.document_request.payload.purpose}</dd>
          <dt>Nơi nộp</dt><dd>{preview.document_request.payload.recipient}</dd><dt>Số bản / cách nhận</dt><dd>{preview.document_request.payload.quantity} / {preview.document_request.payload.delivery_method}</dd>
          <dt>Tệp đính kèm</dt><dd>{preview.document_request.payload.attachments.map(a => a.name).join(", ") || "Không có"}</dd></dl>
          <p className="text-sm">Xác nhận trước: {new Date(preview.expires_at).toLocaleString("vi-VN")}</p>
          <div className="flex gap-3"><button disabled={busy} onClick={() => setPreview(null)}>Quay lại sửa</button><button disabled={busy} className="fluent-btn-primary" onClick={() => void submit()}>Xác nhận gửi hồ sơ</button></div></div>}
        {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && staff && <StaffCaseInsights key={actor?.user_id} kind="certificate_request" onCommitted={async () => {
          setRows(await gateway.list(true)); if (selected) setSelected(await gateway.read(selected.id, true));
        }} />}
        {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && selected && <CaseProjectionPanel key={`projection:${actor?.user_id}:${selected.id}`} resource={{ kind: "certificate_request", id: selected.id, expected_version: selected.version }} />}
        {selected && !editing && <dl className="text-sm space-y-3"><dt>Mục đích</dt><dd>{selected.payload.purpose}</dd><dt>Nơi nộp</dt><dd>{selected.payload.recipient}</dd>
          <dt>Tệp đính kèm</dt><dd>{selected.payload.attachments.map((a, i) => <details key={i}><summary>{a.name}</summary><pre className="whitespace-pre-wrap">{a.content}</pre></details>)}</dd></dl>}
        {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && staff && selected && actor &&
          <StaffWorkspacePanel key={`dossier:${actor.user_id}:${selected.id}`} actorId={actor.user_id} studentId={selected.student_user_id}
            resource={{ kind: "certificate_request", id: selected.id, expected_version: selected.version }} />}
        {process.env.NEXT_PUBLIC_UNIFIED_DURABLE_DRAFTS === "true" && staff && selected && actor && selected.assigned_user_id === actor.user_id &&
          <StaffDraftEditor key={`private-draft:${actor.user_id}:${selected.id}`} actorId={actor.user_id}
            resource={{ kind: "certificate_request", id: selected.id, expected_version: selected.version }} onUse={setNote} />}
        {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && staff && selected && actor && selected.assigned_user_id === actor.user_id &&
          <CaseWorkflowPanel key={`case-workflow:${actor.user_id}:${selected.id}`} studentId={selected.student_user_id}
            resource={{ kind: "certificate_request", id: selected.id, expected_version: selected.version }} onCommitted={async () => {
              const latest = await gateway.read(selected.id, true); setSelected(latest); setRows(await gateway.list(true));
            }} />}
        {staff && selected && <DecisionSheet busy={busy} version={selected.version}><div className="space-y-3"><label className="block text-sm">Lý do / yêu cầu bổ sung<textarea className={input} maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></label>
          <div className="flex flex-wrap gap-3">{selected.status === "SUBMITTED" && <button disabled={busy} className="fluent-btn-primary" onClick={() => void act("accept")}>Tiếp nhận</button>}
            {["VALIDATING", "PROCESSING"].includes(selected.status) && <><button disabled={busy || !note.trim()} onClick={() => void act("request_supplement")}>Yêu cầu bổ sung</button>
              <button disabled={busy || !note.trim()} className="fluent-btn-primary" onClick={() => void act("approve")}>Duyệt và cấp giấy xác nhận</button><button disabled={busy || !note.trim()} onClick={() => void act("reject")}>Từ chối có lý do</button></>}</div></div></DecisionSheet>}
        {selected?.result && <button disabled={busy} className="fluent-btn-primary mt-5" onClick={() => void run(async () => setResult(await gateway.result(selected.id)))}>Xem kết quả</button>}
        {result && <iframe title="Giấy xác nhận sinh viên" sandbox="" srcDoc={result} className="mt-4 w-full min-h-[600px] border rounded-xl" />}
        {selected && <details open className="mt-6"><summary className="font-bold">Lịch sử xử lý</summary><ol className="text-sm space-y-3 mt-3">{selected.history.map(e => <li key={e.id}>
          {new Date(e.occurred_at).toLocaleString("vi-VN")} · {labels[e.status]} · {e.actor_role === "SUPPORT_OFFICER" ? "Cán bộ" : "Sinh viên"}{e.note && <p>{e.note}</p>}</li>)}</ol></details>}
      </section></div>}
  </div>;
  return embedded ? content : <AppShell activeNav={staff ? "staff" : "tickets"} userRole={staff ? "staff" : "student"}>{content}</AppShell>;
}
