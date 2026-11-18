"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  LearningApiError, LearningGateway,
  type LearningOcrAnchor, type LearningOcrBlockType, type LearningOcrCandidateBlock, type LearningOcrDecision,
  type LearningOcrJob, type LearningOcrJobs, type LearningOcrRelease, type LearningOcrReviewRelease,
} from "../../lib/data/api/learning-gateway";
import styles from "./learning.module.css";

const api = new LearningGateway();
export type ConfirmOcrWrite = (path: string, payload: Record<string, unknown>, action: string, title: string, method: string) => Promise<unknown>;
const jobLabels: Record<LearningOcrJob["state"], string> = {
  QUEUED: "Đang xếp hàng", RUNNING: "Đang xử lý", PAUSED: "Đang tạm dừng",
  CANCELLED: "Đã hủy", FAILED: "Xử lý gặp lỗi", NEEDS_REVIEW: "Có trang cần duyệt",
};
const releaseLabels: Record<LearningOcrRelease["state"], string> = {
  DRAFT: "Bản nháp", PUBLISHED: "Đã công bố", WITHDRAWN: "Đã thu hồi", SUPERSEDED: "Đã có bản thay thế",
};
const blockLabels: Record<LearningOcrBlockType, string> = {
  PARAGRAPH: "Đoạn văn", HEADING: "Tiêu đề", LIST: "Danh sách", TABLE: "Bảng",
  FORMULA: "Mô tả công thức", FIGURE: "Mô tả hình", PLACEHOLDER: "Chỉ dẫn đến ảnh gốc",
};
const criticalReasons = new Set(["POSSIBLE_TABLE", "POSSIBLE_FORMULA", "LOW_CONFIDENCE"]);
const reasonLabels: Record<string, string> = {
  POSSIBLE_TABLE: "Có thể là bảng", POSSIBLE_FORMULA: "Có thể là công thức",
  LOW_CONFIDENCE: "Chữ nhận dạng có độ tin cậy thấp", READING_ORDER: "Cần kiểm tra thứ tự đọc",
  READING_ORDER_REVIEW: "Cần kiểm tra thứ tự đọc", OCR_TEXT_REVIEW: "Cần đối chiếu chữ nhận dạng",
  MULTI_COLUMN_LAYOUT: "Có thể có nhiều cột",
};
const authHeaders = (actorId: string) => ({ "X-Campus-Reader-Actor": actorId });

function errorMessage(error: unknown) {
  if (error instanceof LearningApiError) {
    const descriptions: Record<string, string> = {
      OCR_CLASS_BUSY: "Lớp đang có một công việc OCR. Hãy chờ công việc đó kết thúc.",
      OCR_PAGE_QUOTA: "Lớp đã hết hạn mức OCR theo ngày.",
      OCR_STORAGE_QUOTA: "Lớp đã hết dung lượng dành cho bản chữ.",
      OCR_SCOPE_EXISTS: "Phiên bản này đã có yêu cầu OCR cho phạm vi khác. Chọn công việc trong danh sách.",
      OCR_RETRY_LIMIT: "Các trang đã hết lượt thử lại.",
      OCR_PROCESSING_PAUSED: "Lớp đang tạm dừng tạo và thử lại OCR. Bạn vẫn có thể duyệt kết quả đã xử lý.",
      OCR_PROFILE_CHANGED: "Cấu hình OCR đã thay đổi. Hãy gửi yêu cầu mới.",
      OCR_CURRENT_RELEASE_CHANGED: "Bản chữ hiện hành đã đổi. Hãy tải lại trước khi công bố.",
      REVISION_CONFLICT: "Dữ liệu đã đổi. Hãy tải lại trước khi tiếp tục.",
    };
    return descriptions[error.code] ?? error.message;
  }
  return error instanceof Error ? error.message : "Chưa thực hiện được thao tác bản chữ.";
}

function noAccess(error: unknown) {
  return error instanceof LearningApiError && [401, 403, 404].includes(error.status);
}

export function parseOcrPages(input: string, pageCount: number, maxPages: number) {
  const result = new Set<number>();
  if (!input.trim()) throw new Error("Nhập trang hoặc khoảng trang, ví dụ 1–3, 5.");
  for (const entry of input.split(",")) {
    const match = /^(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?$/.exec(entry.trim());
    if (!match) throw new Error("Nhập trang hoặc khoảng trang, ví dụ 1–3, 5.");
    const from = Number(match[1]);
    const to = match[2] ? Number(match[2]) : from;
    if (from < 1 || from > to || to > pageCount) throw new Error(`Chọn các trang từ 1 đến ${pageCount}.`);
    for (let page = from; page <= to; page++) {
      result.add(page);
      if (result.size > maxPages) throw new Error(`Chọn tối đa ${maxPages} trang mỗi yêu cầu.`);
    }
  }
  return [...result].sort((a, b) => a - b);
}

type EditableBlock = {
  id: string; type: LearningOcrBlockType; text: string; level: number; items: string; ordered: boolean;
  headers: string; rows: string; risk: boolean;
};

function critical(block: LearningOcrCandidateBlock, type: LearningOcrBlockType) {
  return type === "TABLE" || type === "FORMULA" || block.review_reasons.some(reason => criticalReasons.has(reason));
}

function initialBlocks(page: LearningOcrReviewRelease): EditableBlock[] {
  const candidates = page.candidate?.blocks ?? [];
  const byId = new Map(candidates.map(block => [block.id, block]));
  const ordered = page.review?.blocks.map(block => byId.get(block.id)).filter((block): block is LearningOcrCandidateBlock => !!block)
    ?? [...candidates].sort((a, b) => a.order - b.order);
  return ordered.map(block => {
    const saved = page.review?.blocks.find(item => item.id === block.id);
    return {
      id: block.id, type: saved?.type ?? (critical(block, "PARAGRAPH") ? "PLACEHOLDER" : "PARAGRAPH"),
      text: saved?.type === "PLACEHOLDER" ? block.text : saved?.text ?? block.text,
      level: saved?.level ?? 3, items: saved?.items?.join("\n") ?? "", ordered: saved?.ordered ?? false,
      headers: saved?.headers?.join(" | ") ?? "", rows: saved?.rows?.map(row => row.join(" | ")).join("\n") ?? "",
      risk: false,
    };
  });
}

function decision(block: EditableBlock, candidate: LearningOcrCandidateBlock): LearningOcrDecision {
  const base = { id: block.id, type: block.type };
  if (block.type === "PLACEHOLDER") return base;
  const requiresVerification = critical(candidate, block.type);
  if (requiresVerification && !block.risk) throw new Error("Hãy xác nhận đã đối chiếu các khối có số liệu hoặc ký hiệu cần kiểm tra.");
  const verified = requiresVerification ? { risk_verified: true } : {};
  const splitLines = (value: string) => value.split("\n").map(line => line.trim()).filter(Boolean);
  if (block.type === "TABLE") {
    const cells = (value: string) => value.split("|").map(cell => cell.trim());
    const headers = cells(block.headers);
    const rows = splitLines(block.rows).map(cells);
    if (headers.length > 12 || !rows.length || rows.length > 40
      || headers.some(cell => !cell || cell.length > 200)
      || rows.some(row => row.length !== headers.length || row.some(cell => !cell || cell.length > 200))) {
      throw new Error("Nhập tối đa 12 cột và 40 hàng, dùng dấu | để phân cách. Mỗi ô cần có nội dung.");
    }
    return { ...base, headers, rows, ...verified };
  }
  if (block.type === "LIST") {
    const items = splitLines(block.items);
    if (!items.length || items.length > 40 || items.some(item => item.length > 500)) throw new Error("Nhập từ 1 đến 40 mục, mỗi dòng một mục.");
    return { ...base, items, ordered: block.ordered, ...verified };
  }
  const text = block.text.trim();
  if (!text || text.length > (block.type === "HEADING" ? 400 : 4000)) throw new Error("Điền nội dung cho từng khối đã duyệt.");
  return { ...base, text, ...(block.type === "HEADING" ? { level: block.level } : {}), ...verified };
}

function PageReview({ value, pageNo, nextPage, busy, onSource, onSave }: {
  value: LearningOcrReviewRelease; pageNo: number; nextPage?: number; busy: boolean;
  onSource: (page: number, anchor?: LearningOcrAnchor, focus?: boolean) => void;
  onSave: (payload: Record<string, unknown>, advanceTo?: number) => void;
}) {
  const [blocks, setBlocks] = useState(() => initialBlocks(value));
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const sourceBlocks = value.candidate?.blocks ?? [];
  const candidates = new Map(sourceBlocks.map(block => [block.id, block]));
  const multiColumn = sourceBlocks.some(block => block.review_reasons.includes("MULTI_COLUMN_LAYOUT"));
  function update(id: string, changes: Partial<EditableBlock>) {
    setBlocks(previous => previous.map(block => block.id === id ? { ...block, risk: false, ...changes } : block));
    setConfirmed(false);
  }
  function move(index: number, step: number) {
    setBlocks(previous => {
      const next = [...previous];
      [next[index], next[index + step]] = [next[index + step], next[index]];
      return next;
    });
    setConfirmed(false);
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!confirmed || !value.candidate || busy) return;
    try {
      const reviewed = blocks.map(block => decision(block, candidates.get(block.id)!));
      const advance = (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") === "next";
      setError("");
      onSave({ operation: "REVIEW_PAGE", revision: value.revision, page_no: pageNo,
        candidate_sha256: value.candidate.sha256, review_confirmed: true, blocks: reviewed }, advance ? nextPage : undefined);
    } catch (error) { setError(errorMessage(error)); }
  }
  return <form className={styles.stack} onSubmit={submit}>
    <p>{value.review ? "Đang sửa bản duyệt đã lưu." : "Bản nháp riêng cho giảng viên. Đối chiếu ảnh trước khi lưu."}</p>
    {multiColumn && <p>Trang có thể có nhiều cột. Đối chiếu chữ theo từng cột và chỉnh thứ tự các khối theo ảnh gốc.</p>}
    {blocks.length > 0 && <p>Nếu chưa đối chiếu được đầy đủ một khối, chọn “Chỉ dẫn đến ảnh gốc” cho khối đó.</p>}
    {!blocks.length && <p>Chưa phát hiện khối chữ trên trang này.</p>}
    {blocks.map((block, index) => {
      const candidate = candidates.get(block.id)!;
      const risk = block.type !== "PLACEHOLDER" && critical(candidate, block.type);
      return <fieldset className={`${styles.stack} ${styles.ocrBlock}`} key={block.id} disabled={busy}>
        <legend>Khối {index + 1}</legend>
        <p className={styles.ocrDraftText}>{candidate.text}</p>
        <p>Nguồn · {candidate.provenance === "NATIVE" ? "Lớp chữ PDF" : "OCR"}{candidate.confidence !== null && ` · Độ tin cậy ${Math.round(candidate.confidence)}%`}</p>
        {candidate.review_reasons.length > 0 && <ul>{candidate.review_reasons.map(reason => <li key={reason}>{reasonLabels[reason] ?? reason}</li>)}</ul>}
        <div className={styles.row}>
          <button type="button" onClick={() => onSource(pageNo, candidate.anchor)}>Đối chiếu khối {index + 1} trên ảnh</button>
          <button type="button" disabled={index === 0} aria-label={`Đưa khối ${index + 1} lên`} onClick={() => move(index, -1)}>Đưa lên</button>
          <button type="button" disabled={index === blocks.length - 1} aria-label={`Đưa khối ${index + 1} xuống`} onClick={() => move(index, 1)}>Đưa xuống</button>
        </div>
        <label>Loại khối<select value={block.type} onChange={event => update(block.id, { type: event.target.value as LearningOcrBlockType })}>
          {Object.entries(blockLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        {block.type === "HEADING" && <label>Cấp tiêu đề<select value={block.level} onChange={event => update(block.id, { level: Number(event.target.value) })}>
          {[2, 3, 4].map(level => <option key={level} value={level}>{level}</option>)}
        </select></label>}
        {block.type === "TABLE" ? <>
          <label>Tiêu đề cột, phân cách bằng dấu |<input value={block.headers} onChange={event => update(block.id, { headers: event.target.value })} /></label>
          <label>Giá trị bảng, mỗi hàng một dòng và mỗi ô cách nhau bằng dấu |<textarea rows={3} value={block.rows}
            onChange={event => update(block.id, { rows: event.target.value })} /></label>
        </> : block.type === "LIST" ? <>
          <label>Mỗi mục một dòng<textarea rows={3} value={block.items} onChange={event => update(block.id, { items: event.target.value })} /></label>
          <label><span><input type="checkbox" checked={block.ordered} onChange={event => update(block.id, { ordered: event.target.checked })} /> Danh sách đánh số</span></label>
        </> : block.type !== "PLACEHOLDER" && <label>Chữ hoặc mô tả đã kiểm tra<textarea rows={4} value={block.text}
          maxLength={block.type === "HEADING" ? 400 : 4000} onChange={event => update(block.id, { text: event.target.value })} /></label>}
        {risk && <label><span><input type="checkbox" checked={block.risk} onChange={event => update(block.id, { risk: event.target.checked })} />
          {" "}Tôi đã đối chiếu số liệu, đơn vị, dấu, chỉ số và ký hiệu của khối này.</span></label>}
      </fieldset>;
    })}
    <label><span><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />
      {" "}Tôi đã đối chiếu nội dung và thứ tự đọc của trang với ảnh gốc.</span></label>
    {error && <p role="alert">{error}</p>}
    <div className={styles.row}>
      <button type="submit" disabled={!confirmed || busy}>Lưu duyệt trang {pageNo}</button>
      {nextPage !== undefined && <button type="submit" value="next" disabled={!confirmed || busy}>Lưu và đến trang {nextPage}</button>}
    </div>
  </form>;
}

export function AccessibleTextReview({ actorId, versionId, pageCount, sourcePage, enabled, published, onSource, onReleaseChange, confirmWrite }: {
  actorId: string; versionId: string; pageCount: number; sourcePage: number; enabled: boolean; published: boolean;
  onSource: (page: number, anchor?: LearningOcrAnchor, focus?: boolean) => void; onReleaseChange: () => void; confirmWrite: ConfirmOcrWrite;
}) {
  const [worklist, setWorklist] = useState<LearningOcrJobs>();
  const [range, setRange] = useState(String(sourcePage));
  const [selection, setSelection] = useState<{ id: string; page: number }>();
  const [loadedPage, setPageData] = useState<{ page: number; release: LearningOcrReviewRelease }>();
  const [publishSelection, setPublishSelection] = useState<{ id: string; pages: number[] }>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [refreshPage, setRefreshPage] = useState(0);
  const scope = useRef<AbortController | null>(null);
  const pending = useRef<{ payload: string; key: string } | undefined>(undefined);
  const locked = useRef(false);
  const pageHeading = useRef<HTMLHeadingElement>(null);
  const focusPage = useRef<number>(undefined);
  const loadedScope = useRef("");
  const listPath = `/versions/${versionId}/ocr-jobs`;
  const release = worklist?.releases.find(item => item.id === selection?.id);
  const checkedPages = publishSelection?.id === release?.id ? publishSelection?.pages ?? [] : [];
  const reviewedToPublish = checkedPages.filter(page => release?.reviewed_pages.includes(page));

  useEffect(() => {
    const controller = new AbortController();
    scope.current = controller;
    locked.current = false; setBusy(false);
    return () => controller.abort();
  }, [actorId, versionId]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let generation = 0;
    const load = () => {
      const current = ++generation;
      void api.request<LearningOcrJobs>(listPath, { signal: controller.signal, headers: authHeaders(actorId) }).then(value => {
        if (!controller.signal.aborted && current === generation) setWorklist(value);
      }).catch(error => {
        if (controller.signal.aborted || current !== generation) return;
        if (noAccess(error)) { setWorklist(undefined); setPageData(undefined); }
        setError(errorMessage(error));
      });
    };
    load();
    const poll = window.setInterval(load, 4000);
    return () => { controller.abort(); window.clearInterval(poll); };
  }, [actorId, enabled, listPath, refresh]);

  const releaseId = selection?.id;
  const pageNo = selection?.page;
  const pageData = loadedPage && loadedPage.page === pageNo && loadedPage.release.id === releaseId ? loadedPage.release : undefined;
  const hasCandidate = !!pageData?.candidate;
  const candidateReady = hasCandidate && pageData.review?.page_no === pageNo;
  const job = worklist?.jobs.find(item => item.release_id === releaseId);
  const remaining = release?.requested_pages.filter(page => page !== pageNo && !release.reviewed_pages.includes(page) && !job?.errors[page]) ?? [];
  const nextPage = remaining.find(page => page > (pageNo ?? 0)) ?? remaining[0];
  useEffect(() => {
    if (focusPage.current === undefined || focusPage.current !== pageNo) return;
    focusPage.current = undefined;
    if (enabled) pageHeading.current?.focus();
  }, [enabled, pageNo]);
  useEffect(() => {
    const nextScope = JSON.stringify([actorId, versionId, enabled, releaseId, pageNo, refreshPage]);
    if (loadedScope.current !== nextScope) {
      loadedScope.current = nextScope; setPageData(undefined);
    }
    if (!enabled || !releaseId || !pageNo) return;
    const controller = new AbortController();
    let poll: number | undefined;
    const load = () => void api.request<LearningOcrReviewRelease>(`/ocr-releases/${releaseId}?page_no=${pageNo}`,
      { signal: controller.signal, headers: authHeaders(actorId) }).then(value => {
      if (controller.signal.aborted || value.id !== releaseId || value.version_id !== versionId) return;
      setPageData({ page: pageNo, release: value });
      if (!value.candidate) poll = window.setTimeout(load, 4000);
    }).catch(error => {
      if (controller.signal.aborted) return;
      if (noAccess(error)) setPageData(undefined);
      setError(errorMessage(error));
    });
    load();
    return () => { controller.abort(); if (poll !== undefined) window.clearTimeout(poll); };
  }, [actorId, enabled, pageNo, refreshPage, releaseId, versionId]);

  function choose(next: LearningOcrReviewRelease, requestedPage?: number) {
    const page = requestedPage ?? (next.requested_pages.includes(sourcePage) ? sourcePage : next.requested_pages[0]);
    if (!page) return;
    setSelection({ id: next.id, page }); setPageData(undefined);
    setError(""); onSource(page, undefined, false);
  }

  async function work(operation: (signal: AbortSignal) => Promise<void>) {
    const signal = scope.current?.signal;
    if (!signal || signal.aborted || locked.current) return;
    locked.current = true; setBusy(true); setError(""); setNotice("");
    try { await operation(signal); }
    catch (error) {
      if (!signal.aborted) {
        if (noAccess(error)) { setPageData(undefined); setWorklist(undefined); }
        setError(errorMessage(error));
      }
    } finally {
      if (scope.current?.signal === signal) {
        locked.current = false; setBusy(false);
      }
    }
  }

  function write<T>(path: string, body: Record<string, unknown>, method: "POST" | "PATCH", signal: AbortSignal) {
    const fingerprint = JSON.stringify([path, body]);
    if (pending.current?.payload !== fingerprint) pending.current = { payload: fingerprint, key: crypto.randomUUID() };
    return api.write<T>(path, body, method, pending.current.key, authHeaders(actorId), signal).then(value => {
      if (signal.aborted) throw new DOMException("Cancelled", "AbortError");
      pending.current = undefined;
      return value;
    });
  }

  function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void work(async signal => {
      const pages = parseOcrPages(range, pageCount, worklist?.max_pages_per_job ?? 100);
      const job = await write<LearningOcrJob>(listPath, { pages }, "POST", signal);
      if (!signal.aborted) {
        setSelection({ id: job.release_id, page: pages.includes(sourcePage) ? sourcePage : pages[0] });
        setNotice("Đã ghi nhận yêu cầu OCR."); setRefresh(value => value + 1);
      }
    });
  }

  function changeJob(job: LearningOcrJob, operation: "CANCEL" | "RESUME") {
    void work(async signal => {
      const next = await write<LearningOcrJob>(`/ocr-jobs/${job.id}`, { operation, revision: job.revision }, "PATCH", signal);
      if (!signal.aborted) {
        setWorklist(current => current && { ...current, jobs: current.jobs.map(item => item.id === next.id ? next : item) });
        setRefresh(value => value + 1);
      }
    });
  }

  function reviewPage(payload: Record<string, unknown>, advanceTo?: number) {
    if (!release) return;
    void work(async signal => {
      await write(`/ocr-releases/${release.id}`, payload, "PATCH", signal);
      if (!signal.aborted) {
        if (advanceTo !== undefined) {
          focusPage.current = advanceTo;
          choose(release, advanceTo);
        }
        setNotice("Đã lưu duyệt trang."); setRefresh(value => value + 1); setRefreshPage(value => value + 1);
      }
    });
  }

  function changeRelease(item: LearningOcrReviewRelease, operation: "PUBLISH" | "WITHDRAW" | "CLONE") {
    const path = `/ocr-releases/${item.id}`;
    const payload = { operation, revision: item.revision, ...(operation === "PUBLISH"
      ? { pages: reviewedToPublish, expected_current_release_id: item.current_release_id } : {}) };
    void work(async signal => {
      if (operation === "CLONE") {
        const next = await write<LearningOcrRelease>(path, payload, "PATCH", signal);
        if (!signal.aborted) {
          setSelection({ id: next.id, page: pageNo ?? item.requested_pages[0] }); setPageData(undefined);
        }
      } else {
        await confirmWrite(path, payload, "ocr-release-update", operation === "PUBLISH" ? "Công bố bản chữ hỗ trợ" : "Thu hồi bản chữ hỗ trợ", "PATCH");
        if (!signal.aborted) { onReleaseChange(); setNotice(operation === "PUBLISH" ? "Đã công bố bản chữ hỗ trợ." : "Đã thu hồi bản chữ hỗ trợ."); }
      }
      if (!signal.aborted) { setRefresh(value => value + 1); setRefreshPage(value => value + 1); }
    });
  }

  return <section className={`${styles.panel} ${styles.stack}`} aria-label="Quản lý bản chữ hỗ trợ" lang="vi">
    <h3>Quản lý bản chữ hỗ trợ</h3>
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!worklist && !error && <p role="status">Đang tải yêu cầu và hạn mức OCR…</p>}
    {worklist && <>
      <p>Còn {worklist.daily_pages_remaining} trang theo ngày · tối đa {worklist.max_pages_per_job} trang mỗi yêu cầu
        · còn {Math.floor(worklist.storage_available_bytes / (1024 * 1024))} MiB lưu bản chữ.</p>
      <form className={styles.stack} onSubmit={start}>
        <label>Trang cần tạo bản chữ (1–{pageCount})<input value={range} maxLength={600} required
          placeholder="1–3, 5" onChange={event => setRange(event.target.value)} /></label>
        <button disabled={busy || !range.trim()}>Yêu cầu OCR</button>
      </form>
      {worklist.jobs.length > 0 && <ul className={styles.list}>{worklist.jobs.map(job => <li key={job.id} className={styles.ocrBlock}>
        <strong>{jobLabels[job.state]}</strong><p>{job.completed_pages}/{job.requested_pages} trang đã xử lý.</p>
        {Object.entries(job.errors).length > 0 && <ul>{Object.entries(job.errors).map(([page, issue]) => <li key={page}>
          Trang {page} · {issue.permanent ? "Lỗi không thể tự thử lại" : "Lỗi xử lý có thể thử lại"} ({issue.code})
        </li>)}</ul>}
        <div className={styles.row}>
          {["QUEUED", "RUNNING", "PAUSED", "FAILED"].includes(job.state) && <button type="button" disabled={busy}
            onClick={() => changeJob(job, "CANCEL")}>Hủy xử lý OCR</button>}
          {(["PAUSED", "FAILED", "CANCELLED"].includes(job.state)
            || job.state === "NEEDS_REVIEW" && Object.values(job.errors).some(issue => !issue.permanent)) &&
            <button type="button" disabled={busy} onClick={() => changeJob(job, "RESUME")}>Thử lại các trang lỗi</button>}
        </div>
      </li>)}</ul>}
      <label>Bản chữ cần xem<select value={releaseId ?? ""} disabled={busy} onChange={event => {
        const next = worklist.releases.find(item => item.id === event.target.value);
        if (next) choose(next);
        else { setSelection(undefined); setPageData(undefined); }
      }}>
        <option value="">Chọn bản chữ</option>
        {worklist.releases.map(item => <option value={item.id} key={item.id}>
          {releaseLabels[item.state]} · Bản {[...worklist.releases].sort((a, b) => (a.id < b.id ? -1 : 1)).findIndex(row => row.id === item.id) + 1} · Lần {item.revision}{item.id === item.current_release_id ? " · Hiện hành" : ""}
        </option>)}
      </select></label>
    </>}
    {release && pageNo !== undefined && <>
      <h4 tabIndex={-1} ref={pageHeading}>Duyệt trang {pageNo}</h4>
      <p>{release.reviewed_pages.length}/{release.requested_pages.length} trang đã duyệt.</p>
      <label>Trang cần đối chiếu<select value={pageNo} disabled={busy} onChange={event => choose(release, Number(event.target.value))}>
        {release.requested_pages.map(page => <option key={page} value={page}>Trang {page}{release.reviewed_pages.includes(page)
          ? " · Đã duyệt" : job?.errors[page] ? " · Lỗi OCR" : " · Chưa duyệt"}</option>)}
      </select></label>
      <button type="button" onClick={() => onSource(pageNo)}>Mở ảnh gốc trang {pageNo}</button>
      {release.state === "DRAFT" && hasCandidate && pageData && <PageReview key={`${release.id}:${pageNo}:${pageData.revision}:${pageData.candidate?.sha256}`}
        value={pageData} pageNo={pageNo} nextPage={nextPage} busy={busy} onSource={onSource} onSave={reviewPage} />}
      {release.state === "DRAFT" && !hasCandidate && <p role="status">{job?.errors[pageNo]
        ? `OCR trang ${pageNo} gặp lỗi. Xem trạng thái yêu cầu ở trên.` : "Chưa có kết quả OCR để duyệt trang này."}</p>}
      {release.state !== "DRAFT" && candidateReady && <p>Trang này đã có nội dung duyệt. Tạo bản nháp mới nếu cần sửa.</p>}
      {release.state === "DRAFT" && release.reviewed_pages.length > 0 && <fieldset className={styles.stack} disabled={busy || !published}>
        <legend>Trang công bố cho sinh viên</legend>
        <p>Có thể công bố một phần. PDF nguồn cần ở trạng thái đã công bố.</p>
        {release.reviewed_pages.map(page => <label key={page}><span><input type="checkbox" checked={checkedPages.includes(page)}
          onChange={event => setPublishSelection({ id: release.id, pages: event.target.checked ? [...checkedPages, page] : checkedPages.filter(value => value !== page) })} />
          {" "}Trang {page}</span></label>)}
        <button type="button" onClick={() => setPublishSelection({ id: release.id, pages: release.reviewed_pages })}>Chọn tất cả trang đã duyệt</button>
        <button type="button" disabled={!reviewedToPublish.length} onClick={() => changeRelease(release, "PUBLISH")}>Xem trước công bố bản chữ</button>
      </fieldset>}
      {release.state !== "DRAFT" && <button type="button" disabled={busy} onClick={() => changeRelease(release, "CLONE")}>Tạo bản nháp mới để sửa</button>}
      {release.state === "PUBLISHED" && release.current_release_id === release.id && <button type="button" disabled={busy}
        onClick={() => changeRelease(release, "WITHDRAW")}>Xem trước thu hồi bản chữ</button>}
    </>}
    <button type="button" disabled={busy} onClick={() => { setError(""); setRefresh(value => value + 1); setRefreshPage(value => value + 1); }}>
      Tải lại quản lý bản chữ
    </button>
  </section>;
}
