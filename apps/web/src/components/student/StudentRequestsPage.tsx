"use client";

import Link from "next/link";
import { useEffect, useRef, useSyncExternalStore, type FormEvent } from "react";
import { ArrowRight, FileText, Plus, Search } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { DataAccessState } from "@/components/shared/DataAccessState";
import { useStore } from "@/lib/store";
import { collectRequests, filterRequests, normalizeFilter, type RequestState } from "@/lib/my-requests";
import { formatDate } from "@/lib/format-date";
import { RequestDetail, RequestStatus } from "./RequestDetail";
import { fieldClass, primaryButton, secondaryButton } from "./StudentFlowUI";

const baseFilters: Array<["all" | RequestState, string]> = [["all", "Tất cả"], ["new", "Mới nộp"], ["processing", "Đang xử lý"], ["supplement", "Cần bổ sung"], ["completed", "Hoàn tất"], ["draft", "Bản nháp"]];

const selectionEvent = "campus-requests-navigation";
function subscribeToSelection(notify: () => void) {
  window.addEventListener("popstate", notify);
  window.addEventListener(selectionEvent, notify);
  return () => { window.removeEventListener("popstate", notify); window.removeEventListener(selectionEvent, notify); };
}
const readSelection = () => window.location.search;
const serverSelection = () => "";

export function RequestsLoading() {
  return <div className="min-h-screen"><Navbar /><main className="mx-auto max-w-3xl px-5 py-12"><h1 className="text-2xl font-semibold">Hồ sơ của tôi</h1><p role="status" className="mt-4 text-slate-600 dark:text-slate-300">Đang tải hồ sơ…</p></main></div>;
}

export function RequestsLoadError({ retry, retrying = false }: { retry: () => void; retrying?: boolean }) {
  return <section className="rounded-2xl border border-red-200 bg-white p-6 dark:border-red-900 dark:bg-slate-900" aria-labelledby="requests-error-title">
    <h2 id="requests-error-title" className="text-xl font-semibold">Chưa tải được hồ sơ</h2>
    <p role="alert" className="mt-3 text-base leading-relaxed text-slate-700 dark:text-slate-200">Không thể xác định danh sách hoặc trạng thái mới nhất lúc này. Điều này không có nghĩa hồ sơ của bạn bị mất. Hãy thử tải lại.</p>
    <button type="button" disabled={retrying} onClick={retry} className={`${primaryButton} mt-5`}>{retrying ? "Đang tải…" : "Thử tải lại"}</button>
  </section>;
}

export function RequestsEmpty({ filtered, reset }: { filtered: boolean; reset: () => void }) {
  return <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-10 text-center dark:border-slate-600 dark:bg-slate-900">
    <FileText className="mx-auto mb-4 h-8 w-8 text-slate-500" aria-hidden="true" />
    <h2 className="text-lg font-semibold">{filtered ? "Không có hồ sơ phù hợp" : "Bạn chưa có hồ sơ"}</h2>
    <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">{filtered ? "Thử đổi trạng thái, loại yêu cầu hoặc từ khóa tìm kiếm." : "Sau khi nộp yêu cầu, mã hồ sơ và trạng thái sẽ xuất hiện tại đây."}</p>
    {filtered ? <button type="button" onClick={reset} className={`${secondaryButton} mt-4 border border-slate-300 dark:border-slate-600`}>Xóa bộ lọc</button> : <Link href="/student" className={`${primaryButton} mt-5`}>Tạo yêu cầu</Link>}
  </div>;
}

export function StudentRequestsPage() {
  // Selection is browser state over already loaded records, with no server navigation.
  const selection = useSyncExternalStore(subscribeToSelection, readSelection, serverSelection);
  const params = new URLSearchParams(selection);
  const { currentUser, tickets, reviewCases, isDataLoading, dataError, dataConfig, reloadData, addTicketMessage, submitStudentSupplement } = useStore();
  const listTitle = useRef<HTMLHeadingElement>(null);
  const lastSelected = useRef<{ id: string; kind: string } | null>(null);
  const localOnly = dataConfig?.mode === "mock";
  const filters = baseFilters.map(([value, label]) => [value, label] as const);
  const filter = normalizeFilter(params.get("filter"));
  const category = params.get("category") === "reviews" ? "reviews" : params.get("category") === "tickets" ? "tickets" : "all";
  const query = params.get("q") || "";
  const selectedKind = params.has("review") ? "review" : "ticket";
  const selectedId = params.get(selectedKind) || "";
  const items = currentUser ? collectRequests(tickets, reviewCases, currentUser.id) : [];
  const filtered = filterRequests(items, filter, query, category);
  const selected = filtered.find((item) => item.id === selectedId && item.kind === selectedKind);
  const hasFilter = filter !== "all" || category !== "all" || Boolean(query.trim());

  useEffect(() => {
    if (!selectedId && lastSelected.current) {
      const previous = lastSelected.current;
      (document.getElementById(`request-${previous.kind}-${previous.id}`) || listTitle.current)?.focus();
    }
    lastSelected.current = selectedId ? { id: selectedId, kind: selectedKind } : null;
  }, [selectedId, selectedKind]);

  function navigate(changes: Record<string, string | null>, replace = false) {
    const next = new URLSearchParams(params.toString());
    Object.entries(changes).forEach(([key, value]) => { if (value) next.set(key, value); else next.delete(key); });
    const url = `/my-requests${next.size ? `?${next.toString()}` : ""}`;
    if (replace) window.history.replaceState(null, "", url); else window.history.pushState(null, "", url);
    window.dispatchEvent(new Event(selectionEvent));
  }

  function clearSelection(changes: Record<string, string | null> = {}) {
    navigate({ ticket: null, review: null, ...changes });
    requestAnimationFrame(() => listTitle.current?.focus());
  }

  function backToList() {
    const previous = lastSelected.current || { id: selectedId, kind: selectedKind };
    navigate({ ticket: null, review: null });
    requestAnimationFrame(() => {
      const button = document.getElementById(`request-${previous.kind}-${previous.id}`);
      (button || listTitle.current)?.focus();
    });
  }

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const value = String(new FormData(event.currentTarget).get("q") || "").trim();
    clearSelection({ q: value });
  }

  if (isDataLoading) return <RequestsLoading />;
  if (!currentUser && !dataError) return <DataAccessState requiredRole="student" />;
  if (currentUser && currentUser.role !== "student") return <DataAccessState requiredRole="student" />;

  return <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
    <a href="#requests-main" className="sr-only z-50 rounded-xl bg-blue-700 p-3 text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Đi đến nội dung hồ sơ</a>
    <Navbar />
    <main id="requests-main" tabIndex={-1} className="mx-auto max-w-[1280px] px-4 py-6 sm:px-6 sm:py-8">
      <header className="mb-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Hồ sơ của tôi</h1><Link href="/student" className={`${primaryButton} px-4 text-sm`}><Plus className="h-4 w-4" aria-hidden="true" />Tạo yêu cầu</Link></div>
        <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-300">Tìm hồ sơ đã nộp, xem việc cần làm và theo dõi phản hồi.</p>
      </header>
      {dataError && <div className="mb-5"><RequestsLoadError retry={() => void reloadData()} /></div>}
      {currentUser && <div className="grid items-start gap-5 lg:grid-cols-[380px_minmax(0,1fr)] xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className={`${selected ? "hidden lg:block" : ""} min-w-0`} aria-labelledby="request-list-title">
          <div className="mb-4 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 dark:border-slate-700 dark:bg-slate-900">
            <h2 id="request-list-title" ref={listTitle} tabIndex={-1} className="text-lg font-semibold">Danh sách hồ sơ <span className="text-sm font-normal text-slate-600 dark:text-slate-300">({items.length})</span></h2>
            <form key={query} onSubmit={search} className="mt-4">
              <label htmlFor="request-search" className="mb-2 block text-sm font-medium">Tìm theo mã hoặc nội dung yêu cầu</label>
              <div className="flex gap-2"><input id="request-search" name="q" type="search" defaultValue={query} maxLength={200} placeholder="Ví dụ: TKT-2026…" className={`${fieldClass} min-w-0 px-3 text-sm`} /><button type="submit" aria-label="Tìm hồ sơ" className={`${secondaryButton} min-w-11 border border-slate-300 px-3 dark:border-slate-600`}><Search className="h-5 w-5" aria-hidden="true" /></button></div>
            </form>
            <div role="group" aria-label="Lọc trạng thái hồ sơ" className="mt-4 hidden flex-wrap gap-2 sm:flex">{filters.filter(([state]) => state !== "draft" || items.some((item) => item.state === "draft")).map(([value, label]) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => clearSelection({ filter: value === "all" ? null : value })} className={`min-h-11 rounded-xl border px-3 py-2 text-sm font-medium ${filter === value ? "border-blue-700 bg-blue-700 text-white" : "border-slate-300 text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"}`}>{label}</button>)}</div>
            <div className="mt-4 sm:hidden"><label htmlFor="request-state" className="mb-2 block text-sm font-medium">Trạng thái</label><select id="request-state" value={filter} onChange={(e) => clearSelection({ filter: e.target.value === "all" ? null : e.target.value })} className={`${fieldClass} text-sm`}>{filters.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
            <details key={category} open={category !== "all" || undefined} className="mt-2"><summary className="flex min-h-11 cursor-pointer items-center text-sm font-medium">Lọc theo loại yêu cầu{category !== "all" ? " · Đang áp dụng" : ""}</summary>
              <label htmlFor="request-category" className="sr-only">Nhóm yêu cầu</label><select id="request-category" value={category} onChange={(e) => clearSelection({ category: e.target.value === "all" ? null : e.target.value })} className={`${fieldClass} text-sm`}><option value="all">Tất cả loại yêu cầu</option><option value="tickets">Tài liệu, khiếu nại và câu hỏi</option><option value="reviews">Rà soát công nhận học phần</option></select>
            </details>
            <p role="status" className="mt-3 text-sm text-slate-600 dark:text-slate-300">{filtered.length} hồ sơ{hasFilter ? " phù hợp" : " · Mới nhất trước"}{filter === "processing" ? " · Gồm mới nộp và chờ cán bộ" : ""}</p>
            {hasFilter && <button type="button" className={`${secondaryButton} mt-2 -ml-3 text-blue-700 dark:text-blue-300`} onClick={() => clearSelection({ filter: null, category: null, q: null })}>Xóa bộ lọc</button>}
          </div>
          {!filtered.length ? <RequestsEmpty filtered={hasFilter} reset={() => clearSelection({ filter: null, category: null, q: null })} /> : <ul className="space-y-3">{filtered.map((item) => <li key={`${item.kind}-${item.id}`}>
            <button id={`request-${item.kind}-${item.id}`} type="button" aria-current={selected?.id === item.id && selected.kind === item.kind ? "true" : undefined} onClick={() => {
              navigate({ ticket: item.kind === "ticket" ? item.id : null, review: item.kind === "review" ? item.id : null });
            }} className={`w-full rounded-2xl border bg-white p-4 text-left transition-colors sm:p-5 dark:bg-slate-900 ${selected?.id === item.id && selected.kind === item.kind ? "border-blue-600 ring-1 ring-blue-600" : "border-slate-200 hover:border-blue-400 dark:border-slate-700"}`}>
              <RequestStatus item={item} localOnly={localOnly} />
              <h3 className="mt-3 break-words text-base font-semibold leading-relaxed">{item.title}</h3>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{item.type}</p>
              <p className="mt-3 break-all font-mono text-sm font-medium">{item.code}</p>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{item.state === "draft" ? "Tạo" : localOnly ? "Ghi nhận" : "Nộp"}: {formatDate(item.submittedAt)}</p>
              {item.state === "supplement" && <p className="mt-3 text-sm font-semibold text-amber-900 dark:text-amber-200">Cần bạn bổ sung thông tin hoặc tài liệu</p>}
              <span className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-blue-700 dark:text-blue-300">Xem chi tiết<ArrowRight className="h-4 w-4" aria-hidden="true" /></span>
            </button>
          </li>)}</ul>}
        </section>
        {selected ? <RequestDetail key={`${currentUser.id}-${selected.kind}-${selected.id}`} item={selected} localOnly={localOnly} onBack={backToList} onMessage={(id, content) => addTicketMessage(id, { senderId: currentUser.id, senderName: currentUser.name, senderRole: "student", content })} onSupplement={async (id, payload) => { await submitStudentSupplement(id, payload); navigate({ filter: null }); }} /> : <section className="hidden rounded-2xl border border-slate-200 bg-white p-8 lg:block dark:border-slate-700 dark:bg-slate-900">
          <h2 className="text-lg font-semibold">{selectedId ? "Không tìm thấy hồ sơ trong danh sách này" : "Chọn hồ sơ để xem chi tiết"}</h2>
          <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-300">{selectedId ? "Mã hồ sơ không thuộc tài khoản này hoặc không phù hợp với bộ lọc hiện tại. Không có hồ sơ khác được tự động mở thay thế." : "Trạng thái, phản hồi và các bước tiếp theo sẽ hiển thị tại đây."}</p>
        </section>}
        {!selected && selectedId && <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 lg:hidden dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">Không tìm thấy hồ sơ này trong tài khoản hoặc bộ lọc hiện tại. Chọn hồ sơ trong danh sách để tiếp tục.</p>}
      </div>}
    </main>
  </div>;
}
