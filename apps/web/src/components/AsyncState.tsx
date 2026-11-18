"use client";

import React, { type ReactNode, useEffect, useRef } from "react";
import { Inbox, WifiOff, AlertTriangle } from "lucide-react";

export type AsyncStatus = "loading" | "empty" | "zero-result" | "error" | "offline" | "stale" | "degraded" | "unauthorized" | "result-unknown" | "success";

export interface AsyncStateProps {
  status: AsyncStatus;
  loadingMessage?: string;
  emptyMessage?: string;
  errorMessage?: string;
  onRetry?: () => void;
  autoFocusRetry?: boolean;
  children?: ReactNode;
}

export function AsyncState({
  status,
  loadingMessage = "Đang tải dữ liệu...",
  emptyMessage = "Không có dữ liệu",
  errorMessage = "Đã xảy ra lỗi khi tải dữ liệu",
  onRetry,
  autoFocusRetry = true,
  children,
}: AsyncStateProps) {
  const retryBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (autoFocusRetry && (status === "error" || status === "offline" || status === "result-unknown") && onRetry) {
      retryBtnRef.current?.focus();
    }
  }, [status, autoFocusRetry, onRetry]);

  if (status === "success") {
    return <>{children}</>;
  }

  if (status === "loading") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="p-12 text-center bg-white/70 dark:bg-slate-900/70 backdrop-blur-md rounded-2xl border border-slate-200/50 dark:border-slate-800/50 shadow-sm flex flex-col items-center gap-5 transition-all"
      >
        <div className="flex flex-col gap-3 w-full max-w-xs opacity-60">
          <div className="h-7 bg-slate-200 dark:bg-slate-700 rounded-md w-full animate-pulse" />
          <div className="h-5 bg-slate-200 dark:bg-slate-700 rounded w-[85%] mx-auto animate-pulse" />
          <div className="h-5 bg-slate-200 dark:bg-slate-700 rounded w-[60%] mx-auto animate-pulse" />
        </div>
        <p className="m-0 text-sm text-blue-900 dark:text-blue-300 font-semibold">
          {loadingMessage}
        </p>
      </div>
    );
  }

  if (status === "zero-result") {
    return (
      <div role="status" aria-live="polite" className="p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700">
        <p className="m-0 text-sm text-slate-600 dark:text-slate-400 font-semibold">
          Không tìm thấy kết quả
        </p>
      </div>
    );
  }

  if (status === "stale") {
    return (
      <>
        <div role="status" aria-live="polite" className="p-4 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 rounded-lg mb-4">
          <p className="m-0 text-sm font-medium">
            Dữ liệu có thể chưa được cập nhật. {onRetry && <button onClick={onRetry} className="bg-transparent border-0 text-amber-900 dark:text-amber-200 underline cursor-pointer p-0 font-medium">Làm mới</button>}
          </p>
        </div>
        {children}
      </>
    );
  }

  if (status === "degraded") {
    return (
      <>
        <div role="status" aria-live="polite" className="p-4 bg-amber-100/70 dark:bg-amber-950/50 border border-amber-300 dark:border-amber-800 text-amber-800 dark:text-amber-300 rounded-lg mb-4">
          <p className="m-0 text-sm font-medium">
            Hệ thống đang phản hồi chậm. Một số tính năng có thể bị gián đoạn.
          </p>
        </div>
        {children}
      </>
    );
  }

  if (status === "unauthorized") {
    return (
      <div role="alert" aria-live="assertive" className="p-6 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300 rounded-2xl text-center">
        <p className="m-0 text-sm sm:text-base font-bold">Bạn không có quyền truy cập chức năng này</p>
      </div>
    );
  }

  if (status === "result-unknown") {
    return (
      <div role="alert" aria-live="assertive" className="p-6 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300 rounded-2xl text-center">
        <p className="m-0 text-sm sm:text-base font-bold">Trạng thái xử lý không rõ ràng</p>
        <p className="mt-2 mb-0 text-xs sm:text-sm text-rose-700 dark:text-rose-400">Vui lòng kiểm tra lại sau hoặc liên hệ hỗ trợ.</p>
        {onRetry && (
          <button
            ref={retryBtnRef}
            type="button"
            onClick={onRetry}
            className="mt-3 px-4 py-2 bg-white dark:bg-slate-800 border border-rose-400 dark:border-rose-700 rounded-md cursor-pointer text-rose-700 dark:text-rose-300 text-xs sm:text-sm font-semibold hover:bg-rose-50 dark:hover:bg-slate-700 transition-colors"
          >
            Kiểm tra lại
          </button>
        )}
      </div>
    );
  }

  if (status === "empty") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 flex flex-col items-center gap-2"
      >
        <div className="text-slate-400 dark:text-slate-500">
          <Inbox className="w-9 h-9" />
        </div>
        <p className="m-0 text-sm text-slate-600 dark:text-slate-400 font-semibold">
          {emptyMessage}
        </p>
      </div>
    );
  }

  if (status === "offline") {
    return (
      <div
        role="alert"
        aria-live="assertive"
        className="p-6 sm:p-7 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-center flex flex-col items-center gap-2 shadow-xs"
      >
        <div className="text-amber-600 dark:text-amber-400">
          <WifiOff className="w-8 h-8" />
        </div>
        <p className="font-bold m-0 text-base text-amber-800 dark:text-amber-300">Mất kết nối mạng</p>
        <p className="m-0 text-xs sm:text-sm text-amber-700 dark:text-amber-400">
          Vui lòng kiểm tra lại đường truyền internet của bạn.
        </p>
        {onRetry && (
          <button
            ref={retryBtnRef}
            type="button"
            onClick={onRetry}
            className="mt-2 px-5 py-2 rounded-md border border-amber-500 bg-white dark:bg-slate-800 text-amber-800 dark:text-amber-300 font-semibold text-xs sm:text-sm cursor-pointer shadow-xs hover:bg-amber-50 dark:hover:bg-slate-700 transition-colors"
          >
            Thử lại
          </button>
        )}
      </div>
    );
  }

  if (status === "error") {
    return (
      <div
        role="alert"
        aria-live="assertive"
        className="p-6 sm:p-7 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-300 text-center flex flex-col items-center gap-2 shadow-xs"
      >
        <div className="text-rose-600 dark:text-rose-400">
          <AlertTriangle className="w-8 h-8" />
        </div>
        <p className="font-bold m-0 text-sm sm:text-base">{errorMessage}</p>
        {onRetry && (
          <button
            ref={retryBtnRef}
            type="button"
            onClick={onRetry}
            className="mt-2 px-5 py-2 rounded-md border border-rose-500 bg-white dark:bg-slate-800 text-rose-700 dark:text-rose-300 font-semibold text-xs sm:text-sm cursor-pointer shadow-xs hover:bg-rose-50 dark:hover:bg-slate-700 transition-colors"
          >
            Thử lại
          </button>
        )}
      </div>
    );
  }

  return null;
}
