"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import { useEffect, useRef, useState } from "react";
import { ApiClient } from "../../lib/api/client";
import { assistantClientId } from "../../lib/assistant-state-service";
import type { ResourceRef } from "../../lib/unified-ai-contracts";

const api = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });
interface Dossier { binding_hash: string; workflow_version: string; sources: Array<{ id: string; locator: string }>; findings: Array<{ id: string; label: string; source_ids: string[]; state: string }> }
interface Rules { template: { version: string; outcomes: string[] } | null }
interface Preview { preview_id: string; confirmation_token: string; client_id: string; public: unknown; internal: unknown }
interface Supplement { id: string; criterion_id: string; source_ids: string[]; field: string; public_reason: string; accepted_format: string }
interface Handover { done: string[]; open: string[]; evidence_ids: string[]; next_action: string; visibility: "internal" | "public"; target_actor: string; target_queue: string }
interface Saved { version: number; body: { public_reasons: string[]; internal_note: string; operation: string; outcome: string; fact_source_ids: string[]; supplement_items: Supplement[]; handover: Handover | null } }

export function CaseWorkflowPanel({ resource, studentId, onCommitted }: { resource: ResourceRef; studentId: string; onCommitted: () => Promise<void> }) {
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [rules, setRules] = useState<Rules | null>(null);
  const [version, setVersion] = useState(0);
  const [operation, setOperation] = useState("respond");
  const [outcome, setOutcome] = useState("");
  const [reason, setReason] = useState("");
  const [internal, setInternal] = useState("");
  const [sources, setSources] = useState<string[]>([]);
  const [supplements, setSupplements] = useState<Supplement[]>([]);
  const [handover, setHandover] = useState<Handover>({ done: [], open: [], evidence_ids: [], next_action: "", visibility: "internal", target_actor: "", target_queue: "" });
  const [directory, setDirectory] = useState<Array<{ user_id: string; display_name: string; queues: string[] }>>([]);
  const [p, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const pending = useRef<{ body: object; id: string } | null>(null);
  const context = `${resource.kind}:${resource.id}:${resource.expected_version}`;
  const current = useRef(context); current.current = context;

  useEffect(() => {
    let cancelled = false;
    setDossier(null); setRules(null); setPreview(null);
    void Promise.all([
      api().post<Dossier>("/v1/assistant/staff-workspace/read", { resource }),
      api().post<Rules>("/v1/assistant/workflows/resolve", { resource }),
      api().post<{ draft: Saved | null; binding_stale: boolean }>("/v1/assistant/cases/draft:read", { resource }),
    ]).then(([d, r, saved]) => {
      if (cancelled) return;
      setDossier(d); setRules(r); setVersion(saved.draft?.version || 0);
      if (saved.draft && !pending.current) {
        const b = saved.draft.body; setReason(b.public_reasons.join("\n")); setInternal(b.internal_note);
        setOperation(b.operation); setOutcome(b.outcome); setSources(b.fact_source_ids);
        setSupplements(b.supplement_items); if (b.handover) setHandover(b.handover);
      } else if (!saved.draft) setOperation(resource.kind === "certificate_request" ? "approve" : "respond");
      if (saved.binding_stale) setMessage("Nháp được giữ. Hồ sơ/nguồn đã đổi; đối chiếu rồi lưu phiên bản mới trước khi xem trước.");
    }).catch(e => { if (!cancelled) setMessage(e instanceof Error ? e.message : "Chưa đọc được dữ liệu; giữ nháp."); });
    return () => { cancelled = true; };
  }, [context]);

  useEffect(() => {
    if (operation !== "transfer") return;
    let cancelled = false;
    void api().get<{ items: typeof directory }>("/v1/service-staff-directory").then(v => { if (!cancelled) setDirectory(v.items); }).catch(e => { if (!cancelled) setMessage(String(e)); });
    return () => { cancelled = true; };
  }, [operation]);

  async function run(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setMessage(""); const started = context;
    try { await work(); } catch (e) { if (current.current === started) setMessage(`${e instanceof Error ? e.message : "Chưa hoàn tất"}. Nội dung được giữ.`); }
    finally { if (current.current === started) setBusy(false); }
  }
  async function save() {
    if (!dossier || !rules?.template) throw new Error("Cần nguồn và mẫu đã đối chiếu");
    const body = { resource, expected_draft_version: version, student_id: studentId, recipient_id: studentId,
      operation, outcome: operation === "respond" ? "RESPONDED" : operation === "request_supplement" ? "SUPPLEMENT_REQUIRED" : operation === "transfer" ? "TRANSFERRED" : outcome, fact_source_ids: sources,
      public_reasons: reason.split("\n").filter(s => s.trim()), internal_note: internal,
      supplement_items: operation === "request_supplement" ? supplements : [], handover: operation === "transfer" ? { ...handover, evidence_ids: sources } : null,
      workflow_version: dossier.workflow_version, template_version: rules.template.version, binding_hash: dossier.binding_hash };
    const intent = pending.current || { body, id: assistantClientId() }; pending.current = intent;
    const saved = await api().post<{ version: number }>("/v1/assistant/cases/draft:prepare", { ...intent.body, client_id: intent.id });
    const latest = await api().post<{ draft: Saved | null }>("/v1/assistant/cases/draft:read", { resource });
    if (latest.draft?.version !== saved.version) throw new Error("Nháp server đã đổi; đọc lại trước khi dùng");
    setVersion(saved.version); pending.current = null; setPreview(null); setMessage(`Đã lưu nháp có cấu trúc v${saved.version}; chưa thực hiện nghiệp vụ.`);
  }
  async function confirm() {
    if (!p) return;
    // A read receipt precedes every retry, including after an interrupted reply.
    const read = await api().post<{ receipt: { state: string } | null }>("/v1/assistant/cases/receipt:read", { client_id: p.client_id });
    if (!read.receipt) await api().post("/v1/assistant/cases:confirm", { preview_id: p.preview_id, confirmation_token: p.confirmation_token, client_id: p.client_id, confirmed: true });
    const receipt = await api().post<{ receipt: { state: string } | null }>("/v1/assistant/cases/receipt:read", { client_id: p.client_id });
    if (receipt.receipt?.state !== "committed") throw new Error("Chưa xác minh receipt; đọc lại trước khi thử tiếp");
    setMessage("Đã ghi nghiệp vụ và receipt. Đang đọc lại hồ sơ."); setPreview(null); await onCommitted();
  }
  return <section className="my-4 space-y-3 rounded-xl border p-4" aria-label="Dự thảo kết quả có kiểm chứng">
    <h3 className="font-semibold">Dự thảo phản hồi / kết quả</h3>
    <p className="text-sm">Nguồn và mẫu local/synthetic. Cán bộ hoàn thành review, đọc bản công khai và xác nhận trước khi thực hiện.</p>
    <fieldset disabled={busy || !!p} className="space-y-3">
      <label className="block">Thao tác<select value={operation} onChange={e => { setOperation(e.target.value); setOutcome(""); }}>
        {resource.kind === "service_request" ? <><option value="respond">Trả lời</option><option value="resolve">Trả kết quả</option><option value="transfer">Bàn giao</option></> : <option value="approve">Duyệt giấy mô phỏng</option>}
        <option value="request_supplement">Yêu cầu bổ sung có item</option>
        <option value="reject">Từ chối có lý do</option></select></label>
      {["approve", "resolve", "reject"].includes(operation) && <label className="block">Kết luận cán bộ<select value={outcome} onChange={e => setOutcome(e.target.value)}><option value="">Chọn kết luận</option>
        {rules?.template?.outcomes.filter(v => operation === "reject" ? v === "REJECTED" : v !== "REJECTED").map(v => <option key={v}>{v}</option>)}</select></label>}
      {operation === "request_supplement" && <div className="space-y-3"><p>Nhóm các mục đã biết thiếu vào cùng yêu cầu. Mỗi mục có tiêu chí, nguồn, lý do và định dạng.</p>
        {dossier?.findings.filter(f => f.source_ids.length).map(f => <button type="button" key={f.id} onClick={() => setSupplements(items => [...items, { id: `item-${items.length + 1}`, criterion_id: f.id, source_ids: f.source_ids, field: resource.kind === "service_request" ? "reason" : "purpose", public_reason: "", accepted_format: "text" }])}>Thêm mục · {f.label}</button>)}
        {supplements.map((s, index) => <div key={s.id} className="rounded border p-2"><p>{s.id} · {s.criterion_id} · {s.source_ids.join(", ")}</p>
          <label>Trường<select value={s.field} onChange={e => { const field = e.target.value; const format: Record<string, string> = { attachments: "text/plain", course_record_id: "course_reference", quantity: "integer", delivery_method: "delivery_method", contact_preference: "contact_preference" }; setSupplements(items => items.map((v, i) => i === index ? { ...v, field, accepted_format: format[field] || "text" } : v)); }}>
            {(resource.kind === "service_request" ? ["reason", "attachments", "course_record_id", "contact_preference"] : ["purpose", "recipient", "quantity", "delivery_method", "attachments"]).map(field => <option key={field}>{field}</option>)}</select></label>
          <label>Lý do công khai<input maxLength={500} value={s.public_reason} onChange={e => setSupplements(items => items.map((v, i) => i === index ? { ...v, public_reason: e.target.value } : v))} /></label><p>Định dạng: {s.accepted_format}</p>
          <button type="button" onClick={() => setSupplements(items => items.filter((_, i) => i !== index))}>Bỏ khỏi nháp yêu cầu</button></div>)}</div>}
      {operation === "transfer" && <div className="space-y-3"><p>Chọn thông tin được bàn giao; không hứa thời hạn chưa xác minh.</p>
        <label className="block">Người nhận<select value={handover.target_actor} onChange={e => { const entry = directory.find(v => v.user_id === e.target.value); setHandover({ ...handover, target_actor: e.target.value, target_queue: entry?.queues[0] || "" }); }}><option value="">Chọn cán bộ và queue được cấp</option>{directory.map(v => <option key={v.user_id} value={v.user_id}>{v.display_name} · {v.queues.join(", ")}</option>)}</select></label>
        <label className="block">Đã làm<textarea maxLength={1500} value={handover.done.join("\n")} onChange={e => setHandover({ ...handover, done: e.target.value.split("\n") })} /></label>
        <label className="block">Còn mở<textarea maxLength={1500} value={handover.open.join("\n")} onChange={e => setHandover({ ...handover, open: e.target.value.split("\n") })} /></label>
        <label className="block">Bước tiếp theo<input maxLength={500} value={handover.next_action} onChange={e => setHandover({ ...handover, next_action: e.target.value })} /></label>
        <label className="block">Phạm vi<select value={handover.visibility} onChange={e => setHandover({ ...handover, visibility: e.target.value as "internal" | "public" })}><option value="internal">Nội bộ người nhận</option><option value="public">Công khai cho sinh viên hồ sơ</option></select></label></div>}
      <label className="block">Lý do công khai, mỗi dòng một lý do<textarea className="fluent-input w-full" maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <label className="block">Ghi chú riêng<textarea className="fluent-input w-full" maxLength={2000} value={internal} onChange={e => setInternal(e.target.value)} /></label>
      <div>Nguồn facts được chọn{dossier?.sources.map(s => <label key={s.id} className="block text-sm"><input type="checkbox" checked={sources.includes(s.id)} onChange={e => setSources(items => e.target.checked ? [...items, s.id] : items.filter(v => v !== s.id))} /> {s.id} · {s.locator}</label>)}</div>
      <button type="button" disabled={!reason.trim() || !sources.length} onClick={() => void run(save)}>{pending.current ? "Thử lại lưu cùng nháp" : "Lưu nháp có cấu trúc"}</button>
      <button type="button" disabled={!version || !!pending.current} onClick={() => void run(async () => setPreview(await api().post<Preview>("/v1/assistant/cases/draft:preview", { resource, draft_version: version, client_id: assistantClientId() })))}>Xem trước nháp server v{version}</button>
    </fieldset>
    {p && <div className="space-y-3"><h4>Bản công khai — người nhận {studentId}</h4><pre className="whitespace-pre-wrap break-words">{JSON.stringify(p.public, null, 2)}</pre>
      <details><summary>Phần nội bộ</summary><pre className="whitespace-pre-wrap">{JSON.stringify(p.internal, null, 2)}</pre></details>
      <button type="button" disabled={busy} onClick={() => setPreview(null)}>Quay lại nháp</button> <button type="button" disabled={busy} onClick={() => void run(confirm)}>Tôi đã review, xác nhận thực hiện</button></div>}
    {message && <p role="status">{message}</p>}
  </section>;
}
