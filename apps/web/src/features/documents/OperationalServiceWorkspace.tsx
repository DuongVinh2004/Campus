"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AppShell, type Role } from "@/components/AppShell";
import { ApiClient, ApiClientError } from "@/lib/api/client";
import { assistantClientId } from "@/lib/assistant-state-service";
import { ServiceCatalog } from "./ServiceCatalog";

type Kind = "STUDENT_CERTIFICATE" | "GRADE_APPEAL" | "GENERAL_SUPPORT";
type Form = { kind: Kind; purpose: string; recipient: string; course: string; reason: string };
type Draft = { id: string; version: number; form: Form; status: "DRAFT"; sent_to_university: false; updated_at: string };
type Preview = { preview_id: string; confirmation_token: string; expires_at: string; payload: { id: string; form: Form } };
type Pending = { preview_id: string; confirmation_token: string; client_id: string; confirmed: true };
const titles: Record<Kind, string> = { STUDENT_CERTIFICATE: "Giấy xác nhận sinh viên đang học", GRADE_APPEAL: "Phúc khảo kết quả học tập", GENERAL_SUPPORT: "Hỗ trợ thủ tục học vụ" };
const blank = (kind: Kind): Form => ({ kind, purpose: "", recipient: "", course: "", reason: "" });
const endpoint = "/v1/student-preparations";

export function OperationalServiceWorkspace({ history = false }: { history?: boolean }) {
  const [actor, setActor] = useState<{ display_name: string; roles: string[] } | null>(null);
  const [rows, setRows] = useState<Draft[]>([]), [selected, setSelected] = useState<Draft | null>(null);
  const [form, setForm] = useState<Form>(blank("GENERAL_SUPPORT"));
  const [editing, setEditing] = useState(false), [showHistory, setShowHistory] = useState(history);
  const [preview, setPreview] = useState<Preview | null>(null), [pending, setPending] = useState<Pending | null>(null);
  const [reviewed, setReviewed] = useState(false), [busy, setBusy] = useState(true), [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState(""), [notice, setNotice] = useState("");
  const [focusRequest, setFocusRequest] = useState(0);
  const formPanel = useRef<HTMLElement>(null);
  const student = actor?.roles.includes("STUDENT");
  const role: Role = actor?.roles.some(r => ["KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"].includes(r)) ? "admin" : actor ? "student" : "guest";
  const api = () => new ApiClient();

  useEffect(() => {
    if (editing) {
      formPanel.current?.scrollIntoView({ block: "start", behavior: "instant" });
      formPanel.current?.focus({ preventScroll: true });
    }
  }, [editing, selected?.id, focusRequest]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const user = await api().get<{ display_name: string; roles: string[] }>("/v1/users/me");
        if (!active) return;
        setActor(user);
        if (!user.roles.includes("STUDENT")) return;
        const result = await api().get<{ items: Draft[] }>(endpoint);
        if (!active) return;
        setRows(result.items);
        const params = new URLSearchParams(window.location.search);
        if (params.get("request")) {
          const draft = await api().get<Draft>(`${endpoint}/${encodeURIComponent(params.get("request")!)}`);
          if (!active) return;
          setSelected(draft); setForm(draft.form); setEditing(true); setShowHistory(true);
        } else if (params.has("new") || params.has("kind")) {
          const kind = params.has("new") ? "STUDENT_CERTIFICATE" : params.get("kind");
          if (kind && kind in titles) { setForm(blank(kind as Kind)); setEditing(true); }
        }
      } catch (e) { if (active) setError(e instanceof Error ? e.message : "Chưa đọc được hồ sơ"); }
      finally { if (active) setBusy(false); }
    })();
    return () => { active = false; };
  }, []);

  function choose(kind: Kind) {
    setSelected(null); setForm(blank(kind)); setEditing(true); setPreview(null); setPending(null); setReviewed(false); setError(""); setNotice("");
    window.history.replaceState(window.history.state, "", `${window.location.pathname}?kind=${kind}`);
  }
  function edit(patch: Partial<Form>) { setForm(current => ({ ...current, ...patch })); setPreview(null); setPending(null); setReviewed(false); setNotice(""); }
  async function prepare() {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api().post<Preview>(`${endpoint}/preview`, { form, document_id: selected?.id ?? null, expected_version: selected?.version ?? 0 });
      setPreview(result); setReviewed(false);
      setPending({ preview_id: result.preview_id, confirmation_token: result.confirmation_token, client_id: assistantClientId(), confirmed: true });
    } catch (e) { setError(e instanceof Error ? e.message : "Chưa xem trước được; nội dung được giữ"); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!pending || !reviewed) return;
    setBusy(true); setError("");
    try {
      const result = await api().post<{ effect: string; document: Draft; receipt_id: string }>(`${endpoint}/save`, pending);
      if (result.effect !== "draft_saved" || result.document.id !== preview?.payload.id || result.document.sent_to_university !== false) throw new Error("Chưa xác nhận được kết quả lưu");
      setSelected(result.document); setForm(result.document.form);
      setRows(current => [result.document, ...current.filter(r => r.id !== result.document.id)]);
      setPreview(null); setPending(null); setUncertain(false); setShowHistory(true);
      setNotice(`Đã lưu nháp · Biên nhận ${result.receipt_id}. Chưa gửi đến trường.`);
      window.history.replaceState(window.history.state, "", `${window.location.pathname}?request=${result.document.id}`);
    } catch (e) {
      setUncertain(!(e instanceof ApiClientError && e.problem.status >= 400 && e.problem.status < 500));
      setError(e instanceof Error ? e.message : "Chưa rõ kết quả lưu; đọc lại bằng cùng mã lưu");
    } finally { setBusy(false); }
  }

  return <AppShell activeNav={history ? "tickets" : "services"} userRole={role}>
    <div className="campus-workflow space-y-5">
      <header className="campus-page-heading"><div><h1 className="text-2xl font-semibold">{history ? "Hồ sơ của tôi" : "Dịch vụ học vụ"}</h1><p className="mt-2 text-sm">{actor?.display_name ? `${actor.display_name} · ` : ""}Dùng chung tài khoản, trợ lý và lịch sử trên Campus 24/7.</p></div></header>
      <p className="campus-panel text-sm" role="status">Bạn có thể chuẩn bị, xem trước và lưu nháp riêng tại đây. Chưa kết nối hệ thống tiếp nhận của HUCE, xác thực hồ sơ sinh viên hoặc dữ liệu điểm; chưa có yêu cầu nào từ trang này được gửi đến trường.</p>
      {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-800">{error} Nội dung đang soạn được giữ.</p>}
      {busy && <p role="status">Đang đọc hoặc lưu hồ sơ…</p>}
      {notice && <p role="status" className="rounded-xl bg-green-50 p-3 text-green-800">{notice}</p>}
      {!actor && !busy && <Link href="/login" className="fluent-btn-primary">Đăng nhập</Link>}
      {actor && !student && <p>Tài khoản này quản trị nguồn. <Link href="/knowledge/sources" className="underline">Mở quản trị nguồn</Link> hoặc <Link href="/login" className="underline">đăng nhập tài khoản sinh viên</Link> để chuẩn bị hồ sơ cá nhân.</p>}
      {!editing && history && !!student && <Link href="/services" className="fluent-btn-primary w-fit">Chuẩn bị thủ tục mới</Link>}
      {!editing && !history && <ServiceCatalog preparationOnly authenticated={!!student} onChoose={choose} onCertificate={() => choose("STUDENT_CERTIFICATE")} onHistory={() => setShowHistory(true)} />}
      {student && showHistory && <section className="campus-panel space-y-3"><h2 className="text-lg font-semibold">Nháp đã lưu của tôi</h2>{!rows.length && !busy && <p>Chưa có nháp đã lưu.</p>}<ul className="space-y-2">{rows.map(row => <li key={row.id}><button type="button" disabled={busy || uncertain} className="campus-record-option w-full rounded-xl border p-3 text-left" onClick={() => {
        setSelected(row); setForm(row.form); setEditing(true); setPreview(null); setPending(null); setReviewed(false); setNotice(""); setError("");
        setFocusRequest(value => value + 1);
        window.history.replaceState(window.history.state, "", `${window.location.pathname}?request=${row.id}`);
      }}><strong>{titles[row.form.kind]}</strong><span className="block truncate text-sm">{(row.form.reason.trim() || row.form.purpose).replace(/\s+/g, " ").trim().slice(0, 80)}</span><span className="block text-sm">Nháp · v{row.version} · Chưa gửi đến trường · {new Date(row.updated_at).toLocaleString("vi-VN")}</span></button></li>)}</ul></section>}
      {student && editing && <section ref={formPanel} tabIndex={-1} aria-label="Biểu mẫu nháp" className="campus-panel space-y-4">
        <button type="button" className="fluent-btn-secondary" disabled={busy || uncertain} onClick={() => { setEditing(false); setPreview(null); setPending(null); }}>{history ? "← Hồ sơ của tôi" : "← Danh mục dịch vụ"}</button>
        <h2 className="text-xl font-semibold">Chuẩn bị {titles[form.kind].toLocaleLowerCase("vi")}</h2>
        {selected && <p className="text-sm">Mã nháp {selected.id} · v{selected.version}</p>}
        {form.kind === "GRADE_APPEAL" && <p>Chưa có bảng điểm, điều kiện và hạn phúc khảo đã xác minh. Tên học phần bạn khai chỉ dùng trong nháp, chưa chứng minh đủ điều kiện nộp.</p>}
        {form.kind === "STUDENT_CERTIFICATE" && <p>Chưa xác thực tình trạng sinh viên với HUCE; bản nháp này không phải giấy xác nhận được cấp.</p>}
        <fieldset disabled={busy || uncertain} className="space-y-4">
          {form.kind === "STUDENT_CERTIFICATE" && <><label className="block">Mục đích sử dụng<input className="fluent-input mt-1 w-full" maxLength={2000} value={form.purpose} onChange={e => edit({ purpose: e.target.value })} /></label><label className="block">Đơn vị nhận<input className="fluent-input mt-1 w-full" maxLength={500} value={form.recipient} onChange={e => edit({ recipient: e.target.value })} /></label></>}
          {form.kind === "GRADE_APPEAL" && <label className="block">Học phần bạn muốn hỏi<input className="fluent-input mt-1 w-full" maxLength={500} value={form.course} onChange={e => edit({ course: e.target.value })} /></label>}
          <label className="block">Nội dung / lý do<textarea className="fluent-input mt-1 w-full" rows={5} maxLength={6000} value={form.reason} onChange={e => edit({ reason: e.target.value })} /></label>
          <button type="button" className="fluent-btn-primary" disabled={!form.reason.trim()} onClick={() => void prepare()}>Xem trước nháp</button>
        </fieldset>
        {preview && <section aria-label="Xem trước nháp" className="space-y-3 rounded-xl border p-4"><h3 className="font-semibold">Xem trước nội dung sẽ lưu</h3><p>{titles[preview.payload.form.kind]}</p>{preview.payload.form.purpose && <p>Mục đích: {preview.payload.form.purpose}</p>}{preview.payload.form.recipient && <p>Đơn vị nhận: {preview.payload.form.recipient}</p>}{preview.payload.form.course && <p>Học phần tự khai: {preview.payload.form.course}</p>}<p className="whitespace-pre-wrap">{preview.payload.form.reason}</p><p className="text-sm">Chỉ lưu nháp vào tài khoản của bạn. Chưa gửi đến cán bộ hoặc hệ thống trường.</p><label className="block"><input type="checkbox" checked={reviewed} disabled={busy || uncertain} onChange={e => setReviewed(e.target.checked)} /> Tôi đã xem nội dung nháp</label><button type="button" className="fluent-btn-primary" disabled={busy || !reviewed} onClick={() => void save()}>{uncertain ? "Đọc lại kết quả bằng cùng mã lưu" : "Lưu nháp đã xem"}</button></section>}
        <Link href="/chat" className="underline">Hỏi trợ lý về hướng dẫn và nguồn công khai</Link>
      </section>}
    </div>
  </AppShell>;
}
