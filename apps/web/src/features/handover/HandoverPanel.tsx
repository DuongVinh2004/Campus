import React, { useState, useEffect } from "react";
import { ShieldCheck, CheckCircle2, Clock, X, AlertTriangle } from "lucide-react";

export interface HandoverReceipt {
  receiptId: string;
  department: string;
  reason: string;
  assignedQueue: string;
  estimatedResponseHours: number;
  status: "queued" | "assigned" | "in_review";
}

export interface HandoverPanelProps {
  receipt: HandoverReceipt;
  isAvailable?: boolean;
}

export function HandoverPanel({
  receipt,
  isAvailable = true,
}: HandoverPanelProps) {
  const [showEmergencyModal, setShowEmergencyModal] = useState(false);

  useEffect(() => {
    if (!showEmergencyModal) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setShowEmergencyModal(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showEmergencyModal]);

  return (
    <div
      role="region"
      aria-label="Thông tin chuyển tiếp chuyên viên"
      className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-7"
    >
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3.5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-base font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-lg">
              Chuyển tiếp chuyên viên hỗ trợ (Human-in-the-Loop)
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Trường hợp cần can thiệp xử lý ngoài phạm vi của AI trợ lý ảo
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowEmergencyModal(true)}
          className="inline-flex min-h-[42px] items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs font-semibold text-rose-800 shadow-2xs transition hover:bg-rose-100 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300 dark:hover:bg-rose-900/60"
        >
          <AlertTriangle className="h-4 w-4 text-rose-600 dark:text-rose-400" aria-label="Khẩn cấp" />
          <span>Đường dây nóng khẩn cấp</span>
        </button>
      </div>

      {/* Availability Notice */}
      {!isAvailable ? (
        <div
          role="alert"
          className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-relaxed text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200"
        >
          <p className="mb-1 font-bold">
            Hiện ngoài giờ tiếp nhận trực tuyến (Giờ làm việc: 08:00 - 17:00 các ngày trong tuần).
          </p>
          <p>
            Yêu cầu của bạn đã được ghi nhận vào hàng đợi và sẽ được xử lý vào phiên làm việc tiếp theo.
          </p>
        </div>
      ) : (
        <div className="flex items-center gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50/70 p-3.5 text-xs font-medium text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <span>
            {receipt.status === "queued" && "Yêu cầu của bạn đã được tiếp nhận vào hàng chờ xử lý của đơn vị."}
            {receipt.status === "assigned" && "Yêu cầu đã được phân công cán bộ phụ trách xem xét."}
            {receipt.status === "in_review" && "Yêu cầu đang trong quá trình xem xét xử lý."}
          </span>
        </div>
      )}

      {/* Handover Details */}
      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-xs dark:border-slate-800 dark:bg-slate-850/60 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <div>
            <span className="text-slate-600 dark:text-slate-400">Mã tiếp nhận: </span>
            <strong className="text-slate-900 dark:text-slate-100">Mã biên nhận: {receipt.receiptId}</strong>
          </div>
          <div className="inline-flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-blue-700 dark:text-blue-400" />
            <span className="text-slate-600 dark:text-slate-400">Thời gian ước tính: </span>
            <strong className="text-blue-700 dark:text-blue-400">Thời gian phản hồi dự kiến: {receipt.estimatedResponseHours} giờ</strong>
          </div>
        </div>
        <div>
          <span className="text-slate-600 dark:text-slate-400">Đơn vị xử lý: </span>
          <strong className="text-slate-900 dark:text-slate-100">{receipt.department}</strong>
        </div>
        <div>
          <span className="text-slate-600 dark:text-slate-400">Lý do chuyển tiếp: </span>
          <span className="text-slate-800 dark:text-slate-200">{receipt.reason}</span>
        </div>
      </div>

      {/* Emergency Modal */}
      {showEmergencyModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="emergency-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div className="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900 sm:p-7">
            <div className="mb-4 flex items-center justify-between">
              <h3
                id="emergency-title"
                className="text-base font-bold text-rose-800 dark:text-rose-300"
              >
                Hotline Y tế & Tâm lý HUCE
              </h3>
              <button
                type="button"
                onClick={() => setShowEmergencyModal(false)}
                className="rounded-lg p-1 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                aria-label="Đóng dialog"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="my-4 space-y-3 rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-xs dark:border-slate-800 dark:bg-slate-850/60">
              <p className="font-semibold text-slate-900 dark:text-slate-100">
                Đầu mối hỗ trợ khẩn cấp chính thức Trường Đại học Xây dựng Hà Nội:
              </p>
              <div className="space-y-1.5 text-slate-700 dark:text-slate-300">
                <p>• <strong>Phòng Y tế (Tầng 1 Nhà H1):</strong> (024) 3869 1300</p>
                <p>• <strong>Ban Quản lý KTX & An ninh trật tự:</strong> (024) 3869 1441</p>
                <p>• <strong>Tư vấn tâm lý & Công tác sinh viên (P.102-H1):</strong> (024) 3869 1684</p>
                <p>• <strong>Tổng đài Cấp cứu Y tế:</strong> 115 • Cứu nạn: 114</p>
              </div>
            </div>

            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setShowEmergencyModal(false)}
                className="min-h-[40px] rounded-xl bg-blue-600 px-5 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
              >
                Đã hiểu
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
