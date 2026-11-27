"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Play, RefreshCw } from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";

const base = "/v1/knowledge/platform/crawl-sources";
const DECISION_LABELS: Record<string, string> = {
  CREATED: "Đã tạo tài liệu", UPDATED: "Đã tạo phiên bản mới", UNCHANGED: "Không đổi", WOULD_CREATE: "Sẽ tạo mới", WOULD_UPDATE: "Sẽ tạo phiên bản mới",
  SKIPPED: "Bỏ qua", BLOCKED_PII: "Loại: dữ liệu cá nhân", BLOCKED_ROBOTS: "Loại: robots.txt", UNSUPPORTED: "Chưa đọc được định dạng", MISSING: "Nguồn không còn", EXISTS: "Đã có trong kho", ERROR: "Lỗi",
};

type Run = { id: string; dry_run: boolean; state: string; counts: Record<string, number>; error: string | null; started_at: string; finished_at: string | null;
  decisions?: Array<{ url: string; kind: string; decision: string; reason: string; title?: string }> };
export type CrawlSource = { id: string; name: string; seed_urls: string[]; kind: string; include: string[]; exclude: string[]; max_depth: number; max_pages: number;
  interval_hours: number; owner_unit: string; mode: "REVIEW" | "DIRECT"; active: boolean; ingest_enabled: boolean; next_run_at: string | null;
  last_run_at: string | null; last_status: string | null; pending_run: string | null; last_run: Run | null };

async function call(path: string, init: RequestInit = {}) {
  const response = await fetch(path, { ...init, credentials: "include", cache: "no-store" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : response.status === 403 ? "Chỉ quản trị tri thức được quản lý nguồn tự động." : `Không thể thực hiện (${response.status}).`);
  }
  return response;
}
const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify(body) });
const when = (value: string | null) => value ? new Date(value).toLocaleString("vi-VN") : "—";
const lines = (value: FormDataEntryValue | null) => String(value || "").split(/\r?\n/).map(item => item.trim()).filter(Boolean);

export function KnowledgeCrawl() {
  const [sources, setSources] = useState<CrawlSource[] | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<{ source: CrawlSource; runs: Run[] } | null>(null);

  const load = useCallback(async () => {
    try { setSources((await (await call(base)).json()).items); setError(""); } catch (failure) { setError((failure as Error).message); }
  }, []);
  useEffect(() => { void load(); const timer = window.setInterval(() => { if (!document.hidden) void load(); }, 8000); return () => window.clearInterval(timer); }, [load]);

  async function run<T>(work: () => Promise<T>, done: string) {
    setBusy(true); setError(""); setNotice("");
    try { await work(); setNotice(done); await load(); } catch (failure) { setError((failure as Error).message); } finally { setBusy(false); }
  }

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    await run(async () => {
      await call(base, json({ name: data.get("name"), owner_unit: data.get("owner_unit"), seed_urls: lines(data.get("seed_urls")), kind: data.get("kind"),
        include: lines(data.get("include")), exclude: lines(data.get("exclude")), max_depth: Number(data.get("max_depth")), max_pages: Number(data.get("max_pages")),
        interval_hours: Number(data.get("interval_hours")), mode: "REVIEW" }));
      form.reset();
    }, "Đã thêm nguồn. Nguồn mới chỉ chạy thử (không nạp gì) cho đến khi bạn xem báo cáo và bật nạp.");
  }

  async function openReport(source: CrawlSource) {
    try { setReport({ source, runs: (await (await call(`${base}/${source.id}/runs`)).json()).items }); } catch (failure) { setError((failure as Error).message); }
  }

  return <div className="space-y-6" data-testid="knowledge-crawl">
    <form className="campus-panel space-y-4" onSubmit={create}>
      <h2 className="font-semibold">Thêm nguồn tự động</h2>
      <fieldset disabled={busy} className="grid gap-4 md:grid-cols-2">
        <label>Tên nguồn<input name="name" className="fluent-input w-full" required minLength={3} maxLength={160} placeholder="Thông báo phòng Đào tạo" /></label>
        <label>Đơn vị ban hành<input name="owner_unit" className="fluent-input w-full" required minLength={2} maxLength={160} /></label>
        <label className="md:col-span-2">Địa chỉ gốc (mỗi dòng một địa chỉ https://…huce.edu.vn)<textarea name="seed_urls" className="fluent-input w-full" rows={2} required placeholder="https://…huce.edu.vn/thong-bao" /></label>
        <label>Loại<select name="kind" className="fluent-input w-full" defaultValue="LIST"><option value="LIST">Trang danh sách</option><option value="SITEMAP">Sitemap</option><option value="PAGE">Một trang</option></select></label>
        <label>Chạy lại mỗi (giờ)<input name="interval_hours" type="number" min={1} max={720} defaultValue={24} className="fluent-input w-full" /></label>
        <label>Chỉ lấy địa chỉ khớp (mỗi dòng một mẫu, để trống = tất cả)<textarea name="include" className="fluent-input w-full" rows={2} placeholder="^/thong-bao" /></label>
        <label>Bỏ qua địa chỉ khớp<textarea name="exclude" className="fluent-input w-full" rows={2} placeholder="page=\d+" /></label>
        <label>Độ sâu tối đa<input name="max_depth" type="number" min={0} max={4} defaultValue={2} className="fluent-input w-full" /></label>
        <label>Số trang tối đa mỗi lượt<input name="max_pages" type="number" min={1} max={1000} defaultValue={200} className="fluent-input w-full" /></label>
        <p className="text-sm md:col-span-2">Chỉ trang công khai của HUCE; hệ thống tuân robots.txt, tải chậm (khoảng 3 giây mỗi yêu cầu), loại trang có dữ liệu cá nhân. Tài liệu lấy về vào hàng chờ duyệt như tài liệu thường.</p>
        <button type="submit" className="fluent-btn-primary">Thêm nguồn</button>
      </fieldset>
    </form>
    {error && <p role="alert" className="rounded-xl border p-3 text-sm text-[var(--color-danger)]">{error}</p>}
    {notice && <p role="status" className="rounded-xl border p-3 text-sm">{notice}</p>}
    <section className="campus-panel space-y-3" aria-label="Danh sách nguồn tự động">
      <div className="flex items-center justify-between"><h2 className="font-semibold">Nguồn tự động</h2><IconButton label="Làm mới" variant="outline" onClick={() => void load()} icon={<RefreshCw size={18} />} /></div>
      {!sources ? <p className="text-sm">Đang tải…</p> : !sources.length ? <p className="text-sm">Chưa có nguồn nào.</p> : <ul className="space-y-3">{sources.map(source => <li key={source.id} className="rounded-xl border p-4 space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-semibold">{source.name}</p><p className="text-xs break-all">{source.seed_urls.join(", ")}</p></div>
          <span className="text-sm font-semibold">{!source.active ? "Đã tạm dừng" : source.ingest_enabled ? "Đang nạp tài liệu" : "Chỉ chạy thử"}</span></div>
        <p className="text-xs">Lần chạy gần nhất: {when(source.last_run_at)} · {source.last_status || "chưa chạy"} · Lần tới: {source.pending_run ? "đang chờ chạy" : when(source.next_run_at)}</p>
        {source.last_run && <p className="text-xs">{Object.entries(source.last_run.counts).map(([key, value]) => `${DECISION_LABELS[key] || key}: ${value}`).join(" · ") || "Không có kết quả"}</p>}
        {!source.ingest_enabled && <p className="text-xs"><AlertTriangle size={12} className="inline" aria-hidden="true" /> Xem báo cáo chạy thử trước khi bật nạp: hệ thống chưa tạo tài liệu nào từ nguồn này.</p>}
        <div className="flex flex-wrap gap-2">
          <button type="button" className="fluent-btn-secondary" disabled={busy} onClick={() => void run(() => call(`${base}/${source.id}/run`, json({ dry_run: true })), "Đã xếp lịch chạy thử; báo cáo hiện sau ít phút.")}><Play size={14} aria-hidden="true" /> Chạy thử</button>
          {source.ingest_enabled && <button type="button" className="fluent-btn-secondary" disabled={busy} onClick={() => void run(() => call(`${base}/${source.id}/run`, json({ dry_run: false })), "Đã xếp lịch chạy; tài liệu mới sẽ vào hàng chờ duyệt.")}>Chạy ngay</button>}
          <button type="button" className="fluent-btn-secondary" onClick={() => void openReport(source)}>Xem báo cáo</button>
          <button type="button" className="fluent-btn-secondary" disabled={busy} onClick={() => void run(() => call(`${base}/${source.id}/settings`, json({ ingest_enabled: !source.ingest_enabled })), source.ingest_enabled ? "Đã tắt nạp: nguồn chỉ chạy thử." : "Đã bật nạp: lượt chạy tới sẽ tạo tài liệu chờ duyệt.")}>{source.ingest_enabled ? "Tắt nạp" : "Bật nạp"}</button>
          <button type="button" className="fluent-btn-secondary" disabled={busy} onClick={() => void run(() => call(`${base}/${source.id}/settings`, json({ active: !source.active })), source.active ? "Đã tạm dừng nguồn." : "Đã bật lại nguồn.")}>{source.active ? "Tạm dừng" : "Bật lại"}</button>
        </div>
      </li>)}</ul>}
    </section>
    {report && <section className="campus-panel space-y-3" aria-label="Báo cáo lượt chạy">
      <div className="flex items-center justify-between"><h2 className="font-semibold">Báo cáo: {report.source.name}</h2><button type="button" className="fluent-btn-secondary" onClick={() => setReport(null)}>Đóng</button></div>
      {!report.runs.length ? <p className="text-sm">Chưa có lượt chạy nào.</p> : (() => { const latest = report.runs[0]; return <div className="space-y-2">
        <p className="text-sm">{latest.dry_run ? "Chạy thử (chưa nạp gì)" : "Chạy nạp"} · {when(latest.started_at)} · {latest.state}{latest.error ? ` · ${latest.error}` : ""}</p>
        <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr><th className="text-left">Kết quả</th><th className="text-left">Địa chỉ</th><th className="text-left">Lý do</th></tr></thead>
          <tbody>{(latest.decisions || []).map((item, index) => <tr key={index}><td className="pr-3 align-top font-semibold">{DECISION_LABELS[item.decision] || item.decision}</td><td className="pr-3 align-top break-all">{item.title ? `${item.title} — ` : ""}{item.url}</td><td className="align-top">{item.reason}</td></tr>)}</tbody></table></div></div>; })()}
    </section>}
  </div>;
}
