import React from "react";
import { CheckCircle2, AlertTriangle, Clock, X } from "lucide-react";

export type ActionState =
  | "pending"
  | "confirmed"
  | "executing"
  | "succeeded"
  | "failed"
  | "result_unknown"
  | "reconciled";

export interface ActionOutcomeProps {
  state: ActionState;
  idempotencyKey: string;
  actionTitle: string;
  actionDetails?: string;
  correlationId?: string;
  errorMessage?: string;
  onRetry?: () => void;
  onReconcile?: (idempotencyKey: string) => Promise<void> | void;
  onDismiss?: () => void;
}

export function ActionOutcome({
  state,
  idempotencyKey,
  actionTitle,
  actionDetails,
  correlationId,
  errorMessage,
  onRetry,
  onReconcile,
  onDismiss,
}: ActionOutcomeProps) {
  const isUnresolved = state === "executing" || state === "result_unknown";

  if (state === "result_unknown") {
    return (
      <div
        role="alert"
        className="p-5 sm:p-6 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 text-amber-950 dark:text-amber-200 flex flex-col gap-3.5 shadow-sm"
      >
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-amber-100 dark:bg-amber-900/60 flex items-center justify-center shrink-0">
            <AlertTriangle className="w-5 h-5 text-amber-700 dark:text-amber-300" />
          </div>
          <h3 className="m-0 text-base font-bold text-amber-950 dark:text-amber-200">
            Kết quả chưa xác định: {actionTitle}
          </h3>
        </div>

        <p className="m-0 text-sm leading-relaxed text-amber-900 dark:text-amber-200">
          Yêu cầu đã được gửi tới máy chủ nhưng chưa nhận được phản hồi xác nhận chắc chắn do gián đoạn kết nối.
          Hệ thống đang bảo vệ giao dịch, vui lòng không gửi lại để tránh thao tác trùng lặp.
        </p>

        <div className="text-xs text-amber-900 dark:text-amber-200 flex flex-wrap gap-4 bg-amber-100/60 dark:bg-amber-900/40 p-3 rounded-lg font-mono border border-amber-200/60 dark:border-amber-800/60">
          <div>Mã giao dịch (Idempotency): <code className="bg-amber-200/80 dark:bg-amber-800/80 px-1.5 py-0.5 rounded font-bold">{idempotencyKey}</code></div>
          {correlationId && (
            <div>Mã tham chiếu (Correlation ID): <code className="bg-amber-200/80 dark:bg-amber-800/80 px-1.5 py-0.5 rounded font-bold">{correlationId}</code></div>
          )}
        </div>

        <div className="flex items-center gap-3 mt-1 pt-1">
          {onReconcile && (
            <button
              type="button"
              onClick={() => onReconcile(idempotencyKey)}
              className="min-h-11 inline-flex items-center justify-center px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm transition-colors shadow-xs"
            >
              Kiểm tra đối soát trạng thái
            </button>
          )}

          {onRetry && (
            <button
              type="button"
              disabled={isUnresolved}
              title="Thao tác bị khóa trong khi đang đối soát để bảo vệ giao dịch duy nhất"
              onClick={onRetry}
              className="min-h-11 inline-flex items-center justify-center px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 border border-slate-200 dark:border-slate-700 font-semibold text-sm cursor-not-allowed opacity-60"
            >
              Gửi lại yêu cầu
            </button>
          )}
        </div>
      </div>
    );
  }

  if (state === "succeeded" || state === "reconciled") {
    return (
      <div
        role="status"
        className="p-4 sm:p-5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/80 text-emerald-950 dark:text-emerald-100 flex justify-between items-center gap-3 shadow-xs"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/60 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-5 h-5 text-emerald-700 dark:text-emerald-300" />
          </div>
          <div>
            <div className="font-bold text-sm sm:text-base text-emerald-950 dark:text-emerald-100">
              {state === "reconciled" ? "Đã đối soát thành công" : "Thực hiện thành công"}: {actionTitle}
            </div>
            {actionDetails && (
              <div className="text-xs sm:text-sm mt-0.5 text-emerald-800 dark:text-emerald-300">
                {actionDetails}
              </div>
            )}
          </div>
        </div>

        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="min-h-9 min-w-9 flex items-center justify-center bg-transparent border-0 cursor-pointer text-emerald-800 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 p-1.5 rounded-lg transition-colors"
            aria-label="Đóng"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    );
  }

  if (state === "failed") {
    return (
      <div
        role="alert"
        className="p-4 sm:p-5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-950 dark:text-rose-100 flex flex-col gap-2.5 shadow-xs"
      >
        <div className="flex items-center gap-2.5 font-bold text-sm sm:text-base text-rose-950 dark:text-rose-100">
          <div className="w-8 h-8 rounded-lg bg-rose-100 dark:bg-rose-900/60 flex items-center justify-center shrink-0">
            <AlertTriangle className="w-5 h-5 text-rose-700 dark:text-rose-300" />
          </div>
          <span>Thao tác thất bại: {actionTitle}</span>
        </div>
        {errorMessage && (
          <p className="m-0 text-xs sm:text-sm text-rose-800 dark:text-rose-300 pl-10.5">
            {errorMessage}
          </p>
        )}
        {onRetry && (
          <div className="mt-1 pl-10.5">
            <button
              type="button"
              onClick={onRetry}
              className="min-h-10 inline-flex items-center justify-center px-4 py-2 rounded-lg bg-rose-700 hover:bg-rose-800 text-white font-semibold text-xs cursor-pointer transition-colors shadow-xs"
            >
              Thử lại
            </button>
          </div>
        )}
      </div>
    );
  }

  // Executing or Pending
  return (
    <div
      role="status"
      className="p-4 sm:p-5 rounded-xl bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 text-blue-950 dark:text-blue-100 flex items-center gap-3 shadow-xs"
    >
      <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-900/60 flex items-center justify-center shrink-0">
        <Clock className="w-5 h-5 text-blue-700 dark:text-blue-300 animate-spin" />
      </div>
      <div className="text-sm font-semibold">
        Đang xử lý giao dịch: {actionTitle}...
      </div>
    </div>
  );
}
