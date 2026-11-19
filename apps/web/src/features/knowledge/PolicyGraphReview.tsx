"use client";

import React, { useState } from "react";

export interface GraphSource {
  source_id: string; document_version_id: string; chunk_id: string;
  content_sha256: string; locator: Record<string, unknown>; quote: string;
}
export interface GraphNode {
  id: string; kind: string; label: string; aliases: string[]; source: GraphSource;
  operator: "ALL" | "ANY" | null; members: string[];
  qualifiers: string[]; predicate?: { comparator: string; value: string; unit: string } | null;
}
export interface GraphEdge {
  id: string; from_id: string; to_id: string; relation: string;
  source: GraphSource; scope: { audiences: string[]; faculties: string[]; programs: string[] };
  interval: { status: string; start: string | null; end: string | null };
}
export interface GraphView {
  proposal: { id: string; origin: string; nodes: GraphNode[]; edges: GraphEdge[];
    index_fingerprint: string; source_fingerprint: string };
  reviews: { target: string; verdict: string; note: string; reviewer: string; revision: number }[];
  issues: { target: string; code: string }[]; revision: number;
  publication: Record<string, unknown> | null; raw_proposal: string;
}

export function PolicyGraphReview({ view, onReview, onPreview, onPublish, onExtract }: {
  view: GraphView;
  onReview: (target: string, verdict: string, note: string, revision: number) => Promise<void>;
  onPreview: (revision: number) => Promise<{ confirmation: string; preview: Record<string, unknown> }>;
  onPublish: (revision: number, confirmation: string) => Promise<void>;
  onExtract?: (target: string) => Promise<void>;
}) {
  const [selected, setSelected] = useState(view.proposal.edges[0]?.id || "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<{ confirmation: string; preview: Record<string, unknown> } | null>(null);
  const records = [...view.proposal.nodes, ...view.proposal.edges];
  const record = records.find(r => r.id === selected);
  const edge = view.proposal.edges.find(e => e.id === selected);
  const labels = new Map(view.proposal.nodes.map(n => [n.id, n.label]));
  const latest = new Map(view.reviews.map(r => [r.target, r]));
  const complete = records.every(r => latest.get(r.id)?.verdict === "approved") && view.issues.length === 0;

  async function action(fn: () => Promise<void>) {
    setBusy(true); setError("");
    try { await fn(); } catch { setError("Thao tác chưa hoàn tất. Kiểm tra quyền, nguồn và phiên bản review rồi tải lại."); }
    finally { setBusy(false); }
  }

  return <section aria-label="Review đồ thị quy định" className="mx-auto max-w-6xl space-y-6 p-6">
    <header className="space-y-2">
      <h1 className="text-2xl font-semibold">Đồ thị quy định</h1>
      <p>Đối chiếu từng quan hệ với đoạn nguồn trước khi xuất bản. Quan hệ giúp tìm điều khoản; việc cấp hồ sơ vẫn cần kiểm tra và xác nhận riêng.</p>
      <p className="text-sm">{view.proposal.id} · {view.publication ? "Đã xuất bản — phiên bản bất biến" : "Ứng viên chưa xuất bản"} · Review {view.revision}</p>
    </header>
    {error && <p role="alert">{error}</p>}
    {onExtract && <button disabled={busy || !record} onClick={() => action(async () => {
      setPreview(null); await onExtract(selected);
    })}>Trích xuất ứng viên từ đoạn nguồn đang chọn</button>}
    {view.issues.length > 0 && <div role="alert">Cần xử lý: {view.issues.map(i => `${i.target}: ${i.code}`).join(", ")}</div>}
    <div className="grid gap-6 md:grid-cols-[minmax(220px,1fr)_2fr]">
      <div className="space-y-3">
        <label htmlFor="policy-relation">Quan hệ hoặc thực thể</label>
        <select id="policy-relation" className="w-full rounded border p-2" value={selected} onChange={e => { setSelected(e.target.value); setNote(""); }}>
          <optgroup label="Quan hệ">{view.proposal.edges.map(e => <option key={e.id} value={e.id}>{labels.get(e.from_id)} → {e.relation} → {labels.get(e.to_id)}</option>)}</optgroup>
          <optgroup label="Thực thể">{view.proposal.nodes.map(n => <option key={n.id} value={n.id}>{n.kind}: {n.label}</option>)}</optgroup>
        </select>
        <p>Verdict: {latest.get(selected)?.verdict || "Chưa review"}</p>
        {latest.get(selected) && <p className="text-sm">{latest.get(selected)?.reviewer}: {latest.get(selected)?.note}</p>}
        {edge && <dl className="space-y-2 text-sm"><dt>Đối tượng / phạm vi</dt><dd>{[...edge.scope.audiences, ...edge.scope.faculties, ...edge.scope.programs].join(" · ")}</dd>
          <dt>Hiệu lực pháp lý</dt><dd>{edge.interval.status === "unknown" ? "Chưa xác minh ngày hiệu lực" : `${edge.interval.start} → ${edge.interval.end || "Chưa xác định ngày kết thúc"}`}</dd></dl>}
        {view.proposal.nodes.filter(n => n.id === selected || n.id === edge?.to_id || n.id === edge?.from_id).map(n => <div key={n.id} className="rounded border p-3">
          <strong>{n.label}</strong>
          {n.operator && <p>{n.operator === "ALL" ? "ALL — cần đủ mọi điều kiện" : "ANY — một trong các điều kiện"}: {n.members.map(k => labels.get(k) || k).join("; ")}</p>}
          {n.predicate && <p>{n.predicate.comparator} {n.predicate.value} {n.predicate.unit}</p>}
          {n.qualifiers.map(q => <p key={q} className="text-sm">{q}</p>)}
        </div>)}
      </div>
      <div className="space-y-3">
        <h2 className="font-semibold">Đoạn nguồn nguyên văn</h2>
        {record && <><p className="text-sm">{JSON.stringify(record.source.locator)}</p>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded border p-4 text-sm">{record.source.quote}</pre>
          <p className="break-all text-xs">Source {record.source.source_id} · Version {record.source.document_version_id}<br/>SHA-256 {record.source.content_sha256}</p></>}
        {!view.publication && <><label htmlFor="policy-review-note">Ghi nhận đối chiếu nguồn, điều kiện và hiệu lực</label>
          <textarea id="policy-review-note" className="w-full rounded border p-3" value={note} onChange={e => setNote(e.target.value)} />
          <div className="flex flex-wrap gap-2">{[["approved", "Duyệt quan hệ"], ["needs_source", "Thiếu nguồn"], ["conflicting", "Mâu thuẫn"], ["rejected", "Từ chối"]].map(([verdict, label]) =>
            <button key={verdict} className="rounded border px-3 py-2" disabled={busy || !record || note.trim().length < 8 || verdict === "approved" && view.issues.length > 0}
              onClick={() => action(async () => { setPreview(null); await onReview(selected, verdict, note, view.revision); setNote(""); })}>{label}</button>)}</div></>}
      </div>
    </div>
    {!view.publication && <div className="space-y-3 rounded border p-4">
      <button disabled={busy || !complete} onClick={() => action(async () => setPreview(await onPreview(view.revision)))}>Xem trước xuất bản</button>
      {preview && <><p>Xuất bản phiên bản {view.proposal.id} tại review {view.revision}. Các phiên bản trước được giữ lại.</p>
        <button disabled={busy || !complete} onClick={() => action(async () => { await onPublish(view.revision, preview.confirmation); setPreview(null); })}>Xác nhận xuất bản phiên bản này</button></>}
    </div>}
    <details><summary>Snapshot và đề xuất nguyên bản</summary><p className="break-all text-xs">Index {view.proposal.index_fingerprint}<br/>Sources {view.proposal.source_fingerprint}</p><pre className="max-h-72 overflow-auto whitespace-pre-wrap text-xs">{view.raw_proposal}</pre></details>
  </section>;
}
