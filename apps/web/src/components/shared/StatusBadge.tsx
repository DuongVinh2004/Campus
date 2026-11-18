import React from "react";

type AnyStatus =
  | "open"
  | "pending_officer"
  | "resolved"
  | "draft"
  | "in_review"
  | "waiting_supplement"
  | "completed";

interface StatusBadgeProps {
  status: AnyStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const mapping: Record<AnyStatus, { label: string; className: string; dot: string }> = {
    open: { label: "Mới tiếp nhận", className: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300", dot: "bg-gray-500" },
    pending_officer: { label: "Chờ xử lý", className: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300", dot: "bg-amber-500" },
    resolved: { label: "Hoàn tất", className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300", dot: "bg-emerald-500" },
    draft: { label: "Bản nháp", className: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300", dot: "bg-slate-500" },
    in_review: { label: "Đang rà soát", className: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300", dot: "bg-blue-500" },
    waiting_supplement: { label: "Chờ bổ sung", className: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300", dot: "bg-amber-500" },
    completed: { label: "Hoàn tất", className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300", dot: "bg-emerald-500" },
  };

  const { label, className, dot } = mapping[status] || { label: "Không xác định", className: "bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700", dot: "bg-slate-400" };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${className}`}>
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

interface PriorityBadgeProps {
  priority: "normal" | "high";
}

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  if (priority === "high") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300 whitespace-nowrap">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-rose-500" />
        Khẩn cấp
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 whitespace-nowrap">
      Bình thường
    </span>
  );
}
