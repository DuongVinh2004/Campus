import React, { useState, useEffect } from "react";
import { AlertTriangle, Clock } from "lucide-react";

export interface ActionParameter {
  label: string;
  value: string;
}

export interface ActionPreviewData {
  actionId: string;
  actionType: string;
  title: string;
  targetEntity: string;
  parameters: ActionParameter[];
  expiresInSeconds: number;
}

export interface ActionConfirmationProps {
  isOpen: boolean;
  action: ActionPreviewData;
  onConfirm: (actionId: string) => void;
  onCancel: () => void;
}

export function ActionConfirmation({
  isOpen,
  action,
  onConfirm,
  onCancel,
}: ActionConfirmationProps) {
  const [secondsLeft, setSecondsLeft] = useState(action.expiresInSeconds);

  useEffect(() => {
    setSecondsLeft(action.expiresInSeconds);
  }, [action.expiresInSeconds]);

  useEffect(() => {
    if (!isOpen || secondsLeft <= 0) return;
    const timer = setInterval(() => {
      setSecondsLeft((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [isOpen, secondsLeft]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  const isExpired = secondsLeft <= 0;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs animate-in fade-in duration-150"
    >
      <div className="flex w-full max-w-lg flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900 sm:p-7">
        {/* Header */}
        <div>
          <h2
            id="confirm-dialog-title"
            className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100"
          >
            {action.title}
          </h2>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Đối tượng tác động:{" "}
            <strong className="text-slate-800 dark:text-slate-200">{action.targetEntity}</strong>
          </p>
        </div>

        {/* Immutable Parameters Preview */}
        <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-xs dark:border-slate-800 dark:bg-slate-850/60">
          <p className="mb-2.5 font-bold text-slate-800 dark:text-slate-200">
            Chi tiết tham số:
          </p>
          <dl className="grid grid-cols-[140px_1fr] gap-y-2">
            {action.parameters.map((param, idx) => (
              <React.Fragment key={idx}>
                <dt className="font-medium text-slate-500 dark:text-slate-400">
                  {param.label}:
                </dt>
                <dd className="m-0 font-semibold text-slate-900 dark:text-slate-100">
                  {param.value}
                </dd>
              </React.Fragment>
            ))}
          </dl>
        </div>

        {/* Expiration Countdown Warning */}
        <div
          aria-live="polite"
          className={`rounded-xl border p-3 text-xs font-medium ${
            isExpired
              ? "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-300"
              : "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200"
          }`}
        >
          {isExpired ? (
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-rose-600 dark:text-rose-400" />
              <span>Phiên xác nhận đã hết hạn. Vui lòng đóng và thao tác lại.</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-700 dark:text-amber-400" />
              <span>Thời gian xác nhận còn lại: {secondsLeft} giây</span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="mt-1 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="min-h-11 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-2xs transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 cursor-pointer"
          >
            Hủy bỏ
          </button>
          <button
            type="button"
            onClick={() => onConfirm(action.actionId)}
            disabled={isExpired}
            className={`min-h-11 rounded-lg px-5 py-2 text-sm font-semibold shadow-xs transition ${
              isExpired
                ? "cursor-not-allowed border border-slate-200 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 opacity-60"
                : "cursor-pointer bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            Xác nhận thực hiện
          </button>
        </div>
      </div>
    </div>
  );
}
