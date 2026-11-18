"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { useState } from "react";
import { ApiClient } from "../../lib/api/client";
import { assistantClientId } from "../../lib/assistant-state-service";
import type { ResourceRef } from "../../lib/unified-ai-contracts";
const api = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });
interface QueueItem { resource: ResourceRef; group: string; status: string; reason: string; queue: string; deadline: string | null; deadline_reason: string }
interface Batch { batch_id: string; target_hash: string; items: Array<{ resource: ResourceRef; state: string; public?: unknown; code?: string }> }
export function StaffCaseInsights({ kind, onCommitted }: { kind: ResourceRef["kind"]; onCommitted: () => Promise<void> }) {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [dashboard, setDashboard] = useState<unknown>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [result, setResult] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function run(work: () => Promise<void>) { if (busy) return; setBusy(true); setMessage(""); try { await work(); } catch (e) { setMessage(`${e instanceof Error ? e.message : "Chưa hoàn tất"}. Batch và receipt đã ghi được giữ.`); } finally { setBusy(false); } }
  async function load() {
    const [queue, metrics] = await Promise.all([api().post<{ items: QueueItem[] }>("/v1/assistant/cases/queue:read", { kind }), api().post("/v1/assistant/cases/dashboard:read", { kind })]);
    setItems(queue.items); setDashboard(metrics);
  }
  return <section className="my-4 space-y-3 rounded-xl border p-4" aria-label="Hàng đợi và xử lý gộp"><h2 className="font-semibold">Đối chiếu hàng đợi và điểm nghẽn</h2>
    <p>Nhóm theo kiểm tra hiện tại, giữ thứ tự trong từng nhóm. Hạn xử lý chưa có nguồn xác minh. Thời gian active/system chưa đo.</p>
    <button type="button" disabled={busy} onClick={() => void run(load)}>Đọc nhóm hàng đợi và tổng hợp theo quyền</button>
    {["ready", "waiting", "blocked"].map(group => <div key={group}><h3>{group}</h3>{items.filter(i => i.group === group).map(item => <label className="block text-sm" key={item.resource.id}>
      <input type="checkbox" disabled={busy || !!batch} checked={selected.includes(item.resource.id)} onChange={e => setSelected(v => e.target.checked ? [...v, item.resource.id] : v.filter(id => id !== item.resource.id))} />
      {item.resource.id} v{item.resource.expected_version} · {item.queue} · {item.status}<span className="block">{item.reason}</span></label>)}</div>)}
    <button type="button" disabled={busy || !selected.length || !!batch} onClick={() => void run(async () => {
      const targets = items.filter(i => selected.includes(i.resource.id));
      if (targets.length !== selected.length || targets.length > 20) throw new Error("Cần danh sách tối đa20 hồ sơ chính xác từ lần đọc hiện tại");
      const previews = [];
      for (const item of targets) {
        const value = await api().post<{ draft: { version: number } | null; binding_stale: boolean }>("/v1/assistant/cases/draft:read", { resource: item.resource });
        if (!value.draft || value.binding_stale) throw new Error(`Cần soạn và review nháp hiện tại cho ${item.resource.id}`);
        previews.push({ resource: item.resource, draft_version: value.draft.version, client_id: assistantClientId() });
      }
      setBatch(await api().post<Batch>("/v1/assistant/cases/batch:prepare", { client_id: assistantClientId(), items: previews }));
    })}>Chuẩn bị batch từ từng nháp server</button>
    {batch && <div><p>Danh sách và payload từng hồ sơ — chưa thực hiện</p><pre className="whitespace-pre-wrap break-words">{JSON.stringify(batch.items, null, 2)}</pre>
      <button type="button" disabled={busy} onClick={() => void run(async () => {
        const value = await api().post("/v1/assistant/cases/batch:confirm", { batch_id: batch.batch_id, target_hash: batch.target_hash, confirmed: true });
        setResult(value); await onCommitted(); await load();
      })}>Xác nhận từng mục đã review / đối chiếu receipt và thử lại</button>
      <button type="button" disabled={busy} onClick={() => void run(async () => setResult(await api().post("/v1/assistant/cases/batch:read", { client_id: batch.batch_id })))}>Đọc receipt batch</button>
      <button type="button" disabled={busy} onClick={() => { setBatch(null); setSelected([]); }}>Giữ batch server, chọn công việc khác</button></div>}
    {result !== null && <pre className="whitespace-pre-wrap break-words">{JSON.stringify(result, null, 2)}</pre>}
    {dashboard !== null && <details><summary>Tổng hợp tối thiểu theo quyền và giới hạn đo lường</summary><pre className="whitespace-pre-wrap">{JSON.stringify(dashboard, null, 2)}</pre></details>}
    {message && <p role="status">{message}</p>}
  </section>;
}
