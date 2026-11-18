import React from "react";
import { AlertTriangle, ShieldAlert, FileText, CheckCircle2, Inbox } from "lucide-react";

export interface KnowledgeChunk {
  id: string;
  locator: string;
  content: string;
  wordCount?: number;
  warnings?: string[];
}

export interface KnowledgeDocItem {
  id: string;
  documentRef: string;
  title: string;
  status: "draft" | "pending_review" | "published" | "archived";
  authorId: string;
  department: string;
  version: string;
  sourceUri?: string;
  contentHash?: string;
  quarantineStatus?: boolean;
  policyViolations?: string[];
  isStale?: boolean;
  effectiveFrom?: string;
  effectiveTo?: string;
  freshnessStatus?: "fresh" | "stale" | "expired";
  parseStatus?: "parsed" | "pending" | "failed";
  chunks?: KnowledgeChunk[];
  reviewEvidenceComplete?: boolean;
  warnings?: string[];
}

export interface KnowledgeReviewProps {
  document: KnowledgeDocItem;
  currentUserId: string;
  userRole?: string;
  onApprove?: (docId: string) => void;
  onReject?: (docId: string) => void;
}

export function KnowledgeReview({
  document,
  currentUserId,
  userRole,
  onApprove,
  onReject,
}: KnowledgeReviewProps) {
  const isAuthor = document.authorId === currentUserId;
  const isParseFailed = document.parseStatus === "failed";
  const isEvidenceIncomplete = document.reviewEvidenceComplete === false;

  const hasAuthority = !userRole || userRole === "ADMIN" || userRole === "KNOWLEDGE_MANAGER";
  const isStaleDoc =
    document.isStale === true ||
    document.freshnessStatus === "stale" ||
    document.freshnessStatus === "expired";
  const isQuarantined =
    !!document.quarantineStatus ||
    (!!document.policyViolations && document.policyViolations.length > 0);

  const canPublish =
    document.status === "pending_review" &&
    !isAuthor &&
    !isParseFailed &&
    !isEvidenceIncomplete &&
    hasAuthority &&
    !isStaleDoc &&
    !isQuarantined;

  const chunks = document.chunks || [];
  const warnings = document.warnings || [];
  const policyViolations = document.policyViolations || [];

  return (
    <div
      role="region"
      aria-label="Phê duyệt văn bản tri thức"
      className="fluent-card flex max-w-3xl flex-col gap-6 rounded-[12px] border border-[var(--border-color)] bg-[var(--surface-card)] p-4 sm:p-6 shadow-xs"
    >
      {/* Quarantine Banner (AC-TASK-WEB-KNOW-003-03) */}
      {isQuarantined && (
        <div
          role="alert"
          className="rounded-[12px] border-2 border-rose-500 bg-rose-50 p-4 text-xs leading-relaxed text-rose-950 dark:border-rose-700 dark:bg-rose-950/40 dark:text-rose-200"
        >
          <div className="mb-1.5 flex items-center gap-2.5 font-bold">
            <AlertTriangle className="h-5 w-5 shrink-0 text-rose-600 dark:text-rose-400" aria-hidden="true" />
            <span>[CÁCH LY KIỂM DUYỆT] Văn bản đang trong trạng thái cách ly</span>
          </div>
          <p className="mb-2">
            Văn bản đã bị cách ly do vi phạm chính sách an toàn thông tin hoặc có dấu hiệu mã độc / prompt injection. Quyền phê duyệt bị khóa toàn bộ.
          </p>
          {policyViolations.length > 0 && (
            <ul className="list-disc pl-5 font-semibold space-y-0.5 break-all">
              {policyViolations.map((v, idx) => (
                <li key={idx}>{v}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Header and Metadata */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <span className="rounded bg-[var(--color-primary-light)] px-2 py-0.5 text-xs font-bold text-[var(--color-primary)] break-all">
              {document.documentRef}
            </span>
            <span className="text-xs text-[var(--text-secondary)]">
              Phiên bản: v{document.version}
            </span>
          </div>

          <h2 className="mb-1.5 text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100 break-words">
            {document.title}
          </h2>

          <div className="text-xs text-[var(--text-secondary)]">
            Đơn vị ban hành: <strong className="font-semibold text-slate-700 dark:text-slate-300 break-words">{document.department}</strong> • Người soạn thảo:{" "}
            <code className="rounded bg-[var(--surface-subtle)] px-1 py-0.5 text-slate-800 dark:bg-slate-800 dark:text-slate-200 break-all">
              {document.authorId}
            </code>
          </div>
        </div>

        <span
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold whitespace-nowrap ${
            document.status === "published"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300"
              : document.status === "draft"
              ? "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300"
              : document.status === "archived"
              ? "border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400"
              : "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300"
          }`}
        >
          {document.status === "published" && (
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          )}
          {document.status === "draft" && (
            <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          )}
          {document.status === "archived" && (
            <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          )}
          {document.status === "pending_review" && (
            <ShieldAlert className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          )}
          <span>
            {document.status === "published"
              ? "✓ Đã duyệt & Ban hành"
              : document.status === "draft"
              ? "Yêu cầu sửa đổi"
              : document.status === "archived"
              ? "Lưu trữ"
              : "Chờ duyệt 4 mắt"}
          </span>
        </span>
      </div>

      {/* Immutable Provenance Information (AC-TASK-WEB-KNOW-003-03) */}
      {(document.sourceUri || document.contentHash) && (
        <div className="flex flex-col gap-1 rounded-[12px] border border-[var(--border-color)] bg-[var(--surface-subtle)] p-3.5 text-xs text-[var(--text-secondary)]">
          <div className="font-bold text-slate-900 dark:text-slate-100">
            Nguồn gốc xuất xứ (Provenance):
          </div>
          {document.sourceUri && (
            <div className="break-all">
              Nguồn gốc: <code className="rounded bg-[var(--surface-card)] px-1 py-0.5 text-slate-800 dark:bg-slate-800 dark:text-slate-200 break-all">{document.sourceUri}</code>
            </div>
          )}
          {document.contentHash && (
            <div className="break-all">
              Mã băm nội dung: <code className="rounded bg-[var(--surface-card)] px-1 py-0.5 text-slate-800 dark:bg-slate-800 dark:text-slate-200 break-all">{document.contentHash}</code>
            </div>
          )}
        </div>
      )}

      {/* Parse and Freshness Status Banner */}
      <div className="grid grid-cols-1 gap-3 rounded-[12px] border border-[var(--border-color)] bg-[var(--surface-subtle)] p-3.5 text-xs text-[var(--text-secondary)] sm:grid-cols-2">
        <div>
          <span className="font-medium text-[var(--text-secondary)]">
            Trạng thái trích xuất:{" "}
          </span>
          <strong className="font-bold text-slate-900 dark:text-slate-100">
            {document.parseStatus === "failed"
              ? "Lỗi trích xuất cú pháp"
              : document.parseStatus === "parsed"
              ? "Đã phân tích cú pháp"
              : "Chờ phân tích"}
          </strong>{" "}
          <span>({chunks.length} đoạn)</span>
        </div>

        <div>
          <span className="font-medium text-[var(--text-secondary)]">
            Thời hạn & Độ tươi:{" "}
          </span>
          <strong className="font-bold text-slate-900 dark:text-slate-100">
            {document.effectiveFrom && document.effectiveTo
              ? `Hiệu lực: ${document.effectiveFrom} - ${document.effectiveTo}`
              : document.freshnessStatus === "fresh"
              ? "Dữ liệu mới cập nhật"
              : "Chưa xác định thời hạn"}
          </strong>
        </div>
      </div>

      {/* Stale / Changed Document Warning (AC-TASK-WEB-KNOW-003-01) */}
      {isStaleDoc && (
        <div
          role="alert"
          className="rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs leading-relaxed text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200"
        >
          <strong>[XUNG ĐỘT PHIÊN BẢN]</strong> Văn bản đã bị thay đổi hoặc hết hạn (Stale). Cần cập nhật phiên bản mới trước khi thẩm định.
        </div>
      )}

      {/* Authority Warning (AC-TASK-WEB-KNOW-003-02) */}
      {!hasAuthority && (
        <div
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-xs leading-relaxed text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200"
        >
          <strong>[KHÔNG ĐỦ THẨM QUYỀN]</strong> Không có thẩm quyền ban hành: Vai trò hiện tại của bạn không được phép phê duyệt hoặc ban hành văn bản tri thức.
        </div>
      )}

      {/* Warnings & Incomplete Review Alerts */}
      {isAuthor && (
        <div
          role="alert"
          className="flex items-center gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-xs leading-relaxed text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200"
        >
          <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400" />
          <span>
            Quy tắc 4 mắt: Tác giả không thể tự phê duyệt tài liệu do chính mình soạn thảo. Cần một cán bộ khác thẩm định và ban hành.
          </span>
        </div>
      )}

      {isEvidenceIncomplete && (
        <div
          role="alert"
          className="rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs leading-relaxed text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200"
        >
          <div className="mb-1 font-bold">
            [CẢNH BÁO] Chưa đủ bằng chứng thẩm định
          </div>
          <p className="mb-1.5">
            Tài liệu này chưa có đầy đủ bằng chứng đối chiếu hoặc kiểm định chất lượng (eval). Nút xuất bản bị khóa để bảo đảm an toàn dữ liệu.
          </p>
          {warnings.length > 0 && (
            <ul className="list-disc pl-5 font-medium space-y-0.5">
              {warnings.map((w, idx) => (
                <li key={idx}>{w}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {isParseFailed && (
        <div
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-xs leading-relaxed text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200"
        >
          <div className="font-bold">[NGHIÊM TRỌNG] Lỗi trích xuất cú pháp</div>
          <div>
            Không thể thẩm định hoặc xuất bản tài liệu do tệp nguồn gặp lỗi bóc tách văn bản. Vui lòng tải lên lại hoặc chỉnh sửa tệp nguồn.
          </div>
        </div>
      )}

      {/* Source to Chunks Hierarchy */}
      <div>
        <h3 className="mb-3 text-xs font-bold tracking-wider text-slate-700 uppercase dark:text-slate-300">
          Phân đoạn văn bản & Định vị trích dẫn (Chunks & Locators)
        </h3>

        {chunks.length === 0 ? (
          <div className="campus-empty-state rounded-[12px] border border-dashed border-[var(--border-color)] bg-[var(--surface-card)]">
            <Inbox aria-hidden="true" />
            <p>Chưa có đoạn trích xuất nào được ghi nhận.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {chunks.map((chunk) => (
              <div
                key={chunk.id}
                tabIndex={0}
                className="rounded-[12px] border border-[var(--border-color)] bg-[var(--surface-card)] p-4 text-xs transition hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-[var(--color-primary)] focus-visible:outline-offset-2"
              >
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <span className="rounded bg-[var(--color-primary-light)] px-2 py-0.5 font-bold text-[var(--color-primary)] break-all">
                    {chunk.locator}
                  </span>
                  {chunk.wordCount !== undefined && (
                    <span className="text-[11px] text-[var(--text-secondary)]">
                      {chunk.wordCount} từ
                    </span>
                  )}
                </div>

                <p className="leading-relaxed text-slate-800 whitespace-pre-wrap break-words dark:text-slate-200">
                  {chunk.content}
                </p>

                {chunk.warnings && chunk.warnings.length > 0 && (
                  <div className="mt-2.5 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200 break-words">
                    <strong>[CẢNH BÁO]:</strong> {chunk.warnings.join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Action footer */}
      <div className="mt-2 flex flex-wrap items-center justify-end gap-3">
        <button
          type="button"
          onClick={() => onReject?.(document.id)}
          className="fluent-btn-secondary inline-flex min-h-[44px] items-center justify-center rounded-[10px] px-4 py-2 text-xs font-medium focus-visible:outline-2 focus-visible:outline-[var(--color-primary)] focus-visible:outline-offset-2 transition-colors"
        >
          Yêu cầu sửa đổi
        </button>

        <button
          type="button"
          onClick={() => onApprove?.(document.id)}
          disabled={!canPublish}
          aria-label="Phê duyệt ban hành"
          title={
            canPublish
              ? "Phê duyệt ban hành"
              : isQuarantined
              ? "Văn bản đang trong trạng thái cách ly"
              : isStaleDoc
              ? "Văn bản đã bị thay đổi hoặc hết hạn"
              : !hasAuthority
              ? "Không có thẩm quyền ban hành"
              : isAuthor
              ? "Tác giả không thể tự phê duyệt (Quy tắc 4 mắt)"
              : isEvidenceIncomplete
              ? "Chưa đủ bằng chứng thẩm định"
              : isParseFailed
              ? "Lỗi trích xuất cú pháp"
              : "Chưa đủ điều kiện ban hành"
          }
          className={`inline-flex min-h-[44px] items-center justify-center rounded-[10px] px-5 py-2 text-xs font-semibold shadow-xs transition focus-visible:outline-2 focus-visible:outline-[var(--color-primary)] focus-visible:outline-offset-2 ${
            canPublish
              ? "fluent-btn-primary cursor-pointer"
              : "cursor-not-allowed border border-[var(--border-color)] bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500"
          }`}
        >
          Phê duyệt ban hành
        </button>
      </div>
    </div>
  );
}
