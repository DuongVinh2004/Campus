"use client";

import React, { useCallback, useEffect, useState } from "react";
import { usePolling } from "@/lib/use-polling";
import {
  AlertTriangle,
  Building2,
  CalendarCheck,
  CalendarDays,
  Clock,
  FileText,
  Info,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import {
  adminApi,
  AdminOverview,
  ApiClientError,
  problemMessage,
  TICKET_STATUS_LABEL,
  TicketStatus,
} from "@/lib/campus-ops-api";

const VN_TIMEZONE = "Asia/Ho_Chi_Minh";

function formatAuditTime(isoStr: string): string {
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: VN_TIMEZONE,
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).formatToParts(d);

    const day = parts.find((p) => p.type === "day")?.value ?? "";
    const month = parts.find((p) => p.type === "month")?.value ?? "";
    const hour = parts.find((p) => p.type === "hour")?.value ?? "";
    const minute = parts.find((p) => p.type === "minute")?.value ?? "";

    return `${day}/${month} ${hour}:${minute}`;
  } catch {
    return isoStr;
  }
}

function formatVnTime(date: Date): string {
  try {
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: VN_TIMEZONE,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).formatToParts(date);

    const hour = parts.find((p) => p.type === "hour")?.value ?? "";
    const minute = parts.find((p) => p.type === "minute")?.value ?? "";
    const second = parts.find((p) => p.type === "second")?.value ?? "";

    return `${hour}:${minute}:${second}`;
  } catch {
    return date.toLocaleTimeString();
  }
}

function getActionLabel(action: string): string {
  switch (action) {
    case "room.book":
      return "Đặt phòng";
    case "room.cancel":
      return "Hủy đặt phòng";
    case "ticket.submit":
      return "Gửi hồ sơ";
    case "ticket.claim":
      return "Nhận xử lý hồ sơ";
    case "ticket.staff_reply":
      return "Cán bộ phản hồi";
    case "ticket.student_reply":
      return "Sinh viên phản hồi";
    case "ticket.cancel":
      return "Hủy hồ sơ";
    case "ticket.note":
      return "Ghi chú nội bộ";
    default:
      if (
        action === "schedule.create" ||
        action === "schedule.update" ||
        action === "schedule.delete" ||
        action.startsWith("schedule.")
      ) {
        return "Lịch cá nhân";
      }
      return action;
  }
}

export function AdminOverviewPanel() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    try {
      const res = await adminApi.overview();
      setData(res);
      setLastUpdated(new Date());
    } catch (err: unknown) {
      if (
        (err instanceof ApiClientError && (err.status === 403 || err.problem?.status === 403)) ||
        (typeof err === "object" && err !== null && (err as { status?: number }).status === 403)
      ) {
        setIsForbidden(true);
      } else {
        setError(problemMessage(err, "Không thể tải dữ liệu tổng quan."));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  usePolling(fetchData, 60000, [fetchData]);

  if (isForbidden) {
    return (
      <div data-testid="admin-overview" className="campus-page min-w-0 space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Quản trị vận hành">
            <h1 className="text-2xl font-semibold">Tổng quan vận hành</h1>
            <p>Khu vực quản trị chỉ dành cho tài khoản có thẩm quyền.</p>
          </div>
        </header>
        <div
          role="alert"
          className="campus-panel flex flex-col items-center justify-center p-8 text-center sm:p-12"
        >
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-primary-light)] text-[var(--color-primary)]">
            <ShieldAlert className="h-7 w-7" aria-hidden="true" />
          </div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Truy cập bị từ chối</h2>
          <p className="mt-2 max-w-md text-sm text-[var(--text-secondary)]">
            Chỉ quản trị viên mới xem được trang này.
          </p>
        </div>
      </div>
    );
  }

  if (loading && !data) {
    return (
      <div data-testid="admin-overview" className="campus-page min-w-0 space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Quản trị vận hành">
            <h1 className="text-2xl font-semibold">Tổng quan vận hành</h1>
            <p>Theo dõi trạng thái dịch vụ, hồ sơ sinh viên và nhật ký hoạt động hệ thống.</p>
          </div>
        </header>
        <div
          role="status"
          className="campus-panel flex flex-col items-center justify-center p-12 text-center text-[var(--text-secondary)]"
        >
          <RefreshCw className="h-8 w-8 animate-spin text-[var(--color-primary)]" aria-hidden="true" />
          <p className="mt-4 text-sm font-medium">Đang tải…</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div data-testid="admin-overview" className="campus-page min-w-0 space-y-6">
        <header className="campus-page-heading">
          <div data-eyebrow="Quản trị vận hành">
            <h1 className="text-2xl font-semibold">Tổng quan vận hành</h1>
            <p>Theo dõi trạng thái dịch vụ, hồ sơ sinh viên và nhật ký hoạt động hệ thống.</p>
          </div>
        </header>
        <div
          role="alert"
          className="campus-panel flex flex-col items-center justify-center p-8 text-center sm:p-12"
        >
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-primary-light)] text-[var(--color-primary)]">
            <AlertTriangle className="h-7 w-7" aria-hidden="true" />
          </div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">Lỗi tải dữ liệu</h2>
          <p className="mt-2 max-w-md text-sm text-[var(--text-secondary)]">{error}</p>
          <button
            type="button"
            onClick={fetchData}
            className="mt-6 inline-flex min-h-[44px] items-center justify-center rounded-lg bg-[var(--color-primary)] px-5 py-2.5 text-sm font-medium text-[var(--color-on-primary)] transition-colors hover:bg-[var(--color-primary-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
          >
            Thử lại
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const ticketStatuses = Object.keys(TICKET_STATUS_LABEL) as TicketStatus[];
  const maintenanceRooms = data.rooms.by_status?.MAINTENANCE ?? 0;

  return (
    <div data-testid="admin-overview" className="campus-page min-w-0 space-y-6">
      <header className="campus-page-heading">
        <div data-eyebrow="Quản trị vận hành">
          <h1 className="text-2xl font-semibold">Tổng quan vận hành</h1>
          <p>Theo dõi trạng thái dịch vụ, hồ sơ sinh viên và nhật ký hoạt động hệ thống.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-[var(--text-secondary)]">
              Cập nhật lúc {formatVnTime(lastUpdated)}
            </span>
          )}
          <button
            type="button"
            data-testid="admin-refresh"
            onClick={fetchData}
            disabled={loading}
            className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 shrink-0 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            Làm mới
          </button>
        </div>
      </header>

      {error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-4 rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4 text-sm text-[var(--text-primary)]"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={fetchData}
            className="inline-flex min-h-[44px] items-center font-medium text-[var(--color-primary)] hover:underline focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
          >
            Thử lại
          </button>
        </div>
      )}

      {data.data_sources?.note && (
        <aside
          aria-label="Ghi chú nguồn dữ liệu"
          className="flex items-start gap-3 rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4 text-xs text-[var(--text-secondary)]"
        >
          <Info className="h-4 w-4 shrink-0 text-[var(--color-primary)] mt-0.5" aria-hidden="true" />
          <span className="leading-relaxed">{data.data_sources.note}</span>
        </aside>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div data-testid="admin-stat-tickets" className="campus-panel">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-[var(--text-secondary)]">Hồ sơ hỗ trợ</span>
            <Clock className="h-5 w-5 text-[var(--color-primary)]" aria-hidden="true" />
          </div>
          <p className="mt-2 text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            {data.tickets.total}
          </p>
          {data.tickets.overdue > 0 ? (
            <div className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-[var(--color-primary)]">
              <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{data.tickets.overdue} hồ sơ quá hạn</span>
            </div>
          ) : (
            <p className="mt-2 text-xs text-[var(--text-secondary)]">Không có hồ sơ quá hạn</p>
          )}
        </div>

        <div data-testid="admin-stat-bookings" className="campus-panel">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-[var(--text-secondary)]">Lượt đặt phòng</span>
            <CalendarCheck className="h-5 w-5 text-[var(--color-primary)]" aria-hidden="true" />
          </div>
          <p className="mt-2 text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            {data.bookings.upcoming}
          </p>
          <div className="mt-2 flex flex-wrap gap-x-2 text-xs text-[var(--text-secondary)]">
            {Object.entries(data.bookings.by_status).length > 0 ? (
              Object.entries(data.bookings.by_status).map(([st, cnt]) => (
                <span key={st}>
                  {st === "CONFIRMED" ? "Đã xác nhận" : st === "CANCELLED" ? "Đã hủy" : st}: {cnt}
                </span>
              ))
            ) : (
              <span>Sắp tới: {data.bookings.upcoming}</span>
            )}
          </div>
        </div>

        <div data-testid="admin-stat-rooms" className="campus-panel">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-[var(--text-secondary)]">Phòng học</span>
            <Building2 className="h-5 w-5 text-[var(--color-primary)]" aria-hidden="true" />
          </div>
          <p className="mt-2 text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            {data.rooms.total}
          </p>
          <p className="mt-2 text-xs text-[var(--text-secondary)]">
            {maintenanceRooms > 0 ? `Đang bảo trì: ${maintenanceRooms}` : "Tất cả phòng đang hoạt động"}
          </p>
        </div>

        <div className="campus-panel">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-[var(--text-secondary)]">Mục lịch học</span>
            <CalendarDays className="h-5 w-5 text-[var(--color-primary)]" aria-hidden="true" />
          </div>
          <p className="mt-2 text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            {data.schedule_entries}
          </p>
          <p className="mt-2 text-xs text-[var(--text-secondary)]">Lịch giảng dạy & thời khóa biểu</p>
        </div>
      </div>

      <section className="campus-panel">
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
          Phân bố hồ sơ theo trạng thái
        </h2>
        <div className="space-y-4">
          {ticketStatuses.map((st) => {
            const label = TICKET_STATUS_LABEL[st];
            const count = data.tickets.by_status[st] ?? 0;
            const pct = data.tickets.total > 0 ? Math.round((count / data.tickets.total) * 100) : 0;
            return (
              <div key={st} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs sm:text-sm">
                  <span className="font-medium text-[var(--text-primary)]">{label}</span>
                  <span className="text-[var(--text-secondary)]">{count} ({pct}%)</span>
                </div>
                <div
                  role="img"
                  aria-label={`${label}: ${count} (${pct}%)`}
                  className="h-3 w-full overflow-hidden rounded-full bg-[var(--surface-subtle)]"
                >
                  <div
                    className="h-full rounded-full bg-[var(--color-primary)] transition-all duration-300"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="campus-panel">
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
          Nhật ký thao tác gần đây
        </h2>
        <div className="overflow-x-auto" data-testid="admin-audit-table">
          {data.recent_audit.length === 0 ? (
            <div className="campus-empty-state my-2">
              <FileText className="h-8 w-8 text-[var(--color-primary)]" aria-hidden="true" />
              <p className="text-sm font-medium text-[var(--text-primary)]">Chưa có thao tác nào gần đây</p>
              <p className="text-xs text-[var(--text-secondary)]">
                Nhật ký sẽ tự động ghi lại khi phát sinh hoạt động trên hệ thống.
              </p>
            </div>
          ) : (
            <table className="w-full min-w-[540px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
                  <th className="px-3 py-2.5 font-semibold">Thời gian</th>
                  <th className="px-3 py-2.5 font-semibold">Người thực hiện</th>
                  <th className="px-3 py-2.5 font-semibold">Hành động</th>
                  <th className="px-3 py-2.5 font-semibold">Tài nguyên</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]">
                {data.recent_audit.map((item, idx) => {
                  const actorShort = item.actor.length > 28 ? `${item.actor.slice(0, 28)}…` : item.actor;
                  const resourceShort =
                    item.resource.length > 24 ? `${item.resource.slice(0, 24)}…` : item.resource;
                  return (
                    <tr key={`${item.at}-${idx}`} className="transition-colors hover:bg-[var(--surface-subtle)]">
                      <td className="whitespace-nowrap px-3 py-2.5 text-xs text-[var(--text-secondary)]">
                        {formatAuditTime(item.at)}
                      </td>
                      <td
                        className="px-3 py-2.5 font-mono text-xs text-[var(--text-primary)]"
                        title={item.actor}
                      >
                        {actorShort}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 font-medium text-[var(--text-primary)]">
                        {getActionLabel(item.action)}
                      </td>
                      <td
                        className="break-all px-3 py-2.5 text-xs text-[var(--text-secondary)]"
                        title={item.resource}
                      >
                        {resourceShort}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
