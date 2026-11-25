"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { fieldLabel } from "@/lib/ticket-labels";
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Ban,
  CheckCircle2,
  Clock,
  FileText,
  RefreshCw,
  Search,
  Send,
  StickyNote,
  UserCheck,
  XCircle,
} from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";
import {
  ApiClientError,
  problemMessage,
  staffApi,
  TICKET_STATUS_LABEL,
  type StaffQueue,
  type TicketDetail,
  type TicketStatus,
} from "@/lib/campus-ops-api";

export interface StaffTicketsConsoleProps {
  initialId?: string | null;
}

type FilterKey = "open" | "SUBMITTED" | "IN_REVIEW" | "NEED_INFO" | "closed";

function formatDate(isoString?: string | null): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    return new Intl.DateTimeFormat("vi-VN", {
      timeZone: "Asia/Ho_Chi_Minh",
      hour: "2-digit",
      minute: "2-digit",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(d);
  } catch {
    return isoString;
  }
}

function StatusBadge({ status }: { status: TicketStatus }) {
  const label = TICKET_STATUS_LABEL[status] || status;
  const getIcon = () => {
    switch (status) {
      case "SUBMITTED":
        return <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />;
      case "IN_REVIEW":
        return <RefreshCw className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />;
      case "NEED_INFO":
        return <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />;
      case "RESOLVED":
        return <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />;
      case "REJECTED":
        return <XCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />;
      case "CANCELLED":
        return <Ban className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />;
      default:
        return <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />;
    }
  };

  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[var(--surface-subtle)] text-[var(--text-primary)] border border-[var(--border-color)]">
      {getIcon()}
      <span>{label}</span>
    </span>
  );
}

export function StaffTicketsConsole({ initialId = null }: StaffTicketsConsoleProps) {
  const [queue, setQueue] = useState<StaffQueue | null>(null);
  const [queueLoading, setQueueLoading] = useState<boolean>(true);
  const [queueError, setQueueError] = useState<string | null>(null);

  const [activeFilter, setActiveFilter] = useState<FilterKey>("open");
  const [mineOnly, setMineOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [selectedId, setSelectedId] = useState<string | null>(initialId ?? null);
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [actionError, setActionError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const [replyText, setReplyText] = useState<string>("");
  const [replyStatus, setReplyStatus] = useState<"" | "IN_REVIEW" | "NEED_INFO" | "RESOLVED" | "REJECTED">("");
  const [showCloseConfirm, setShowCloseConfirm] = useState<boolean>(false);

  const [noteText, setNoteText] = useState<string>("");

  const loadQueue = useCallback(async (isPolling = false) => {
    try {
      if (!isPolling) setQueueLoading(true);
      setQueueError(null);
      const res = await staffApi.queue({
        mine: mineOnly ? true : undefined,
        q: searchQuery.trim() ? searchQuery.trim() : undefined,
      });
      setQueue(res);
    } catch (err) {
      if (!isPolling) setQueueError(problemMessage(err));
    } finally {
      if (!isPolling) setQueueLoading(false);
    }
  }, [mineOnly, searchQuery]);

  const loadDetail = useCallback(async (id: string) => {
    try {
      setDetailLoading(true);
      setDetailError(null);
      setActionError(null);
      const res = await staffApi.detail(id);
      setDetail(res);
    } catch (err) {
      setDetailError(problemMessage(err));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    loadQueue();
    const interval = setInterval(() => {
      loadQueue(true);
    }, 30000);
    return () => clearInterval(interval);
  }, [loadQueue]);

  useEffect(() => {
    if (initialId) {
      setSelectedId(initialId);
    }
  }, [initialId]);

  useEffect(() => {
    if (selectedId) {
      loadDetail(selectedId);
      setShowCloseConfirm(false);
      setReplyText("");
      setReplyStatus("");
      setNoteText("");
    } else {
      setDetail(null);
    }
  }, [selectedId, loadDetail]);

  const counts = queue?.counts ?? {
    SUBMITTED: 0,
    IN_REVIEW: 0,
    NEED_INFO: 0,
    RESOLVED: 0,
    REJECTED: 0,
    CANCELLED: 0,
  };

  const openCount = (counts.SUBMITTED ?? 0) + (counts.IN_REVIEW ?? 0) + (counts.NEED_INFO ?? 0);
  const closedCount = (counts.RESOLVED ?? 0) + (counts.REJECTED ?? 0) + (counts.CANCELLED ?? 0);

  const filterChips: Array<{ key: FilterKey; label: string; count: number; testId: string }> = [
    { key: "open", label: "Đang mở", count: openCount, testId: "staff-filter-open" },
    { key: "SUBMITTED", label: "Chờ tiếp nhận", count: counts.SUBMITTED ?? 0, testId: "staff-filter-SUBMITTED" },
    { key: "IN_REVIEW", label: "Đang xử lý", count: counts.IN_REVIEW ?? 0, testId: "staff-filter-IN_REVIEW" },
    { key: "NEED_INFO", label: "Cần bổ sung", count: counts.NEED_INFO ?? 0, testId: "staff-filter-NEED_INFO" },
    { key: "closed", label: "Đã đóng", count: closedCount, testId: "staff-filter-closed" },
  ];

  const filteredItems = useMemo(() => {
    let list = queue?.items ?? [];
    if (activeFilter === "open") {
      list = list.filter((it) => it.status === "SUBMITTED" || it.status === "IN_REVIEW" || it.status === "NEED_INFO");
    } else if (activeFilter === "closed") {
      list = list.filter((it) => it.status === "RESOLVED" || it.status === "REJECTED" || it.status === "CANCELLED");
    } else {
      list = list.filter((it) => it.status === activeFilter);
    }

    const q = searchQuery.trim().toLowerCase();
    if (q) {
      list = list.filter((it) =>
        it.code.toLowerCase().includes(q) ||
        it.title.toLowerCase().includes(q) ||
        it.owner_display.toLowerCase().includes(q) ||
        it.owner_code.toLowerCase().includes(q)
      );
    }
    return list;
  }, [queue, activeFilter, searchQuery]);

  const handleClaim = async () => {
    if (!detail) return;
    try {
      setIsSubmitting(true);
      setActionError(null);
      await staffApi.claim(detail.id);
      window.dispatchEvent(new Event("campus:notifications-changed"));
      await Promise.all([loadQueue(true), loadDetail(detail.id)]);
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 409) {
        setActionError("Hồ sơ đã có người khác tiếp nhận xử lý.");
        await Promise.all([loadQueue(true), loadDetail(detail.id)]);
      } else {
        setActionError(problemMessage(err));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReplySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detail) return;
    const trimmed = replyText.trim();
    if (!trimmed) {
      setActionError("Vui lòng nhập nội dung phản hồi.");
      return;
    }

    if (replyStatus === "RESOLVED" || replyStatus === "REJECTED") {
      setShowCloseConfirm(true);
      return;
    }

    await executeReply(trimmed, replyStatus ? replyStatus : undefined);
  };

  const confirmCloseAndReply = async () => {
    if (!detail) return;
    const trimmed = replyText.trim();
    if (!trimmed) {
      setActionError("Vui lòng nhập nội dung phản hồi trước khi đóng hồ sơ.");
      return;
    }
    if (replyStatus === "RESOLVED" || replyStatus === "REJECTED") {
      await executeReply(trimmed, replyStatus);
    }
  };

  const executeReply = async (text: string, statusArg?: "IN_REVIEW" | "NEED_INFO" | "RESOLVED" | "REJECTED") => {
    if (!detail) return;
    try {
      setIsSubmitting(true);
      setActionError(null);
      await staffApi.reply(detail.id, text, statusArg);
      window.dispatchEvent(new Event("campus:notifications-changed"));
      setReplyText("");
      setReplyStatus("");
      setShowCloseConfirm(false);
      await Promise.all([loadQueue(true), loadDetail(detail.id)]);
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 409) {
        setActionError("Hồ sơ đã có thay đổi bởi cán bộ khác.");
        await Promise.all([loadQueue(true), loadDetail(detail.id)]);
      } else {
        setActionError(problemMessage(err));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNoteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detail) return;
    const trimmed = noteText.trim();
    if (!trimmed) return;
    try {
      setIsSubmitting(true);
      setActionError(null);
      await staffApi.note(detail.id, trimmed);
      window.dispatchEvent(new Event("campus:notifications-changed"));
      setNoteText("");
      await Promise.all([loadQueue(true), loadDetail(detail.id)]);
    } catch (err) {
      setActionError(problemMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div data-testid="staff-console" className="campus-page space-y-6">
      <header className="campus-page-heading">
        <div data-eyebrow="Dành cho cán bộ hỗ trợ">
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Hàng đợi xử lý hồ sơ</h1>
          <p>Tiếp nhận, phản hồi và giải quyết yêu cầu hỗ trợ học vụ từ sinh viên HUCE.</p>
        </div>
      </header>

      <div className="flex flex-col md:flex-row gap-6 items-start">
        {/* Left Column: Queue List */}
        <section
          className={`w-full md:w-[380px] lg:w-[420px] shrink-0 campus-panel p-4 space-y-4 ${
            selectedId ? "hidden md:block" : "block"
          }`}
        >
          {/* Controls: Mine Toggle and Search */}
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <label className="inline-flex items-center gap-2 text-sm text-[var(--text-primary)] cursor-pointer">
                <input
                  type="checkbox"
                  checked={mineOnly}
                  onChange={(e) => setMineOnly(e.target.checked)}
                  className="rounded border-[var(--border-color)] accent-[var(--color-primary)] w-4 h-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                />
                <span className="font-medium">Của tôi</span>
              </label>
              <IconButton label="Làm mới" onClick={() => loadQueue()} icon={<RefreshCw size={18} />} />
            </div>

            <div className="relative">
              <Search
                className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-secondary)] pointer-events-none"
                aria-hidden="true"
              />
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm mã hồ sơ, tiêu đề, sinh viên..."
                className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] min-h-[44px]"
              />
            </div>
          </div>

          {/* Filter Chips */}
          <div className="flex flex-wrap gap-1.5" role="toolbar" aria-label="Bộ lọc trạng thái">
            {filterChips.map((chip) => {
              const active = activeFilter === chip.key;
              return (
                <button
                  key={chip.key}
                  type="button"
                  data-testid={chip.testId}
                  onClick={() => setActiveFilter(chip.key)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium min-h-[44px] border transition-colors ${
                    active
                      ? "bg-[var(--color-primary-light)] text-[var(--color-primary)] border-[var(--color-primary)]"
                      : "bg-[var(--surface-card)] text-[var(--text-secondary)] border-[var(--border-color)] hover:bg-[var(--surface-subtle)]"
                  } focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]`}
                >
                  <span>{chip.label}</span>
                  <span className="px-1.5 py-0.2 rounded-full text-[11px] bg-[var(--surface-subtle)] text-[var(--text-primary)] border border-[var(--border-color)]">
                    {chip.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Ticket List States */}
          {queueLoading && (
            <div role="status" className="p-8 text-center text-sm text-[var(--text-secondary)]">
              Đang tải danh sách hồ sơ…
            </div>
          )}

          {!queueLoading && queueError && (
            <div role="alert" className="p-4 rounded-lg bg-[var(--surface-subtle)] border border-[var(--border-color)] text-sm space-y-2">
              <p className="text-[var(--text-primary)]">{queueError}</p>
              <button
                type="button"
                onClick={() => loadQueue()}
                className="inline-flex items-center justify-center min-h-[44px] px-4 py-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              >
                Thử lại
              </button>
            </div>
          )}

          {!queueLoading && !queueError && filteredItems.length === 0 && (
            <div className="p-8 text-center space-y-2 border border-dashed border-[var(--border-color)] rounded-xl">
              <p className="text-sm font-medium text-[var(--text-primary)]">Không có hồ sơ phù hợp</p>
              <p className="text-xs text-[var(--text-secondary)]">
                Hãy thử đổi trạng thái lọc hoặc thay đổi từ khóa tìm kiếm.
              </p>
            </div>
          )}

          {!queueLoading && !queueError && filteredItems.length > 0 && (
            <div className="space-y-2.5 max-h-[calc(100vh-320px)] overflow-y-auto pr-1">
              {filteredItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  data-testid={`staff-ticket-${item.id}`}
                  onClick={() => setSelectedId(item.id)}
                  className={`w-full text-left p-3.5 rounded-xl border transition-colors min-h-[44px] flex flex-col gap-2 ${
                    selectedId === item.id
                      ? "border-[var(--color-primary)] bg-[var(--color-primary-light)]"
                      : "border-[var(--border-color)] bg-[var(--surface-card)] hover:bg-[var(--surface-subtle)]"
                  } focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-semibold text-[var(--text-secondary)]">
                      {item.code}
                    </span>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {item.overdue && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-[var(--surface-subtle)] border border-[var(--border-color)] text-[var(--text-primary)]">
                          <AlertTriangle className="h-3 w-3 shrink-0" aria-hidden="true" />
                          Quá hạn
                        </span>
                      )}
                      <StatusBadge status={item.status} />
                    </div>
                  </div>
                  <h2 className="text-sm font-semibold text-[var(--text-primary)] line-clamp-2 break-words">
                    {item.title}
                  </h2>
                  <div className="flex items-center justify-between text-xs text-[var(--text-secondary)] gap-2 flex-wrap">
                    <span className="truncate">
                      {item.owner_display} · {item.owner_code}
                    </span>
                    <span>{item.assignee_display ? item.assignee_display : "Chưa phân công"}</span>
                  </div>
                  {item.due_at && (
                    <div className="text-[11px] text-[var(--text-secondary)]">
                      Hạn xử lý: {formatDate(item.due_at)}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </section>

        {/* Right Column: Ticket Detail */}
        <section
          className={`w-full min-w-0 flex-1 campus-panel p-6 space-y-6 ${
            selectedId ? "block" : "hidden md:block"
          }`}
          data-testid="staff-detail"
        >
          {detailLoading && (
            <div role="status" className="p-12 text-center text-sm text-[var(--text-secondary)]">
              Đang tải chi tiết hồ sơ…
            </div>
          )}

          {!detailLoading && detailError && (
            <div role="alert" className="p-4 rounded-lg bg-[var(--surface-subtle)] border border-[var(--border-color)] text-sm space-y-2">
              <p className="text-[var(--text-primary)]">{detailError}</p>
              {selectedId && (
                <button
                  type="button"
                  onClick={() => loadDetail(selectedId)}
                  className="inline-flex items-center justify-center min-h-[44px] px-4 py-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                >
                  Thử lại
                </button>
              )}
            </div>
          )}

          {!detailLoading && !detailError && !detail && (
            <div className="campus-empty-state">
              <FileText className="h-10 w-10 text-[var(--text-secondary)]" aria-hidden="true" />
              <h2 className="font-medium text-sm text-[var(--text-primary)]">Chưa chọn hồ sơ</h2>
              <p>Chọn một hồ sơ từ danh sách bên trái để xem chi tiết và thực hiện tiếp nhận, phản hồi.</p>
            </div>
          )}

          {!detailLoading && !detailError && detail && (
            <div className="space-y-6 min-w-0">
              {/* Detail Top Navigation and Status */}
              <div className="flex items-center justify-between gap-3 pb-4 border-b border-[var(--border-color)] flex-wrap">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setSelectedId(null)}
                    className="md:hidden inline-flex items-center gap-1 min-h-[44px] px-3 py-2 rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] text-xs font-medium text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                  >
                    <ArrowLeft className="h-4 w-4 shrink-0" aria-hidden="true" />
                    Quay lại danh sách
                  </button>
                  <span className="font-mono text-sm font-semibold text-[var(--text-secondary)]">
                    {detail.code}
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  {detail.overdue && (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-[var(--surface-subtle)] border border-[var(--border-color)] text-[var(--text-primary)]">
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                      Quá hạn
                    </span>
                  )}
                  <StatusBadge status={detail.status} />
                </div>
              </div>

              {/* Action alert if any */}
              {actionError && (
                <div role="alert" className="p-3 rounded-lg bg-[var(--surface-subtle)] border border-[var(--border-color)] text-sm text-[var(--text-primary)] flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
                  <p className="flex-1">{actionError}</p>
                </div>
              )}

              {/* Title & Student Meta */}
              <div className="space-y-2">
                <h2 className="text-xl font-bold text-[var(--text-primary)] break-words">
                  {detail.title}
                </h2>
                <div className="text-sm text-[var(--text-secondary)]">
                  Sinh viên: <strong className="font-semibold text-[var(--text-primary)]">{detail.owner_display}</strong> · Mã SV: <span className="font-mono text-[var(--text-primary)]">{detail.owner_code}</span>
                </div>
                <div className="text-xs text-[var(--text-secondary)] flex flex-wrap gap-x-4 gap-y-1">
                  <span>Dịch vụ: {detail.service_label}</span>
                  <span>Ngày gửi: {formatDate(detail.created_at)}</span>
                  {detail.due_at && <span>Hạn xử lý: {formatDate(detail.due_at)}</span>}
                  <span>Phụ trách: {detail.assignee_display || "Chưa có"}</span>
                </div>
              </div>

              {/* Summary */}
              <div className="p-4 rounded-xl bg-[var(--surface-subtle)] border border-[var(--border-color)] space-y-1.5">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                  Nội dung yêu cầu
                </h3>
                <p className="text-sm text-[var(--text-primary)] whitespace-pre-wrap break-words">
                  {detail.summary}
                </p>
              </div>

              {/* Fields Table */}
              {detail.fields && Object.keys(detail.fields).length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                    Thông tin chi tiết biểu mẫu
                  </h3>
                  <div className="overflow-x-auto rounded-xl border border-[var(--border-color)]">
                    <table className="w-full text-left text-xs border-collapse">
                      <tbody>
                        {Object.entries(detail.fields).map(([key, val]) => (
                          <tr key={key} className="border-b border-[var(--border-color)] last:border-0">
                            <th className="py-2.5 px-3.5 font-medium text-[var(--text-secondary)] bg-[var(--surface-subtle)] w-1/3 break-words">
                              {fieldLabel(key)}
                            </th>
                            <td className="py-2.5 px-3.5 text-[var(--text-primary)] break-words">
                              {val}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Actions Section */}
              <div className="space-y-6 pt-4 border-t border-[var(--border-color)]">
                {/* Claim Button */}
                {detail.allowed_actions.includes("claim") && (
                  <div>
                    <button
                      type="button"
                      data-testid="staff-claim-button"
                      disabled={isSubmitting}
                      onClick={handleClaim}
                      className="min-h-[44px] px-4 py-2 rounded-lg bg-[var(--color-primary)] text-[var(--color-on-primary)] font-medium text-sm inline-flex items-center gap-2 hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] disabled:opacity-50"
                    >
                      <UserCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
                      Nhận xử lý
                    </button>
                  </div>
                )}

                {/* Reply Form */}
                {detail.allowed_actions.includes("reply") && (
                  <form onSubmit={handleReplySubmit} className="space-y-3">
                    <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                      Phản hồi sinh viên
                    </h3>
                    <label htmlFor="staff-reply-input" className="sr-only">
                      Nội dung phản hồi
                    </label>
                    <textarea
                      id="staff-reply-input"
                      data-testid="staff-reply-input"
                      value={replyText}
                      onChange={(e) => setReplyText(e.target.value)}
                      maxLength={2000}
                      rows={3}
                      placeholder="Nhập nội dung phản hồi gửi tới sinh viên (1 - 2000 ký tự)..."
                      className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] p-3 text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] min-h-[96px]"
                      disabled={isSubmitting}
                    />

                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <label htmlFor="staff-status-select" className="text-xs text-[var(--text-secondary)] whitespace-nowrap">
                          Chuyển trạng thái:
                        </label>
                        <select
                          id="staff-status-select"
                          value={replyStatus}
                          onChange={(e) => {
                            setReplyStatus(e.target.value as "" | "IN_REVIEW" | "NEED_INFO" | "RESOLVED" | "REJECTED");
                            setShowCloseConfirm(false);
                          }}
                          className="min-h-[44px] rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-3 py-1.5 text-xs text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                          disabled={isSubmitting}
                        >
                          <option value="">Giữ nguyên trạng thái hiện tại</option>
                          <option value="NEED_INFO">Cần bổ sung thông tin</option>
                          <option value="RESOLVED">Đã giải quyết</option>
                          <option value="REJECTED">Từ chối</option>
                        </select>
                      </div>

                      {!showCloseConfirm && (
                        <button
                          type="submit"
                          data-testid="staff-reply-submit"
                          disabled={isSubmitting || !replyText.trim()}
                          className="min-h-[44px] px-4 py-2 rounded-lg bg-[var(--color-primary)] text-[var(--color-on-primary)] font-medium text-sm inline-flex items-center justify-center gap-2 hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] disabled:opacity-50"
                        >
                          <Send className="h-4 w-4 shrink-0" aria-hidden="true" />
                          Gửi phản hồi
                        </button>
                      )}
                    </div>

                    {showCloseConfirm && (
                      <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] space-y-3">
                        <p className="text-sm font-medium text-[var(--text-primary)]">
                          Đóng hồ sơ? Sinh viên sẽ được thông báo.
                        </p>
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={confirmCloseAndReply}
                            autoFocus
                            disabled={isSubmitting}
                            className="min-h-[44px] px-4 py-2 rounded-lg bg-[var(--color-primary)] text-[var(--color-on-primary)] font-medium text-sm inline-flex items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] disabled:opacity-50"
                          >
                            Xác nhận
                          </button>
                          <button
                            type="button"
                            onClick={() => setShowCloseConfirm(false)}
                            disabled={isSubmitting}
                            className="min-h-[44px] px-4 py-2 rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                          >
                            Hủy
                          </button>
                        </div>
                      </div>
                    )}
                  </form>
                )}

                {/* Internal Note Form */}
                {detail.allowed_actions.includes("note") && (
                  <form onSubmit={handleNoteSubmit} className="space-y-3 pt-4 border-t border-[var(--border-color)]">
                    <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                      Ghi chú nội bộ
                    </h3>
                    <label htmlFor="staff-note-input" className="sr-only">
                      Nội dung ghi chú
                    </label>
                    <textarea
                      id="staff-note-input"
                      data-testid="staff-note-input"
                      value={noteText}
                      onChange={(e) => setNoteText(e.target.value)}
                      maxLength={2000}
                      rows={2}
                      placeholder="Ghi chú nội bộ cho cán bộ xử lý (sinh viên không thấy)..."
                      className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] p-3 text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] min-h-[80px]"
                      disabled={isSubmitting}
                    />
                    <div className="flex justify-end">
                      <button
                        type="submit"
                        data-testid="staff-note-submit"
                        disabled={isSubmitting || !noteText.trim()}
                        className="min-h-[44px] px-4 py-2 rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] font-medium text-sm text-[var(--text-primary)] inline-flex items-center justify-center gap-2 hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] disabled:opacity-50"
                      >
                        <StickyNote className="h-4 w-4 shrink-0" aria-hidden="true" />
                        Lưu ghi chú
                      </button>
                    </div>
                  </form>
                )}
              </div>

              {/* Timeline Events */}
              <div className="space-y-3 pt-6 border-t border-[var(--border-color)]">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                  Dòng thời gian sự kiện
                </h3>
                <div className="space-y-3">
                  {detail.events.map((evt) => (
                    <div
                      key={evt.id}
                      className="p-3.5 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] space-y-1.5"
                    >
                      <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
                        <span className="font-semibold text-[var(--text-primary)]">
                          {evt.actor_display} ({evt.actor_role_label ?? "Hệ thống"})
                        </span>
                        <span className="text-[var(--text-secondary)]">
                          {formatDate(evt.created_at)}
                        </span>
                      </div>
                      {evt.kind === "NOTE" && (
                        <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-[var(--surface-subtle)] text-[var(--text-secondary)] border border-[var(--border-color)]">
                          <StickyNote className="h-3 w-3 shrink-0" aria-hidden="true" />
                          Ghi chú nội bộ — sinh viên không thấy
                        </div>
                      )}
                      <p className="text-sm text-[var(--text-primary)] whitespace-pre-wrap break-words">
                        {evt.body}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
