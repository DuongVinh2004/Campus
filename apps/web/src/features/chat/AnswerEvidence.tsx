"use client";

import React, { useEffect, useId, useState } from "react";
import { AccessibleDialog } from "../../components/shared/AccessibleDialog";
import { answerReceiptsApi, type AnswerReceipt } from "../../lib/answer-receipts-api";

function badge(checks: AnswerReceipt["statements"][number]["checks"]): { word: string; why: string } {
  if (checks.verbatim) return { word: "Nguyên văn", why: "Ý này trùng nguyên văn với đoạn nguồn được dẫn." };
  if (checks.semantic === "PASSED") return { word: "Đã đối chiếu", why: "Số liệu, ngày tháng và ý nghĩa của ý này đã được đối chiếu với nguồn." };
  return { word: "Đã kiểm số liệu", why: "Số liệu và ngày tháng của ý này đã được đối chiếu với nguồn." };
}

const SOURCE_NOW: Record<string, string> = { UNCHANGED: "nguồn còn nguyên", CHANGED: "nguồn đã được sửa", REMOVED: "nguồn đã bị gỡ" };

// Reason codes of dropped statements, in words, for staff only (decision D5).
// The codes are rag_v2/verification/deterministic.py REASON_CODES plus "UNVERIFIED" (compose.py, no reason given).
const REASONS: Record<string, string> = {
  NUMBER_NOT_IN_SOURCE: "số không có trong nguồn", CODE_NOT_IN_SOURCE: "mã không có trong nguồn", DATE_NOT_IN_SOURCE: "ngày không có trong nguồn",
  NEGATION_MISMATCH: "đảo phủ định so với nguồn", UNIT_NOT_CITED: "không dẫn nguồn", SEMANTIC_UNSUPPORTED: "ý không được nguồn đỡ",
  SCOPE_MISMATCH: "nguồn thuộc phạm vi khác", UNIT_MISMATCH: "đơn vị đo khác nguồn", UNVERIFIED: "chưa kiểm được",
};

/** What each point of an answer went through, from the stored receipt. Shows nothing when there is no receipt (feature off, old answer). */
export function AnswerEvidence({ conversationId, messageId }: { conversationId: string; messageId: string }) {
  const [receipt, setReceipt] = useState<AnswerReceipt | null>(null);
  const [open, setOpen] = useState(false);
  const titleId = useId();
  useEffect(() => {
    let alive = true;
    answerReceiptsApi.forMessage(conversationId, messageId).then(r => { if (alive) setReceipt(r); }).catch(() => { if (alive) setReceipt(null); });
    return () => { alive = false; };
  }, [conversationId, messageId]);
  if (!receipt || receipt.statements.length === 0) return null;
  const dropped = Object.values(receipt.rejected_counts).reduce((a, b) => a + b, 0);
  const stale = receipt.now.sources_changed + receipt.now.sources_removed;
  return (
    <section aria-label="Bằng chứng của câu trả lời" className="mt-2 text-xs text-slate-600 dark:text-slate-400">
      <p>
        {receipt.statements.length} ý đã kiểm với nguồn{dropped > 0 ? ` · ${dropped} ý bị loại vì không đủ nguồn` : ""}
        {" · "}<button type="button" className="underline" onClick={() => setOpen(true)}>Xem biên nhận</button>
      </p>
      {stale > 0 && <p role="status">Nguồn đã được sửa đổi hoặc gỡ sau lần trả lời này; hãy hỏi lại để có thông tin mới nhất.</p>}
      {receipt.show_reason_codes && dropped > 0 && (
        <p>Ý bị loại: {Object.entries(receipt.rejected_counts).map(([code, n]) => `${n} × ${REASONS[code] ?? code}`).join(" · ")}</p>
      )}
      <AccessibleDialog open={open} onClose={() => setOpen(false)} labelledBy={titleId} className="campus-card space-y-2">
        <h2 id={titleId}>Biên nhận câu trả lời</h2>
        <p>Trả lời lúc {new Date(receipt.created_at).toLocaleString("vi-VN")}, theo bản phát hành tri thức <code>{receipt.release_id}</code>.</p>
        {receipt.now.release_id && receipt.now.release_id !== receipt.release_id && <p>Bản phát hành hiện tại: <code>{receipt.now.release_id}</code>.</p>}
        <ol>
          {receipt.statements.map(s => {
            const b = badge(s.checks);
            return (
              <li key={s.index}>
                Ý {s.index}: <span title={b.why} aria-label={`${b.word}: ${b.why}`}>{b.word}</span>
                {s.sources.length > 0 && (
                  <ul>{s.sources.map((src, i) => (
                    <li key={`${src.unit_id}-${i}`}>{src.doc_title ?? "Nguồn"}{src.path ? ` — ${src.path}` : ""}{src.page ? `, trang ${src.page}` : ""} ({SOURCE_NOW[src.status_now] ?? src.status_now})</li>
                  ))}</ul>
                )}
              </li>
            );
          })}
        </ol>
        <button type="button" onClick={() => setOpen(false)}>Đóng</button>
      </AccessibleDialog>
    </section>
  );
}
