"use client";

import { useCallback, useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  LearningApiError, LearningGateway,
  type LearningOcrAnchor, type LearningOcrBlock, type LearningOcrRelease, type LearningPreview,
} from "../../lib/data/api/learning-gateway";
import { AccessibleTextReview, type ConfirmOcrWrite } from "./AccessibleTextReview";
import styles from "./learning.module.css";

const api = new LearningGateway();
type SearchHit = { page_no: number; block_id: string };
type TextSearch = { release_id: string; hits: SearchHit[]; limit_reached: boolean };
type TextPage = { release_id: string; version_id: string; page_no: number; blocks: LearningOcrBlock[] };
type Mode = "PDF" | "TEXT" | "REVIEW";
type OpenSource = (page: number, anchor?: LearningOcrAnchor, focus?: boolean) => void;

function message(error: unknown) {
  return error instanceof Error ? error.message : "Chưa đọc được bản chữ hỗ trợ.";
}

function isUnavailable(error: unknown) {
  return error instanceof LearningApiError && [401, 403, 404].includes(error.status);
}

function ReadingBlock({ block }: { block: LearningOcrBlock }) {
  if (block.type === "HEADING") {
    const Heading = block.level === 2 ? "h2" : block.level === 4 ? "h4" : "h3";
    return <Heading>{block.text}</Heading>;
  }
  if (block.type === "LIST") {
    const List = block.ordered ? "ol" : "ul";
    return <List>{block.items?.map((item, index) => <li key={index}>{item}</li>)}</List>;
  }
  if (block.type === "TABLE") {
    return <div className={styles.ocrTable} tabIndex={0} role="region" aria-label="Bảng dữ liệu đã đối chiếu">
      <table><caption>Bảng dữ liệu đã đối chiếu</caption>
        <thead><tr>{block.headers?.map((cell, index) => <th key={index} scope="col">{cell}</th>)}</tr></thead>
        <tbody>{block.rows?.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody>
      </table>
    </div>;
  }
  if (block.type === "FORMULA") return <p><strong>Mô tả công thức:</strong> {block.text}</p>;
  if (block.type === "FIGURE") return <p><strong>Mô tả hình:</strong> {block.text}</p>;
  return <p>{block.text}</p>;
}

export function OcrReleasePreview({ value }: { value: NonNullable<LearningPreview["ocr_release"]> }) {
  return <div className={styles.stack}>
    <p>{value.operation === "PUBLISH" ? "Trang sẽ được công bố" : "Trang sẽ bị rút khỏi bản chữ"} · {value.pages.join(", ")}.</p>
    <p>{value.pages.length}/{value.page_count} trang trong phiên bản PDF này.</p>
    {value.operation === "PUBLISH" && value.pages.length < value.page_count && <p>Các trang còn lại đọc bằng ảnh PDF gốc.</p>}
  </div>;
}

export function AccessibleText({ actorId, versionId, pageCount, sourcePage, canRead, canManage, published, onSource, confirmWrite, children }: {
  actorId: string; versionId: string; pageCount: number; sourcePage: number; canRead: boolean; canManage: boolean;
  published: boolean; onSource: OpenSource; confirmWrite: ConfirmOcrWrite; children: ReactNode;
}) {
  const panelId = useId();
  const originalId = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const [mode, setMode] = useState<Mode>("PDF");
  const [mobilePane, setMobilePane] = useState<"original" | "text">("text");
  const [visitedReview, setVisitedReview] = useState(false);
  const [manifest, setRelease] = useState<LearningOcrRelease | null>();
  const [pageNo, setPageNo] = useState(sourcePage);
  const [page, setPage] = useState<TextPage>();
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<TextSearch>();
  const [requestedHit, setRequestedHit] = useState<SearchHit>();
  const [searching, setSearching] = useState(false);
  const [failure, setFailure] = useState("");
  const [manifestFailure, setManifestFailure] = useState("");
  const [manifestTick, setManifestTick] = useState(0);
  const searchRequest = useRef<AbortController | null>(null);
  const path = `/versions/${versionId}/accessible-text`;
  const release = canRead && published ? manifest : null;
  const releaseId = release?.id;
  const pageAvailable = release?.available_pages.includes(pageNo) ?? false;
  const visibleMode = mode === "TEXT" && !release || mode === "REVIEW" && !canManage ? "PDF" : mode;
  const fetchManifest = useCallback(() => setManifestTick(value => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    let generation = 0;
    if (!canRead || !published) {
      setRelease(null);
      return () => controller.abort();
    }
    const load = () => {
      const current = ++generation;
      void api.request<{ release: LearningOcrRelease | null; version_id: string }>(path, {
        signal: controller.signal, headers: { "X-Campus-Reader-Actor": actorId },
      }).then(value => {
        if (!controller.signal.aborted && current === generation) {
          setRelease(value.version_id === versionId ? value.release : null);
          setManifestFailure("");
        }
      }).catch(error => {
        if (controller.signal.aborted || current !== generation) return;
        setRelease(null); setPage(undefined); setSearch(undefined);
        setManifestFailure(isUnavailable(error) ? "" : message(error));
      });
    };
    load();
    window.addEventListener("focus", load);
    const poll = window.setInterval(load, 15000);
    return () => {
      controller.abort(); window.removeEventListener("focus", load); window.clearInterval(poll);
    };
  }, [actorId, canRead, manifestTick, path, published, versionId]);

  useEffect(() => {
    const controller = new AbortController();
    setPage(undefined);
    if (!releaseId || !pageAvailable || visibleMode !== "TEXT") return () => controller.abort();
    void api.request<TextPage>(`${path}/pages/${pageNo}`, {
      signal: controller.signal, headers: { "X-Campus-Reader-Actor": actorId },
    }).then(value => {
      if (controller.signal.aborted) return;
      if (value.release_id !== releaseId || value.version_id !== versionId || value.page_no !== pageNo) {
        fetchManifest();
        return;
      }
      setPage(value);
    }).catch(error => {
      if (controller.signal.aborted) return;
      if (isUnavailable(error)) {
        setRelease(null); setSearch(undefined); fetchManifest();
      }
      setFailure(message(error));
    });
    return () => controller.abort();
  }, [actorId, fetchManifest, pageAvailable, pageNo, path, releaseId, versionId, visibleMode]);

  useEffect(() => {
    setSearch(undefined); setRequestedHit(undefined); setSearching(false);
    return () => searchRequest.current?.abort();
  }, [releaseId, actorId, versionId]);

  function textBlockId(page: number, id: string) {
    return `${panelId}-${page}-${id}`;
  }

  useEffect(() => {
    if (!requestedHit || requestedHit.page_no !== page?.page_no || page.release_id !== releaseId || visibleMode !== "TEXT") return;
    const node = document.getElementById(textBlockId(requestedHit.page_no, requestedHit.block_id));
    if (node) node.focus();
    setRequestedHit(undefined);
  }, [page, releaseId, requestedHit, visibleMode]);

  function sourceAt(page: number, anchor?: LearningOcrAnchor, focus = true) {
    if (focus) setMobilePane("original");
    onSource(page, anchor, focus);
  }

  function show(next: Mode) {
    if (next === "TEXT" && mode !== "TEXT") setPageNo(sourcePage);
    if (next === "REVIEW") setVisitedReview(true);
    setMode(next); setMobilePane(next === "PDF" ? "original" : "text");
    if (next === "TEXT") requestAnimationFrame(() => heading.current?.focus());
  }

  function selectPage(next: number, hit?: SearchHit) {
    setFailure(""); setMobilePane("text"); setPageNo(next); setRequestedHit(hit);
    sourceAt(next, undefined, false);
  }

  async function find(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const term = query.trim();
    if (!releaseId || !term || searching) return;
    searchRequest.current?.abort();
    const controller = new AbortController();
    searchRequest.current = controller;
    setSearching(true); setSearch(undefined); setFailure("");
    try {
      const value = await api.request<TextSearch>(`${path}/search?q=${encodeURIComponent(term)}`, {
        signal: controller.signal, headers: { "X-Campus-Reader-Actor": actorId },
      });
      if (controller.signal.aborted) return;
      if (value.release_id === releaseId) setSearch(value);
      else fetchManifest();
    } catch (error) {
      if (!controller.signal.aborted) {
        if (isUnavailable(error)) { setRelease(null); setPage(undefined); fetchManifest(); }
        setFailure(message(error));
      }
    } finally {
      if (!controller.signal.aborted) setSearching(false);
    }
  }

  const currentPage = page?.page_no === pageNo && page.release_id === releaseId ? page : undefined;
  const currentSearch = search?.release_id === releaseId ? search : undefined;
  const split = visibleMode !== "PDF";
  return <div className={styles.stack}>
    <nav aria-label="Cách đọc tài liệu" className={styles.row}>
      <button type="button" aria-pressed={visibleMode === "PDF"} aria-controls={originalId} onClick={() => show("PDF")}>Ảnh PDF gốc</button>
      {release && <button type="button" aria-pressed={visibleMode === "TEXT"} aria-controls={panelId} onClick={() => show("TEXT")}>Bản chữ hỗ trợ</button>}
      {canManage && <button type="button" aria-pressed={visibleMode === "REVIEW"} onClick={() => show("REVIEW")}>Quản lý bản chữ</button>}
      {split && mobilePane === "original" && <button type="button" className={styles.ocrMobileOnly} onClick={() => show(visibleMode)}>
        {visibleMode === "TEXT" ? "Về bản chữ" : "Về phần duyệt bản chữ"}
      </button>}
    </nav>
    {canRead && published && release === null && <p role="status">Chưa có bản chữ hỗ trợ đang công bố cho phiên bản này.</p>}
    {manifestFailure && canRead && published && <p role="alert">{manifestFailure}</p>}
    {failure && visibleMode === "TEXT" && <p role="alert">{failure}</p>}
    <div className={split ? styles.ocrColumns : undefined} data-ocr-pane={split ? mobilePane : undefined}>
      <div id={originalId} className={styles.ocrOriginal}>{children}</div>
      {visibleMode === "TEXT" && release && <section id={panelId} className={`${styles.panel} ${styles.stack} ${styles.ocrTextPane}`} aria-label="Đọc bản chữ hỗ trợ" lang="vi">
        <h3 tabIndex={-1} ref={heading}>Bản chữ hỗ trợ</h3>
        <p>{release.available_pages.length}/{release.page_count} trang đã công bố. {release.missing_page_count > 0 && "Trang còn thiếu có thể mở ở ảnh PDF gốc."}</p>
        <label>Trang bản chữ<select value={pageNo} onChange={event => selectPage(Number(event.target.value))}>
          {!pageAvailable && <option value={pageNo}>Trang {pageNo} · Chưa có bản chữ</option>}
          {release.available_pages.map(page => <option key={page} value={page}>Trang {page}</option>)}
        </select></label>
        <button type="button" onClick={() => sourceAt(pageNo)}>Mở ảnh gốc trang {pageNo}</button>
        <form className={styles.stack} onSubmit={event => void find(event)}>
          <label>Tìm trong bản chữ<input type="search" value={query} maxLength={120} onChange={event => setQuery(event.target.value)} /></label>
          <button disabled={searching || !query.trim()}>Tìm bản chữ</button>
        </form>
        {searching && <p role="status">Đang tìm bản chữ…</p>}
        {currentSearch && <section aria-label="Kết quả tìm bản chữ">
          <p role="status">{currentSearch.hits.length} kết quả{currentSearch.limit_reached ? " đầu tiên" : ""}.</p>
          <ul className={styles.list}>{currentSearch.hits.map((hit, index) => <li key={`${hit.page_no}:${hit.block_id}`}>
            <button type="button" onClick={() => selectPage(hit.page_no, hit)}>Kết quả {index + 1} · Trang {hit.page_no}</button>
          </li>)}</ul>
        </section>}
        {!pageAvailable && <p role="status">Trang {pageNo} chưa có bản chữ đã duyệt.</p>}
        {pageAvailable && !currentPage && !failure && <p role="status">Đang đọc bản chữ trang {pageNo}…</p>}
        {currentPage?.blocks.length === 0 && <p>Trang này không có khối chữ đã ghi nhận.</p>}
        {currentPage?.blocks.map((block, index) => <div key={block.id} id={textBlockId(pageNo, block.id)} tabIndex={-1} className={styles.ocrBlock}>
          <ReadingBlock block={block} />
          <button type="button" onClick={() => sourceAt(pageNo, block.anchor)}>
            Mở ảnh gốc trang {pageNo} · Khối {index + 1}
          </button>
        </div>)}
      </section>}
      {visitedReview && canManage && <div className={styles.ocrTextPane} hidden={visibleMode !== "REVIEW"}>
        <AccessibleTextReview actorId={actorId} versionId={versionId} pageCount={pageCount} sourcePage={sourcePage}
          enabled={visibleMode === "REVIEW"} published={published} onSource={sourceAt} onReleaseChange={fetchManifest} confirmWrite={confirmWrite} />
      </div>}
    </div>
  </div>;
}
