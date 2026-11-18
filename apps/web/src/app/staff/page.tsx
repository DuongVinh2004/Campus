"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import React, { useEffect, useState, useCallback } from "react";
import { CheckCircle2, FileCheck2 } from "lucide-react";
import { AppShell } from "../../components/AppShell";
import {
  StaffTicketQueue,
  type StaffQueueItem,
} from "../../features/staff/StaffTicketQueue";
import { AsyncState, type AsyncStatus } from "../../components/AsyncState";
import { ApiClient, ApiClientError } from "../../lib/api/client";
import { staffSurface } from "../../components/staff/StaffShell";
import { CERTIFICATE_DEMO } from "../../lib/data/api/certificate-gateway";
import { CertificateWorkspace } from "../../features/documents/CertificateWorkspace";
import { StaffTicketsConsole } from "../../features/staff/StaffTicketsConsole";
import { OPS_ENABLED } from "../../lib/campus-ops-api";

const API_BASE_URL = CAMPUS_API_BASE_URL;

interface HandoverItemResponse {
  handover_id: string;
  conversation_id: string;
  requester_user_id: string;
  queue_key: string;
  reason_code: string;
  risk_level: string;
  status: string;
  summary_redacted?: string;
  created_at: string;
  assigned_user_id?: string;
}

interface HandoverListResponse {
  items: HandoverItemResponse[];
}

function mapHandoverToQueueItem(handover: HandoverItemResponse): StaffQueueItem {
  let itemStatus: StaffQueueItem["status"] = "unassigned";
  if (handover.assigned_user_id) itemStatus = "assigned";
  if (handover.status.toLowerCase() === "resolved") itemStatus = "resolved";

  let itemPriority: StaffQueueItem["priority"] = "normal";
  if (handover.risk_level === "CRITICAL") itemPriority = "urgent";
  else if (handover.risk_level === "HIGH") itemPriority = "high";

  return {
    id: handover.handover_id,
    ticketCode: `HO-${handover.handover_id.slice(0, 6).toUpperCase()}`,
    studentName: "Sinh viên HUCE",
    studentId: handover.requester_user_id.slice(0, 8),
    title: handover.summary_redacted || handover.reason_code,
    publicContent: handover.summary_redacted || `Yêu cầu hỗ trợ sinh viên: ${handover.reason_code}`,
    internalNotes: `Chuyển giao từ hệ thống tư vấn AI. Mã hàng đợi: ${handover.queue_key}`,
    status: itemStatus,
    assignedStaffId: handover.assigned_user_id,
    priority: itemPriority,
    createdAt: new Date(handover.created_at).toLocaleDateString("vi-VN"),
  };
}

function OpsStaffPage() {
  const [initialId, setInitialId] = useState<string | null>(null);
  useEffect(() => { setInitialId(new URLSearchParams(window.location.search).get("id")); }, []);
  return (
    <AppShell activeNav="staff">
      <div className="campus-page space-y-6">
        <StaffTicketsConsole initialId={initialId} />
      </div>
    </AppShell>
  );
}

export default function StaffPage() {
  if (OPS_ENABLED) return <OpsStaffPage />;
  return CERTIFICATE_DEMO ? <CertificateWorkspace staff /> : <LegacyStaffPage />;
}

function LegacyStaffPage() {
  const [items, setItems] = useState<StaffQueueItem[]>([]);
  const [status, setStatus] = useState<AsyncStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [notification, setNotification] = useState<string | null>(null);
  const currentStaffId = "staff-support-huce-01";

  const showToast = (message: string) => {
    setNotification(message);
    setTimeout(() => {
      setNotification((curr) => (curr === message ? null : curr));
    }, 4000);
  };

  const fetchStaffQueue = useCallback(async () => {
    setStatus("loading");
    setErrorMessage("");

    try {
      const client = new ApiClient({ baseUrl: API_BASE_URL });
      const response = await client.get<HandoverListResponse>("/v1/staff/handovers");

      const rawItems = response.items || [];
      if (rawItems.length === 0) {
        setItems([]);
        setStatus("empty");
        return;
      }

      setItems(rawItems.map(mapHandoverToQueueItem));
      setStatus("success");
    } catch (err: unknown) {
      // Fail honestly: NEVER fabricate demo tickets!
      const detail =
        err instanceof ApiClientError
          ? err.problem.detail || err.problem.title
          : "Không thể tải danh sách hàng đợi. Vui lòng thử lại.";

      setErrorMessage(detail);
      setItems((prev) => {
        if (prev.length > 0) {
          setStatus("stale");
          return prev;
        }
        setStatus("error");
        return [];
      });
    }
  }, []);

  const handleClaimTicket = useCallback((ticketId: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === ticketId
          ? { ...item, status: "assigned", assignedStaffId: currentStaffId }
          : item
      )
    );
    showToast(`Đã nhận xử lý hồ sơ ${ticketId} thành công.`);
  }, []);

  const handleTransferTicket = useCallback((ticketId: string, payload: { targetDepartment: string; transferReason?: string }) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === ticketId
          ? {
              ...item,
              targetDepartment: payload.targetDepartment,
              internalNotes: `${item.internalNotes || ""}\n[Chuyển đơn vị]: Chuyển sang ${payload.targetDepartment}. Lý do: ${payload.transferReason || "Theo thẩm quyền nghiệp vụ"}`,
            }
          : item
      )
    );
    showToast(`Đã chuyển ca ${ticketId} sang ${payload.targetDepartment}.`);
  }, []);

  const handleRequestSupplement = useCallback((ticketId: string, payload: { requestMessage: string }) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === ticketId
          ? {
              ...item,
              internalNotes: `${item.internalNotes || ""}\n[Yêu cầu bổ sung]: ${payload.requestMessage}`,
            }
          : item
      )
    );
    showToast(`Đã gửi thông báo yêu cầu sinh viên bổ sung hồ sơ cho ca ${ticketId}.`);
  }, []);

  const handleFinalizeIntake = useCallback((ticketId: string, payload: { checklistPassed: boolean; exceptionReason?: string }) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === ticketId
          ? {
              ...item,
              status: "in_progress",
              internalNotes: `${item.internalNotes || ""}\n[Checklist đã thẩm định]: Đã nghiệm thu tiếp nhận một cửa lúc ${new Date().toLocaleTimeString("vi-VN")}.${payload.exceptionReason ? ` Ngoại lệ: ${payload.exceptionReason}` : ""}`,
            }
          : item
      )
    );
    showToast(`Đã hoàn tất quy trình tiếp nhận và thẩm định checklist cho hồ sơ ${ticketId}!`);
  }, []);

  useEffect(() => {
    fetchStaffQueue();
  }, [fetchStaffQueue]);

  const unassignedCount = items.filter((i) => i.status === "unassigned").length;
  const urgentCount = items.filter((i) => i.priority === "urgent").length;

  return (
    <AppShell activeNav="staff" userRole="staff">
      <div className="campus-page space-y-5">
        {/* Dynamic Toast Feedback */}
        {notification && (
          <div
            role="status"
            aria-live="polite"
            className="flex items-center gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800 shadow-xs dark:border-emerald-900/60 dark:bg-emerald-950/60 dark:text-emerald-300"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
            <span>{notification}</span>
          </div>
        )}

        {/* Page Header */}
        <header className="campus-page-heading">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--color-primary-light)] text-[var(--color-primary)]">
                <FileCheck2 className="h-4 w-4" aria-hidden="true" />
              </span>
              <h1 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
                Hàng đợi tiếp nhận hỗ trợ cán bộ (HITL)
              </h1>
            </div>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Cơ chế Một cửa số kết hợp Trí tuệ nhân tạo (AI Copilot) & Bộ thẩm định Checklist 6 cổng ISO
            </p>
          </div>

          {/* Quick KPI Counters */}
          <div className="flex items-center gap-3">
            <div className={`${staffSurface} px-4 py-2 text-center shadow-xs border border-[var(--border-color)] bg-[var(--surface-card)]`}>
              <div className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                Chờ tiếp nhận
              </div>
              <div
                className={`mt-0.5 text-xl font-extrabold ${
                  unassignedCount > 0
                    ? "text-[var(--color-primary)]"
                    : "text-emerald-600 dark:text-emerald-400"
                }`}
              >
                {unassignedCount}
              </div>
            </div>

            <div className={`${staffSurface} px-4 py-2 text-center shadow-xs border border-[var(--border-color)] bg-[var(--surface-card)]`}>
              <div className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                Khẩn cấp (SLA &lt; 24h)
              </div>
              <div
                className={`mt-0.5 text-xl font-extrabold ${
                  urgentCount > 0
                    ? "text-rose-600 dark:text-rose-400"
                    : "text-[var(--text-secondary)]"
                }`}
              >
                {urgentCount}
              </div>
            </div>
          </div>
        </header>

        {/* Queue Content inside AsyncState */}
        <AsyncState
          status={status}
          loadingMessage="Đang tải hàng đợi chuyển giao..."
          emptyMessage="Không có yêu cầu hỗ trợ nào đang chờ tiếp nhận."
          errorMessage={errorMessage}
          onRetry={fetchStaffQueue}
        >
          <StaffTicketQueue
            items={items}
            currentStaffId={currentStaffId}
            userRole="STAFF"
            onClaimTicket={handleClaimTicket}
            onTransferTicket={handleTransferTicket}
            onRequestSupplement={handleRequestSupplement}
            onFinalizeIntake={handleFinalizeIntake}
            onRefresh={fetchStaffQueue}
          />
        </AsyncState>
      </div>
    </AppShell>
  );
}
