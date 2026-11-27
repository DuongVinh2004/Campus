"use client";

import React, { useEffect, useState } from "react";
import { answerQualityApi, type VerificationReport } from "../../lib/answer-quality-api";

const REASON_LABEL: Record<string, string> = {
  NUMBER_NOT_IN_SOURCE: "Số liệu không có trong nguồn", DATE_NOT_IN_SOURCE: "Ngày tháng không có trong nguồn", CODE_NOT_IN_SOURCE: "Mã không có trong nguồn",
  NEGATION_MISMATCH: "Ngược nghĩa phủ định so với nguồn", UNIT_NOT_CITED: "Không dẫn nguồn", UNIT_MISMATCH: "Sai đơn vị tính",
  SEMANTIC_UNSUPPORTED: "Nguồn không đỡ ý nghĩa", SCOPE_MISMATCH: "Sai phạm vi (ngành, khóa)", UNVERIFIED: "Chưa xác minh được",
};
/**
 * The latest day's dropped statements against the average of the 7 days before it: a spike when it is more than twice that
 * average and at least MIN_SPIKE (a few drops on a quiet day are not a signal). Days with no row count as 0.
 */
export const MIN_SPIKE = 5;
export function rejectedSpike(daily: VerificationReport["daily_rejected"]): { day: string; count: number; average: number } | null {
  if (daily.length === 0) return null;
  const totals = new Map(daily.map(d => [d.day, Object.values(d.by_reason).reduce((a, b) => a + b, 0)]));
  const last = [...totals.keys()].sort().at(-1) as string;
  const count = totals.get(last) ?? 0;
  const start = new Date(`${last}T00:00:00Z`);
  let sum = 0;
  for (let i = 1; i <= 7; i++) {
    const day = new Date(start.getTime() - i * 86400000).toISOString().slice(0, 10);
    sum += totals.get(day) ?? 0;
  }
  const average = sum / 7;
  return count >= MIN_SPIKE && count > 2 * average ? { day: last, count, average: Math.round(average * 10) / 10 } : null;
}

const percent = (value: number | null) => (value === null ? "chưa có số liệu" : `${Math.round(value * 1000) / 10}%`);

/** How many statements the verifier kept and dropped, and why. Counts only: no question, answer or person is behind these numbers. */
export function VerificationPanel() {
  const [days, setDays] = useState(30);
  const [report, setReport] = useState<VerificationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    answerQualityApi.verification(days).then(r => { if (alive) { setReport(r); setError(null); } })
      .catch(e => { if (alive) setError(e instanceof Error ? e.message : "Không tải được số liệu kiểm chứng."); });
    return () => { alive = false; };
  }, [days]);

  return (
    <section aria-labelledby="verification-title" className="campus-card space-y-2">
      <h2 id="verification-title">Kiểm chứng câu trả lời</h2>
      <label>Khoảng thời gian{" "}
        <select value={days} onChange={e => setDays(Number(e.target.value))}>
          <option value={7}>7 ngày</option><option value={30}>30 ngày</option>
        </select>
      </label>
      {error && <p role="alert">{error}</p>}
      {!report && !error && <p role="status">Đang tải…</p>}
      {report && (
        <>
          <p>{report.statements} ý được giữ lại · {report.rejected_total} ý bị loại ({percent(report.rejected_share)} số ý được kiểm).</p>
          {(() => {
            const spike = rejectedSpike(report.daily_rejected ?? []);
            return spike && (
              <p role="status"><strong>Số ý bị loại tăng bất thường:</strong> ngày {spike.day} có {spike.count} ý bị loại, hơn gấp đôi trung bình 7 ngày trước ({spike.average} ý/ngày). Hãy rà nguồn mới phát hành hoặc thay đổi gần đây.</p>
            );
          })()}
          <p>Ý trùng nguyên văn với nguồn: {percent(report.verbatim_share)}. Ý cần đối chiếu ý nghĩa: {report.semantic}.</p>
          {report.rejected_total === 0 ? <p>Chưa có ý nào bị loại trong khoảng này.</p> : (
            <table>
              <caption>Ý bị loại theo lý do</caption>
              <thead><tr><th scope="col">Lý do</th><th scope="col">Số ý</th></tr></thead>
              <tbody>{Object.entries(report.rejected).map(([reason, n]) => <tr key={reason}><td>{REASON_LABEL[reason] ?? reason}</td><td>{n}</td></tr>)}</tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
}
