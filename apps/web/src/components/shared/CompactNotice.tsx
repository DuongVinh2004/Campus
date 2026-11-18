"use client";

import { useState, type ReactNode } from "react";
import { X } from "lucide-react";

export function CompactNotice({ title, children, alert = false }: {
  title: string;
  children?: ReactNode;
  alert?: boolean;
}) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  return <div role={alert ? "alert" : "status"} data-compact-notice
    className={`pointer-events-auto flex w-fit max-w-full items-start gap-1 rounded-lg border px-2 py-1 text-xs shadow-sm ${alert ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100" : "border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"}`}>
    {children ? <details className="min-w-0 flex-1">
      <summary className="cursor-pointer truncate py-1" title={title}>{title}</summary>
      <div className="max-h-32 overflow-y-auto py-2 text-xs leading-relaxed">{children}</div>
    </details> : <span className="min-w-0 truncate py-1" title={title}>{title}</span>}
    <button type="button" aria-label={`Đóng thông báo: ${title}`} title="Đóng thông báo"
      style={{ minHeight: 24, minWidth: 24 }}
      className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded hover:bg-black/5 dark:hover:bg-white/10"
      onClick={() => setDismissed(true)}><X className="h-3.5 w-3.5" aria-hidden="true" /></button>
  </div>;
}
