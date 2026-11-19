"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { useEffect, useState } from "react";
import { ApiClient } from "../../lib/api/client";
import { assistantClientId } from "../../lib/assistant-state-service";
import type { ResourceRef } from "../../lib/unified-ai-contracts";
const api = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });
interface Request { id: string; version: number; workflow_version: string; items: Array<{ id: string; field: string; criterion_id: string; source_ids: string[]; public_reason: string; accepted_format: string }> }
interface Preview { preview_id: string; confirmation_token: string; client_id: string; responses: unknown; form: unknown }

export function CaseSupplementPanel({ resource, onCommitted }: { resource: ResourceRef; onCommitted: () => Promise<void> }) {
  const [request, setRequest] = useState<Request | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [p, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    let cancelled = false;
    void api().post<{ current_request: Request | null }>("/v1/assistant/cases/supplement:read", { resource }).then(v => { if (!cancelled) setRequest(v.current_request); }).catch(e => { if (!cancelled) setMessage(String(e)); });
    return () => { cancelled = true; };
  }, [resource.id, resource.expected_version]);
  async function run(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setMessage("");
    try { await work(); } catch (e) { setMessage(`${e instanceof Error ? e.message : "Chưa hoàn tất"}. Bản đang soạn được giữ.`); } finally { setBusy(false); }
  }
  if (!request) return message ? <p role="status">{message}</p> : null;
  return <section className="my-4 space-y-3 rounded-xl border p-4" aria-label="Checklist bổ sung có cấu trúc"><h3>Đáp ứng từng mục bổ sung</h3><p>Yêu cầu v{request.version} · {request.workflow_version}. Cán bộ sẽ kiểm lại phần thay đổi sau khi bạn gửi.</p>
    {!p ? <fieldset disabled={busy} className="space-y-3">{request.items.map(item => <label className="block" key={item.id}>{item.id} · {item.public_reason}<span className="block text-sm">{item.criterion_id} · nguồn {item.source_ids.join(", ")} · định dạng {item.accepted_format}</span>
      <textarea className="fluent-input w-full" maxLength={item.field === "attachments" ? 16000 : 2000} value={values[item.id] || ""} onChange={e => setValues(v => ({ ...v, [item.id]: e.target.value }))} /></label>)}
      <label className="block">Lời phản hồi<textarea maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></label>
      <button type="button" disabled={!note.trim() || request.items.some(i => !values[i.id]?.trim())} onClick={() => void run(async () => setPreview(await api().post<Preview>("/v1/assistant/cases/supplement:preview", {
        resource, request_id: request.id, request_version: request.version, client_id: assistantClientId(), note,
        responses: request.items.map(item => ({ item_id: item.id, field: item.field, value: item.accepted_format === "integer" ? Number(values[item.id]) : values[item.id] })),
      })))}>Xem trước các mục bổ sung</button></fieldset> : <div><pre className="whitespace-pre-wrap break-words">{JSON.stringify({ responses: p.responses, form: p.form }, null, 2)}</pre>
      <button type="button" disabled={busy} onClick={() => setPreview(null)}>Quay lại sửa</button> <button type="button" disabled={busy} onClick={() => void run(async () => {
        await api().post("/v1/assistant/cases/supplement:confirm", { preview_id: p.preview_id, confirmation_token: p.confirmation_token, client_id: p.client_id, confirmed: true });
        await onCommitted(); setPreview(null); setRequest(null); setMessage("Đã ghi bổ sung; cán bộ cần kiểm lại.");
      })}>Xác nhận gửi bổ sung đúng mục</button></div>}
    {message && <p role="status">{message}</p>}
  </section>;
}
