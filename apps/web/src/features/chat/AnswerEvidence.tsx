"use client";

import React, { useEffect, useState } from "react";
import { answerReceiptsApi, type AnswerReceipt } from "../../lib/answer-receipts-api";

function badge(checks: AnswerReceipt["statements"][number]["checks"]): { word: string; why: string } {
  if (checks.verbatim) return { word: "Nguyên văn", why: "Ý này trùng nguyên văn với đoạn nguồn được dẫn." };
  if (checks.semantic === "PASSED") return { word: "Đã đối chiếu", why: "Số liệu, ngày tháng và ý nghĩa của ý này đã được đối chiếu với nguồn." };
  return { word: "Đã kiểm số liệu", why: "Số liệu và ngày tháng của ý này đã được đối chiếu với nguồn." };
}

/** What each point of an answer went through, from the stored receipt. Shows nothing when there is no receipt (feature off, old answer). */
export function AnswerEvidence({ conversationId, messageId }: { conversationId: string; messageId: string }) {
  const [receipt, setReceipt] = useState<AnswerReceipt | null>(null);
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
      <p>{receipt.statements.length} ý đã kiểm với nguồn{dropped > 0 ? ` · ${dropped} ý bị loại vì không đủ nguồn` : ""}</p>
      {stale > 0 && <p role="status">Nguồn đã được sửa đổi hoặc gỡ sau lần trả lời này; hãy hỏi lại để có thông tin mới nhất.</p>}
      <details>
        <summary>Chi tiết kiểm chứng</summary>
        <ol>
          {receipt.statements.map(s => {
            const b = badge(s.checks);
            return (
              <li key={s.index}>
                Ý {s.index}: <span title={b.why} aria-label={b.why}>{b.word}</span>
                {s.sources.length > 0 && <small> — {s.sources.map(src => src.path ?? src.doc_title ?? "nguồn").join("; ")}</small>}
              </li>
            );
          })}
        </ol>
      </details>
    </section>
  );
}
