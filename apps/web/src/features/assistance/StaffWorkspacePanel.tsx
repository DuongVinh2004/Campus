"use client";
import { RefreshCw } from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import { useEffect, useRef, useState } from "react";
import { ApiClient } from "@/lib/api/client";
import type { ResourceRef } from "@/lib/unified-ai-contracts";

type State = "unchecked" | "checked" | "missing_source" | "error" | "conflicting";
interface Finding { id: string; label: string; layer: "deterministic" | "officer_review"; state: State; reason: string;
  dependency_hash: string; source_ids: string[]; reviewed_by: string | null; note: string | null }
interface Source { id: string; version: string; locator: string; sha256: string; classification: string }
interface Dossier { schema_version: "staff-workspace.v1"; resource: ResourceRef; tenant: string; student_id: string;
  assigned_actor: string | null; purpose: string | null; binding_hash: string; workflow_version: string; criteria_version: string;
  facts: Array<{ field: string; value: unknown; origin: string; source_id: string }>;
  timeline: Array<{ id: string; occurred_at: string; action: string; note: string }>;
  documents: Array<{ name: string; source_id: string; ocr_state: State; reason: string }>;
  sources: Source[]; findings: Finding[]; readiness: string; reasons: string[]; next_action: string;
  delta: { previous_version: number | null; current_version: number; changes: Array<{ field: string; before: unknown; after: unknown }>;
    reused: string[]; rechecked: string[]; draft_invalidated: boolean }; capabilities: Record<string, string> }
const labels: Record<State, string> = { unchecked: "Chưa kiểm", checked: "Đã kiểm", missing_source: "Thiếu nguồn", error: "Lỗi", conflicting: "Xung đột" };
const readyLabels: Record<string, string> = { ready: "Đã đối chiếu các mục", needs_verification: "Cần xác minh", missing: "Thiếu dữ liệu", waiting: "Đang chờ", blocked: "Cần xử lý vấn đề" };
const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });
const notes = new Map<string, string>();
const text = (value: unknown) => typeof value === "string" ? value : JSON.stringify(value, null, 2) ?? "Chưa có";
function uuid7() {
  const bytes = crypto.getRandomValues(new Uint8Array(16)); let stamp = Date.now();
  for (let i = 5; i >= 0; i--) { bytes[i] = stamp % 256; stamp = Math.floor(stamp / 256); }
  bytes[6] = (bytes[6] & 15) | 112; bytes[8] = (bytes[8] & 63) | 128;
  const h = Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function StaffWorkspacePanel({ resource, actorId, studentId }: { resource: ResourceRef; actorId: string; studentId: string }) {
  const context = `${actorId}:${resource.kind}:${resource.id}:${resource.expected_version}`;
  const current = useRef(context); current.current = context;
  const [data, setData] = useState<{ context: string; value: Dossier } | null>(null);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const [opened, setOpened] = useState<{ context: string; source: Source; content: unknown } | null>(null);
  const [editing, setEditing] = useState(""); const [note, setNote] = useState("");
  const [verdict, setVerdict] = useState<"checked" | "missing_source" | "conflicting">("checked");
  const pending = useRef<{ fingerprint: string; client_id: string } | null>(null);
  const lock = useRef(false);
  const dossier = data?.context === context ? data.value : null;
  function check(value: Dossier) {
    if (value.schema_version !== "staff-workspace.v1" || value.resource.id !== resource.id || value.resource.kind !== resource.kind
      || value.resource.expected_version !== resource.expected_version || value.student_id !== studentId || value.tenant !== "huce-local-public"
      || !Array.isArray(value.findings) || !Array.isArray(value.sources) || !/^[a-f0-9]{64}$/.test(value.binding_hash))
      throw new Error("Bộ hồ sơ không khớp chủ thể hoặc phiên bản đang xem.");
    return value;
  }
  async function load() {
    const started = context;
    const value = check(await client().post<Dossier>("/v1/assistant/staff-workspace/read", { resource }));
    if (current.current === started) setData({ context: started, value });
  }
  useEffect(() => {
    let cancelled = false; setData(null); setOpened(null); setError(""); setEditing(""); setBusy(false);
    void client().post<Dossier>("/v1/assistant/staff-workspace/read", { resource }).then(value => {
      check(value); if (!cancelled && current.current === context) setData({ context, value });
    }).catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : "Chưa đọc được bộ hồ sơ; giữ nháp và đối chiếu thủ công."); });
    return () => { cancelled = true; };
  }, [context]);
  async function run(work: () => Promise<void>) {
    if (lock.current) return; lock.current = true; setBusy(true); setError(""); const started = context;
    try { await work(); } catch (e) { if (current.current === started) setError(e instanceof Error ? e.message : "Chưa xác minh được kết quả. Nội dung đang soạn được giữ."); }
    finally { lock.current = false; if (current.current === started) setBusy(false); }
  }
  async function open(sourceId: string) {
    if (!dossier) return; const started = context;
    const value = await client().post<{ source: Source; content: unknown; binding_hash: string }>("/v1/assistant/staff-workspace/source", { resource, source_id: sourceId, binding_hash: dossier.binding_hash });
    const expected = dossier.sources.find(s => s.id === sourceId);
    if (!expected || JSON.stringify(value.source) !== JSON.stringify(expected) || value.binding_hash !== dossier.binding_hash)
      throw new Error("Nguồn không khớp binding. Mở lại bộ hồ sơ để đối chiếu.");
    if (current.current === started) setOpened({ context: started, source: value.source, content: value.content });
  }
  async function saveReview() {
    if (!dossier) return; const started = context;
    const finding = dossier.findings.find(f => f.id === editing);
    if (!finding) return;
    const body = { resource, criterion_id: finding.id, binding_hash: dossier.binding_hash, dependency_hash: finding.dependency_hash, verdict, note };
    const fingerprint = JSON.stringify(body);
    if (pending.current?.fingerprint !== fingerprint) pending.current = { fingerprint, client_id: uuid7() };
    const receipt = await client().post<{ saved: boolean; binding_hash: string; criterion_id: string }>("/v1/assistant/staff-workspace/review", { ...body, client_id: pending.current.client_id });
    if (!receipt.saved || receipt.binding_hash !== dossier.binding_hash || receipt.criterion_id !== finding.id) throw new Error("Chưa xác minh được receipt kiểm tra.");
    if (current.current !== started) return;
    pending.current = null; setEditing(""); await load();
  }
  return <section aria-label="Bộ hồ sơ làm việc" className="my-4 space-y-4 rounded-xl border p-4">
    <h3 className="font-semibold">Bộ hồ sơ làm việc · dữ liệu mô phỏng</h3>
    <p className="text-sm">Thông tin khai báo và đối chiếu theo bản hồ sơ. OCR, SLA và quy định chính thức chưa được xác minh.</p>
    {error && <p role="alert">{error}</p>}<IconButton label="Đọc lại bộ hồ sơ" disabled={busy} onClick={() => void run(load)} icon={<RefreshCw size={16} />} />
    {dossier && <>
      <p role="status">{readyLabels[dossier.readiness]} · {dossier.workflow_version} · {dossier.criteria_version}</p>
      <p>{dossier.purpose || "Chưa có mục đích được khai báo"}</p><p className="text-sm">{dossier.next_action}</p>
      <details><summary>Dữ kiện và nguồn khai báo</summary>{dossier.facts.map(f => <div key={f.field} className="my-2 break-words text-sm"><strong>{f.field}</strong><pre className="whitespace-pre-wrap">{text(f.value)}</pre><span>{f.origin}</span> <button disabled={busy} onClick={() => void run(() => open(f.source_id))}>Mở bản ghi nguồn</button></div>)}</details>
      <details><summary>Tài liệu và nguồn áp dụng</summary>{dossier.documents.map(d => <p key={d.source_id}>{d.name} · OCR: {labels[d.ocr_state]} <button disabled={busy} onClick={() => void run(() => open(d.source_id))}>Mở tài liệu</button></p>)}{dossier.sources.filter(s => s.id.startsWith("workflow:")).map(s => <p key={s.id}><button disabled={busy} onClick={() => void run(() => open(s.id))}>{s.locator} · {s.version}</button></p>)}</details>
      <div className="space-y-3">{dossier.findings.map(f => <article key={f.id} className="rounded-lg border p-3"><h4>{f.label}</h4><p className="text-sm">{f.layer === "deterministic" ? "Kiểm tra quy tắc" : "Cán bộ đối chiếu"}: {labels[f.state]} · {f.reason}</p>{f.reviewed_by && <p className="text-sm">{f.reviewed_by} · {f.note}</p>}<div className="flex flex-wrap gap-2">{f.source_ids.map(id => <button key={id} disabled={busy} onClick={() => void run(() => open(id))}>Nguồn {id}</button>)}{f.layer === "officer_review" && dossier.assigned_actor === actorId && <button disabled={busy} onClick={() => { setEditing(f.id); setNote(notes.get(`${context}:${f.id}`) || ""); setVerdict("checked"); }}>Ghi nhận kiểm tra mục này</button>}</div></article>)}</div>
      {editing && <div className="space-y-3 rounded-lg border p-3"><p>{dossier.findings.find(f => f.id === editing)?.label}</p><label className="block">Kết quả đối chiếu<select className="fluent-input w-full" value={verdict} onChange={e => setVerdict(e.target.value as typeof verdict)}><option value="checked">Đã đối chiếu</option><option value="missing_source">Thiếu nguồn</option><option value="conflicting">Xung đột</option></select></label><label className="block">Căn cứ và phần cần làm rõ<textarea className="fluent-input w-full" maxLength={1000} value={note} onChange={e => { setNote(e.target.value); notes.set(`${context}:${editing}`, e.target.value); }} /></label><button disabled={busy || !note.trim()} onClick={() => void run(saveReview)}>Lưu kiểm tra này</button><button disabled={busy} onClick={() => setEditing("")}>Quay lại</button></div>}
      <p className="text-sm">Đề xuất AI: chưa có consumer; cán bộ soạn và đối chiếu thủ công. Kiểm tra quy tắc không xác nhận giấy tờ hoặc thay cán bộ quyết định.</p>
      <details><summary>Thay đổi và phần đã kiểm lại</summary><p>Bản trước: {dossier.delta.previous_version ?? "Chưa có"} → {dossier.delta.current_version}</p>{dossier.delta.changes.map(c => <div key={c.field}><strong>{c.field}</strong><pre className="whitespace-pre-wrap">Trước: {text(c.before)}{"\n"}Sau: {text(c.after)}</pre></div>)}<p>Kiểm lại: {dossier.delta.rechecked.join(", ") || "Không có"}</p><p>Giữ kết quả còn binding hợp lệ: {dossier.delta.reused.join(", ") || "Không có"}</p>{dossier.delta.draft_invalidated && <p>Hồ sơ đã đổi; kiểm lại nháp trước khi sử dụng.</p>}</details>
      <details><summary>Timeline</summary>{dossier.timeline.map(e => <p key={e.id}>{e.occurred_at} · {e.action} · {e.note}</p>)}</details>
      <details><summary>Lý do và capability</summary>{dossier.reasons.map(reason => <p key={reason}>{reason}</p>)}{Object.entries(dossier.capabilities).map(([key, value]) => <p key={key}>{key}: {value}</p>)}</details>
    </>}
    {opened?.context === context && <div className="rounded-lg border p-3"><p>{opened.source.locator} · {opened.source.version}</p><p className="break-all text-xs">SHA256 {opened.source.sha256}</p><pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words">{text(opened.content)}</pre><button onClick={() => setOpened(null)}>Đóng nguồn</button></div>}
  </section>;
}
