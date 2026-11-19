import React from "react";
import { Loader2 } from "lucide-react";

interface LoadingStateProps {
  title?: string;
  description?: string;
}

export function LoadingState({ title = "Đang tải dữ liệu...", description }: LoadingStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 space-y-4 text-center animate-in fade-in">
      <Loader2 className="w-8 h-8 text-[var(--color-primary)] animate-spin" />
      <div>
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
        {description && (
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{description}</p>
        )}
      </div>
    </div>
  );
}
