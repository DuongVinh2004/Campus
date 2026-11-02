"use client";

import React, { FormEvent, useEffect, useRef, useState } from "react";

type Page = { page: number; text: string; expected_page_sha256: string; preview_image_sha256: string };
type Preview = { expected_revision: number; expected_rendition_sha256: string; intake_id: string; pages: Page[] };
type Item = { id: string; created_by: string; proposal_sha256: string; revision: number; version_id: string | null; latest_verdict?: string | null };
type Detail = { correction_id: string; created_by: string; proposal_sha256: string; revision: number; intake_id: string; pages: Page[]; note: string };
const base = "/v1/knowledge/platform";

async function request(path: string, init: RequestInit = {}) {
  const response = await fetch(path, { ...init, credentials: "include", cache: "no-store",
    headers: init.headers });
  if (!response.ok) { const problem = await response.json().catch(() => ({})); throw new Error(typeof problem.detail === "string" ? problem.detail : `Chưa thực hiện được (${response.status}).`); }
  return response;
}

export function RenditionCorrection({ versionId, actorId, authorId, onCreated }: {
  versionId: string; actorId: string; authorId: string; onCreated: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [history, setHistory] = useState<Item[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [texts, setTexts] = useState<Record<number,string>>({});
  const [reviewVerdict, setReviewVerdict] = useState("REJECTED");
  const [images, setImages] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const key = useRef<string | null>(null);
  const urls = useRef<string[]>([]);
  useEffect(() => () => urls.current.forEach(url => URL.revokeObjectURL(url)), []);
  async function load() {
    const [a, b] = await Promise.all([request(`${base}/versions/${versionId}/correction-preview`), request(`${base}/versions/${versionId}/corrections`)]);
    setPreview(await a.json()); setHistory((await b.json()).items);
  }
  async function run(action: () => Promise<void>) {
    setBusy(true); setError("");
    try { await action(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function propose(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!preview) return;
    const form = event.currentTarget; const data = new FormData(form); const page = preview.pages[pageIndex];
    await run(async () => {
      key.current ||= crypto.randomUUID();
      const response = await request(`${base}/versions/${versionId}/corrections`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key.current },
        body: JSON.stringify({ expected_revision: preview.expected_revision, expected_rendition_sha256: preview.expected_rendition_sha256,
          pages: [{ ...page, text: data.get("corrected_text") }], note: data.get("note"), confirmed_source_comparison: data.get("compared") === "on" }) });
      await response.json(); key.current = null; form.reset(); setTexts(old => { const next = {...old}; delete next[page.page]; return next; });
      setNotice("Đã lưu đề xuất. Cần người khác đối chiếu độc lập; bản đang phục vụ giữ nguyên."); await load();
    });
  }
  async function review(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!detail) return;
    const data = new FormData(event.currentTarget);
    await run(async () => {
      key.current ||= crypto.randomUUID();
      const response = await request(`${base}/corrections/${detail.correction_id}/reviews`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key.current },
        body: JSON.stringify({ expected_revision: detail.revision, expected_proposal_sha256: detail.proposal_sha256,
          verdict: data.get("verdict"), coverage: data.get("verdict") === "APPROVED" ? "PROSE_ONLY" : null, note: data.get("note"), confirmed_full_page_and_conditions: data.get("compared") === "on" }) });
      const result = await response.json(); key.current = null; setDetail(null);
      setNotice(result.version_id ? "Đã tạo bản trích xuất mới của cùng edition. Còn bước lập chỉ mục và duyệt xuất bản; chưa phát hành." : "Đã giữ quyết định từ chối trong lịch sử.");
      await load(); if (result.version_id) onCreated(result.version_id);
    });
  }
  async function image(intake: string, page: number) {
    await run(async () => {
      const response = await request(`${base}/intakes/${intake}/pages/${page}/preview`);
      const url = URL.createObjectURL(await response.blob()); urls.current.push(url); setImages(old => ({ ...old, [`${intake}:${page}`]: url }));
    });
  }
  if (!open) return <button onClick={() => { setOpen(true); void run(load); }}>Sửa chữ/OCR bằng bản mới</button>;
  return <section aria-label="Sửa bản trích xuất có lịch sử" className="rounded-xl border p-3 space-y-3">
    <h3 className="font-semibold">Sửa chữ/OCR, giữ bản gốc và lịch sử</h3>
    <p className="text-sm">Chỉ dùng cho trang văn xuôi. Bảng, tiêu đề/đơn vị chung và quan hệ chưa rõ cần kiểm cấu trúc riêng. Ngày ban hành và hiệu lực giữ nguyên.</p>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {preview && actorId === authorId && <form onSubmit={event => void propose(event)} onChange={() => { key.current = null; }}>
      <fieldset disabled={busy} className="space-y-3">
        <label>Trang có ảnh đối chiếu<select value={pageIndex} onChange={event => setPageIndex(Number(event.target.value))}>{preview.pages.map((page, index) => <option key={page.page} value={index}>Trang {page.page}</option>)}</select></label>
        {preview.pages[pageIndex] && <>
          <button type="button" onClick={() => void image(preview.intake_id, preview.pages[pageIndex].page)}>Mở ảnh trang cần sửa</button>
          {images[`${preview.intake_id}:${preview.pages[pageIndex].page}`] && <img src={images[`${preview.intake_id}:${preview.pages[pageIndex].page}`]} alt="Ảnh gốc để đối chiếu toàn trang" className="w-full" />}
          <label className="block">Toàn bộ chữ của trang đã đối chiếu<textarea name="corrected_text" className="fluent-input w-full min-h-48" value={texts[preview.pages[pageIndex].page] ?? preview.pages[pageIndex].text}
            onChange={event => setTexts(old => ({...old,[preview.pages[pageIndex].page]:event.target.value}))} required minLength={20} maxLength={200000} /></label>
          <label className="block">Căn cứ đề xuất sửa<textarea name="note" required minLength={10} maxLength={2000} className="fluent-input w-full" /></label>
          <label className="block"><input type="checkbox" name="compared" required /> Tôi đã đối chiếu chữ với đúng ảnh toàn trang, giữ điều kiện và ngoại lệ.</label>
          <button type="submit">Lưu đề xuất để người khác đối chiếu</button>
        </>}
      </fieldset>
    </form>}
    {history.map(item => <div key={item.id} className="border-t pt-2 text-sm">
      <p>Đề xuất {item.id} · revision {item.revision}{item.version_id ? " · Đã có rendition riêng" : item.latest_verdict === "REJECTED" ? " · Đã từ chối, giữ lịch sử" : " · Chờ quyết định độc lập"}</p>
      <button disabled={busy} onClick={() => void run(async () => { setDetail(await (await request(`${base}/corrections/${item.id}`)).json()); key.current = null; setReviewVerdict("REJECTED"); })}>Mở đề xuất để đối chiếu</button>
    </div>)}
    {detail && <form onSubmit={event => void review(event)} onChange={() => { key.current = null; }} className="space-y-3 border-t pt-3">
      <p className="text-sm">Căn cứ người đề xuất: {detail.note}</p>
      {detail.pages.map(page => <div key={page.page} className="space-y-2">
        <button type="button" disabled={busy} onClick={() => void image(detail.intake_id, page.page)}>Đối chiếu ảnh gốc trang {page.page}</button>
        {images[`${detail.intake_id}:${page.page}`] && <img src={images[`${detail.intake_id}:${page.page}`]} alt={`Ảnh gốc trang ${page.page} để duyệt bản sửa`} className="w-full" />}
        <pre className="whitespace-pre-wrap text-sm">{page.text}</pre>
      </div>)}
      {detail.created_by === actorId ? <p>Người đề xuất không được tự duyệt. Cần một người khác có quyền quản trị.</p> : <fieldset disabled={busy} className="space-y-3">
        <label className="block">Kết luận<select name="verdict" value={reviewVerdict} onChange={event => setReviewVerdict(event.target.value)}><option value="REJECTED">Chưa đạt, giữ từ chối</option><option value="APPROVED">Đạt đối chiếu chữ toàn trang</option></select></label>
        <label className="block">Ghi nhận đối chiếu độc lập<textarea name="note" required minLength={10} maxLength={2000} className="fluent-input w-full" /></label>
        <label className="block"><input name="compared" type="checkbox" required={reviewVerdict === "APPROVED"} /> Tôi đã đối chiếu toàn trang, xác nhận chỉ có văn xuôi và giữ đủ điều kiện/ngoại lệ.</label>
        <button type="submit">Ghi quyết định độc lập</button>
      </fieldset>}
      <button type="button" onClick={() => setDetail(null)}>Đóng đề xuất</button>
    </form>}
    <button type="button" onClick={() => setOpen(false)}>Đóng sửa bản trích xuất</button>
  </section>;
}
