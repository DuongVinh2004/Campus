"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import React, { useEffect, useState, useCallback, type FormEvent } from "react";
import { AccessibleDialog } from "../../components/shared/AccessibleDialog";
import { AppShell } from "../../components/AppShell";
import { TicketList, type StudentTicket } from "../../features/tickets/TicketList";
import { AsyncState, type AsyncStatus } from "../../components/AsyncState";
import {
  Plus,
  CheckCircle2,
  X,
  ArrowRight,
  Clock,
  AlertTriangle,
} from "lucide-react";
import { ApiClient, ApiClientError } from "../../lib/api/client";
import { CERTIFICATE_DEMO } from "../../lib/data/api/certificate-gateway";
import { CertificateWorkspace } from "../../features/documents/CertificateWorkspace";
import { OperationalServiceWorkspace } from "../../features/documents/OperationalServiceWorkspace";

const API_BASE_URL = CAMPUS_API_BASE_URL;

interface TicketApiResponse {
  items: Array<{
    id: string;
    category: string;
    priority: string;
    status: string;
    subject: string;
    description_redacted?: string;
    created_at: string;
    updated_at: string;
  }>;
}

interface TicketCreateResponse {
  id: string;
  category: string;
  priority: string;
  status: string;
  subject: string;
  description_redacted?: string;
  created_at: string;
  updated_at: string;
}

interface TicketPreviewResponse {
  id?: string;
  preview_id?: string;
  confirmation_token?: string;
  category?: string;
  priority?: string;
  status?: string;
  subject?: string;
  description_redacted?: string;
  created_at?: string;
  updated_at?: string;
}

interface TicketConfirmResponse {
  ticket_id?: string;
  id?: string;
  status?: string;
}

const docTitles: Record<string, string> = {
  xac_nhan_sinh_vien: "Giấy xác nhận sinh viên (mục đích chung)",
  bang_diem_tam_thoi: "Bảng điểm tạm thời (xác nhận học phần đã hoàn thành)",
  gioi_thieu_thuc_tap: "Giấy giới thiệu thực tập doanh nghiệp",
  hoan_nghia_vu_quan_su: "Giấy xác nhận tạm hoãn NVQS",
};

export default function TicketsPage() {
  return process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true" ? <OperationalServiceWorkspace history /> : CERTIFICATE_DEMO ? <CertificateWorkspace /> : <LegacyTicketsPage />;
}

function LegacyTicketsPage() {
  const [tickets, setTickets] = useState<StudentTicket[]>([]);
  const [status, setStatus] = useState<AsyncStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [createNotice, setCreateNotice] = useState<string | null>(null);

  // Form draft state (retained across errors)
  const [step, setStep] = useState<"editing" | "preview">("editing");
  const [documentType, setDocumentType] = useState("xac_nhan_sinh_vien");
  const [deliveryMethod, setDeliveryMethod] = useState("pickup");
  const [quantity, setQuantity] = useState(1);
  const [reason, setReason] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<{
    type: "no_effect" | "result_unknown";
    message: string;
  } | null>(null);

  useEffect(() => {
    if (!isModalOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsModalOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isModalOpen]);

  const fetchTickets = useCallback(async () => {
    setStatus("loading");
    setErrorMessage("");

    try {
      const client = new ApiClient({ baseUrl: API_BASE_URL });
      const response = await client.get<TicketApiResponse>("/v1/tickets");

      const items = response.items || [];
      if (items.length === 0) {
        setTickets([]);
        setStatus("empty");
        return;
      }

      const mappedTickets: StudentTicket[] = items.map((ticketItem) => {
        let normalizedStatus: StudentTicket["status"] = "submitted";
        const statusRaw = ticketItem.status.toLowerCase();
        if (statusRaw === "in_progress") normalizedStatus = "in_progress";
        else if (statusRaw === "waiting_student") normalizedStatus = "waiting_student";
        else if (statusRaw === "resolved") normalizedStatus = "resolved";
        else if (statusRaw === "closed") normalizedStatus = "closed";

        return {
          id: ticketItem.id,
          code: `TK-${ticketItem.id.slice(0, 6).toUpperCase()}`,
          title: ticketItem.subject,
          category: ticketItem.category,
          status: normalizedStatus,
          createdAt: new Date(ticketItem.created_at).toLocaleDateString("vi-VN"),
          description: ticketItem.description_redacted || ticketItem.subject,
        };
      });

      setTickets(mappedTickets);
      setStatus("success");
    } catch (err: unknown) {
      // Fail honestly: NEVER fabricate success or fake demo tickets!
      const detail =
        err instanceof ApiClientError
          ? err.problem.detail || err.problem.title
          : "Không thể kết nối cơ sở dữ liệu phiếu hỗ trợ. Vui lòng thử lại.";

      setErrorMessage(detail);

      setTickets((prev) => {
        if (prev.length > 0) {
          setStatus("stale");
          return prev;
        } else {
          setStatus("error");
          return [];
        }
      });
    }
  }, []);

  const handleProceedToPreview = (e: FormEvent) => {
    e.preventDefault();
    const finalReason = reason.trim();
    if (!finalReason) {
      setValidationError("Vui lòng nhập mục đích xin cấp giấy tờ.");
      return;
    }
    setValidationError(null);
    setSubmitError(null);
    setStep("preview");
  };

  const handleConfirmSubmit = async () => {
    // Prevent duplicate submission during flight or when result is pending unknown reconciliation
    if (isSubmitting || submitError?.type === "result_unknown") {
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    const docName = docTitles[documentType] || "giấy tờ";
    const subject = `Xin cấp ${docName} (${quantity} bản)`;

    try {
      const client = new ApiClient({ baseUrl: API_BASE_URL });

      const ticketPayload = {
        category: "DOCUMENT_REQUEST",
        subject,
        description: reason.trim(),
        priority: "normal",
      };

      const previewResponse = await client.post<TicketPreviewResponse>(
        "/v1/tickets/preview",
        ticketPayload
      );

      let response: TicketCreateResponse;
      if (previewResponse?.id) {
        response = {
          id: previewResponse.id,
          category: previewResponse.category || "DOCUMENT_REQUEST",
          priority: previewResponse.priority || "normal",
          status: previewResponse.status || "submitted",
          subject: previewResponse.subject || subject,
          description_redacted: previewResponse.description_redacted || reason.trim(),
          created_at: previewResponse.created_at || new Date().toISOString(),
          updated_at: previewResponse.updated_at || new Date().toISOString(),
        };
      } else {
        const previewId = previewResponse.preview_id || "";
        const confirmRes = await client.post<TicketConfirmResponse>(
          `/v1/tickets/${previewId}/confirm`,
          {
            confirmation_token: previewResponse.confirmation_token,
            idempotency_key: `idem-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
            payload: ticketPayload,
          }
        );
        response = {
          id: confirmRes.ticket_id || confirmRes.id || previewId,
          category: "DOCUMENT_REQUEST",
          priority: "normal",
          status: confirmRes.status || "submitted",
          subject,
          description_redacted: reason.trim(),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
      }

      // Authoritative response handling
      const createdTicket: StudentTicket = {
        id: response.id,
        code: `TK-${response.id.slice(0, 6).toUpperCase()}`,
        title: response.subject || subject,
        category: response.category || "Thủ tục hành chính",
        status: "submitted",
        createdAt: new Date(response.created_at || Date.now()).toLocaleDateString("vi-VN"),
        description: response.description_redacted || reason.trim(),
      };

      setTickets((prev) => [createdTicket, ...prev]);
      setIsModalOpen(false);
      setStep("editing");
      setReason("");
      setCreateNotice(`Đã gửi yêu cầu thành công! Mã yêu cầu: ${createdTicket.code}`);
      setStatus("success");
    } catch (err: unknown) {
      // Fail honestly: Never fabricate receipt! Retain form draft!
      if (err instanceof ApiClientError) {
        const isTimeoutOrNetwork =
          err.problem.code === "TIMEOUT" ||
          err.problem.status === 504 ||
          err.problem.status === 0;

        if (isTimeoutOrNetwork) {
          setSubmitError({
            type: "result_unknown",
            message:
              "Kết quả chưa xác định do mất kết nối hoặc hết thời gian chờ phản hồi. Hệ thống đang kiểm tra trạng thái yêu cầu, vui lòng không gửi lại để tránh trùng lặp.",
          });
        } else {
          setSubmitError({
            type: "no_effect",
            message:
              err.problem.detail ||
              "Gửi yêu cầu thất bại. Dữ liệu chưa được ghi nhận trên máy chủ.",
          });
        }
      } else {
        setSubmitError({
          type: "no_effect",
          message: "Gửi yêu cầu thất bại do lỗi không xác định.",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  return (
    <AppShell activeNav="tickets">
      <div className="campus-page">
        <header className="campus-page-heading">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)] sm:text-3xl">
              Yêu cầu hỗ trợ sinh viên
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Theo dõi tiến độ xử lý hồ sơ một cửa và các thủ tục học vụ của bạn
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              setIsModalOpen(true);
              setSubmitError(null);
            }}
            className="fluent-btn-primary text-xs"
          >
            <Plus className="h-4 w-4" />
            <span>Tạo yêu cầu mới</span>
          </button>
        </header>

        {createNotice && (
          <div
            role="status"
            className="mb-5 flex items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs font-semibold text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300"
          >
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
              <span>{createNotice}</span>
            </div>
            <button
              type="button"
              onClick={() => setCreateNotice(null)}
              className="rounded-lg p-1 text-emerald-700 hover:bg-emerald-100 dark:text-emerald-300 dark:hover:bg-emerald-900/40"
              aria-label="Đóng thông báo"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        <AsyncState
          status={status}
          loadingMessage="Đang tải danh sách hồ sơ của bạn..."
          emptyMessage="Bạn chưa có hồ sơ nào. Khi cần hỗ trợ thủ tục, bạn hãy bấm 'Tạo yêu cầu mới' nhé."
          errorMessage={errorMessage}
          onRetry={fetchTickets}
        >
          <TicketList tickets={tickets} />
        </AsyncState>

        {/* Modal Đăng ký Giấy tờ Sinh viên với Fail Honestly Architecture */}
        {isModalOpen && (
          <AccessibleDialog open onClose={() => { if (!isSubmitting) setIsModalOpen(false); }} preventClose={isSubmitting} labelledBy="request-form-title" className="campus-request-dialog">
            <div className="relative max-h-[90vh] w-full max-w-xl overflow-y-auto fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-6 shadow-2xl sm:p-7">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                aria-label="Đóng"
                className="absolute top-5 right-5 flex h-9 w-9 items-center justify-center rounded-full bg-[var(--surface-subtle)] text-[var(--text-secondary)] transition hover:text-[var(--text-primary)]"
              >
                <X className="h-4 w-4" />
              </button>

              <h2
                id="request-form-title"
                className="mb-5 text-lg font-bold tracking-tight text-[var(--text-primary)]"
              >
                Tạo yêu cầu cấp giấy tờ hành chính
              </h2>

              {/* Submit Error Presentation: Distinguish No-Effect from Result-Unknown */}
              {submitError && (
                <div
                  role="alert"
                  className={`mb-4 rounded-xl border p-3.5 text-xs leading-relaxed ${
                    submitError.type === "result_unknown"
                      ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200"
                      : "border-rose-200 bg-rose-50 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200"
                  }`}
                >
                  <div className="mb-1 flex items-center gap-2 font-bold">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    <span>
                      {submitError.type === "result_unknown"
                        ? "[?] Kết quả chưa xác định"
                        : "[!] Gửi yêu cầu thất bại (Chưa ghi nhận)"}
                    </span>
                  </div>
                  <div>{submitError.message}</div>
                </div>
              )}

              {/* Form Step: Editing vs Preview */}
              {step === "editing" ? (
                <form
                  onSubmit={handleProceedToPreview}
                  className="flex flex-col gap-4 text-xs"
                >
                  {validationError && (
                    <div
                      role="alert"
                      className="rounded-lg border border-rose-200 bg-rose-50 p-3 font-medium text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300"
                    >
                      {validationError}
                    </div>
                  )}

                  <div className="flex flex-col gap-1.5">
                    <label
                      htmlFor="doc-type"
                      className="font-semibold text-[var(--text-primary)]"
                    >
                      Loại giấy tờ <span className="text-rose-500">*</span>
                    </label>
                    <select
                      id="doc-type"
                      value={documentType}
                      onChange={(e) => setDocumentType(e.target.value)}
                      className="fluent-input min-h-[42px] text-xs"
                    >
                      <option value="xac_nhan_sinh_vien">
                        Giấy xác nhận sinh viên (mục đích chung)
                      </option>
                      <option value="bang_diem_tam_thoi">
                        Bảng điểm tạm thời (xác nhận học phần đã hoàn thành)
                      </option>
                      <option value="gioi_thieu_thuc_tap">
                        Giấy giới thiệu thực tập doanh nghiệp
                      </option>
                      <option value="hoan_nghia_vu_quan_su">
                        Giấy xác nhận tạm hoãn NVQS
                      </option>
                    </select>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label
                      htmlFor="delivery-method"
                      className="font-semibold text-[var(--text-primary)]"
                    >
                      Phương thức nhận kết quả <span className="text-rose-500">*</span>
                    </label>
                    <select
                      id="delivery-method"
                      value={deliveryMethod}
                      onChange={(e) => setDeliveryMethod(e.target.value)}
                      className="fluent-input min-h-[42px] text-xs"
                    >
                      <option value="pickup">
                        Nhận trực tiếp tại bộ phận Một cửa (Phòng 102 - Tòa H1)
                      </option>
                      <option value="email">
                        Bản điện tử (PDF gửi qua email sinh viên)
                      </option>
                    </select>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label
                      htmlFor="quantity"
                      className="font-semibold text-[var(--text-primary)]"
                    >
                      Số lượng bản <span className="text-rose-500">*</span>
                    </label>
                    <input
                      id="quantity"
                      type="number"
                      min={1}
                      max={5}
                      value={quantity}
                      onChange={(e) =>
                        setQuantity(Math.max(1, Math.min(5, Number(e.target.value))))
                      }
                      className="fluent-input min-h-[42px] w-24 text-xs"
                    />
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label
                      htmlFor="reason"
                      className="font-semibold text-[var(--text-primary)]"
                    >
                      Mục đích xin cấp <span className="text-rose-500">*</span>
                    </label>
                    <textarea
                      id="reason"
                      rows={3}
                      value={reason}
                      onChange={(e) => {
                        setReason(e.target.value);
                        if (validationError) setValidationError(null);
                        if (submitError) setSubmitError(null);
                      }}
                      placeholder="Ví dụ: Vay vốn sinh viên, hồ sơ xin thực tập..."
                      className="fluent-input w-full p-3 text-xs leading-relaxed"
                    />
                  </div>

                  <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                      <Clock className="h-4 w-4" />
                      <span>Xử lý: 1 - 2 ngày làm việc</span>
                    </div>

                    <button
                      type="submit"
                      className="fluent-btn-primary min-h-[42px] text-xs font-semibold"
                    >
                      <span>Xem trước yêu cầu</span>
                      <ArrowRight className="h-4 w-4" />
                    </button>
                  </div>
                </form>
              ) : (
                <div className="flex flex-col gap-5 text-xs">
                  <dl className="flex flex-col gap-3 rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4">
                    <div>
                      <dt className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase">
                        Loại giấy tờ
                      </dt>
                      <dd className="mt-0.5 font-bold text-[var(--text-primary)]">
                        {docTitles[documentType] || documentType}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase">
                        Phương thức nhận
                      </dt>
                      <dd className="mt-0.5 text-[var(--text-primary)]">
                        {deliveryMethod === "pickup"
                          ? "Nhận trực tiếp tại Một cửa (Phòng 102 - Tòa H1)"
                          : "Bản điện tử (PDF)"}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase">
                        Số lượng
                      </dt>
                      <dd className="mt-0.5 text-[var(--text-primary)]">
                        {quantity} bản
                      </dd>
                    </div>

                    <div>
                      <dt className="text-[11px] font-semibold text-[var(--text-secondary)] uppercase">
                        Mục đích xin cấp
                      </dt>
                      <dd className="mt-0.5 font-medium text-[var(--text-primary)]">
                        {reason}
                      </dd>
                    </div>
                  </dl>

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        setStep("editing");
                        setSubmitError(null);
                      }}
                      disabled={isSubmitting}
                      className="fluent-btn-secondary min-h-[42px] text-xs font-semibold"
                    >
                      Quay lại chỉnh sửa
                    </button>

                    <button
                      type="button"
                      onClick={handleConfirmSubmit}
                      disabled={isSubmitting || submitError?.type === "result_unknown"}
                      className="fluent-btn-primary min-h-[42px] text-xs font-semibold"
                    >
                      {isSubmitting ? "Đang gửi..." : "Gửi yêu cầu"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </AccessibleDialog>
        )}
      </div>
    </AppShell>
  );
}
