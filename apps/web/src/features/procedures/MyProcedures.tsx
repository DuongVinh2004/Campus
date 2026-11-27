"use client";

import React, { useEffect, useState } from "react";
import { proceduresApi, type ProcedureRun } from "../../lib/procedures-api";

const STATE: Record<string, string> = {
  STARTED: "Mới bắt đầu", COLLECTING: "Đang điền", BLOCKED: "Chưa đủ điều kiện", READY_FOR_PREVIEW: "Sẵn sàng xem trước",
  PREVIEWED: "Đã xem trước, chưa gửi", SUBMITTED: "Đã gửi", CANCELLED: "Đã hủy", EXPIRED: "Đã hết hạn",
};
const OPEN = new Set(["STARTED", "COLLECTING", "BLOCKED", "READY_FOR_PREVIEW", "PREVIEWED"]);

/** "Thủ tục của tôi": the student's procedure runs, unfinished ones first, with a link to continue or to the ticket. */
export function MyProcedures({ currentRunId }: { currentRunId?: string }) {
  const [runs, setRuns] = useState<ProcedureRun[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    proceduresApi.list().then(r => { if (alive) setRuns(r.items ?? []); })
      .catch(e => { if (alive) setError(e instanceof Error ? e.message : "Không tải được danh sách thủ tục."); });
    return () => { alive = false; };
  }, []);
  if (error) return <p role="alert">{error}</p>;
  if (!runs) return <p role="status">Đang tải thủ tục của bạn…</p>;
  const ordered = [...runs].sort((a, b) => Number(OPEN.has(b.state)) - Number(OPEN.has(a.state)));
  return (
    <section aria-labelledby="my-procedures" className="campus-card space-y-2">
      <h2 id="my-procedures">Thủ tục của tôi</h2>
      {ordered.length === 0 ? <p>Bạn chưa bắt đầu thủ tục nào.</p> : (
        <ul>
          {ordered.map(run => (
            <li key={run.id} aria-current={run.id === currentRunId ? "true" : undefined}>
              <strong>{run.title || run.procedure_id}</strong> · {STATE[run.state] ?? run.state}
              {run.ticket?.code && <> · mã hồ sơ {run.ticket.code}</>}
              {OPEN.has(run.state) && run.id !== currentRunId && <> · <a href={`/services/procedures?run=${encodeURIComponent(run.id)}`}>Làm tiếp</a></>}
              {run.state === "SUBMITTED" && <> · <a href="/tickets">Xem hồ sơ</a></>}
              {OPEN.has(run.state) && run.expires_at && <small> (hết hạn {new Date(run.expires_at).toLocaleDateString("vi-VN")})</small>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
