"use client";

import React, { useState } from "react";
import { AlertTriangle, X } from "lucide-react";

export type OperationalMode = "healthy" | "degraded" | "safe_mode" | "outage";

export interface OperationalMetric {
  name: string;
  value: number | string;
  unit: string;
  timeWindow: string;
  freshness: string;
  source: string;
  status: "normal" | "degraded" | "unavailable" | "stale";
}

export interface SystemOperationalStatus {
  mode: OperationalMode;
  message: string;
  affectedServices: string[];
  metrics?: OperationalMetric[];
  isDismissible?: boolean;
  impact?: string;
  safeNextAction?: string;
}

export interface CapabilityBannerProps {
  status: SystemOperationalStatus;
  onDismiss?: () => void;
}

export function CapabilityBanner({ status, onDismiss }: CapabilityBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  const hasAbnormalMetrics =
    status.metrics && status.metrics.some((m) => m.status !== "normal");

  if (dismissed || (status.mode === "healthy" && !hasAbnormalMetrics)) {
    return null;
  }

  const isCritical = status.mode === "outage" || status.mode === "safe_mode";

  const getModeLabel = (mode: OperationalMode) => {
    switch (mode) {
      case "outage":
        return "[✕] SỰ CỐ NGỪNG DỊCH VỤ";
      case "safe_mode":
        return "[S] CHẾ ĐỘ AN TOÀN";
      case "degraded":
        return "[!] SUY GIẢM";
      case "healthy":
      default:
        return "[✓] BÌNH THƯỜNG";
    }
  };

  const getMetricBadge = (mStatus: OperationalMetric["status"]) => {
    switch (mStatus) {
      case "unavailable":
        return {
          label: "[✕] Không khả dụng",
          badgeClass:
            "bg-rose-100 text-rose-900 border-rose-300 dark:bg-rose-950/60 dark:text-rose-200 dark:border-rose-800",
        };
      case "degraded":
        return {
          label: "[!] Suy giảm",
          badgeClass:
            "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950/60 dark:text-amber-200 dark:border-amber-800",
        };
      case "stale":
        return {
          label: "[~] Dữ liệu cũ",
          badgeClass:
            "bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
        };
      case "normal":
      default:
        return {
          label: "[•] Bình thường",
          badgeClass:
            "bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-200 dark:border-emerald-800",
        };
    }
  };

  const handleDismiss = () => {
    setDismissed(true);
    onDismiss?.();
  };

  return (
    <section
      role="region"
      aria-label="Cảnh báo vận hành và chỉ số KPI"
      aria-live={isCritical ? "assertive" : "polite"}
      className={`fixed right-3 top-20 z-40 w-[min(320px,calc(100vw-24px))] rounded-lg border px-2 py-1 pr-8 text-xs shadow-sm ${
        isCritical
          ? "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
          : "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200"
      }`}
    >
      <button type="button" onClick={handleDismiss} aria-label="Đóng thông báo" title="Đóng thông báo" style={{ minHeight: 24, minWidth: 24 }} className="absolute right-1 top-1 inline-flex h-6 w-6 items-center justify-center rounded hover:bg-black/5"><X aria-hidden="true" className="h-3.5 w-3.5" /></button>
      <details><summary className="cursor-pointer truncate py-1" title={status.message}>{status.message}</summary><div className="max-h-40 space-y-2 overflow-y-auto pt-2">
      {/* Details remain available on demand. */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 font-bold">
          <AlertTriangle className="h-4 w-4 shrink-0 text-current" />
          <span>Cảnh báo vận hành hệ thống {getModeLabel(status.mode)}:</span>
          <span className="font-medium">{status.message}</span>
        </div>

      </div>

      {/* Affected services list */}
      {status.affectedServices.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">Dịch vụ bị ảnh hưởng:</span>
          <div className="flex flex-wrap gap-1.5">
            {status.affectedServices.map((svc) => (
              <span
                key={svc}
                className={`rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${
                  isCritical
                    ? "border-rose-300 bg-rose-100 text-rose-950 dark:border-rose-800 dark:bg-rose-900/50 dark:text-rose-200"
                    : "border-amber-300 bg-amber-100 text-amber-950 dark:border-amber-800 dark:bg-amber-900/50 dark:text-amber-200"
                }`}
              >
                {svc}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Impact and Safe Next Action details */}
      {(status.impact || status.safeNextAction) && (
        <div className="flex flex-col gap-1 rounded-xl bg-black/5 p-3 text-xs dark:bg-white/5">
          {status.impact && (
            <div>
              <strong className="font-bold">Ảnh hưởng thực tế: </strong>
              <span>{status.impact}</span>
            </div>
          )}
          {status.safeNextAction && (
            <div>
              <strong className="font-bold">Hành động an toàn khuyến nghị: </strong>
              <span>{status.safeNextAction}</span>
            </div>
          )}
        </div>
      )}

      {/* Operational Metrics & KPI Context */}
      {status.metrics && status.metrics.length > 0 && (
        <div className="mt-1 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {status.metrics.map((metric, idx) => {
            const badge = getMetricBadge(metric.status);
            return (
              <div
                key={idx}
                className="flex flex-col gap-1.5 rounded-xl border border-slate-200 bg-white p-3.5 text-xs text-slate-800 shadow-2xs dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900 dark:text-slate-100">{metric.name}</span>
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${badge.badgeClass}`}
                  >
                    {badge.label}
                  </span>
                </div>

                <div className="text-lg font-bold text-blue-700 dark:text-blue-400">
                  <span>{metric.value}</span>{" "}
                  <span className="text-xs font-normal text-slate-500 dark:text-slate-400">
                    {metric.unit}
                  </span>
                </div>

                <div className="flex flex-col gap-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                  <div>
                    Khung thời gian: <strong className="text-slate-700 dark:text-slate-300">{metric.timeWindow}</strong>
                  </div>
                  <div>
                    Độ tươi: <strong className="text-slate-700 dark:text-slate-300">{metric.freshness}</strong>
                  </div>
                  <div>
                    Nguồn: <code className="rounded bg-slate-100 px-1 py-0.2 text-slate-800 dark:bg-slate-800 dark:text-slate-200">{metric.source}</code>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
      </div></details>
    </section>
  );
}
