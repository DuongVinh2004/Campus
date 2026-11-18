import React from "react";
import { AlertOctagon } from "lucide-react";

interface ErrorStateProps {
  title?: string;
  description: string;
  onRetry?: () => void;
}

export function ErrorState({ title = "Đã xảy ra lỗi", description, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center bg-red-50/50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/50 rounded-2xl">
      <AlertOctagon className="w-10 h-10 text-red-500 dark:text-red-400 mb-3" />
      <h3 className="text-sm font-bold text-red-700 dark:text-red-400 mb-1">{title}</h3>
      <p className="text-sm text-red-600/80 dark:text-red-400/80 mb-4">{description}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 rounded-lg text-sm font-medium hover:bg-red-200 dark:hover:bg-red-900/60 transition-colors"
        >
          Thử lại
        </button>
      )}
    </div>
  );
}
