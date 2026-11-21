"use client";

import Link from "next/link";
import React, { useCallback, useEffect, useState } from "react";
import { ApiClientError } from "../../lib/api/client";
import { answerQualityApi, type AnswerQualityReport, type GapAction, type GapCluster } from "../../lib/answer-quality-api";

const REASON: Record<string, string> = {
  no_source: "Không tìm thấy nguồn phù hợp",
  out_of_scope: "Ngoài phạm vi trợ lý",
  unverified: "Chưa kiểm chứng được nội dung",
  unsafe: "Bị chặn vì an toàn",
  unspecified: "Không rõ lý do",
};
const ACTION: Record<GapAction, string> = {
  NEEDS_SOURCE: "Cần thêm nguồn",
  SOURCE_OUTDATED: "Nguồn đã cũ",
  OUT_OF_SCOPE: "Ngoài phạm vi",
  RESOLVED: "Đã xử lý",
};
const ACTIONS = Object.keys(ACTION) as GapAction[];
const TIME_ZONE = "Asia/Ho_Chi_Minh";

function day(iso: string): string {
  const value = new Date(iso);
  return Number.isNaN(value.getTime()) ? iso : new Intl.DateTimeFormat("vi-VN", { timeZone: TIME_ZONE, day: "2-digit", month: "2-digit" }).format(value);
}

function Cluster({ cluster, onSaved }: { cluster: GapCluster; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState<GapAction>("NEEDS_SOURCE");
  const [note, setNote] = useState("");
  const [release, setRelease] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = note.trim().length > 0 && (action !== "RESOLVED" || release.trim().length > 0);

  async function save() {
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      await answerQualityApi.decide(cluster.cluster_key, { action, note: note.trim(), release_ref: release.trim() });
      setOpen(false);
      setNote("");
      setRelease("");
      onSaved();
    } catch (caught) {
      setError(caught instanceof ApiClientError ? caught.message : "Không ghi nhận được. Hãy thử lại.");
    } finally {
      setBusy(false);
    }
  }

  const names = cluster.sources.map((s) => s.title ?? "Nguồn không còn trong bản phát hành").join("; ") || "Không có nguồn nào được nêu";
  return (
    <li data-testid={`gap-${cluster.cluster_key}`} className="campus-panel space-y-2 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="break-words font-medium">{REASON[cluster.reason] ?? cluster.reason}</p>
          <p className="break-words text-xs text-[var(--text-secondary)]">{names}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {cluster.is_new_trend ? <span className="rounded-full border px-3 py-1 text-xs font-semibold">Mới tăng</span> : null}
          <span className="rounded-full border px-3 py-1 text-xs">{cluster.count} lần · {cluster.count_7d} trong 7 ngày · gần nhất {day(cluster.last_at)}</span>
        </div>
      </div>
      {cluster.decision ? (
        <p className="text-xs text-[var(--text-secondary)]">
          {ACTION[cluster.decision.action]} ({day(cluster.decision.at)}): {cluster.decision.note}
          {cluster.decision.release_ref ? ` · bản phát hành ${cluster.decision.release_ref}` : ""}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Link href="/knowledge/documents" className="inline-flex min-h-[44px] items-center rounded-lg border px-4 text-sm">Thêm nguồn</Link>
        {!open ? <button type="button" onClick={() => setOpen(true)} className="min-h-[44px] rounded-lg border px-4 text-sm">Ghi nhận xử lý</button> : null}
      </div>
      {open ? (
        <div className="space-y-2">
          <label className="block text-sm" htmlFor={`action-${cluster.cluster_key}`}>Quyết định</label>
          <select id={`action-${cluster.cluster_key}`} value={action} onChange={(event) => setAction(event.target.value as GapAction)} className="min-h-[44px] rounded-lg border px-2 text-sm">
            {ACTIONS.map((value) => <option key={value} value={value}>{ACTION[value]}</option>)}
          </select>
          <label className="block text-sm" htmlFor={`note-${cluster.cluster_key}`}>Ghi chú (tối đa 500 ký tự)</label>
          <textarea id={`note-${cluster.cluster_key}`} value={note} onChange={(event) => setNote(event.target.value)} rows={2} maxLength={500} className="w-full rounded-lg border p-2 text-sm" />
          {action === "RESOLVED" ? (
            <>
              <label className="block text-sm" htmlFor={`release-${cluster.cluster_key}`}>Mã bản phát hành đã thay đổi</label>
              <input id={`release-${cluster.cluster_key}`} value={release} onChange={(event) => setRelease(event.target.value)} maxLength={100} className="min-h-[44px] w-full rounded-lg border px-2 text-sm" />
            </>
          ) : null}
          {error ? <p role="alert" className="text-sm text-[var(--color-danger,#c0392b)]">{error}</p> : null}
          <div className="flex gap-2">
            <button type="button" disabled={!valid || busy} onClick={() => void save()}
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

export function AnswerQualityPanel() {
  const [report, setReport] = useState<AnswerQualityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);

  const load = useCallback(async () => {
    try {
      setReport(await answerQualityApi.report(30));
      setError(null);
    } catch (caught) {
      if (caught instanceof ApiClientError && caught.problem.status === 403) setForbidden(true);
      else setError(caught instanceof ApiClientError ? caught.message : "Không tải được thống kê chất lượng câu trả lời.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (forbidden) return <p data-testid="quality-forbidden" role="alert" className="campus-panel p-4 text-sm">Chỉ quản trị tri thức mới xem được thống kê này.</p>;
  if (!report) {
    return error ? (
      <div data-testid="quality-error" role="alert" className="campus-panel space-y-3 p-4">
        <p className="text-sm">{error}</p>
        <button type="button" onClick={() => void load()} className="min-h-[44px] rounded-lg border px-4 text-sm">Thử lại</button>
      </div>
    ) : <p data-testid="quality-loading" role="status" className="campus-panel p-4 text-sm">Đang tải thống kê…</p>;
  }

  return (
    <div data-testid="quality-panel" className="space-y-6">
      <section aria-labelledby="gaps-heading" className="space-y-3">
        <header>
          <h2 id="gaps-heading" className="text-xl font-semibold">Câu hỏi bị từ chối</h2>
          <p className="text-sm text-[var(--text-secondary)]">
            Gom theo nguồn mà lần từ chối nhắc tới. Hệ thống không lưu nội dung câu hỏi hay người hỏi; chỉ hiện nhóm có từ {report.gaps.minimum_count} lần trong {report.gaps.days} ngày.
          </p>
        </header>
        {report.gaps.clusters.length === 0 ? (
          <p data-testid="gaps-empty" className="campus-panel p-4 text-sm">Chưa có nhóm nào đủ số lần để hiển thị.</p>
        ) : (
          <ul className="space-y-3">{report.gaps.clusters.map((cluster) => <Cluster key={cluster.cluster_key} cluster={cluster} onSaved={() => void load()} />)}</ul>
        )}
      </section>
      <section aria-labelledby="rated-heading" className="space-y-3">
        <header>
          <h2 id="rated-heading" className="text-xl font-semibold">Nguồn bị đánh giá &quot;chưa hữu ích&quot;</h2>
          <p className="text-sm text-[var(--text-secondary)]">Chỉ liệt kê nguồn có ít nhất {report.minimum_votes} lượt đánh giá. Đây là gợi ý đọc lại nguồn, không phải kết luận nguồn sai.</p>
        </header>
        {report.sources.length === 0 ? (
          <p data-testid="rated-empty" className="campus-panel p-4 text-sm">Chưa có nguồn nào đủ lượt đánh giá.</p>
        ) : (
          <ul className="space-y-2">
            {report.sources.map((source) => (
              <li key={source.version_id} className="campus-panel p-4 text-sm">
                <p className="break-words font-medium">{source.title ?? "Nguồn không còn trong bản phát hành"}</p>
                <p className="text-xs text-[var(--text-secondary)]">{source.owner_unit ?? ""} · {source.not_helpful} chưa hữu ích / {source.helpful + source.not_helpful} đánh giá ({Math.round(source.share_not_helpful * 100)}%)</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
