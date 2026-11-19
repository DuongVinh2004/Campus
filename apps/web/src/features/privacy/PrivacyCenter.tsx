import React, { useState } from "react";
import { ShieldCheck, Clock, AlertTriangle, Shield, Check, Lock } from "lucide-react";

export interface PrivacyNoticeData {
  version: string;
  effectiveDate: string;
  purpose: string;
  hasConsented: boolean;
}

export interface PrivacyRequestStatus {
  requestId: string;
  requestType: "EXPORT_DATA" | "DELETE_DATA" | "RECTIFY_DATA";
  status: "received" | "processing" | "completed" | "rejected" | "legal_hold" | "denied";
  submittedAt: string;
}

export interface PrivacyCenterProps {
  notice: PrivacyNoticeData;
  requests?: PrivacyRequestStatus[];
  isPendingConfirmation?: boolean;
  onConsentChange?: (consented: boolean) => void;
  onRequestErasure?: () => void;
}

const requestTypeLabels: Record<PrivacyRequestStatus["requestType"], string> = {
  EXPORT_DATA: "Yêu cầu xuất dữ liệu cá nhân",
  DELETE_DATA: "Yêu cầu xóa dữ liệu cá nhân",
  RECTIFY_DATA: "Yêu cầu đính chính dữ liệu",
};

const requestStatusLabels: Record<
  PrivacyRequestStatus["status"],
  { label: string; badgeClass: string; explanation?: string }
> = {
  received: {
    label: "Đã tiếp nhận",
    badgeClass:
      "border border-[var(--border-color)] bg-[var(--surface-subtle)] text-[var(--text-secondary)]",
  },
  processing: {
    label: "Đang xử lý",
    badgeClass:
      "border border-[var(--color-primary-subtle)] bg-[var(--color-primary-subtle)] text-[var(--color-primary)]",
  },
  completed: {
    label: "Đã hoàn thành",
    badgeClass:
      "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900/50",
  },
  rejected: {
    label: "Không thể thực hiện",
    badgeClass:
      "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/50",
  },
  legal_hold: {
    label: "Tạm giữ pháp lý",
    badgeClass:
      "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950/60 dark:text-amber-200 dark:border-amber-800",
    explanation:
      "Dữ liệu đang được lưu trữ bắt buộc theo quy định lưu trữ của cơ sở đào tạo.",
  },
  denied: {
    label: "Bị từ chối theo quy định",
    badgeClass:
      "bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900/50",
    explanation:
      "Yêu cầu không thể thực hiện do không đáp ứng quy định hiện hành.",
  },
};

export function PrivacyCenter({
  notice,
  requests = [],
  isPendingConfirmation = false,
  onConsentChange,
  onRequestErasure,
}: PrivacyCenterProps) {
  const [consented, setConsented] = useState<boolean>(Boolean(notice.hasConsented));
  const [announcement, setAnnouncement] = useState<string | null>(null);
  const [isConfirmingErasure, setIsConfirmingErasure] = useState<boolean>(false);

  const handleToggle = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (isPendingConfirmation) return;
    const nextConsent = e.target.checked;
    setConsented(nextConsent);
    setAnnouncement(`Đã cập nhật lựa chọn đồng ý: ${nextConsent ? "Đã bật" : "Đã tắt"}`);
    onConsentChange?.(nextConsent);
  };

  return (
    <div
      role="region"
      aria-label="Trung tâm quyền riêng tư & bảo vệ dữ liệu"
      className="flex max-w-3xl flex-col gap-6"
    >
      {/* Accessible Status Announcement */}
      {announcement && (
        <div role="status" aria-live="polite" className="sr-only">
          {announcement}
        </div>
      )}

      {/* Header */}
      <div>
        <div className="mb-1.5 flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-primary-subtle)] text-[var(--color-primary)]">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
            Trung tâm Quyền riêng tư & Bảo vệ Dữ liệu — HUCE
          </h2>
        </div>
        <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
          Chính sách minh bạch dữ liệu theo quy định bảo vệ dữ liệu cá nhân Nghị định 13/2023/NĐ-CP.
        </p>
      </div>

      {/* Section 1: Required Processing */}
      <div className="fluent-card p-6">
        <h3 className="mb-3 text-base font-bold text-[var(--text-primary)]">
          1. Xử lý dữ liệu bắt buộc
        </h3>
        <div className="rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4 text-xs">
          <p className="mb-1.5 font-semibold text-[var(--text-primary)]">
            Cơ sở pháp lý & Phạm vi phục vụ:
          </p>
          <p className="leading-relaxed text-[var(--text-secondary)]">
            Dữ liệu tài khoản (Mã sinh viên, họ tên, lớp, lịch học và yêu cầu hành chính) được xử lý bắt buộc để vận hành tài khoản và dịch vụ Một cửa số phục vụ hoạt động đào tạo tại Trường Đại học Xây dựng Hà Nội (HUCE).
          </p>
        </div>
      </div>

      {/* Section 2: Optional Processing & Granular Consent */}
      <div className="fluent-card p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            2. Xử lý dữ liệu tùy chọn
          </h3>
          <span className="rounded-full border border-[var(--border-color)] bg-[var(--surface-subtle)] px-3 py-1 text-xs font-semibold text-[var(--color-primary)]">
            Phiên bản {notice.version} · Có hiệu lực từ {notice.effectiveDate}
          </span>
        </div>

        <div className="mb-4 rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4 text-xs">
          <p className="mb-1.5 font-semibold text-[var(--text-primary)]">
            Mục đích nghiên cứu & Nâng cao chất lượng AI:
          </p>
          <p className="leading-relaxed text-[var(--text-secondary)]">
            {notice.purpose} Bạn có quyền tự do lựa chọn đồng ý hoặc từ chối. Việc không đồng ý hoàn toàn không làm suy giảm quyền lợi của bạn đối với dịch vụ Một cửa số.
          </p>
        </div>

        {/* Server Confirmation State */}
        {isPendingConfirmation && (
          <div
            role="status"
            className="mb-3.5 rounded-xl border border-[var(--color-primary-subtle)] bg-[var(--surface-subtle)] p-3 text-xs font-medium text-[var(--color-primary)]"
          >
            Đang chờ máy chủ xác nhận trạng thái đồng ý...
          </div>
        )}

        {/* Consent Checkbox Control (Never Preselected) */}
        <label
          className={`flex items-start gap-3.5 rounded-xl border p-4 text-xs font-semibold transition ${
            isPendingConfirmation
              ? "cursor-not-allowed opacity-60"
              : "cursor-pointer"
          } ${
            consented
              ? "border-[var(--color-primary)] bg-[var(--color-primary-subtle)] text-[var(--text-primary)]"
              : "border-[var(--border-color)] bg-[var(--surface-subtle)] text-[var(--text-primary)] hover:bg-[var(--surface-card)]"
          }`}
        >
          <input
            type="checkbox"
            checked={consented}
            disabled={isPendingConfirmation}
            onChange={handleToggle}
            className="mt-0.5 h-4 w-4 rounded border-[var(--border-color)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
          />
          <div className="flex flex-col gap-0.5">
            <span>
              Đồng ý chia sẻ dữ liệu hội thoại ẩn danh để nâng cao chất lượng AI
            </span>
            <span className="text-[11px] font-normal text-[var(--text-secondary)]">
              Dữ liệu sẽ được khử định danh toàn diện trước khi đưa vào tập huấn luyện đánh giá chất lượng.
            </span>
          </div>
        </label>
      </div>

      {/* Section 3: Consequential Action - Erasure */}
      <div className="fluent-card p-6">
        <h3 className="mb-2 text-base font-bold text-[var(--text-primary)]">
          3. Thực hiện quyền xóa dữ liệu cá nhân (Right to Erasure)
        </h3>
        <p className="mb-4 text-xs leading-relaxed text-[var(--text-secondary)]">
          Bạn có quyền yêu cầu xóa vĩnh viễn các dữ liệu hội thoại và dữ liệu tài khoản theo quy định bảo vệ dữ liệu cá nhân.
        </p>

        {!isConfirmingErasure ? (
          <button
            type="button"
            onClick={() => setIsConfirmingErasure(true)}
            className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs font-semibold text-rose-700 shadow-2xs transition hover:bg-rose-100 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300 dark:hover:bg-rose-900/60 cursor-pointer"
          >
            Yêu cầu xóa dữ liệu vĩnh viễn
          </button>
        ) : (
          <div className="rounded-xl border-1.5 border-rose-400 bg-rose-50/70 p-4 text-xs text-rose-900 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-200">
            <div className="mb-2 flex items-center gap-2 text-sm font-bold">
              <AlertTriangle className="h-4 w-4 text-rose-600" />
              <span>Xác nhận yêu cầu xóa dữ liệu có hệ quả nghiêm trọng</span>
            </div>
            <p className="mb-1.5 leading-relaxed">
              <strong>Phạm vi áp dụng:</strong> Toàn bộ dữ liệu hội thoại, lịch học và yêu cầu hành chính cá nhân trên hệ thống.
            </p>
            <p className="mb-3 leading-relaxed">
              <strong>Hệ quả pháp lý:</strong> Hành động không thể hoàn tác. Dữ liệu sẽ bị xóa hoặc ẩn danh vĩnh viễn, bạn sẽ không thể khôi phục lại lịch sử hỗ trợ.
            </p>
            <div className="flex gap-2.5">
              <button
                type="button"
                onClick={() => setIsConfirmingErasure(false)}
                className="fluent-btn-secondary text-xs"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsConfirmingErasure(false);
                  onRequestErasure?.();
                }}
                className="rounded-lg bg-rose-600 px-4 py-1.5 font-semibold text-white shadow-sm transition hover:bg-rose-700 dark:bg-rose-500 dark:hover:bg-rose-600 cursor-pointer"
              >
                Xác nhận xóa vĩnh viễn
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Section 4: Privacy Requests Status */}
      <div className="fluent-card p-6">
        <h3 className="mb-4 text-base font-bold text-[var(--text-primary)]">
          4. Trạng thái yêu cầu quyền dữ liệu của bạn
        </h3>

        {requests.length === 0 ? (
          <p className="text-xs text-[var(--text-secondary)]">
            Bạn chưa gửi yêu cầu trích xuất hoặc xóa dữ liệu nào.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {requests.map((request) => {
              const badge = requestStatusLabels[request.status] || requestStatusLabels.received;
              return (
                <div
                  key={request.requestId}
                  className="flex flex-col gap-2 rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4 text-xs"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2.5">
                    <div>
                      <div className="text-xs font-semibold text-[var(--text-primary)]">
                        {requestTypeLabels[request.requestType] || requestTypeLabels.EXPORT_DATA}
                      </div>
                      <div className="mt-1 flex items-center gap-1.5 text-[var(--text-secondary)]">
                        <Clock className="h-3 w-3" />
                        <span>
                          Mã yêu cầu: {request.requestId} • Ngày gửi: {request.submittedAt}
                        </span>
                      </div>
                    </div>

                    <span
                      className={`rounded-full border px-3 py-0.5 text-xs font-semibold ${badge.badgeClass}`}
                    >
                      {badge.label}
                    </span>
                  </div>

                  {badge.explanation && (
                    <div className="mt-1 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs leading-relaxed text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300">
                      {badge.explanation}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
