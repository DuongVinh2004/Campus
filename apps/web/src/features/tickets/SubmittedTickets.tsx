"use client";

import { useCallback, useEffect, useState } from "react";
import { fieldLabel } from "@/lib/ticket-labels";
import {
  AlertCircle,
  Ban,
  CheckCircle2,
  Clock,
  FileText,
  Send,
  XCircle,
} from "lucide-react";
import {
  problemMessage,
  ticketsApi,
  TICKET_STATUS_LABEL,
  type Ticket,
  type TicketDetail,
  type TicketStatus,
} from "@/lib/campus-ops-api";

interface SubmittedTicketsProps {
  initialId?: string | null;
  refreshToken?: number;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("vi-VN", {
      timeZone: "Asia/Ho_Chi_Minh",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function StatusBadge({ status }: { status: TicketStatus }) {
  const label = TICKET_STATUS_LABEL[status] || status;

  let icon = <Send className="h-4 w-4 shrink-0" aria-hidden="true" />;
  if (status === "IN_REVIEW") {
    icon = <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />;
  } else if (status === "NEED_INFO") {
    icon = <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />;
  } else if (status === "RESOLVED") {
    icon = <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />;
  } else if (status === "REJECTED") {
    icon = <XCircle className="h-4 w-4 shrink-0" aria-hidden="true" />;
  } else if (status === "CANCELLED") {
    icon = <Ban className="h-4 w-4 shrink-0" aria-hidden="true" />;
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border-color)] bg-[var(--surface-subtle)] px-2.5 py-1 text-xs font-medium text-[var(--text-primary)]">
      {icon}
      <span>{label}</span>
    </span>
  );
}

export function SubmittedTickets({
  initialId = null,
  refreshToken = 0,
}: SubmittedTicketsProps) {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(initialId ?? null);
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [replyText, setReplyText] = useState("");
  const [replySubmitting, setReplySubmitting] = useState(false);
  const [replyError, setReplyError] = useState<string | null>(null);

  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelSubmitting, setCancelSubmitting] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const fetchTickets = useCallback(async () => {
    try {
      setListError(null);
      const res = await ticketsApi.mine();
      setTickets(res.items || []);
    } catch (err) {
      setListError(problemMessage(err));
    } finally {
      setLoadingList(false);
    }
  }, []);

  const fetchDetail = useCallback(async (id: string) => {
    try {
      setLoadingDetail(true);
      setDetailError(null);
      const data = await ticketsApi.detail(id);
      setDetail(data);
    } catch (err) {
      setDetailError(problemMessage(err));
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    fetchTickets();
    const interval = setInterval(fetchTickets, 30000);
    return () => clearInterval(interval);
  }, [fetchTickets, refreshToken]);

  useEffect(() => {
    if (initialId) {
      setSelectedId(initialId);
    }
  }, [initialId]);

  useEffect(() => {
    if (selectedId) {
      fetchDetail(selectedId);
      setCancelOpen(false);
      setReplyText("");
      setReplyError(null);
      setCancelError(null);
    } else {
      setDetail(null);
    }
  }, [selectedId, fetchDetail]);

  const handleReplySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detail || !replyText.trim() || replyText.length > 2000) return;

    try {
      setReplySubmitting(true);
      setReplyError(null);
      const updated = await ticketsApi.reply(detail.id, replyText.trim());
      setDetail(updated);
      setReplyText("");
      window.dispatchEvent(new Event("campus:notifications-changed"));
      fetchTickets();
    } catch (err) {
      setReplyError(problemMessage(err));
    } finally {
      setReplySubmitting(false);
    }
  };

  const handleCancelSubmit = async () => {
    if (!detail) return;

    try {
      setCancelSubmitting(true);
      setCancelError(null);
      const updated = await ticketsApi.cancel(detail.id, cancelReason.trim());
      setDetail(updated);
      setCancelOpen(false);
      setCancelReason("");
      window.dispatchEvent(new Event("campus:notifications-changed"));
      fetchTickets();
    } catch (err) {
      setCancelError(problemMessage(err));
    } finally {
      setCancelSubmitting(false);
    }
  };

  return (
    <div className="campus-page min-w-0 space-y-6">
      <header className="campus-page-heading">
        <div data-eyebrow="Theo dõi hồ sơ">
          <h1 className="text-2xl font-semibold">Hồ sơ đã gửi</h1>
          <p>Theo dõi tiến trình xử lý và phản hồi yêu cầu một cửa.</p>
        </div>
      </header>

      <section className="campus-panel border-[var(--border-color)] bg-[var(--surface-subtle)] p-4 text-sm text-[var(--text-secondary)]">
        Hồ sơ được xử lý trong hệ thống Một cửa nội bộ của Campus 24/7; chưa kết nối hệ thống tiếp nhận của HUCE.
      </section>

      {loadingList && (
        <div
          role="status"
          className="campus-panel p-8 text-center text-sm text-[var(--text-secondary)]"
        >
          Đang tải…
        </div>
      )}

      {!loadingList && listError && (
        <div role="alert" className="campus-panel p-6 text-center">
          <p className="text-sm text-[var(--color-primary)] mb-3">{listError}</p>
          <button
            type="button"
            onClick={fetchTickets}
            className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-5 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
          >
            Thử lại
          </button>
        </div>
      )}

      {!loadingList && !listError && tickets.length === 0 && (
        <div className="campus-empty-state">
          <FileText className="h-10 w-10 text-[var(--color-primary)]" aria-hidden="true" />
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            Bạn chưa gửi hồ sơ nào
          </h2>
          <p>Soạn nháp ở &apos;Dịch vụ học vụ&apos; rồi bấm &apos;Gửi hồ sơ&apos;.</p>
        </div>
      )}

      {!loadingList && !listError && tickets.length > 0 && (
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
          {/* Ticket list */}
          <section
            data-testid="submitted-tickets"
            className="space-y-3 lg:col-span-5"
            aria-label="Danh sách hồ sơ đã gửi"
          >
            {tickets.map((t) => {
              const isSelected = t.id === selectedId;
              return (
                <div
                  key={t.id}
                  data-testid={`submitted-ticket-${t.id}`}
                  onClick={() => setSelectedId(t.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedId(t.id);
                    }
                  }}
                  tabIndex={0}
                  role="button"
                  aria-pressed={isSelected}
                  className={`campus-panel cursor-pointer p-4 transition-all focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] ${
                    isSelected
                      ? "border-[var(--color-primary)] bg-[var(--color-primary-light)]"
                      : "hover:border-[var(--border-color)]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-mono text-xs font-semibold text-[var(--color-primary)]">
                      {t.code}
                    </span>
                    <StatusBadge status={t.status} />
                  </div>
                  <h2 className="mt-2 text-base font-semibold text-[var(--text-primary)] break-words">
                    {t.title}
                  </h2>
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">
                    {t.service_label}
                  </p>
                  {t.assignee_display && (
                    <p className="mt-2 text-xs text-[var(--text-secondary)]">
                      Cán bộ phụ trách:{" "}
                      <span className="font-medium text-[var(--text-primary)]">
                        {t.assignee_display}
                      </span>
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border-color)] pt-2 text-xs text-[var(--text-secondary)]">
                    <span>Gửi: {formatDate(t.created_at)}</span>
                    <span>Cập nhật: {formatDate(t.updated_at)}</span>
                  </div>
                </div>
              );
            })}
          </section>

          {/* Ticket detail */}
          <section className="lg:col-span-7">
            {!selectedId ? (
              <div className="campus-panel p-8 text-center text-sm text-[var(--text-secondary)]">
                Chọn một hồ sơ từ danh sách để xem chi tiết tiến trình xử lý.
              </div>
            ) : loadingDetail ? (
              <div
                data-testid="ticket-detail"
                className="campus-panel p-8 text-center text-sm text-[var(--text-secondary)]"
                role="status"
              >
                Đang tải…
              </div>
            ) : detailError ? (
              <div
                data-testid="ticket-detail"
                role="alert"
                className="campus-panel p-6 text-center"
              >
                <p className="text-sm text-[var(--color-primary)] mb-3">{detailError}</p>
                <button
                  type="button"
                  onClick={() => fetchDetail(selectedId)}
                  className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-5 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                >
                  Thử lại
                </button>
              </div>
            ) : detail ? (
              <article
                data-testid="ticket-detail"
                className="campus-panel space-y-6 p-6"
              >
                <div className="border-b border-[var(--border-color)] pb-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-sm font-semibold text-[var(--color-primary)]">
                      {detail.code}
                    </span>
                    <StatusBadge status={detail.status} />
                  </div>
                  <h2 className="mt-2 text-xl font-bold text-[var(--text-primary)] break-words">
                    {detail.title}
                  </h2>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">
                    {detail.service_label}
                  </p>

                  <div className="mt-4 grid grid-cols-1 gap-2 text-xs text-[var(--text-secondary)] sm:grid-cols-2">
                    <div>
                      Ngày gửi:{" "}
                      <span className="font-medium text-[var(--text-primary)]">
                        {formatDate(detail.created_at)}
                      </span>
                    </div>
                    <div>
                      Cập nhật:{" "}
                      <span className="font-medium text-[var(--text-primary)]">
                        {formatDate(detail.updated_at)}
                      </span>
                    </div>
                    {detail.assignee_display && (
                      <div className="sm:col-span-2">
                        Cán bộ phụ trách:{" "}
                        <span className="font-medium text-[var(--text-primary)]">
                          {detail.assignee_display}
                        </span>
                      </div>
                    )}
                  </div>

                  {detail.due_at && (
                    <div className="mt-3 flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                      <span>
                        Hạn xử lý dự kiến:{" "}
                        <span className="font-medium text-[var(--text-primary)]">
                          {formatDate(detail.due_at)}
                        </span>
                      </span>
                      {detail.overdue && (
                        <span className="rounded border border-[var(--border-color)] bg-[var(--surface-subtle)] px-2 py-0.5 text-xs font-semibold text-[var(--color-primary)]">
                          Quá hạn
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Summary */}
                <div>
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                    Nội dung yêu cầu
                  </h3>
                  <p className="mt-2 text-sm text-[var(--text-secondary)] whitespace-pre-wrap break-words">
                    {detail.summary}
                  </p>
                </div>

                {/* Fields */}
                {detail.fields && Object.keys(detail.fields).length > 0 && (
                  <div>
                    <h3 className="mb-2 text-sm font-semibold text-[var(--text-primary)]">
                      Thông tin đã cung cấp
                    </h3>
                    <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {Object.entries(detail.fields).map(([k, v]) => (
                        <div
                          key={k}
                          className="rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] p-3"
                        >
                          <dt className="text-xs text-[var(--text-secondary)] break-words">
                            {fieldLabel(k)}
                          </dt>
                          <dd className="mt-1 text-sm font-medium text-[var(--text-primary)] break-words">
                            {v}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}

                {/* Events Timeline */}
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
                    Tiến trình xử lý
                  </h3>
                  {(() => {
                    const publicEvents = (detail.events || []).filter(
                      (e) => e.visibility === "PUBLIC"
                    );
                    if (publicEvents.length === 0) {
                      return (
                        <p className="text-sm text-[var(--text-secondary)] italic">
                          Chưa có cập nhật tiến trình công khai.
                        </p>
                      );
                    }
                    return (
                      <ol className="relative ml-2 space-y-4 border-l border-[var(--border-color)] pl-4">
                        {publicEvents.map((ev) => {
                          const senderLabel = ev.is_mine ? "Bạn" : ev.actor_kind === "student" ? "Sinh viên" : ev.actor_kind === "system" ? "Hệ thống" : "Cán bộ";
                          return (
                            <li key={ev.id} className="relative">
                              <div className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border border-[var(--border-color)] bg-[var(--surface-card)]" />
                              <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--text-secondary)]">
                                <span className="font-semibold text-[var(--text-primary)]">
                                  {senderLabel}
                                </span>
                                {ev.actor_display && ev.actor_display !== senderLabel && (
                                  <span>({ev.actor_display})</span>
                                )}
                                <span>·</span>
                                <time>{formatDate(ev.created_at)}</time>
                              </div>
                              <p className="mt-1 text-sm text-[var(--text-primary)] whitespace-pre-wrap break-words">
                                {ev.body}
                              </p>
                            </li>
                          );
                        })}
                      </ol>
                    );
                  })()}
                </div>

                {/* Actions */}
                {detail.allowed_actions &&
                  (detail.allowed_actions.includes("reply") ||
                    detail.allowed_actions.includes("cancel")) && (
                    <div className="space-y-4 border-t border-[var(--border-color)] pt-4">
                      {detail.allowed_actions.includes("reply") && (
                        <form onSubmit={handleReplySubmit} className="space-y-3">
                          <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                            Phản hồi cán bộ
                          </h3>

                          {detail.status === "NEED_INFO" && (
                            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--color-primary-light)] p-3 text-sm font-medium text-[var(--color-primary)]">
                              Cán bộ đang chờ bạn bổ sung thông tin
                            </div>
                          )}

                          {replyError && (
                            <div role="alert" className="text-sm text-[var(--color-primary)]">
                              {replyError}
                            </div>
                          )}

                          <textarea
                            data-testid="ticket-reply-input"
                            value={replyText}
                            onChange={(e) => setReplyText(e.target.value)}
                            maxLength={2000}
                            rows={3}
                            placeholder="Nhập nội dung phản hồi hoặc bổ sung thông tin (tối đa 2000 ký tự)…"
                            className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] p-3 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                          />
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-[var(--text-secondary)]">
                              {replyText.length}/2000 ký tự
                            </span>
                            <button
                              type="submit"
                              data-testid="ticket-reply-submit"
                              disabled={
                                replySubmitting ||
                                !replyText.trim() ||
                                replyText.length > 2000
                              }
                              className="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-[var(--color-primary)] px-5 py-2 text-sm font-medium text-[var(--color-on-primary,white)] transition-opacity hover:opacity-90 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                            >
                              {replySubmitting ? "Đang gửi…" : "Gửi phản hồi"}
                            </button>
                          </div>
                        </form>
                      )}

                      {detail.allowed_actions.includes("cancel") && (
                        <div className="border-t border-[var(--border-color)] pt-4">
                          {!cancelOpen ? (
                            <button
                              type="button"
                              data-testid="ticket-cancel-button"
                              onClick={() => setCancelOpen(true)}
                              className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-5 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                            >
                              Hủy hồ sơ
                            </button>
                          ) : (
                            <div className="rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4 space-y-3">
                              <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                                Xác nhận hủy hồ sơ?
                              </h4>
                              <p className="text-xs text-[var(--text-secondary)]">
                                Hồ sơ sẽ ngừng xử lý sau khi xác nhận.
                              </p>
                              {cancelError && (
                                <div role="alert" className="text-sm text-[var(--color-primary)]">
                                  {cancelError}
                                </div>
                              )}
                              <input
                                type="text"
                                value={cancelReason}
                                onChange={(e) => setCancelReason(e.target.value)}
                                placeholder="Lý do hủy (tùy chọn)"
                                className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] p-2.5 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                              />
                              <div className="flex flex-wrap items-center gap-2 pt-1">
                                <button
                                  type="button"
                                  data-testid="ticket-cancel-confirm"
                                  disabled={cancelSubmitting}
                                  onClick={handleCancelSubmit}
                                  className="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-[var(--color-primary)] px-5 py-2 text-sm font-medium text-[var(--color-on-primary,white)] transition-opacity hover:opacity-90 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                                >
                                  {cancelSubmitting ? "Đang hủy…" : "Xác nhận hủy"}
                                </button>
                                <button
                                  type="button"
                                  disabled={cancelSubmitting}
                                  onClick={() => {
                                    setCancelOpen(false);
                                    setCancelError(null);
                                  }}
                                  className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-5 py-2 text-sm font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                                >
                                  Giữ hồ sơ
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
              </article>
            ) : null}
          </section>
        </div>
      )}
    </div>
  );
}
