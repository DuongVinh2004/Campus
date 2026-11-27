"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ApiClient } from "../../lib/api/client";
import { CAMPUS_API_BASE_URL } from "../../lib/api/base-url";
import { FeatureGate } from "../../lib/features";

interface Change { status: string; labels: string[]; severity: "HIGH" | "MEDIUM" | "LOW"; renumbered: boolean; family: string; path: string; similarity: number | null;
  numeric: { old: string | null; new: string | null }[] }
interface Report { old_release: string | null; new_release: string; status: "ANALYZED" | "BASELINE_ONLY"; summary: { by_status?: Record<string, number>; by_severity?: Record<string, number> };
  truncated?: boolean; items: Change[]; dependencies: { rules?: { rule_id: string; version?: number }[]; eval_cases?: unknown[] } }
interface Conflict { code: string; kind: string; subject: string; a: { value: string; quote: string }; b: { value: string; quote: string } }

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });
const SEVERITY: Record<string, string> = { HIGH: "Cao", MEDIUM: "Vừa", LOW: "Thấp" };
const STATUS: Record<string, string> = { ADDED: "Thêm mới", REMOVED: "Bị gỡ", MODIFIED: "Sửa đổi", MOVED: "Chuyển chỗ", UNCHANGED: "Giữ nguyên" };
// The labels of domain/policy_impact/diff.py.
const LABEL: Record<string, string> = { NUMERIC: "số liệu", DEADLINE: "thời hạn", NEGATION: "phủ định", SCOPE: "đối tượng áp dụng",
  EFFECTIVE: "hiệu lực", WORDING_ONLY: "chỉ câu chữ", TEXT_OTHER: "nội dung khác" };

function message(error: unknown): string {
  return error instanceof Error && error.message ? error.message : "Không tải được dữ liệu.";
}

function numbersText(numeric: Change["numeric"]): string {
  return (numeric ?? []).map(n => `${n.old ?? "—"} → ${n.new ?? "—"}`).join("; ");
}

function ImpactReport() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try { setReport(await client().get<Report>("/v1/policy-impact/report")); setError(null); } catch (e) { setReport(null); setError(message(e)); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function snapshot() {
    setBusy(true);
    try { await client().post("/v1/policy-impact/snapshot", {}); await load(); } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  return (
    <section aria-labelledby="impact-title" className="campus-card space-y-2">
      <h2 id="impact-title">Thay đổi so với bản phát hành trước</h2>
      <button type="button" disabled={busy} onClick={() => void snapshot()}>{busy ? "Đang phân tích…" : "Chụp và phân tích bản phát hành hiện tại"}</button>
      {error && <p role="status">{error}</p>}
      {report && (report.status === "BASELINE_ONLY"
        ? <p>Đây là ảnh chụp đầu tiên: lần phát hành sau sẽ được so với bản này.</p>
        : (
          <>
            <p>Bản <code>{report.old_release}</code> → <code>{report.new_release}</code>: {Object.entries(report.summary.by_severity ?? {}).map(([k, n]) => `${n} mức ${SEVERITY[k] ?? k}`).join(" · ") || "không có thay đổi"}.</p>
            {(report.dependencies.rules?.length ?? 0) > 0 && (
              <p role="status">{report.dependencies.rules!.length} luật trích đoạn đã đổi, cần rà lại: {report.dependencies.rules!.map(r => r.rule_id).join(", ")}.</p>
            )}
            {(report.dependencies.eval_cases?.length ?? 0) > 0 && <p>{report.dependencies.eval_cases!.length} ca kiểm thử dùng đoạn đã đổi.</p>}
            {report.items.length > 0 && (
              <table>
                <caption>Các đoạn thay đổi{report.truncated ? " (chỉ hiện phần đầu)" : ""}</caption>
                <thead><tr><th scope="col">Mức</th><th scope="col">Loại</th><th scope="col">Vị trí</th><th scope="col">Nội dung đổi</th><th scope="col">Số liệu</th></tr></thead>
                <tbody>{report.items.map((c, i) => (
                  <tr key={i}><td>{SEVERITY[c.severity] ?? c.severity}</td><td>{STATUS[c.status] ?? c.status}{c.renumbered ? " (đánh số lại)" : ""}</td>
                    <td>{c.path}</td><td>{c.labels.map(l => LABEL[l] ?? l).join(", ") || "—"}</td><td>{numbersText(c.numeric)}</td></tr>
                ))}</tbody>
              </table>
            )}
          </>
        ))}
    </section>
  );
}

function Conflicts() {
  const [data, setData] = useState<{ count: number; items: Conflict[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { client().get<{ count: number; items: Conflict[] }>("/v1/policy-conflicts").then(setData).catch(e => setError(message(e))); }, []);
  return (
    <section aria-labelledby="conflicts-title" className="campus-card space-y-2">
      <h2 id="conflicts-title">Mâu thuẫn giữa các nguồn</h2>
      {error && <p role="status">{error}</p>}
      {data && (data.count === 0 ? <p>Không thấy hai nguồn nào ghi khác nhau cho cùng một dữ kiện.</p> : (
        <ul>{data.items.map((c, i) => (
          <li key={i}>
            <strong>{c.subject}</strong>: một nguồn ghi «{c.a.value}», nguồn khác ghi «{c.b.value}».
            <details><summary>Xem hai đoạn</summary><blockquote>{c.a.quote}</blockquote><blockquote>{c.b.quote}</blockquote></details>
          </li>
        ))}</ul>
      ))}
    </section>
  );
}

/** For knowledge administrators: what changed in the regulation between releases, what depends on it, and conflicting facts. */
export function PolicyImpact() {
  return (
    <div className="space-y-6">
      <FeatureGate feature="policy.impact"><ImpactReport /></FeatureGate>
      <FeatureGate feature="policy.conflicts"><Conflicts /></FeatureGate>
    </div>
  );
}
