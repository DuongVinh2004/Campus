"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { ApiClient } from "../../lib/api/client";
import { KnowledgeIntake } from "./KnowledgeIntake";
import { RenditionCorrection } from "./RenditionCorrection";
import { EditionWorkspace } from "./EditionWorkspace";
import { KnowledgeSchedules } from "./KnowledgeSchedules";

const base = "/v1/knowledge/platform";
const client = () => new ApiClient();
type Version = { version_id: string; source_id: string; filename: string; created_by: string; revision: number;
  review_state: string; publication_state: string; original_sha256: string; rendition_sha256: string | null;
  revoked_at: string | null; index_version: string | null; effective_from: string | null; effective_until?: string | null;
  applicability_basis?: string | null; is_in_desired_release?: boolean; is_historical?: boolean; review_note?: string | null };
type Job = { id: string; version_id: string; state: string; stage: string; progress: number; attempts: number;
  error_code: string | null; cancel_requested: boolean };
type Pointer = { release_id: string | null; generation: number; policy_generation: number };
type State = { mode: string; environment?: string; correction_history_available?: boolean; edition_decisions_available?: boolean; session_schedules_available?: boolean; sources: Array<{ id: string; title: string; canonical_uri: string;
  disposition?: { category: string; note: string; related_source_id: string | null } }>;
  versions: Version[]; jobs: Job[]; desired: Pointer; is_serving: boolean;
  serving: Array<{ instance_id: string; release_id: string; generation: number; valid_until: string }>;
  runtime: Array<{ instance_id: string; error_code: string | null; live: boolean }>;
  releases: Array<{ id: string; document_count: number; membership_sha256: string }> };
type Preview = { preview_id: string; confirmation_token: string; expires_at: string;
  payload: { operation: string; target_id: string; generation: number; members: unknown[] } };
type Rendition = { pages: Array<{ page: number | null; text: string }>; issues: Array<{ page: number | null; code: string }> };
type Hit = { chunk_id: string; title: string; content_text: string; page_start: number | null; section_path: string; release_id: string };

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("campus247_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function checkedFetch(path: string, init: RequestInit = {}) {
  const response = await fetch(path, { ...init, headers: { ...authHeaders(), ...init.headers }, credentials: "include", cache: "no-store" });
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    throw new Error(typeof problem.detail === "string" ? problem.detail : response.status === 404
      ? "Runtime quản trị tri thức chưa được bật trên địa chỉ hiện tại."
      : response.status === 401 ? "Cần đăng nhập bằng phiên hợp lệ." : `Không thể thực hiện (${response.status}).`);
  }
  return response;
}

export function KnowledgePlatform() {
  const [state, setState] = useState<State | null>(null);
  const [actor, setActor] = useState<{ user_id: string; roles: string[] } | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState("");
  const [rendition, setRendition] = useState<Rendition | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [releaseId, setReleaseId] = useState("");
  const [note, setNote] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [libraryFilter, setLibraryFilter] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [applicableFrom, setApplicableFrom] = useState("");
  const [applicableUntil, setApplicableUntil] = useState("");
  const [basis, setBasis] = useState("");
  const uploadKey = useRef<string | null>(null);
  const version = state?.versions.find(v => v.version_id === selected);
  const source = state?.sources.find(s => s.id === version?.source_id);
  const job = state?.jobs.find(j => j.version_id === selected);
  const mayReview = actor && version && actor.user_id !== version.created_by;

  const load = useCallback(async () => {
    const [nextState, currentActor] = await Promise.all([
      client().get<State>(base + "/state"), client().get<{ user_id: string; roles: string[] }>("/v1/users/me")]);
    setState(nextState); setActor(currentActor);
  }, []);
  useEffect(() => {
    let active = true;
    const refresh = async () => { try { if (active) await load(); } catch (e) { if (active) setError((e as Error).message); } };
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => { active = false; clearInterval(timer); };
  }, [load]);

  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); await load(); } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function choose(identifier: string) {
    setSelected(identifier); setPreview(null); setRendition(null); setNote(""); setApplicableFrom(""); setApplicableUntil(""); setBasis("");
    await run(async () => {
      const data = await client().get<Rendition>(`${base}/versions/${identifier}/rendition`);
      setRendition(data);
    });
  }
  async function requestPreview(operation: "activate" | "revoke" | "rollback", target_id: string) {
    if (!state) return;
    setPreview(await client().post<Preview>(base + "/previews", { operation, target_id, expected_generation: state.desired.generation }));
  }

  return <AppShell userRole="admin" activeNav="knowledge"><main className="campus-knowledge space-y-5">
    <header><h1 className="text-2xl font-semibold">Kho tri thức RAG</h1>
      <p className="mt-2 text-sm">Tài liệu gốc → xử lý nền BGE → duyệt độc lập → xuất bản → xác nhận runtime.</p></header>
    {error && <div role="alert" className="rounded-xl border border-red-300 p-4 text-red-800">{error}
      <button className="ml-3 underline" disabled={busy} onClick={() => void run(async () => {})}>Tải lại</button>
      {/phiên|đăng nhập/i.test(error) && <a className="ml-3 underline" href="/login">Đăng nhập tài khoản quản trị</a>}</div>}
    {notice && <p role="status" className="rounded-xl bg-green-50 p-3 text-green-900">{notice}</p>}
    {process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM !== "true" && <details className="campus-panel"><summary>Phiên phát triển local</summary>
      <p className="my-3 text-sm">Tài khoản thử có vai trò thật trong phiên local. KA01 tạo tài liệu; KA02 duyệt và xác nhận. Nội dung upload được lưu thật.</p>
      <div className="flex flex-wrap gap-3">{["KA01", "KA02", "SV01"].map(account => <button key={account} disabled={busy} onClick={() => void run(async () => {
        const response = await client().post<{ token: string }>(base + "/local-session", { account });
        localStorage.setItem("campus247_token", response.token); setPreview(null); setState(null); setSelected(""); setRendition(null);
        setNotice(`Đã mở phiên ${account}.`);
      })}>Đăng nhập {account}</button>)}</div>
      {actor && <p className="mt-3 break-all text-xs">{actor.user_id} · {actor.roles.join(", ")}</p>}
    </details>}
    {state && <>
      {state.environment === "rehearsal" && <p className="campus-panel text-sm" role="status">Bản chạy thử tiếp nhận tài liệu · Hồ sơ mới được lưu trong kho thử riêng.</p>}
      <section className="campus-panel space-y-2"><h2 className="font-semibold">Xuất bản và phục vụ</h2>
        <p className="break-all text-sm">Desired: {state.desired.release_id || "Chưa xuất bản"} · generation {state.desired.generation}</p>
        <p role="status" className="font-medium">{state.is_serving ? "Runtime đã xác nhận phục vụ release hiện tại" : "Chưa có xác nhận phục vụ còn hiệu lực"}</p>
        {state.serving.map(a => <p key={a.instance_id} className="text-xs">{a.instance_id} · ack đến {new Date(a.valid_until).toLocaleTimeString("vi-VN")}</p>)}
        {state.runtime.filter(a => a.error_code).map(a => <p key={a.instance_id} className="text-red-700">{a.instance_id}: {a.error_code}</p>)}
        <a href="/chat" className="underline">Mở chatbot kiểm chứng nguồn</a>
      </section>
      <KnowledgeIntake onResolved={identifier => { void choose(identifier); }} />
      {state.session_schedules_available && <KnowledgeSchedules releases={state.releases} generation={state.desired.generation}
        onPreview={identifier => run(() => requestPreview("activate", identifier))} />}
      <form className="campus-panel space-y-4" onChange={() => { uploadKey.current = null; }} onSubmit={event => {
        event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); const file = data.get("file") as File;
        void run(async () => {
          if (!file?.size || file.size > 50 * 1024 * 1024) throw new Error("Chọn PDF/TXT, tối đa 50 MB.");
          const metadata = { title: data.get("title"), owner_unit: data.get("owner_unit"), canonical_uri: data.get("canonical_uri"),
            programs: ["PUBLIC"], audiences: ["STUDENT", "KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"],
            effective_from: data.get("effective_from") ? new Date(String(data.get("effective_from"))).toISOString() : null,
            ...(data.get("source_id") ? { source_id: data.get("source_id") } : {}) };
          const payload = new FormData(); payload.append("metadata", JSON.stringify(metadata)); payload.append("file", file);
          uploadKey.current ||= crypto.randomUUID();
          const response = await checkedFetch(base + "/uploads", { method: "POST", body: payload, headers: { "Idempotency-Key": uploadKey.current } });
          const result = await response.json(); setSelected(result.version_id); form.reset(); uploadKey.current = null;
          setNotice(`Đã tiếp nhận, job ${result.job_id} đang chờ worker. Chưa xuất bản.`);
        });
      }}><h2 className="font-semibold">Upload tài liệu</h2><fieldset disabled={busy} className="grid gap-4 md:grid-cols-2">
        <label>Tên tài liệu<input name="title" className="fluent-input w-full" required minLength={3} maxLength={300} /></label>
        <label>Đơn vị ban hành<input name="owner_unit" className="fluent-input w-full" required minLength={2} maxLength={160} /></label>
        <label>URI gốc / xuất xứ<input name="canonical_uri" placeholder="https://… hoặc urn:…" className="fluent-input w-full" required /></label>
        <label>Bắt đầu hiệu lực<input name="effective_from" type="datetime-local" className="fluent-input w-full" /></label>
        <label>Phiên bản của nguồn<select name="source_id" className="fluent-input w-full"><option value="">Nguồn mới</option>
          {state.sources.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select></label>
        <label>File PDF/TXT UTF-8<input name="file" type="file" accept=".pdf,.txt" required className="block mt-2" /></label>
        <p className="text-sm md:col-span-2">Phạm vi lát đầu: HUCE / FIT / PUBLIC, sinh viên và quản trị. Chỉ upload tài liệu được phép trong phạm vi này. Chưa rõ hiệu lực vẫn tiếp nhận, nhưng chưa thể xuất bản.</p>
        <button type="submit" className="fluent-btn-primary">{busy ? "Đang thực hiện…" : "Tiếp nhận và tạo job"}</button>
      </fieldset></form>
      <div className="campus-workflow-grid"><section className="campus-panel"><h2 className="font-semibold">Thư viện và jobs</h2>
        <p className="my-2 text-sm">{state.sources.length} nguồn · {state.versions.filter(v => v.is_historical).length} phiên bản lịch sử được giữ lại.</p>
        <label className="block my-2 text-sm"><input type="checkbox" checked={showHistory} onChange={e => setShowHistory(e.target.checked)} /> Hiện cả phiên bản lịch sử</label>
        <label className="block my-3 text-sm">Lọc tên nguồn, tệp hoặc trạng thái<input className="fluent-input w-full" value={libraryFilter} onChange={e => setLibraryFilter(e.target.value)} /></label>
        {!state.versions.length && <p className="my-4">Chưa có tài liệu. Tệp upload sẽ xuất hiện ở đây.</p>}
        <ul className="mt-4 space-y-3">{state.versions.filter(v => {
          if (!showHistory && v.is_historical) return false;
          const searchKey = (s: string) => s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d");
          return searchKey(`${state.sources.find(s => s.id === v.source_id)?.title} ${v.filename} ${v.review_state} ${v.publication_state}`).includes(searchKey(libraryFilter));
        }).map(v => {
          const j = state.jobs.find(item => item.version_id === v.version_id);
          return <li key={v.version_id}><button disabled={busy} className="w-full rounded-xl border p-3 text-left" onClick={() => void choose(v.version_id)}>
            <strong>{state.sources.find(s => s.id === v.source_id)?.title || v.filename}</strong><span className="block text-xs break-all">{v.filename} · {v.version_id.slice(-8)}</span>
            <span className="block text-sm">{v.review_state} · {v.revoked_at ? "ĐÃ THU HỒI" : v.publication_state}</span>
            <span className="block text-xs">{v.is_in_desired_release ? "Trong release đích" : "Ngoài release đích"}</span>
            {v.is_historical && <span className="block text-xs">Bản lịch sử; nguồn đã có phiên bản mới hơn trong release.</span>}
            {!v.effective_from && !v.is_historical && <span className="block text-xs text-amber-800">Chưa xác minh ngày hiệu lực; chưa được phục vụ.</span>}
            {v.review_state === "NEEDS_REVIEW" && !v.is_historical && <span className="block text-xs text-amber-800">Cần đối chiếu nguyên bản, OCR/bảng và phạm vi; không phải tài liệu đã duyệt.</span>}
            {j && <span className="block text-xs">{j.state} · {j.stage} · {j.progress}% {j.error_code ? `· ${j.error_code}` : ""}</span>}
          </button></li>;
        })}</ul></section>
        <section className="campus-panel space-y-3"><h2 className="font-semibold">{source?.title || "Chọn tài liệu để đối chiếu"}</h2>
          {source?.disposition && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-950">{source.disposition.note}</p>}
          {version && <><p className="break-all text-xs">Version {version.version_id} · revision {version.revision}</p>
            {version.review_note && <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">Ghi nhận duyệt: {version.review_note}</p>}
            <p className="break-all text-xs">Original SHA256: {version.original_sha256}</p>
            <p className="text-sm">Hiệu lực: {version.effective_from || "CHƯA XÁC MINH"} → {version.effective_until || "Chưa có ngày kết thúc đã ghi"}</p>
            {version.applicability_basis && <p className="text-sm">Căn cứ hiệu lực: {version.applicability_basis}</p>}
            <button disabled={busy} onClick={() => void run(async () => {
              const response = await checkedFetch(`${base}/versions/${version.version_id}/original`);
              const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a");
              link.href = url; link.download = version.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 30_000);
            })}>Tải original để đối chiếu</button>
            {rendition && <><p className="text-sm">Rendition: {rendition.pages.length} trang/khối · {rendition.issues.length} lỗi cần xử lý</p>
              <div className="max-h-96 overflow-auto rounded-xl border p-3">{rendition.pages.map((p, i) => <section key={i} className="mb-4">
                <h3 className="text-sm font-semibold">{p.page ? `Trang ${p.page}` : `Khối văn bản ${i + 1}`}</h3><pre className="whitespace-pre-wrap text-sm">{p.text}</pre></section>)}</div></>}
            {job && <div className="flex gap-3"><progress aria-label="Tiến độ xử lý" value={job.progress} max={100} />
              {["QUEUED", "RUNNING", "RETRY_WAIT"].includes(job.state) && <button disabled={busy || job.cancel_requested} onClick={() => void run(async () => { await client().post(`${base}/jobs/${job.id}/cancel`); })}>Hủy job</button>}
              {["FAILED", "CANCELLED"].includes(job.state) && <button disabled={busy || job.attempts >= 3} onClick={() => void run(async () => { await client().post(`${base}/jobs/${job.id}/retry`); })}>Thử lại từ checkpoint</button>}
              {job.attempts >= 3 && <p className="text-sm">Đã dùng hết ba lần xử lý; checkpoint được giữ để đối chiếu nguyên nhân.</p>}</div>}
            {state.correction_history_available && actor && version.publication_state === "DRAFT" && !version.revoked_at &&
              <RenditionCorrection key={version.version_id} versionId={version.version_id} actorId={actor.user_id} authorId={version.created_by} onCreated={id => void choose(id)} />}
            {state.edition_decisions_available && actor && <EditionWorkspace key={`edition:${version.version_id}`} versionId={version.version_id} actorId={actor.user_id} />}
            {version.index_version && !version.revoked_at && <details className="rounded-xl border p-3 space-y-3"><summary>Bổ sung hiệu lực bằng phiên bản mới</summary>
              <p className="my-3 text-sm">Nhập ngày và căn cứ đã kiểm chứng từ nguồn. Bản mới dùng lại original/vector đúng input, cần người khác duyệt trước khi xuất bản.</p>
              <label className="block text-sm">Ngày bắt đầu đã xác minh<input type="datetime-local" className="fluent-input w-full" value={applicableFrom} onChange={e => setApplicableFrom(e.target.value)} /></label>
              <label className="block text-sm">Ngày kết thúc nếu có<input type="datetime-local" className="fluent-input w-full" value={applicableUntil} onChange={e => setApplicableUntil(e.target.value)} /></label>
              <label className="block text-sm">Căn cứ trong văn bản<textarea className="fluent-input w-full" value={basis} maxLength={2000} onChange={e => setBasis(e.target.value)} /></label>
              <button disabled={busy || !applicableFrom || basis.trim().length < 10} onClick={() => void run(async () => {
                const result = await client().post<{ version_id: string }>(`${base}/versions/${version.version_id}/applicability-versions`, {
                  expected_revision: version.revision, effective_from: new Date(applicableFrom).toISOString(),
                  effective_until: applicableUntil ? new Date(applicableUntil).toISOString() : null, basis,
                }, { "Idempotency-Key": `applicability:${version.version_id}:${version.revision}:${applicableFrom}:${applicableUntil}` });
                setSelected(result.version_id); setPreview(null); setNote(""); setNotice("Đã tạo phiên bản metadata mới, cần duyệt độc lập; release đang phục vụ giữ nguyên.");
              })}>Tạo phiên bản để duyệt</button>
            </details>}
            <label className="block">Ghi chú đối chiếu original và rendition<textarea className="fluent-input w-full" value={note} maxLength={2000} onChange={e => setNote(e.target.value)} /></label>
            <div className="flex flex-wrap gap-3">
              {mayReview && version.index_version && version.publication_state === "DRAFT" && ["APPROVED", "REJECTED"].map(verdict => <button key={verdict} disabled={busy || note.trim().length < 5} onClick={() => void run(async () => {
                await client().post(`${base}/versions/${version.version_id}/reviews`, { expected_revision: version.revision, verdict, note }); setPreview(null);
              })}>{verdict === "APPROVED" ? "Duyệt nội dung" : "Từ chối"}</button>)}
              {version.review_state === "APPROVED" && !version.revoked_at && <button disabled={busy} onClick={() => void run(async () => {
                const result = await client().post<{ release_id: string }>(`${base}/versions/${version.version_id}/releases`, {},
                  { "Idempotency-Key": `build:${version.version_id}:${version.revision}:${state.desired.generation}` });
                setReleaseId(result.release_id); setNotice("Release ứng viên đã dựng, chưa xuất bản.");
              })}>Dựng release ứng viên</button>}
              {mayReview && version.publication_state === "PUBLISHED" && !version.revoked_at && <button disabled={busy} onClick={() => void run(() => requestPreview("revoke", version.version_id))}>Xem trước thu hồi</button>}
            </div></>}
        </section></div>
      <section className="campus-panel space-y-4"><h2 className="font-semibold">Kiểm chứng và kích hoạt release</h2>
        <label>Release<select className="fluent-input w-full" value={releaseId} onChange={e => { setReleaseId(e.target.value); setPreview(null); setHits([]); }}>
          <option value="">Chọn release</option>{state.releases.map(r => <option key={r.id} value={r.id}>{r.id} · {r.document_count} tài liệu</option>)}</select></label>
        <label>Câu hỏi kiểm chứng<input className="fluent-input w-full" value={query} maxLength={2000} onChange={e => setQuery(e.target.value)} /></label>
        <div className="flex flex-wrap gap-3"><button disabled={busy || !releaseId || query.trim().length < 3} onClick={() => void run(async () => {
          const result = await client().post<{ items: Hit[] }>(base + "/search-preview", { query, release_id: releaseId }); setHits(result.items);
          setNotice(`${result.items.length} đoạn ứng viên, cần đối chiếu nội dung và locator.`);
        })}>Tìm thử bằng BGE</button>
          <button disabled={busy || !releaseId} onClick={() => void run(() => requestPreview("activate", releaseId))}>Xem trước xuất bản</button>
          <button disabled={busy || !releaseId} onClick={() => void run(() => requestPreview("rollback", releaseId))}>Xem trước quay về release</button></div>
        {hits.map(hit => <article key={hit.chunk_id} className="rounded-xl border p-3"><h3 className="font-semibold">{hit.title} {hit.page_start ? `· trang ${hit.page_start}` : ""}</h3>
          <p className="text-xs break-all">{hit.section_path} · release {hit.release_id}</p><p className="whitespace-pre-wrap text-sm mt-2">{hit.content_text}</p></article>)}
        {preview && <section className="rounded-xl border-2 p-4 space-y-3"><h3 className="font-semibold">Xác nhận {preview.payload.operation}</h3>
          <p className="break-all">Đích: {preview.payload.target_id} · expected generation {preview.payload.generation}</p>
          <p>Membership: {preview.payload.members.length} tài liệu · hết hạn {new Date(preview.expires_at).toLocaleString("vi-VN")}</p>
          <pre className="text-xs whitespace-pre-wrap break-all max-h-48 overflow-auto">{JSON.stringify(preview.payload.members, null, 2)}</pre>
          <p className="text-sm">Thao tác ghi desired pointer. Trạng thái phục vụ chỉ đổi sau khi runtime xác nhận đúng generation.</p>
          <button disabled={busy} className="fluent-btn-primary" onClick={() => void run(async () => {
            await client().post(base + "/confirmations", { preview_id: preview.preview_id, confirmation_token: preview.confirmation_token, confirmed: true },
              { "Idempotency-Key": `confirm:${preview.preview_id}` }); setPreview(null); setNotice("Đã ghi thay đổi; đang chờ xác nhận runtime.");
          })}>Tôi xác nhận thao tác này</button><button disabled={busy} className="ml-3" onClick={() => setPreview(null)}>Bỏ preview</button>
        </section>}
      </section>
    </>}
  </main></AppShell>;
}
