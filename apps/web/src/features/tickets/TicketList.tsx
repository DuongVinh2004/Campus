import React, { useEffect, useState } from "react";
import {
  ClipboardList,
  Clock,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Star,
  Send,
  MessageSquare,
} from "lucide-react";

export interface TicketEvent {
  id: string;
  timestamp: string;
  description: string;
  actor?: string;
}

export interface StudentTicket {
  id: string;
  code: string;
  title: string;
  category: string;
  status:
    | "submitted"
    | "queued"
    | "claimed"
    | "in_progress"
    | "waiting_student"
    | "transferred"
    | "resolved"
    | "closed"
    | "escalated";
  createdAt: string;
  updatedAt?: string;
  description: string;
  nextAction?: string;
  events?: TicketEvent[];
}

export interface TicketListProps {
  tickets?: StudentTicket[];
  onSupplementInfo?: (ticketId: string, payload: { content: string }) => void;
  onFeedbackRating?: (ticketId: string, payload: { rating: number; comment?: string }) => void;
}

const statusLabels: Record<
  StudentTicket["status"],
  { label: string; badgeClass: string }
> = {
  submitted: {
    label: "Đã tiếp nhận",
    badgeClass:
      "border border-[var(--border-color)] bg-[var(--surface-subtle)] text-[var(--text-secondary)]",
  },
  queued: {
    label: "Đã tiếp nhận",
    badgeClass:
      "border border-[var(--border-color)] bg-[var(--surface-subtle)] text-[var(--text-secondary)]",
  },
  claimed: {
    label: "Đã chuyển cán bộ phụ trách",
    badgeClass:
      "border border-[var(--color-primary-subtle)] bg-[var(--color-primary-subtle)] text-[var(--color-primary)]",
  },
  in_progress: {
    label: "Đang xử lý",
    badgeClass:
      "border border-[var(--color-primary-subtle)] bg-[var(--color-primary-subtle)] text-[var(--color-primary)]",
  },
  waiting_student: {
    label: "Cần bạn bổ sung thông tin",
    badgeClass:
      "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/50",
  },
  transferred: {
    label: "Đã chuyển đơn vị phù hợp",
    badgeClass:
      "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-900/50",
  },
  resolved: {
    label: "Đã có kết quả",
    badgeClass:
      "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900/50",
  },
  closed: {
    label: "Đã đóng",
    badgeClass:
      "border border-[var(--border-color)] bg-[var(--surface-subtle)] text-[var(--text-secondary)]",
  },
  escalated: {
    label: "Đang được ưu tiên xem xét",
    badgeClass:
      "bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900/50",
  },
};

export function TicketList({
  tickets = [],
  onSupplementInfo,
  onFeedbackRating,
}: TicketListProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    const update = () => setCompact(window.innerWidth < 768);
    update(); window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  const [filterStatus, setFilterStatus] = useState<"all" | "active" | "waiting" | "resolved">("all");
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  // Additional info state
  const [isSupplementOpen, setIsSupplementOpen] = useState<Record<string, boolean>>({});
  const [supplementTexts, setSupplementTexts] = useState<Record<string, string>>({});
  const [supplementSubmitted, setSupplementSubmitted] = useState<Record<string, boolean>>({});

  // Feedback rating state
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [comments, setComments] = useState<Record<string, string>>({});
  const [feedbackSubmitted, setFeedbackSubmitted] = useState<Record<string, boolean>>({});

  const toggleDetail = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const handleCopyCode = async (code: string) => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(code);
        setCopiedCode(code);
        setTimeout(() => setCopiedCode(null), 3000);
      }
    } catch {
      // Fallback
    }
  };

  const handleSubmitSupplement = (ticketId: string) => {
    const text = (supplementTexts[ticketId] || "").trim();
    if (!text) return;
    onSupplementInfo?.(ticketId, { content: text });
    setSupplementSubmitted((prev) => ({ ...prev, [ticketId]: true }));
    setIsSupplementOpen((prev) => ({ ...prev, [ticketId]: false }));
  };

  const handleSubmitFeedback = (ticketId: string) => {
    const star = ratings[ticketId] || 5;
    const comment = (comments[ticketId] || "").trim();
    onFeedbackRating?.(ticketId, { rating: star, comment: comment || undefined });
    setFeedbackSubmitted((prev) => ({ ...prev, [ticketId]: true }));
  };

  const filteredTickets = tickets.filter((ticket) => {
    if (filterStatus === "waiting") return ticket.status === "waiting_student";
    if (filterStatus === "active") {
      return ticket.status !== "resolved" && ticket.status !== "closed";
    }
    if (filterStatus === "resolved") {
      return ticket.status === "resolved" || ticket.status === "closed";
    }
    return true;
  });

  return (
    <div className="flex flex-col gap-6">
      {/* Accessible Live Region for Copy Feedback */}
      {copiedCode && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-5 right-5 z-50 rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] px-4 py-2 text-xs font-medium text-[var(--text-primary)] shadow-lg animate-in fade-in slide-in-from-bottom-2 duration-200"
        >
          Đã sao chép mã {copiedCode} vào bộ nhớ tạm
        </div>
      )}

      {/* Header & Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
            Tra cứu & Theo dõi yêu cầu hỗ trợ (Một cửa số)
          </h2>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Theo dõi trạng thái và tiến độ xử lý hồ sơ hành chính, học vụ của bạn
          </p>
        </div>

        {/* Filter Pills */}
        <div
          role="group"
          aria-label="Lọc trạng thái yêu cầu"
          className="inline-flex rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] p-1"
        >
          <button
            type="button"
            onClick={() => setFilterStatus("all")}
            aria-pressed={filterStatus === "all"}
            className={`rounded-lg px-4 py-1.5 text-xs font-medium transition ${
              filterStatus === "all"
                ? "bg-[var(--surface-card)] font-semibold text-[var(--color-primary)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            Tất cả ({tickets.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterStatus("active")}
            aria-pressed={filterStatus === "active"}
            className={`rounded-lg px-4 py-1.5 text-xs font-medium transition ${
              filterStatus === "active"
                ? "bg-[var(--surface-card)] font-semibold text-[var(--color-primary)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            Đang xử lý
          </button>
          <button
            type="button"
            aria-pressed={filterStatus === "waiting"}
            onClick={() => setFilterStatus("waiting")}
            className={`rounded-lg px-4 py-1.5 text-xs font-medium transition ${
              filterStatus === "waiting"
                ? "bg-[var(--surface-card)] font-semibold text-[var(--color-primary)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            Cần bổ sung
          </button>
          <button
            type="button"
            onClick={() => setFilterStatus("resolved")}
            aria-pressed={filterStatus === "resolved"}
            className={`rounded-lg px-4 py-1.5 text-xs font-medium transition ${
              filterStatus === "resolved"
                ? "bg-[var(--surface-card)] font-semibold text-[var(--color-primary)] shadow-xs"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            Đã hoàn thành
          </button>
        </div>
      </div>

      <div className="campus-record-stats" aria-label="Thống kê hồ sơ">{[
        ["Tổng hồ sơ", tickets.length], ["Đang xử lý", tickets.filter(ticket => !["resolved", "closed", "waiting_student"].includes(ticket.status)).length], ["Cần bổ sung", tickets.filter(ticket => ticket.status === "waiting_student").length], ["Đã hoàn thành", tickets.filter(ticket => ["resolved", "closed"].includes(ticket.status)).length],
      ].map(([label, count]) => <div key={label}><span>{label}</span><strong>{count}</strong></div>)}</div>
      {!compact && filteredTickets.length > 0 && <div className="campus-record-table-wrap"><table className="campus-record-table"><caption className="sr-only">Danh sách hồ sơ sinh viên</caption><thead><tr><th scope="col">Mã hồ sơ / Dịch vụ</th><th scope="col">Ngày gửi</th><th scope="col">Trạng thái</th><th scope="col">Thao tác</th></tr></thead><tbody>{filteredTickets.map(ticket => <tr key={ticket.id}><td><div className="flex items-center gap-2"><strong>{ticket.code}</strong><button type="button" aria-label={`Sao chép mã ${ticket.code}`} onClick={() => handleCopyCode(ticket.code)}><Copy size={14} /></button></div><span>{ticket.title}</span><small>{ticket.category}</small>{ticket.nextAction && <p className="mt-2 text-amber-700 dark:text-amber-300">{ticket.nextAction}</p>}</td><td>{ticket.createdAt}{ticket.updatedAt && <small>Cập nhật: {ticket.updatedAt}</small>}</td><td><span className={`campus-record-status ${statusLabels[ticket.status]?.badgeClass}`}>{statusLabels[ticket.status]?.label}</span></td><td><button type="button" className="fluent-btn-secondary" aria-label={`Chi tiết ${ticket.code}`} aria-expanded={expandedId === ticket.id} aria-controls={`ticket-detail-${ticket.id}`} onClick={() => toggleDetail(ticket.id)}>{expandedId === ticket.id ? "Thu gọn" : ticket.status === "waiting_student" ? "Bổ sung hồ sơ" : "Xem chi tiết"}</button></td></tr>)}</tbody></table></div>}
      {/* Ticket List View */}
      {tickets.length === 0 ? (
        <div
          role="status"
          className="campus-empty-state flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-[var(--border-color)] bg-[var(--surface-card)] py-14 px-6 text-center text-[var(--text-secondary)] shadow-xs"
        >
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--surface-subtle)] text-[var(--text-secondary)]">
            <ClipboardList className="h-7 w-7" />
          </div>
          <div>
            <p className="mb-1 text-base font-bold text-[var(--text-primary)]">
              Bạn chưa có yêu cầu hỗ trợ nào.
            </p>
            <p className="text-xs text-[var(--text-secondary)]">
              Các phiếu hỗ trợ một cửa số sau khi tạo sẽ hiển thị tại đây.
            </p>
          </div>
        </div>
      ) : filteredTickets.length === 0 ? (
        <div
          role="status"
          className="rounded-2xl border border-[var(--border-color)] bg-[var(--surface-card)] py-10 px-6 text-center text-xs text-[var(--text-secondary)]"
        >
          Không có kết quả phù hợp với bộ lọc đã chọn.
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {filteredTickets.filter(ticket => compact || ticket.id === expandedId).map((ticket) => {
            const isExpanded = expandedId === ticket.id;
            const badge = statusLabels[ticket.status] || statusLabels.submitted;
            const detailId = `ticket-detail-${ticket.id}`;
            const isWaiting = ticket.status === "waiting_student";
            const isDone = ticket.status === "resolved" || ticket.status === "closed";
            const hasSupplementForm = !!isSupplementOpen[ticket.id];
            const alreadySupplied = !!supplementSubmitted[ticket.id];
            const currentRating = ratings[ticket.id] || 5;
            const isRated = !!feedbackSubmitted[ticket.id];

            return (
              <article
                key={ticket.id}
                data-expanded={isExpanded}
                className="campus-ticket-card overflow-hidden fluent-card p-5 transition hover:border-[var(--color-primary-subtle)] sm:p-6"
              >
                {compact && <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-[260px] flex-1">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className="inline-flex items-center gap-1.5 rounded-md bg-[var(--color-primary-subtle)] px-2 py-0.5 text-xs font-bold text-[var(--color-primary)]">
                        <span>{ticket.code}</span>
                        <button
                          type="button"
                          onClick={() => handleCopyCode(ticket.code)}
                          aria-label={`Sao chép mã ${ticket.code}`}
                          title={`Sao chép mã ${ticket.code}`}
                          className="cursor-pointer text-[var(--color-primary)] hover:opacity-80"
                        >
                          📋
                        </button>
                      </span>
                      <span
                        className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badge.badgeClass}`}
                      >
                        {badge.label}
                      </span>
                      <span className="rounded-md bg-[var(--surface-subtle)] border border-[var(--border-color)] px-2.5 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
                        {ticket.category}
                      </span>
                    </div>

                    <h3 className="my-1.5 text-base font-bold text-[var(--text-primary)] sm:text-lg">
                      {ticket.title}
                    </h3>

                    <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--text-secondary)]">
                      <Clock className="h-3.5 w-3.5 text-[var(--text-secondary)]" />
                      <span>Ngày gửi: {ticket.createdAt}</span>
                      {ticket.updatedAt && (
                        <span>· Cập nhật: {ticket.updatedAt}</span>
                      )}
                    </div>

                    {/* Next Action Callout for Student Ownership */}
                    {ticket.nextAction && (
                      <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300">
                        <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                        <div>
                          <span className="font-semibold">Cần thực hiện:</span>{" "}
                          <span>{ticket.nextAction}</span>
                        </div>
                      </div>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => toggleDetail(ticket.id)}
                    aria-expanded={isExpanded}
                    aria-controls={detailId}
                    className={`inline-flex items-center gap-1.5 rounded-xl border px-4 py-2 text-xs font-semibold shadow-xs transition ${
                      isExpanded
                        ? "border-[var(--border-color)] bg-[var(--surface-subtle)] text-[var(--text-primary)]"
                        : "fluent-btn-secondary"
                    }`}
                  >
                    <span>{isExpanded ? "Thu gọn" : "Chi tiết"}</span>
                    {isExpanded ? (
                      <ChevronUp className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5" />
                    )}
                  </button>
                </div>}

                {isExpanded && (
                  <div
                    id={detailId}
                    className="mt-4 flex flex-col gap-4 rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4 text-xs sm:p-5"
                  >
                    <div>
                      <p className="mb-1.5 font-semibold text-[var(--text-primary)]">
                        Nội dung yêu cầu chi tiết:
                      </p>
                      <p className="leading-relaxed text-[var(--text-secondary)]">
                        {ticket.description}
                      </p>
                    </div>

                    {/* Interactive Supplement Form for waiting_student */}
                    {isWaiting && (
                      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/60 dark:bg-amber-950/30">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <div className="font-bold text-amber-900 dark:text-amber-200">
                              ⚠️ Cán bộ đang chờ bạn bổ sung thông tin hồ sơ
                            </div>
                            <div className="mt-0.5 text-amber-800 dark:text-amber-400">
                              {ticket.nextAction ||
                                "Vui lòng phản hồi sớm để quy trình tiếp tục xử lý."}
                            </div>
                          </div>

                          {!alreadySupplied && !hasSupplementForm && (
                            <button
                              type="button"
                              onClick={() =>
                                setIsSupplementOpen((prev) => ({
                                  ...prev,
                                  [ticket.id]: true,
                                }))
                              }
                              className="rounded-lg bg-amber-600 px-3.5 py-1.5 font-semibold text-white shadow-xs transition hover:bg-amber-700 dark:bg-amber-500 dark:hover:bg-amber-600"
                            >
                              Bổ sung thông tin theo yêu cầu
                            </button>
                          )}
                        </div>

                        {alreadySupplied && (
                          <div className="mt-2.5 font-semibold text-emerald-700 dark:text-emerald-400">
                            ✓ Bạn đã gửi bổ sung thông tin. Cán bộ Một cửa đang tiến hành thẩm định.
                          </div>
                        )}

                        {hasSupplementForm && (
                          <div className="mt-3 flex flex-col gap-2.5">
                            <textarea
                              rows={3}
                              placeholder="Nhập nội dung phản hồi hoặc làm rõ thông tin theo yêu cầu cán bộ..."
                              value={supplementTexts[ticket.id] || ""}
                              onChange={(e) =>
                                setSupplementTexts((prev) => ({
                                  ...prev,
                                  [ticket.id]: e.target.value,
                                }))
                              }
                              className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] p-2.5 text-xs text-[var(--text-primary)] focus:border-amber-500 focus:outline-none"
                            />
                            <div className="flex justify-end gap-2">
                              <button
                                type="button"
                                onClick={() =>
                                  setIsSupplementOpen((prev) => ({
                                    ...prev,
                                    [ticket.id]: false,
                                  }))
                                }
                                className="fluent-btn-secondary text-xs"
                              >
                                Đóng
                              </button>
                              <button
                                type="button"
                                onClick={() => handleSubmitSupplement(ticket.id)}
                                className="rounded-md bg-amber-600 px-3.5 py-1 font-semibold text-white transition hover:bg-amber-700 dark:bg-amber-500 dark:hover:bg-amber-600"
                              >
                                Gửi bổ sung cho cán bộ
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* CSAT Satisfaction Rating for Resolved / Closed tickets */}
                    {isDone && (
                      <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4 dark:border-emerald-900/60 dark:bg-emerald-950/30">
                        <h4 className="mb-1 font-bold text-emerald-900 dark:text-emerald-200">
                          ⭐ Đánh giá mức độ hài lòng về kết quả xử lý
                        </h4>
                        <p className="mb-2.5 text-emerald-800 dark:text-emerald-400">
                          Ý kiến của bạn giúp Nhà trường không ngừng nâng cao chất lượng dịch vụ Một cửa số.
                        </p>

                        {isRated ? (
                          <div className="font-semibold text-emerald-700 dark:text-emerald-400">
                            ✓ Cảm ơn bạn đã gửi đánh giá! Nhà trường đã ghi nhận phản hồi của bạn.
                          </div>
                        ) : (
                          <div className="flex flex-col gap-2.5">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold text-emerald-900 dark:text-emerald-300">
                                Chọn số sao:
                              </span>
                              {[1, 2, 3, 4, 5].map((star) => (
                                <button
                                  key={star}
                                  type="button"
                                  onClick={() =>
                                    setRatings((prev) => ({
                                      ...prev,
                                      [ticket.id]: star,
                                    }))
                                  }
                                  aria-label={`${star} sao`}
                                  className={`rounded-md px-2.5 py-1 font-bold transition ${
                                    star <= currentRating
                                      ? "border border-amber-300 bg-amber-100 text-amber-900 dark:border-amber-700 dark:bg-amber-950/80 dark:text-amber-200"
                                      : "border border-[var(--border-color)] bg-[var(--surface-card)] text-[var(--text-secondary)]"
                                  }`}
                                >
                                  ★ {star}
                                </button>
                              ))}
                            </div>

                            <textarea
                              rows={2}
                              placeholder="Ý kiến đóng góp cải tiến chất lượng phục vụ (không bắt buộc)..."
                              value={comments[ticket.id] || ""}
                              onChange={(e) =>
                                setComments((prev) => ({
                                  ...prev,
                                  [ticket.id]: e.target.value,
                                }))
                              }
                              className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] p-2 text-xs text-[var(--text-primary)] focus:border-emerald-500 focus:outline-none"
                            />

                            <button
                              type="button"
                              onClick={() => handleSubmitFeedback(ticket.id)}
                              className="self-start rounded-md bg-emerald-600 px-3.5 py-1.5 font-semibold text-white transition hover:bg-emerald-700 dark:bg-emerald-500 dark:hover:bg-emerald-600"
                            >
                              Gửi đánh giá
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Ordered Public Event History (No Internal Notes) */}
                    {ticket.events && ticket.events.length > 0 && (
                      <div className="border-t border-dashed border-[var(--border-color)] pt-3">
                        <h4 className="mb-2 font-bold text-[var(--text-primary)]">
                          Lịch sử xử lý công khai:
                        </h4>
                        <ol className="flex flex-col gap-1.5 pl-4 text-[var(--text-secondary)]">
                          {ticket.events.map((evt) => (
                            <li key={evt.id} className="leading-relaxed">
                              <span className="font-semibold text-[var(--text-primary)]">
                                {evt.timestamp}
                              </span>
                              {evt.actor && <span> ({evt.actor})</span>}
                              <span>: </span>
                              <span>{evt.description}</span>
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
