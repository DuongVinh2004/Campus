"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { ApiServiceGateway, type KnowledgeState, type KnowledgeSource, type KnowledgeVersion, type PublicationPreview, type ServiceKind } from "../../lib/data/api/service-gateway";
import { type CertificateActor } from "../../lib/data/api/certificate-gateway";

const api = new ApiServiceGateway();
const panel = "campus-panel";
const input = "fluent-input w-full text-sm";
function original(source: KnowledgeSource) { return new TextDecoder().decode(Uint8Array.from(atob(source.original_base64), c => c.charCodeAt(0))); }

export function SourceOperations() {
  const [actor, setActor] = useState<CertificateActor | null>(null);
  const [state, setState] = useState<KnowledgeState | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [sourceId, setSourceId] = useState("");
  const [title, setTitle] = useState("");
  const [filename, setFilename] = useState("source-demo.txt");
  const [locator, setLocator] = useState("");
  const [content, setContent] = useState("");
  const [text, setText] = useState("");
  const [mapping, setMapping] = useState("ORIGINAL_TEXT");
  const [kind, setKind] = useState<ServiceKind>("GRADE_APPEAL");
  const [effectiveFrom, setEffectiveFrom] = useState("2026-10-14T00:00:00+07:00");
  const [effectiveUntil, setEffectiveUntil] = useState("");
  const [candidate, setCandidate] = useState("");
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<PublicationPreview | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const version = state?.versions.find(v => v.id === selected);
  const source = state?.sources.find(s => s.id === (version?.source_id || sourceId));
  const reviewer = actor && version && actor.user_id !== version.created_by;
  async function load() {
    setBusy(true); setError("");
    try { const user = await api.me(); setActor(user); setState(await api.knowledge()); }
    catch (e) { setError(e instanceof Error ? e.message : "Không thể tải nguồn"); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []);
  async function run(fn: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await fn(); setState(await api.knowledge()); }
    catch (e) { setError(`${e instanceof Error ? e.message : "Thao tác chưa hoàn tất"}. Active version chỉ đổi sau confirmation thành công; tải lại để kiểm tra.`); }
    finally { setBusy(false); }
  }
  function choose(v: KnowledgeVersion) { setSelected(v.id); setSourceId(v.source_id); setText(v.text); setMapping(v.mapping); setKind(v.procedure);
    setEffectiveFrom(v.effective_from); setEffectiveUntil(v.effective_until || ""); setCandidate(v.candidate_text); setPreview(null); setNote(""); }
  return <AppShell userRole="admin" activeNav="knowledge"><main className="campus-knowledge space-y-5">
    <header className="campus-page-heading"><div><h1 className="text-2xl font-semibold">Vận hành nguồn tri thức</h1><p className="mt-2 text-sm">Nguồn demo · original bất biến · rendition mới · reviewer khác tác giả · preview trước xuất bản.</p></div>
      <nav className="flex flex-wrap gap-4 text-sm"><Link href="/services">Dịch vụ</Link><Link href="/knowledge/policy-graph">Graph review</Link><Link href="/login">Đổi tài khoản</Link></nav></header>
    {actor && <p>{actor.display_name}</p>}{busy && <p role="status">Đang tải hoặc xử lý…</p>}
    {error && <div role="alert" className="rounded-xl bg-red-50 p-3 text-red-800">{error} <button disabled={busy} onClick={() => void load()}>Tải lại</button></div>}
    {notice && <p role="status" className="rounded-xl bg-green-50 p-3 text-green-800">{notice}</p>}
    {state && <><section className={panel}><h2 className="font-semibold">Active version</h2><ul className="mt-3 space-y-2">{state.active.map(p => <li key={p.id} className="break-all text-sm">{p.id} · {p.version_id || "Chưa có nguồn current"} · generation {p.generation}</li>)}</ul></section>
      <div className="campus-workflow-grid"><aside className={panel}><h2 className="font-semibold">Phiên bản và lịch sử nguồn</h2><ul className="mt-4 space-y-3">{state.versions.map(v => <li key={v.id}><button disabled={busy} className="w-full rounded-xl border p-3 text-left text-sm" onClick={() => choose(v)}>
        <strong>{v.procedure}</strong><span className="block">{v.id.slice(-8)} · {v.state} · r{v.revision}</span></button></li>)}</ul></aside>
      <section className={panel}>{version ? <><h2 className="font-semibold break-all">{version.id} · {version.state} · revision {version.revision}</h2>
        <p className="my-3 text-sm">Hiệu lực: {version.effective_from} → {version.effective_until || "Chưa đặt kết thúc"}</p>
        <p className="break-all text-xs">Rendition SHA256 {version.rendition_sha256}</p><pre className="my-4 max-h-72 overflow-auto whitespace-pre-wrap text-sm">{version.text}</pre>
        <p className="text-sm">Mapping: {version.mapping}</p><details className="my-3"><summary>Candidate — không phải source evidence</summary><p>{version.candidate_text || "Không có"}</p></details>
        <p className="break-all text-sm">Build: {version.build ? `${version.build.compatibility} · ${version.build.error || "Thành công"} · ${version.build.checksum}` : "Chưa build"}</p>
        <ol className="my-4 space-y-2 text-sm">{version.reviews.map((r, i) => <li key={i}>{r.verdict} · {r.note} · {r.reviewer}</li>)}</ol>
        <label className="block text-sm">Ghi chú đối chiếu nguồn<textarea className={input} maxLength={1000} value={note} onChange={e => setNote(e.target.value)} /></label>
        <div className="mt-4 flex flex-wrap gap-3">
          {reviewer && ["DRAFT", "REVIEWED", "BUILD_FAILED", "BUILT"].includes(version.state) && <><button disabled={busy || !note.trim()} onClick={() => void run(async () => { setPreview(null); await api.review(version, "approved", note); })}>Review đồng ý</button><button disabled={busy || !note.trim()} onClick={() => void run(async () => { setPreview(null); await api.review(version, "rejected", note); })}>Review không đạt</button></>}
          {["REVIEWED", "BUILT", "BUILD_FAILED"].includes(version.state) && <button disabled={busy} onClick={() => void run(async () => { setPreview(null); await api.build(version); })}>Build candidate local</button>}
          {reviewer && version.state === "BUILT" && <button disabled={busy} className="fluent-btn-primary" onClick={() => void run(async () => setPreview(await api.publicationPreview(version, "publish")))}>Xem trước xuất bản</button>}
          {reviewer && version.state === "PUBLISHED" && <button disabled={busy} onClick={() => void run(async () => setPreview(await api.publicationPreview(version, "withdraw")))}>Xem trước thu hồi</button>}
        </div>
        {preview && <section className="mt-4 rounded-xl border p-4 space-y-3"><h3 className="font-semibold">Preview {preview.payload.operation}</h3><p className="break-all text-sm">{preview.payload.version_id} · Hết hạn {new Date(preview.expires_at).toLocaleString("vi-VN")}</p>
          <p className="text-sm">Đổi nguồn current của nghiệp vụ demo; lịch sử/source bytes vẫn được giữ.</p><button disabled={busy} className="fluent-btn-primary" onClick={() => void run(async () => { await api.publish(preview); setPreview(null); setNotice("Đã ghi thay đổi active version"); })}>Xác nhận {preview.payload.operation === "withdraw" ? "thu hồi" : "xuất bản"}</button></section>}
      </> : <h2 className="font-semibold">Chọn phiên bản để đối chiếu</h2>}
      {source && <details open className="mt-5"><summary className="font-semibold">Original snapshot · {source.title}</summary><p className="mt-3 text-sm">{source.locator} · {source.filename}</p>
        <p className="break-all text-xs">Original SHA256 {source.original_sha256}</p><pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap text-sm">{original(source)}</pre></details>}
      </section></div>
      <div className="grid gap-5 lg:grid-cols-2"><form className={panel + " space-y-4"} onSubmit={e => { e.preventDefault(); void run(async () => {
        const uploaded = await api.upload({ title, filename, content, locator }); setSourceId(uploaded.id); setSelected(""); setText(content); setMapping("ORIGINAL_TEXT"); setNotice("Đã giữ immutable original snapshot; chưa xuất bản");
      }); }}><h2 className="font-semibold">Thêm snapshot nguồn demo</h2><fieldset disabled={busy} className="space-y-3">
        <label className="block text-sm">Tên nguồn<input required className={input} maxLength={200} value={title} onChange={e => setTitle(e.target.value)} /></label>
        <label className="block text-sm">Tên tệp .txt<input required className={input} value={filename} onChange={e => setFilename(e.target.value)} /></label>
        <label className="block text-sm">Locator / xuất xứ<input required className={input} maxLength={500} value={locator} onChange={e => setLocator(e.target.value)} /></label>
        <label className="block text-sm">Original UTF-8 (tối đa 16 KB)<textarea required className={input} maxLength={16000} value={content} onChange={e => setContent(e.target.value)} /></label>
      </fieldset><button type="submit" disabled={busy} className="fluent-btn-primary">Giữ snapshot mới</button></form>
      <form className={panel + " space-y-4"} onSubmit={e => { e.preventDefault(); void run(async () => {
        const created = await api.version({ source_id: sourceId, procedure: kind, text, mapping, effective_from: effectiveFrom, effective_until: effectiveUntil || null, candidate_text: candidate });
        setSelected(created.id); setNotice("Đã tạo rendition/version mới; cần admin khác review"); setPreview(null);
      }); }}><h2 className="font-semibold">Tạo rendition / version mới</h2><fieldset disabled={busy} className="space-y-3">
        <label className="block text-sm">Snapshot gốc<select required className={input} value={sourceId} onChange={e => {
          setSourceId(e.target.value); const s = state.sources.find(v => v.id === e.target.value); if (s) setText(original(s)); setMapping("ORIGINAL_TEXT");
        }}><option value="">Chọn nguồn</option>{state.sources.map(s => <option key={s.id} value={s.id}>{s.title} · {s.id.slice(-8)}</option>)}</select></label>
        <label className="block text-sm">Nghiệp vụ<select className={input} value={kind} onChange={e => setKind(e.target.value as ServiceKind)}><option value="GRADE_APPEAL">Phúc khảo demo</option><option value="GENERAL_SUPPORT">Hỗ trợ chung demo</option></select></label>
        <label className="block text-sm">Rendition<textarea required className={input} value={text} maxLength={16000} onChange={e => setText(e.target.value)} /></label>
        <label className="block text-sm">Mapping (ORIGINAL_TEXT hoặc REVIEWED_RENDITION: vị trí và sửa đổi)<input required className={input} maxLength={1000} value={mapping} onChange={e => setMapping(e.target.value)} /></label>
        <label className="block text-sm">Hiệu lực từ (ISO timezone)<input required className={input} value={effectiveFrom} onChange={e => setEffectiveFrom(e.target.value)} /></label>
        <label className="block text-sm">Hiệu lực đến (tùy chọn)<input className={input} value={effectiveUntil} onChange={e => setEffectiveUntil(e.target.value)} /></label>
        <label className="block text-sm">Candidate contextual text (tách khỏi evidence)<textarea className={input} maxLength={4000} value={candidate} onChange={e => setCandidate(e.target.value)} /></label>
      </fieldset><button type="submit" disabled={busy || !sourceId} className="fluent-btn-primary">Tạo version mới</button></form></div>
      <details className={panel}><summary className="font-semibold">Audit vận hành</summary><ol className="mt-3 space-y-3 text-sm">{state.history.map(e => <li key={e.id}>{e.occurred_at} · {e.action} · {e.target}<p>{e.note}</p></li>)}</ol></details>
    </>}
  </main></AppShell>;
}
