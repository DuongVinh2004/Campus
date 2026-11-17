"use client";

import React, { FormEvent, useCallback, useEffect, useRef, useState } from "react";

type Intake = {
  id: string; filename: string; state: string; stage: string; progress: number; revision: number;
  job_id: string; original_sha256: string; observed_at: string; version_id: string | null;
  can_refresh_url?: boolean;
  hints: { title_hint?: string; source_uri?: string };
  issues: Array<{ id: string; code: string; fields: string[]; evidence: {
    title_candidate?: string; candidate_is_verified?: boolean; extraction_issues?: Array<{ page: number; code: string }>;
    preview_pages?: number[];
    generation?: number; policy_generation?: number; duplicate_candidates?: DuplicateCandidate[];
    evidence_unit_count?: number;
    ocr_pages?: number[]; ocr_pending_pages?: number[];
  } }>;
};
type DuplicateCandidate = { version_id: string; source_id: string; title: string; canonical_uri: string };
type EvidenceView = { unit_count: number; dependency_count: number; issue_count: number; offset: number; next_offset: number | null;
  units: Array<{ id: string; kind: string; verbatim: string; locator: { page: number | null; char_start: number | null; char_end: number | null; bbox: number[] | null } }> };
type OcrView = { text: string; confidence: number; evidence?: {
  unit_count: number; dependency_count: number; offset: number; next_offset: number | null;
  units: EvidenceView["units"];
} | null };

const base = "/v1/knowledge/platform/intakes";
const labels: Record<string, string> = { QUEUED: "Đã tiếp nhận, chờ xử lý", RUNNING: "Đang xử lý", RETRY_WAIT: "Đang chờ thử lại",
  NEEDS_INFORMATION: "Cần bổ sung thông tin nguồn", SUCCEEDED: "Đã chuyển sang đối chiếu và duyệt", FAILED: "Xử lý gặp lỗi", CANCELLED: "Đã hủy" };

async function request(path: string, init: RequestInit = {}) {
  const response = await fetch(path, { ...init, credentials: "include", cache: "no-store",
    headers: init.headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Không thể tiếp nhận tài liệu (${response.status}).`);
  }
  return response;
}

export function KnowledgeIntake({ onResolved }: { onResolved: (version: string) => void }) {
  const [items, setItems] = useState<Intake[]>([]);
  const [available, setAvailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selected, setSelected] = useState<Intake | null>(null);
  const [linkChoice, setLinkChoice] = useState<{ intake: Intake; candidate: DuplicateCandidate; generation: number; policy: number } | null>(null);
  const [separateChoice, setSeparateChoice] = useState<Intake | null>(null);
  const [previewImages, setPreviewImages] = useState<Record<string, string>>({});
  const [evidenceView, setEvidenceView] = useState<{ intake: string; result: EvidenceView } | null>(null);
  const [ocrViews, setOcrViews] = useState<Record<string, OcrView>>({});
  const previewUrls = useRef<string[]>([]);
  const requestKey = useRef<string | null>(null);
  const urlKey = useRef<string | null>(null);
  const resolutionKey = useRef<string | null>(null);
  const linkKey = useRef<string | null>(null);
  const recheckKeys = useRef<Record<string,string>>({});
  const refreshKeys = useRef<Record<string,string>>({});
  const load = useCallback(async () => {
    const response = await request(base);
    const body = await response.json();
    // A prior local server can still serve the rest of the administration UI.
    if (Array.isArray(body.items)) { setItems(body.items); setAvailable(true); }
  }, []);
  useEffect(() => {
    let alive = true;
    const refresh = async () => { try { if (alive) await load(); } catch (e) { if (alive) setError((e as Error).message); } };
    void refresh();
    const timer = setInterval(() => void refresh(), 4000);
    return () => { alive = false; clearInterval(timer); };
  }, [load]);
  useEffect(() => () => { previewUrls.current.forEach(url => URL.revokeObjectURL(url)); }, []);

  async function viewOcr(intakeId: string, page: number, offset = 0) {
    setBusy(true); setError("");
    try {
      const response = await request(`${base}/${intakeId}/pages/${page}/ocr?offset=${offset}&limit=20`);
      const result: OcrView = await response.json();
      setOcrViews(views => ({ ...views, [`${intakeId}:${page}`]: result }));
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function accept(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget;
    const data = new FormData(form);
    const file = (form.elements.namedItem("draft_file") as HTMLInputElement).files?.[0];
    if (!file?.size) { setError("Chọn tệp PDF hoặc TXT có nội dung."); return; }
    setBusy(true); setError("");
    try {
      const payload = new FormData(); payload.append("file", file);
      payload.append("metadata", JSON.stringify({ source_uri: data.get("draft_uri") || null }));
      requestKey.current ||= crypto.randomUUID();
      const response = await request(base, { method: "POST", body: payload, headers: { "Idempotency-Key": requestKey.current } });
      const result = await response.json();
      setNotice(`Đã tiếp nhận hồ sơ ${result.intake_id}. Bạn có thể đóng trang và quay lại theo dõi. Chưa phát hành.`);
      form.reset(); requestKey.current = null; await load();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function resolve(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selected) return;
    const data = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      resolutionKey.current ||= crypto.randomUUID();
      const response = await request(`${base}/${selected.id}/metadata`, { method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": resolutionKey.current },
        body: JSON.stringify({ expected_revision: selected.revision, metadata: {
          title: data.get("title"), owner_unit: data.get("owner_unit"), canonical_uri: data.get("canonical_uri"),
          campus: "HUCE", faculties: ["FIT"], programs: String(data.get("programs")).split(",").map(p => p.trim()).filter(Boolean),
          audiences: ["STUDENT", "KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"], effective_from: null, effective_until: null,
        } }) });
      const result = await response.json(); setSelected(null); resolutionKey.current = null;
      setNotice("Đã bổ sung thông tin nguồn. Cần đối chiếu nội dung, căn cứ hiệu lực và duyệt theo quyền trước khi phát hành.");
      onResolved(result.version_id); await load();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function acceptUrl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget;
    setBusy(true); setError("");
    try {
      urlKey.current ||= crypto.randomUUID();
      const response = await request("/v1/knowledge/platform/url-intakes", { method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": urlKey.current },
        body: JSON.stringify({ url: new FormData(form).get("fetch_url") }) });
      const result = await response.json();
      setNotice(`Đã tạo hồ sơ URL ${result.intake_id}. Hệ thống sẽ tải nền; lỗi truy cập không tự thu hồi nguồn đang dùng.`);
      form.reset(); urlKey.current = null; await load();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function linkExisting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!linkChoice) return;
    const data = new FormData(event.currentTarget); setBusy(true); setError("");
    try {
      linkKey.current ||= crypto.randomUUID();
      const response = await request(`${base}/${linkChoice.intake.id}/link-existing`, { method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": linkKey.current },
        body: JSON.stringify({ expected_revision: linkChoice.intake.revision, expected_generation: linkChoice.generation,
          expected_policy_generation: linkChoice.policy, version_id: linkChoice.candidate.version_id,
          source_uri: linkChoice.candidate.canonical_uri, basis: data.get("basis"), confirmed_same_source: data.get("same_source") === "on" }) });
      const result = await response.json(); setLinkChoice(null); linkKey.current = null;
      setNotice("Đã ghi nhận lần tiếp nhận mới và dùng lại bằng chứng hiện có. Phiên bản, ngày hiệu lực và bản phát hành giữ nguyên.");
      onResolved(result.version_id); await load();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function keepSeparate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!separateChoice) return;
    const data = new FormData(event.currentTarget); setBusy(true); setError("");
    try {
      linkKey.current ||= crypto.randomUUID();
      await request(`${base}/${separateChoice.id}/keep-separate`, { method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": linkKey.current },
        body: JSON.stringify({ expected_revision: separateChoice.revision, reason: data.get("reason") }) });
      setSeparateChoice(null); linkKey.current = null;
      setNotice("Đã giữ riêng xuất xứ và tiếp tục xử lý nền."); await load();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function viewEvidence(intake: string, offset = 0) {
    setBusy(true); setError("");
    try {
      const response = await request(`${base}/${intake}/evidence?offset=${offset}&limit=20`);
      setEvidenceView({ intake, result: await response.json() });
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return <section className="campus-panel space-y-4" aria-label="Tiếp nhận tài liệu nền">
    <h2 className="font-semibold">Thêm tài liệu, bổ sung thông tin sau</h2>
    <p className="text-sm">Tải tệp trước; hệ thống xử lý nền và giữ tiến độ khi bạn rời trang. Ngày tải lên không được dùng làm ngày hiệu lực.</p>
    {error && <p role="alert" className="text-sm text-red-800">{error}</p>}
    {notice && <p role="status" className="text-sm">{notice}</p>}
    <form onSubmit={event => void accept(event)} onChange={() => { requestKey.current = null; }}>
      <fieldset disabled={busy || !available} className="grid gap-3 md:grid-cols-2">
        <label>Tệp tiếp nhận PDF/TXT<input name="draft_file" type="file" accept=".pdf,.txt" required /></label>
        <label>URL xuất xứ nếu biết<input name="draft_uri" type="url" pattern="https://.*" placeholder="https://…" className="fluent-input w-full" /></label>
        <button className="fluent-btn-primary" type="submit">Tiếp nhận trước, xử lý nền</button>
      </fieldset>
    </form>
    <form onSubmit={event => void acceptUrl(event)} onChange={() => { urlKey.current = null; }}>
      <fieldset disabled={busy || !available} className="grid gap-3 md:grid-cols-2">
        <label>Hoặc URL tài liệu công khai HUCE<input name="fetch_url" type="url" pattern="https://.*" className="fluent-input w-full" required placeholder="https://…huce.edu.vn/…" /></label>
        <button type="submit" className="fluent-btn-primary">Tiếp nhận URL và tải nền</button>
        <p className="text-xs md:col-span-2">Hiện nhận PDF/TXT qua HTTPS thuộc HUCE. Trang có liên kết đính kèm, nguồn ngoài phạm vi hoặc yêu cầu đăng nhập sẽ cần đối chiếu.</p>
      </fieldset>
    </form>
    {!available && <p className="text-sm">Luồng tiếp nhận nền chưa sẵn sàng trên phiên ứng dụng này.</p>}
    <ul className="space-y-3">{items.map(item => <li key={item.id} className="rounded-xl border p-3 space-y-2">
      <strong>{item.filename}</strong><p className="text-sm">{item.stage === "LINKED_EXISTING" ? "Đã liên kết bằng chứng của phiên bản hiện có" : labels[item.state] || item.state} · {item.progress}%</p>
      <p className="text-xs break-all">Mã hồ sơ: {item.id} · Công việc: {item.job_id}</p>
      <p className="text-xs">Thời điểm tiếp nhận: {new Date(item.observed_at).toLocaleString("vi-VN")}</p>
      {item.can_refresh_url && item.original_sha256 && <button disabled={busy} onClick={() => void (async () => {
        setBusy(true); setError("");
        try {
          refreshKeys.current[item.id] ||= crypto.randomUUID();
          await request(`${base}/${item.id}/url-refresh`, { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": refreshKeys.current[item.id] },
            body: JSON.stringify({ expected_original_sha256: item.original_sha256 }) });
          delete refreshKeys.current[item.id];
          setNotice("Đã xếp lịch kiểm tra URL một lần trong hàng đợi, giữ hồ sơ cũ. Có thay đổi sẽ cần đối chiếu; chưa thay bản đang sử dụng."); await load();
        } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
      })()}>Kiểm tra lại URL, giữ bản cũ</button>}
      {item.issues.some(issue => issue.evidence.evidence_unit_count) && <button disabled={busy} onClick={() => void viewEvidence(item.id)}>Xem các đơn vị bằng chứng của {item.filename}</button>}
      {evidenceView?.intake === item.id && <section aria-label={`Bằng chứng của ${item.filename}`} className="rounded-lg border p-3 space-y-2">
        <p className="text-sm">{evidenceView.result.unit_count} đơn vị · {evidenceView.result.dependency_count} liên kết ngữ cảnh · {evidenceView.result.issue_count} điểm cần đối chiếu. Nội dung và các liên kết này chưa được xác minh.</p>
        <ol className="space-y-3">{evidenceView.result.units.map(unit => <li key={unit.id} className="border-t pt-2">
          <p className="text-xs">{unit.kind === "TABLE_CELL" ? "Ô bảng" : unit.kind === "IMAGE_REGION" ? "Vùng ảnh chưa đọc" : unit.kind === "GRAPHIC_OBJECT" ? "Nét hình học chưa xác minh" : "Đoạn chữ"} · {unit.locator.page ? `Trang ${unit.locator.page}` : "Tệp văn bản"}
            {unit.locator.char_start != null && ` · Ký tự ${unit.locator.char_start}–${unit.locator.char_end}`}</p>
          <p className="whitespace-pre-wrap text-sm">{unit.verbatim || (unit.kind === "TABLE_CELL"
            ? "Ô này chưa có chữ được trích xuất; cần đối chiếu ảnh và tiêu đề bảng."
            : "Cần đọc nội dung vùng ảnh; chưa có kết luận về bảng hoặc chiều mũi tên.")}</p>
        </li>)}</ol>
        {evidenceView.result.offset > 0 && <button disabled={busy} onClick={() => void viewEvidence(item.id, Math.max(0, evidenceView.result.offset-20))}>Phần bằng chứng trước</button>}
        {evidenceView.result.next_offset != null && <button disabled={busy} onClick={() => void viewEvidence(item.id, evidenceView.result.next_offset!)}>Phần bằng chứng tiếp theo</button>}
        <button onClick={() => setEvidenceView(null)}>Đóng bằng chứng</button>
      </section>}
      {item.issues.some(issue => issue.evidence.extraction_issues?.length) && <p className="text-sm text-amber-800">Có vùng cần OCR hoặc đối chiếu. Bổ sung metadata chưa giải quyết các lỗi nội dung này.</p>}
      {[...new Set(item.issues.flatMap(issue => issue.evidence.ocr_pages || []))].map(page => {
        const key = `${item.id}:${page}`;
        return <div key={`ocr:${key}`} className="space-y-2">
          <button disabled={busy} onClick={() => void viewOcr(item.id, page)}>Xem OCR chưa xác minh trang {page}</button>
          {ocrViews[key] && <div className="rounded-lg border p-3 text-sm">
            <p>OCR cục bộ chưa xác minh. Điểm đọc chữ không xác nhận số liệu, điều kiện, ô bảng hay chiều mũi tên.</p>
            <p className="whitespace-pre-wrap">{ocrViews[key].text || "OCR chưa đọc được chữ của trang này. Cần đối chiếu ảnh gốc."}</p>
            {ocrViews[key].evidence && <details className="mt-3">
              <summary>Vị trí chữ OCR và ngữ cảnh: {ocrViews[key].evidence!.unit_count} phần</summary>
              <p>Các vùng dùng tọa độ pixel của ảnh đối chiếu. Nhóm chữ và liên kết ngữ cảnh do OCR đề xuất, chưa xác minh.</p>
              <ol className="my-2 space-y-2">
                {ocrViews[key].evidence!.units.map(unit => <li key={unit.id} className="rounded border p-2">
                  <p className="whitespace-pre-wrap">{unit.verbatim}</p>
                  {unit.locator.bbox && <p>Vùng ảnh: {unit.locator.bbox.join(", ")} pixel.</p>}
                </li>)}
              </ol>
              {ocrViews[key].evidence!.offset > 0 && <button disabled={busy} onClick={() => void viewOcr(item.id, page, Math.max(0, ocrViews[key].evidence!.offset-20))}>Phần chữ OCR trước</button>}
              {ocrViews[key].evidence!.next_offset != null && <button disabled={busy} onClick={() => void viewOcr(item.id, page, ocrViews[key].evidence!.next_offset!)}>Phần chữ OCR tiếp theo</button>}
            </details>}
          </div>}
        </div>;
      })}
      {[...new Set(item.issues.flatMap(issue => issue.evidence.preview_pages || []))].map(page => {
        const key = `${item.id}:${page}`;
        return <div key={key}>
          <button disabled={busy} onClick={() => void (async () => {
            setBusy(true); setError("");
            try {
              const response = await request(`${base}/${item.id}/pages/${page}/preview`);
              const url = URL.createObjectURL(await response.blob()); previewUrls.current.push(url);
              setPreviewImages(images => ({ ...images, [key]: url }));
            } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
          })()}>Xem ảnh đối chiếu trang {page}</button>
          {previewImages[key] && <img src={previewImages[key]} alt={`Ảnh nguyên bản trang ${page}, chưa xác minh nội dung`} className="w-full rounded-xl border" />}
        </div>;
      })}
      {item.state === "NEEDS_INFORMATION" && item.stage === "DUPLICATE_REVIEW" && (() => {
        const evidence = item.issues.filter(issue => issue.code === "DUPLICATE_BYTES_CANDIDATE").at(-1)?.evidence;
        return <div className="space-y-2"><p className="text-sm">Tệp trùng bytes với nguồn đã có bằng chứng. Cần đối chiếu nhà xuất bản và phạm vi trước khi liên kết; hệ thống đang giữ riêng lần tiếp nhận này.</p>
          {evidence?.duplicate_candidates?.map(candidate => <div key={candidate.version_id} className="rounded-lg border p-2 text-sm">
            <p>{candidate.title}</p><p className="break-all">{candidate.canonical_uri}</p>
            <button disabled={busy} onClick={() => onResolved(candidate.version_id)}>Mở bằng chứng hiện có</button>
            <button disabled={busy} onClick={() => { setLinkChoice({ intake: item, candidate, generation: evidence.generation!, policy: evidence.policy_generation! }); linkKey.current = null; }}>Đối chiếu và liên kết bản tiếp nhận</button>
          </div>)}
          <button disabled={busy} onClick={() => { setSeparateChoice(item); linkKey.current = null; }}>Giữ riêng nguồn và tiếp tục xử lý</button>
        </div>;
      })()}
      {item.state === "NEEDS_INFORMATION" && item.stage !== "DUPLICATE_REVIEW" && <button disabled={busy} onClick={() => { setSelected(item); resolutionKey.current = null; }}>Bổ sung thông tin {item.filename}</button>}
      {item.state === "NEEDS_INFORMATION" && item.original_sha256 && <button className="block text-left" disabled={busy} onClick={() => void (async () => {
        setBusy(true); setError("");
        try {
          recheckKeys.current[item.id] ||= crypto.randomUUID();
          await request(`${base}/${item.id}/recheck`,{method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":recheckKeys.current[item.id]},
            body:JSON.stringify({expected_revision:item.revision,expected_original_sha256:item.original_sha256})});
          delete recheckKeys.current[item.id]; setNotice("Đã yêu cầu kiểm lại bằng checkpoint còn hợp lệ; giới hạn lần thử giữ nguyên."); await load();
        } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
      })()}>Kiểm lại bằng chứng và trạng thái nguồn</button>}
      {item.version_id && <button disabled={busy} onClick={() => onResolved(item.version_id!)}>Mở phiên bản để đối chiếu</button>}
      {["FAILED", "CANCELLED"].includes(item.state) && <button disabled={busy} onClick={() => void (async () => {
        setBusy(true); setError("");
        try { await request(`/v1/knowledge/platform/jobs/${item.job_id}/retry`, { method: "POST" }); await load(); }
        catch (e) { setError((e as Error).message); } finally { setBusy(false); }
      })()}>Thử lại từ tiến độ đã lưu</button>}
    </li>)}</ul>
    {linkChoice && <form onSubmit={event => void linkExisting(event)} onChange={() => { linkKey.current = null; }} className="rounded-xl border p-4 space-y-3">
      <h3 className="font-semibold">Đối chiếu bản tiếp nhận trùng</h3><p>{linkChoice.candidate.title}</p>
      <fieldset disabled={busy} className="space-y-3">
        <label className="block">Căn cứ cùng nguồn và phạm vi<textarea name="basis" className="fluent-input w-full" required minLength={10} maxLength={2000} /></label>
        <label className="block"><input type="checkbox" name="same_source" required /> Tôi đã đối chiếu cùng nhà xuất bản và phạm vi của phiên bản được chọn.</label>
        <button type="submit" className="fluent-btn-primary">Ghi nhận liên kết, dùng lại bằng chứng</button>
        <button type="button" onClick={() => setLinkChoice(null)}>Đóng đối chiếu</button>
      </fieldset>
    </form>}
    {separateChoice && <form onSubmit={event => void keepSeparate(event)} onChange={() => { linkKey.current = null; }} className="rounded-xl border p-4 space-y-3">
      <h3 className="font-semibold">Giữ riêng nguồn</h3><fieldset disabled={busy}>
        <label>Lý do cần giữ riêng<textarea name="reason" className="fluent-input w-full" required minLength={10} maxLength={2000} /></label>
        <button type="submit" className="fluent-btn-primary">Giữ riêng và xử lý tiếp</button>
        <button type="button" onClick={() => setSeparateChoice(null)}>Đóng lựa chọn</button>
      </fieldset>
    </form>}
    {selected && <form key={selected.id} onSubmit={event => void resolve(event)} onChange={() => { resolutionKey.current = null; }} className="rounded-xl border p-4 space-y-3">
      <h3 className="font-semibold">Bổ sung nguồn: {selected.filename}</h3>
      <p className="text-sm">Tên gợi ý từ văn bản chưa được xác minh. Chỉ nhập thông tin có căn cứ; ngày hiệu lực sẽ được đối chiếu ở bước duyệt.</p>
      <fieldset disabled={busy} className="grid gap-3 md:grid-cols-2">
        <label>Tên nguồn đã đối chiếu<input name="title" className="fluent-input w-full" required minLength={3} maxLength={300}
          defaultValue={selected.hints.title_hint || selected.issues.find(issue => issue.code === "SOURCE_METADATA_REQUIRED")?.evidence.title_candidate || ""} /></label>
        <label>Đơn vị ban hành đã đối chiếu<input name="owner_unit" className="fluent-input w-full" required minLength={2} maxLength={160} /></label>
        <label>URI nguồn đã đối chiếu<input name="canonical_uri" className="fluent-input w-full" required defaultValue={selected.hints.source_uri || ""} /></label>
        <label>Phạm vi chương trình<input name="programs" className="fluent-input w-full" required placeholder="Mã chương trình, phân cách bằng dấu phẩy" /></label>
        <button className="fluent-btn-primary" type="submit">Lưu thông tin và chuyển sang đối chiếu</button>
        <button type="button" onClick={() => setSelected(null)}>Đóng bổ sung</button>
      </fieldset>
    </form>}
  </section>;
}
