"use client";

import React, { useRef, useState } from "react";
import Link from "next/link";
import {
  ShieldAlert,
  Send,
  Lock,
  CheckCircle2,
  X,
  Sparkles,
} from "lucide-react";
import { useStore } from "@/lib/store";

interface Submit1ModalProps {
  onSuccess: (ticketId: string) => void;
  onCancel: () => void;
}

export function Submit1Modal({ onSuccess, onCancel }: Submit1ModalProps) {
  const {
    currentUser,
    createTicket,
    gate1FormData,
    setGate1FormData,
    lastUpdatedField,
    tickets,
  } = useStore();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const reasonInputRef = useRef<HTMLInputElement>(null);

  if (!currentUser) return null;

  const handleSubmit = async () => {
    const reason = gate1FormData.reason.trim();
    if (!reason) {
      setValidationError("Vui lòng nhập mục đích xin giấy trước khi gửi hồ sơ.");
      requestAnimationFrame(() => reasonInputRef.current?.focus());
      return;
    }

    setValidationError(null);
    setIsSubmitting(true);

    try {
      const created = await createTicket({
        title: "Cấp Giấy xác nhận sinh viên (BM-03)",
        certificateType: "Giấy xác nhận sinh viên chính quy (BM-03)",
        destinationOrg:
          gate1FormData.destinationOrg ||
          reason ||
          "Ngân hàng Chính sách Xã hội Chi nhánh Q. Thủ Đức",
        purpose: reason,
        receiveMethod: gate1FormData.receiveMethod,
        priority: "normal",
        priorityReason: "Hồ sơ đã xác nhận thông tin, không ghi nhận vi phạm kỷ luật.",
      });

      setIsSubmitting(false);
      onSuccess(created.id);
    } catch (err) {
      console.error(err);
      setValidationError("Không thể gửi hồ sơ lúc này. Vui lòng kiểm tra lại và thử lại.");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-white dark:bg-slate-900 shadow-sm border border-slate-200 dark:border-slate-800 rounded-3xl overflow-hidden text-xs">
      {/* Header */}
      <div className="shrink-0 p-4 bg-white/40 dark:bg-slate-900/40 backdrop-blur-md border-b border-slate-200/60 dark:border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-pulse" />
          <h3 className="font-bold text-slate-900 dark:text-white text-sm">
            Biểu mẫu yêu cầu
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 font-semibold border border-blue-200 dark:border-blue-700/50">
            Bước 1/2: Kiểm tra thông tin
          </span>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Đóng biểu mẫu yêu cầu"
            className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain p-4 space-y-4">
        {/* Academic Verification Notice */}
        <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-900 dark:text-amber-200 space-y-1 backdrop-blur-sm">
            <div className="flex items-center gap-1.5 font-bold text-xs text-amber-700 dark:text-amber-300">
            <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>Thông tin cần được kiểm tra:</span>
          </div>
          <p className="text-[11px] leading-relaxed text-amber-800/90 dark:text-amber-300/80">
              Dữ liệu bạn kê khai sẽ được cán bộ đối chiếu với thông tin đào tạo trước khi yêu cầu được xử lý.
          </p>
        </div>

        {/* Form Preview */}
        <div className="p-4 rounded-2xl bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm border border-slate-200/60 dark:border-slate-800/80 shadow-none space-y-3.5">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
            <span className="font-bold text-slate-900 dark:text-white text-xs">
              Thông tin giấy xác nhận sinh viên
            </span>
            <span className="text-[10px] font-mono text-slate-500">Mã biểu mẫu: XN-VV-2025</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-slate-700 dark:text-slate-300">
            <div>
              <span className="text-[11px] font-medium text-slate-600 dark:text-slate-400 block">
                Họ và tên SV:
              </span>
              <span className="font-semibold text-slate-900 dark:text-white text-xs">
                {currentUser.name}
              </span>
            </div>

            <div>
              <span className="text-[11px] font-medium text-slate-600 dark:text-slate-400 block">
                Mã số sinh viên (MSSV):
              </span>
              <span className="font-mono font-semibold text-slate-900 dark:text-white text-xs">
                {currentUser.mssv || currentUser.id}
              </span>
            </div>

            <div>
              <span className="text-[11px] font-medium text-slate-600 dark:text-slate-400 block">
                Khóa học / Lớp sinh hoạt:
              </span>
              <span className="text-xs">{currentUser.classYear || "Khóa 18 (2021 - 2025)"}</span>
            </div>

            <div>
              <span className="text-[11px] font-medium text-slate-600 dark:text-slate-400 block">
                Khoa quản lý chuyên môn:
              </span>
              <span className="text-xs">{currentUser.major || "Khoa Công nghệ Phần mềm"}</span>
            </div>
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label htmlFor="gate1-reason" className="text-[11px] font-medium text-slate-600 dark:text-slate-400 block">
                Mục đích và nơi gửi:
              </label>
              {lastUpdatedField === "reason" && (
                <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1 animate-pulse">
                  <Sparkles className="w-3 h-3" />
                  Vừa được cập nhật
                </span>
              )}
            </div>
            <input
              ref={reasonInputRef}
              id="gate1-reason"
              name="purpose"
              type="text"
              value={gate1FormData.reason}
              onChange={(e) => {
                const nextReason = e.target.value;
                setGate1FormData((prev) => ({ ...prev, reason: nextReason }));
                if (validationError && nextReason.trim()) setValidationError(null);
              }}
              required
              aria-invalid={validationError ? "true" : "false"}
              aria-describedby={validationError ? "gate1-reason-error" : undefined}
              placeholder="Nhập mục đích xin giấy hoặc nhờ trợ lý chỉnh sửa..."
              className={`w-full p-2.5 rounded-xl text-xs border transition-all duration-300 text-slate-900 dark:text-white backdrop-blur-sm ${
                lastUpdatedField === "reason"
                  ? "bg-emerald-50/80 dark:bg-emerald-950/40 border-emerald-500 ring-2 ring-emerald-500/30"
                  : "bg-white/50 dark:bg-slate-800/60 border-slate-200/70 dark:border-slate-700/60 focus:outline-none focus:ring-2 focus:ring-blue-500"
              }`}
            />
            {validationError && (
              <p id="gate1-reason-error" role="alert" aria-live="polite" className="text-[11px] font-medium text-rose-600 dark:text-rose-400">
                {validationError}
              </p>
            )}
          </div>

          {/* Receive Method */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-medium text-slate-600 dark:text-slate-400 block">
                Phương thức nhận văn bản:
              </label>
              {lastUpdatedField === "receiveMethod" && (
                <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1 animate-pulse">
                  <Sparkles className="w-3 h-3" />
                  Vừa được cập nhật
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <label
                className={`flex items-start gap-2 p-2.5 rounded-xl border cursor-pointer transition-all backdrop-blur-xs ${
                  gate1FormData.receiveMethod === "digital_pdf"
                    ? lastUpdatedField === "receiveMethod"
                      ? "bg-emerald-50/80 dark:bg-emerald-950/40 border-emerald-500 ring-2 ring-emerald-500/30 text-emerald-950 dark:text-emerald-200"
                      : "bg-blue-50/70 dark:bg-blue-950/40 border-blue-500 text-blue-900 dark:text-blue-200"
                    : "bg-white/50 dark:bg-slate-800/40 border-slate-200/60 dark:border-slate-700/50 text-slate-700 dark:text-slate-300"
                }`}
              >
                <input
                  type="radio"
                  name="receiveMethod"
                  checked={gate1FormData.receiveMethod === "digital_pdf"}
                  onChange={() =>
                    setGate1FormData((prev) => ({ ...prev, receiveMethod: "digital_pdf" }))
                  }
                  className="mt-0.5 text-blue-600 focus:ring-blue-500"
                />
                <div>
                  <div className="font-semibold text-xs">Bản điện tử (PDF)</div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400">
                    Ký số, gửi qua Cổng dịch vụ sinh viên
                  </div>
                </div>
              </label>

              <label
                className={`flex items-start gap-2 p-2.5 rounded-xl border cursor-pointer transition-all backdrop-blur-xs ${
                  gate1FormData.receiveMethod === "paper_stamped"
                    ? lastUpdatedField === "receiveMethod"
                      ? "bg-emerald-50/80 dark:bg-emerald-950/40 border-emerald-500 ring-2 ring-emerald-500/30 text-emerald-950 dark:text-emerald-200"
                      : "bg-blue-50/70 dark:bg-blue-950/40 border-blue-500 text-blue-900 dark:text-blue-200"
                    : "bg-white/50 dark:bg-slate-800/40 border-slate-200/60 dark:border-slate-700/50 text-slate-700 dark:text-slate-300"
                }`}
              >
                <input
                  type="radio"
                  name="receiveMethod"
                  checked={gate1FormData.receiveMethod === "paper_stamped"}
                  onChange={() =>
                    setGate1FormData((prev) => ({ ...prev, receiveMethod: "paper_stamped" }))
                  }
                  className="mt-0.5 text-blue-600 focus:ring-blue-500"
                />
                <div>
                  <div className="font-semibold text-xs">Bản giấy</div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400">
                    Nhận tại Phòng Đào tạo (Bàn 3)
                  </div>
                </div>
              </label>
            </div>
          </div>

          {/* Action button */}
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={isSubmitting}
            className="w-full py-3 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold flex items-center justify-center gap-2 shadow-lg shadow-blue-500/25 transition-all text-xs"
          >
            {isSubmitting ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <Send className="w-3.5 h-3.5" />
                <span>Gửi yêu cầu</span>
              </>
            )}
          </button>

          {/* Business rule disclaimer */}
          <div className="flex items-start gap-2 p-2.5 rounded-xl bg-white/40 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800 text-[10px] text-slate-500 dark:text-slate-400">
            <Lock className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
            <span>
              <strong>Lưu ý:</strong> Chỉ sau khi bấm nút trên, yêu cầu mới được chuyển đến cán bộ xử lý. Văn bản chưa được phát hành ở bước này.
            </span>
          </div>
        </div>

        {/* Existing Tracked Tickets Mini List */}
        <div className="space-y-2 pt-2 border-t border-slate-200/60 dark:border-slate-800">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-slate-900 dark:text-white">
              Yêu cầu đang theo dõi ({tickets.filter((t) => t.studentId === currentUser.id).length} yêu cầu)
            </span>
            <Link
              href="/my-requests"
              className="inline-flex min-h-[44px] items-center px-2 rounded-lg text-[11px] text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/30 hover:underline"
            >
              Xem tất cả yêu cầu
            </Link>
          </div>

          <div className="space-y-2">
            {tickets
              .filter((t) => t.studentId === currentUser.id)
              .map((t) => (
                <div
                  key={t.id}
                  className="p-3 rounded-xl bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm border border-slate-200/60 dark:border-slate-800 space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                      #{t.code}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        t.status === "open"
                          ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                          : t.status === "pending_officer"
                          ? "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
                          : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20"
                      }`}
                    >
                      {t.status === "open"
                        ? "Mới tiếp nhận"
                        : t.status === "pending_officer"
                          ? "Đang chờ xử lý"
                          : "Đã hoàn tất"}
                    </span>
                  </div>

                  <div className="font-medium text-slate-900 dark:text-white text-[11px] min-h-[2rem] line-clamp-2">
                    {t.title}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[10px] text-slate-500 dark:text-slate-400 pt-1">
                    <span>Cán bộ phụ trách: {t.assignedOfficerName || "Phòng Đào tạo"}</span>
                    <span className="font-mono text-amber-600 dark:text-amber-400">
                      Thời gian còn lại: {t.slaRemaining || t.slaDeadline}
                    </span>
                  </div>
                </div>
              ))}
          </div>

          {/* Tuition Status Banner */}
          <div className="p-2.5 rounded-xl bg-white/50 dark:bg-slate-800/50 backdrop-blur-sm border border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>Học phí Học kỳ II: Đã quyết toán (Không nợ phí)</span>
            </div>
            <span className="font-mono font-bold text-slate-800 dark:text-slate-200">0 VNĐ nợ</span>
          </div>
        </div>
      </div>
    </div>
  );
}
