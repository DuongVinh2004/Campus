"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ApiClientError } from "../../lib/api/client";
import { freshnessApi, type FreshnessItem, type FreshnessReport, type FreshnessState } from "../../lib/knowledge-freshness-api";

const STATE_LABEL: Record<FreshnessState, string> = {
  EXPIRED: "Đã hết hiệu lực",
  OVERDUE: "Quá hạn rà soát",
  DUE_SOON: "Sắp đến hạn",
  OK: "Còn hạn",
};
const FILTERS: Array<"ALL" | FreshnessState> = ["ALL", "EXPIRED", "OVERDUE", "DUE_SOON", "OK"];
const MIN_NOTE = 10;
const TIME_ZONE = "Asia/Ho_Chi_Minh";

function date(iso: string | null): string {
  if (!iso) return "—";
  const value = new Date(iso);
  return Number.isNaN(value.getTime()) ? iso : new Intl.DateTimeFormat("vi-VN", { timeZone: TIME_ZONE, day: "2-digit", month: "2-digit", year: "numeric" }).format(value);
}

function dueText(item: FreshnessItem): string {
  if (item.due_at === null || item.days_left === null) return "Chưa có mốc rà soát";
  const what = item.reason === "EFFECTIVE_UNTIL" ? "Hết hiệu lực" : "Rà soát lại";
  if (item.days_left < 0) return `${what} ${date(item.due_at)} (quá ${-item.days_left} ngày)`;
  return `${what} ${date(item.due_at)} (còn ${item.days_left} ngày)`;
}

function Row({ item, onReviewed }: { item: FreshnessItem; onReviewed: () => void }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = note.trim().length >= MIN_NOTE;
  // An expired source is already left out of answers; checking it again would not bring it back, so no button.
  const canReview = item.state !== "EXPIRED";

  async function submit() {
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      await freshnessApi.reviewed(item.source_id, note.trim());
      setOpen(false);
      setNote("");
      onReviewed();
    } catch (caught) {
      setError(caught instanceof ApiClientError ? caught.message : "Không ghi nhận được. Hãy thử lại.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <li data-testid={`freshness-${item.source_id}`} data-state={item.state} className="campus-panel space-y-2 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="break-words font-medium text-[var(--text-primary)]">{item.title}</p>
          <p className="text-xs text-[var(--text-secondary)]">{item.owner_unit}{item.version_label ? ` · ${item.version_label}` : ""}</p>
        </div>
        <span className="rounded-full border px-3 py-1 text-xs font-medium">{STATE_LABEL[item.state]}</span>
      </div>
      <p className="text-sm text-[var(--text-secondary)]">{dueText(item)}</p>
      {item.applicability_unknown ? (
        <p className="text-xs text-[var(--text-secondary)]">Chưa rõ phạm vi áp dụng của nguồn này.</p>
      ) : null}
      {item.last_review ? (
        <p className="text-xs text-[var(--text-secondary)]">Rà soát gần nhất {date(item.last_review.reviewed_at)}: {item.last_review.note}</p>
      ) : null}
      {canReview && !open ? (
        <button type="button" onClick={() => setOpen(true)} className="min-h-[44px] rounded-lg border px-4 text-sm">Đã rà soát nguồn này</button>
      ) : null}
      {open ? (
        <div className="space-y-2">
          <label className="block text-sm" htmlFor={`note-${item.source_id}`}>Ghi chú rà soát (ít nhất {MIN_NOTE} ký tự)</label>
          <textarea id={`note-${item.source_id}`} value={note} onChange={(event) => setNote(event.target.value)} rows={3} maxLength={1000}
                    className="w-full rounded-lg border p-2 text-sm" />
          {error ? <p role="alert" className="text-sm text-[var(--color-danger,#c0392b)]">{error}</p> : null}
          <div className="flex gap-2">
            <button type="button" disabled={!valid || busy} onClick={() => void submit()}
                    className="min-h-[44px] rounded-lg bg-[var(--color-primary)] px-4 text-sm font-medium text-[var(--color-on-primary)] disabled:opacity-50">
              {busy ? "Đang ghi…" : "Ghi nhận"}
            </button>
            <button type="button" onClick={() => { setOpen(false); setError(null); }} className="min-h-[44px] rounded-lg border px-4 text-sm">Hủy</button>
          </div>
        </div>
      ) : null}
    </li>
  );
}

export function FreshnessPanel() {
  const [report, setReport] = useState<FreshnessReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [filter, setFilter] = useState<"ALL" | FreshnessState>("ALL");

  const load = useCallback(async () => {
    try {
      setReport(await freshnessApi.report());
      setError(null);
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.problem.status === 403) setForbidden(true);
      else setError(caught instanceof ApiClientError ? caught.message : "Không tải được hiệu lực của nguồn.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const shown = useMemo(() => (report?.items ?? []).filter((item) => filter === "ALL" || item.state === filter), [report, filter]);

  if (forbidden) return <p data-testid="freshness-forbidden" role="alert" className="campus-panel p-4 text-sm">Chỉ quản trị tri thức mới xem được hiệu lực của nguồn.</p>;
  if (!report) {
    return error ? (
      <div data-testid="freshness-error" role="alert" className="campus-panel space-y-3 p-4">
        <p className="text-sm">{error}</p>
        <button type="button" onClick={() => void load()} className="min-h-[44px] rounded-lg border px-4 text-sm">Thử lại</button>
      </div>
    ) : <p data-testid="freshness-loading" role="status" className="campus-panel p-4 text-sm">Đang tải hiệu lực của nguồn…</p>;
  }

  return (
    <section data-testid="freshness-panel" aria-labelledby="freshness-heading" className="space-y-4">
      <header>
        <h2 id="freshness-heading" className="text-xl font-semibold text-[var(--text-primary)]">Hiệu lực của nguồn</h2>
        <p className="text-sm text-[var(--text-secondary)]">
          Nguồn đã hết hiệu lực không còn xuất hiện trong câu trả lời. Nguồn không có ngày hết hạn được nhắc rà soát lại sau 12 tháng.
        </p>
      </header>
      <ul className="flex flex-wrap gap-2" aria-label="Lọc theo trạng thái">
        {FILTERS.map((name) => (
          <li key={name}>
            <button type="button" aria-pressed={filter === name} onClick={() => setFilter(name)}
                    className="min-h-[44px] rounded-full border px-4 text-sm aria-pressed:font-semibold">
              {name === "ALL" ? `Tất cả (${report.items.length})` : `${STATE_LABEL[name]} (${report.summary[name]})`}
            </button>
          </li>
        ))}
      </ul>
      {report.summary.applicability_unknown ? (
        <p className="text-sm text-[var(--text-secondary)]">{report.summary.applicability_unknown} nguồn chưa rõ phạm vi áp dụng.</p>
      ) : null}
      {error ? <p role="alert" className="text-sm text-[var(--color-danger,#c0392b)]">{error}</p> : null}
      {shown.length === 0 ? <p data-testid="freshness-empty" className="text-sm text-[var(--text-secondary)]">Không có nguồn nào ở mục này.</p> : (
        <ul className="space-y-3">{shown.map((item) => <Row key={item.source_id} item={item} onReviewed={() => void load()} />)}</ul>
      )}
    </section>
  );
}
