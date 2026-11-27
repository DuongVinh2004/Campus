"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, FileUp, Loader2, RefreshCw, ShieldCheck, XCircle } from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";

const base = "/v1/knowledge/platform/documents";
const ATTEST = "Tôi xác nhận đây là văn bản chính thức, đúng nguồn và đúng phạm vi áp dụng.";
const STEPS = ["PROCESSING", "AWAITING_REVIEW", "READY_TO_PUBLISH", "INDEXING", "ACTIVE"] as const;
const STEP_LABELS: Record<string, string> = { PROCESSING: "Xử lý", AWAITING_REVIEW: "Duyệt", READY_TO_PUBLISH: "Phát hành", INDEXING: "Cập nhật chatbot", ACTIVE: "Dùng được" };

type Check = { name: string; label: string; ok: boolean; detail: string };
export type PipelineItem = {
  version_id: string; title: string; filename: string; canonical_uri: string; mode: "DIRECT" | "REVIEW"; origin: string; state: string; label: string;
  flags: string[]; checks: Check[]; error_code: string | null; error_detail: string | null; created_at: string; state_changed_at: string;
  usable_at: string | null; effective_from: string | null; review_note: string | null; can_approve: boolean; can_retry: boolean; can_reject: boolean; can_revoke?: boolean;
};
type Listing = { items: PipelineItem[]; generation: number; can_publish_directly: boolean };

async function call(path: string, init: RequestInit = {}) {
  const response = await fetch(path, { ...init, credentials: "include", cache: "no-store" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : response.status === 403 ? "Tài khoản không có quyền thực hiện thao tác này."
      : response.status === 401 ? "Cần đăng nhập lại." : `Không thể thực hiện (${response.status}).`);
  }
  return response;
}

const when = (value: string | null) => value ? new Date(value).toLocaleString("vi-VN") : "—";

export function KnowledgeDocuments() {
  const [listing, setListing] = useState<Listing | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [direct, setDirect] = useState(true);
  const [attested, setAttested] = useState(false);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const key = useRef<string | null>(null);

  const load = useCallback(async () => {
    try { setListing(await (await call(base)).json()); setError(""); }
    catch (failure) { setError((failure as Error).message); }
  }, []);
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => { if (!document.hidden) void load(); }, 5000);
    return () => window.clearInterval(timer);
  }, [load]);

  const canDirect = !!listing?.can_publish_directly;
  const publishDirectly = canDirect && direct;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget; const data = new FormData(form);
    const file = (form.elements.namedItem("file") as HTMLInputElement).files?.[0];
    const problems: Array<[string, string]> = [];
    if (String(data.get("title") ?? "").trim().length < 3) problems.push(["title", "Tên tài liệu cần ít nhất 3 ký tự."]);
    if (String(data.get("owner_unit") ?? "").trim().length < 2) problems.push(["owner_unit", "Nhập đơn vị ban hành."]);
    if (!/^https:\/\/\S+$/.test(String(data.get("canonical_uri") ?? "").trim())) problems.push(["canonical_uri", "Địa chỉ nguồn phải bắt đầu bằng https://."]);
    if (!file?.size || file.size > 50 * 1024 * 1024) problems.push(["file", "Chọn tệp PDF hoặc TXT có nội dung, tối đa 50 MB."]);
    if (problems.length) {
      setNotice(""); setError(problems.map(([, message]) => message).join(" "));
      (form.elements.namedItem(problems[0][0]) as HTMLElement | null)?.focus();
      return;
    }
    if (!file) return;
    if (publishDirectly && !attested) { setError("Cần tick xác nhận văn bản chính thức trước khi đăng."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      const metadata = { title: data.get("title"), owner_unit: data.get("owner_unit"), canonical_uri: data.get("canonical_uri"),
        programs: ["PUBLIC"], audiences: ["STUDENT", "KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"],
        effective_from: data.get("effective_from") ? new Date(String(data.get("effective_from"))).toISOString() : null,
        ...(publishDirectly ? { publish_directly: true, attested: true } : {}) };
      const payload = new FormData(); payload.append("metadata", JSON.stringify(metadata)); payload.append("file", file);
      key.current ||= crypto.randomUUID();
      const result = await (await call(base, { method: "POST", body: payload, headers: { "Idempotency-Key": key.current } })).json();
      key.current = null; form.reset(); setAttested(false);
      setNotice(result.mode === "DIRECT" ? "Đã nhận. Hệ thống tự xử lý, phát hành và cập nhật chatbot; theo dõi tiến độ bên dưới."
        : "Đã gửi duyệt. Sau khi người duyệt bấm Duyệt, hệ thống tự phát hành và cập nhật chatbot.");
      await load();
    } catch (failure) { setError((failure as Error).message); } finally { setBusy(false); }
  }

  async function act(item: PipelineItem, action: "approve" | "reject" | "retry" | "revoke") {
    const note = (notes[item.version_id] || "").trim();
    if ((action === "reject" || action === "revoke") && note.length < 5) { setError(action === "revoke" ? "Nhập lý do thu hồi (ít nhất 5 ký tự)." : "Nhập lý do từ chối (ít nhất 5 ký tự)."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await call(`${base}/${item.version_id}/${action}`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
        body: action === "retry" ? undefined : JSON.stringify({ note: note || null }) });
      setNotice(action === "approve" ? "Đã duyệt. Hệ thống tự phát hành và cập nhật chatbot." : action === "reject" ? "Đã từ chối tài liệu."
        : action === "revoke" ? "Đã thu hồi: chatbot không dùng tài liệu này nữa (có hiệu lực ngay)." : "Đã thử lại.");
      await load();
    } catch (failure) { setError((failure as Error).message); } finally { setBusy(false); }
  }

  return <div className="space-y-6" data-testid="knowledge-documents">
    <form noValidate className="campus-panel space-y-4" onSubmit={submit} onChange={() => { key.current = null; }}>
      <h2 className="font-semibold">Thêm tài liệu</h2>
      <fieldset disabled={busy} className="grid gap-4 md:grid-cols-2">
        <label>Tên tài liệu<input name="title" className="fluent-input w-full" required minLength={3} maxLength={300} /></label>
        <label>Đơn vị ban hành<input name="owner_unit" className="fluent-input w-full" required minLength={2} maxLength={160} /></label>
        <label>Địa chỉ nguồn (URI)<input name="canonical_uri" className="fluent-input w-full" required pattern="https://.*" placeholder="https://…huce.edu.vn/…" title="Địa chỉ nguồn phải bắt đầu bằng https://" /></label>
        <label>Bắt đầu hiệu lực (để trống = ngay)<input name="effective_from" type="datetime-local" className="fluent-input w-full" /></label>
        <label className="md:col-span-2">Tệp PDF hoặc TXT (UTF-8)<input name="file" type="file" accept=".pdf,.txt" required className="block mt-2" /></label>
        {canDirect && <div className="md:col-span-2 space-y-2" role="group" aria-label="Cách đưa tài liệu vào hệ thống">
          <label className="flex items-center gap-2"><input type="radio" name="mode" checked={direct} onChange={() => setDirect(true)} />Đăng trực tiếp — hệ thống tự phát hành, không cần người duyệt</label>
          <label className="flex items-center gap-2"><input type="radio" name="mode" checked={!direct} onChange={() => setDirect(false)} />Gửi duyệt — chờ một quản trị viên khác duyệt</label>
        </div>}
        {publishDirectly && <label className="md:col-span-2 flex items-start gap-2"><input type="checkbox" checked={attested} onChange={event => setAttested(event.target.checked)} /><span>{ATTEST}</span></label>}
        <p className="text-sm md:col-span-2"><ShieldCheck size={14} className="inline" aria-hidden="true" /> {publishDirectly
          ? "Sau khi bấm Đăng, hệ thống tự kiểm tra, phát hành và cập nhật chatbot (khoảng 1–2 phút). Bạn có thể thu hồi bất cứ lúc nào."
          : "Tài liệu cần một người duyệt khác bạn. Sau khi họ bấm Duyệt, mọi bước còn lại tự chạy."}</p>
        <button type="submit" className="fluent-btn-primary" disabled={busy || (publishDirectly && !attested)}>
          {busy ? "Đang gửi…" : publishDirectly ? "Đăng" : "Gửi duyệt"}</button>
      </fieldset>
    </form>
    {error && <p role="alert" className="rounded-xl border p-3 text-sm text-[var(--color-danger)]">{error}</p>}
    {notice && <p role="status" className="rounded-xl border p-3 text-sm">{notice}</p>}
    <section className="campus-panel space-y-3" aria-label="Tiến độ tài liệu">
      <div className="flex items-center justify-between"><h2 className="font-semibold">Tiến độ tài liệu</h2>
        <IconButton label="Làm mới" variant="outline" onClick={() => void load()} icon={<RefreshCw size={18} />} /></div>
      {!listing ? <p className="text-sm">Đang tải…</p> : !listing.items.length ? <p className="text-sm">Chưa có tài liệu nào được thêm qua trang này. Tài liệu bạn thêm sẽ hiện ở đây.</p>
        : <ul className="space-y-3">{listing.items.map(item => <li key={item.version_id} className="rounded-xl border p-4 space-y-2" data-state={item.state}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div><p className="font-semibold">{item.title}</p><p className="text-xs break-all">{item.filename} · {item.canonical_uri}</p></div>
            <StateBadge item={item} />
          </div>
          <ol className="flex flex-wrap gap-2 text-xs" aria-label="Các bước">{(item.mode === "DIRECT" ? STEPS.filter(step => step !== "AWAITING_REVIEW") : STEPS).map(step => {
            const reached = stepIndex(item.state, item.mode) >= stepIndex(step, item.mode) && item.state !== "NEEDS_ATTENTION" && item.state !== "REJECTED";
            return <li key={step} aria-current={item.state === step ? "step" : undefined} className={reached ? "font-semibold" : "opacity-60"}>{reached ? "● " : "○ "}{STEP_LABELS[step]}</li>;
          })}</ol>
          {item.state === "ACTIVE" && <p className="text-xs">Chatbot dùng được từ {when(item.usable_at)}.</p>}
          {item.state === "WAITING_EFFECTIVE" && <p className="text-xs">Sẽ tự phát hành khi tới ngày hiệu lực: {when(item.effective_from)}.</p>}
          {item.state === "INDEXING" && <p className="text-xs">Đã phát hành; đang cập nhật chỉ mục để chatbot trả lời được (thường dưới 2 phút).</p>}
          {item.flags.includes("EFFECTIVE_FROM_ASSUMED") && <p className="text-xs">Ngày hiệu lực chưa nhập: lấy là lúc thêm tài liệu. Người duyệt cần xác nhận.</p>}
          {!!item.checks.length && <details><summary className="cursor-pointer text-xs">Kết quả kiểm tra tự động</summary><ul className="mt-1 text-xs">{item.checks.map(check => <li key={check.name}>{check.ok ? "✓" : "✗"} {check.label}{check.detail ? ` — ${check.detail}` : ""}</li>)}</ul></details>}
          {item.state === "NEEDS_ATTENTION" && <p role="alert" className="text-xs text-[var(--color-danger)]"><AlertTriangle size={12} className="inline" aria-hidden="true" /> {item.error_detail || item.error_code}</p>}
          {item.review_note && <p className="text-xs">Ghi chú duyệt: {item.review_note}</p>}
          {(item.can_approve || item.can_reject || item.can_retry || item.can_revoke) && <div className="flex flex-wrap items-center gap-2">
            {(item.can_approve || item.can_reject || item.can_revoke) && <input aria-label={`Ghi chú cho ${item.title}`} className="fluent-input flex-1 min-w-48" placeholder={item.can_revoke ? "Lý do thu hồi (bắt buộc)" : "Ghi chú (bắt buộc khi từ chối)"}
              value={notes[item.version_id] || ""} onChange={event => setNotes(previous => ({ ...previous, [item.version_id]: event.target.value }))} />}
            {item.can_approve && <button type="button" className="fluent-btn-primary" disabled={busy} onClick={() => void act(item, "approve")}>Duyệt</button>}
            {item.can_reject && <button type="button" className="fluent-btn-secondary" disabled={busy} onClick={() => void act(item, "reject")}>Từ chối</button>}
            {item.can_retry && <button type="button" className="fluent-btn-secondary" disabled={busy} onClick={() => void act(item, "retry")}>Thử lại</button>}
            {item.can_revoke && <button type="button" className="fluent-btn-secondary" disabled={busy} onClick={() => void act(item, "revoke")}>Thu hồi</button>}
          </div>}
        </li>)}</ul>}
    </section>
  </div>;
}

function stepIndex(state: string, mode: string) {
  const steps = mode === "DIRECT" ? STEPS.filter(step => step !== "AWAITING_REVIEW") : STEPS;
  const mapped = state === "WAITING_EFFECTIVE" ? "READY_TO_PUBLISH" : state;
  return (steps as readonly string[]).indexOf(mapped);
}

function StateBadge({ item }: { item: PipelineItem }) {
  const Icon = item.state === "ACTIVE" ? CheckCircle2 : item.state === "NEEDS_ATTENTION" ? AlertTriangle : item.state === "REJECTED" ? XCircle
    : item.state === "AWAITING_REVIEW" || item.state === "WAITING_EFFECTIVE" ? Clock3 : Loader2;
  return <span className="inline-flex items-center gap-1 text-sm font-semibold"><Icon size={16} aria-hidden="true" /><FileUp size={0} aria-hidden="true" />{item.label}</span>;
}
