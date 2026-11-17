"use client";

import { AccessibleDialog } from "../../components/shared/AccessibleDialog";
import React, { useState, useEffect, useCallback } from "react";
import {
  Search,
  RefreshCw,
  AlertTriangle,
  Sparkles,
  Printer,
  ChevronDown,
  ChevronUp,
  Copy,
  RotateCcw,
  X,
} from "lucide-react";
import {
  staffButton,
  staffPrimary,
  staffField,
  staffSurface,
} from "../../components/staff/StaffShell";

export interface StaffAttachment {
  name: string;
  ocrBadge: string;
  confidence: string;
  type?: "pdf" | "image";
  evidence?: { state: "unchecked" | "checked" | "missing_source" | "error" | "conflicting"; reason: string; locator?: string; version?: string };
}

export interface StaffQueueItem {
  id: string;
  ticketCode: string;
  studentName: string;
  studentId: string;
  title: string;
  status: "unassigned" | "assigned" | "in_progress" | "resolved";
  assignedStaffId?: string;
  priority: "normal" | "high" | "urgent";
  createdAt: string;
  version?: number;
  isStale?: boolean;
  actionOutcome?: "idle" | "succeeded" | "failed" | "unknown";
  age?: string;
  publicContent?: string;
  internalNotes?: string;
  isRestricted?: boolean;
  hasConflict?: boolean;
  conflictStaffId?: string;
  targetDepartment?: string;
  attachments?: StaffAttachment[];
  classification?: "synthetic" | "live";
  sla?: { deadline: string; locator: string; version: string };
}

export interface StaffTicketQueueProps {
  items?: StaffQueueItem[];
  currentStaffId?: string;
  userRole?: string;
  onClaimTicket?: (queueId: string) => Promise<void> | void;
  onRefresh?: () => void;
  onTransferTicket?: (queueId: string, payload: { targetDepartment: string; transferReason?: string }) => void;
  onRequestSupplement?: (queueId: string, payload: { requestMessage: string }) => void;
  onFinalizeIntake?: (queueId: string, payload: { checklistPassed: boolean; exceptionReason?: string }) => void;
  onReconcile?: (queueId: string) => void;
  businessActionsAvailable?: boolean;
}

type FilterType = "all" | "unassigned" | "my" | "urgent";
type SortType = "default" | "urgent" | "wait";

interface IntakeGate {
  id: string;
  label: string;
  sourceBadge: string;
  sourceBadgeClass: string;
  aiEvidence: string;
  confidence: string;
}

const INTAKE_CHECKLIST_GATES: IntakeGate[] = [
  {
    id: "gate_identity",
    label: "Xác minh danh tính & MSSV qua tài khoản định danh",
    sourceBadge: "Chưa kiểm định danh",
    sourceBadgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800",
    aiEvidence: "Cần đối chiếu nguồn định danh được cấp quyền.",
    confidence: "Chưa xác minh",
  },
  {
    id: "gate_scope",
    label: "Kiểm tra thẩm quyền xử lý Một cửa số (tránh nhận nhầm phạm vi)",
    sourceBadge: "Cần nguồn thẩm quyền",
    sourceBadgeClass: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-800",
    aiEvidence: "Cán bộ đối chiếu phạm vi và quy trình áp dụng.",
    confidence: "Chưa xác minh",
  },
  {
    id: "gate_duplicate",
    label: "Kiểm tra tiền sử đơn trùng lặp trong 30 ngày qua",
    sourceBadge: "Lịch sử Hệ thống",
    sourceBadgeClass: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800",
    aiEvidence: "Chưa có kết quả truy vấn đơn trùng lặp được xác minh.",
    confidence: "Chưa kiểm",
  },
  {
    id: "gate_attachment",
    label: "Kiểm tra tính hợp lệ minh chứng đính kèm (dấu đỏ, ảnh, văn bản)",
    sourceBadge: "OCR chưa cấu hình",
    sourceBadgeClass: "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/60 dark:text-purple-300 dark:border-purple-800",
    aiEvidence: "Đối chiếu tài liệu thủ công; chưa xác minh chữ ký hoặc con dấu.",
    confidence: "Chưa kiểm",
  },
  {
    id: "gate_sla",
    label: "Xác định mức độ khẩn cấp & thời hạn cam kết SLA tiếp nhận",
    sourceBadge: "Cần nguồn thời hạn",
    sourceBadgeClass: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800",
    aiEvidence: "Chưa có thời hạn xử lý đã được ràng buộc với nguồn áp dụng.",
    confidence: "Thiếu nguồn",
  },
  {
    id: "gate_privacy",
    label: "Rà soát thông tin nhạy cảm trước khi xử lý theo Nghị định 13",
    sourceBadge: "Cán bộ kiểm tra",
    sourceBadgeClass: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800",
    aiEvidence: "Cần đối chiếu phạm vi dữ liệu và quyền truy cập trước khi chia sẻ.",
    confidence: "Chưa kiểm",
  },
];

export interface AuditLogEntry {
  timestamp: string;
  staffId: string;
  ticketId: string;
  action: string;
  detail: string;
}

const LS_CHECKED_GATES = "campus247_checkedGates";
const LS_EXCEPTION_REASONS = "campus247_exceptionReasons";
const LS_FINALIZED = "campus247_finalizedTickets";
const LS_AUDIT_LOG = "campus247_auditLog";
const LS_GATE_TIMESTAMPS = "campus247_gateTimestamps";

function loadLS<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function saveLS<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // quota exceeded — silently ignore
  }
}

function getSlaInfo(item: StaffQueueItem): { remaining: string; urgencyColor: string; percentUsed: number } {
  const unverified = { remaining: "Chưa xác minh thời hạn", urgencyColor: "text-slate-500", percentUsed: 0 };
  if (!item.sla?.locator || !item.sla.version) return unverified;
  const created = new Date(item.createdAt), deadline = new Date(item.sla.deadline);
  const totalMs = deadline.getTime() - created.getTime();
  if (!Number.isFinite(totalMs) || totalMs <= 0) return unverified;
  const diffMs = deadline.getTime() - Date.now();
  const diffH = Math.floor(diffMs / (1000 * 60 * 60));
  const diffM = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
  const percentUsed = Math.min(100, Math.max(0, ((totalMs - diffMs) / totalMs) * 100));

  if (diffMs <= 0) return { remaining: "QUÁ HẠN", urgencyColor: "text-rose-600 dark:text-rose-400", percentUsed: 100 };
  if (diffH < 1) return { remaining: `${diffM} phút`, urgencyColor: "text-rose-600 dark:text-rose-400", percentUsed };
  if (diffH < 4) return { remaining: `${diffH}h ${diffM}p`, urgencyColor: "text-amber-600 dark:text-amber-400", percentUsed };
  return { remaining: `${diffH}h ${diffM}p`, urgencyColor: "text-emerald-600 dark:text-emerald-400", percentUsed };
}

export function StaffTicketQueue({
  items = [],
  currentStaffId = "",
  userRole,
  onClaimTicket,
  onRefresh,
  onTransferTicket,
  onRequestSupplement,
  onFinalizeIntake,
  onReconcile,
  businessActionsAvailable = false,
}: StaffTicketQueueProps) {
  if (userRole && userRole !== "STAFF" && userRole !== "ADMIN") {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900 shadow-xs dark:border-red-900/60 dark:bg-red-950/60 dark:text-red-200"
      >
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-600 dark:text-red-400" aria-hidden="true" />
          <div>
            <h3 className="mb-2 text-lg font-bold">Từ chối quyền truy cập</h3>
            <p className="text-sm leading-relaxed text-red-800 dark:text-red-300">
              Bạn không có thẩm quyền truy cập hàng đợi cán bộ một cửa. Chức năng này chỉ dành cho tài khoản có vai trò Cán bộ tiếp nhận hoặc Quản trị viên hệ thống.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const [filter, setFilter] = useState<FilterType>("all");
  const [sortBy, setSortBy] = useState<SortType>("default");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({});

  const [checkedGates, setCheckedGates] = useState<Record<string, Record<string, boolean>>>(() => loadLS(LS_CHECKED_GATES, {}));
  const [exceptionReasons, setExceptionReasons] = useState<Record<string, string>>(() => loadLS(LS_EXCEPTION_REASONS, {}));
  const [finalizedTickets, setFinalizedTickets] = useState<Record<string, boolean>>(() => loadLS(LS_FINALIZED, {}));
  const [gateTimestamps, setGateTimestamps] = useState<Record<string, Record<string, string>>>(() => loadLS(LS_GATE_TIMESTAMPS, {}));
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>(() => loadLS(LS_AUDIT_LOG, []));

  const [showAuditLog, setShowAuditLog] = useState(false);

  const [, setTimerTick] = useState(0);
  useEffect(() => {
    const interval = setInterval(() => setTimerTick((t) => t + 1), 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => { saveLS(LS_CHECKED_GATES, checkedGates); }, [checkedGates]);
  useEffect(() => { saveLS(LS_EXCEPTION_REASONS, exceptionReasons); }, [exceptionReasons]);
  useEffect(() => { saveLS(LS_FINALIZED, finalizedTickets); }, [finalizedTickets]);
  useEffect(() => { saveLS(LS_GATE_TIMESTAMPS, gateTimestamps); }, [gateTimestamps]);
  useEffect(() => { saveLS(LS_AUDIT_LOG, auditLog); }, [auditLog]);

  const addAuditEntry = useCallback((ticketId: string, action: string, detail: string) => {
    const entry: AuditLogEntry = {
      timestamp: new Date().toISOString(),
      staffId: currentStaffId || "unknown",
      ticketId,
      action,
      detail,
    };
    setAuditLog((prev) => [entry, ...prev].slice(0, 200));
  }, [currentStaffId]);

  const [transferModalId, setTransferModalId] = useState<string | null>(null);
  const [targetDept, setTargetDept] = useState("phong_dao_tao");
  const [transferReason, setTransferReason] = useState("");

  const [supplementModalId, setSupplementModalId] = useState<string | null>(null);
  const [supplementMsg, setSupplementMsg] = useState("");

  const [aiDraftModalId, setAiDraftModalId] = useState<string | null>(null);
  const [aiDraftType, setAiDraftType] = useState<"approve" | "supplement" | "forward">("approve");
  const [aiDraftContent, setAiDraftContent] = useState("");
  const [draftCopied, setDraftCopied] = useState(false);

  const [receiptModalId, setReceiptModalId] = useState<string | null>(null);

  const getAiDraftText = (type: "approve" | "supplement" | "forward", item: StaffQueueItem) => {
    if (type === "approve") {
      return `Bản nháp cần cán bộ kiểm tra.\n\nChào bạn ${item.studentName} (MSSV: ${item.studentId}),\nHồ sơ ${item.ticketCode}: ${item.title}. Cán bộ đang đối chiếu thông tin và nguồn áp dụng.\n[Điền kết quả đã xác minh và thời hạn có căn cứ trước khi gửi.]`;
    } else if (type === "supplement") {
      return `Bản nháp cần cán bộ kiểm tra.\n\nChào bạn ${item.studentName}, hồ sơ ${item.ticketCode}: ${item.title}.\n[Cán bộ ghi rõ thông tin cần bổ sung, lý do và nguồn áp dụng; chưa xác định thời hạn.]`;
    } else {
      return `Bản nháp cần cán bộ kiểm tra.\n\nHồ sơ ${item.ticketCode}: ${item.title}.\n[Cán bộ xác minh đơn vị có thẩm quyền và receipt chuyển hồ sơ trước khi thông báo.]`;
    }
  };

  const handleOpenAiDraft = (item: StaffQueueItem) => {
    setAiDraftModalId(item.id);
    setAiDraftType("approve");
    setAiDraftContent(getAiDraftText("approve", item));
    setDraftCopied(false);
  };

  const handleAiDraftTypeChange = (type: "approve" | "supplement" | "forward", item: StaffQueueItem) => {
    setAiDraftType(type);
    setAiDraftContent(getAiDraftText(type, item));
    setDraftCopied(false);
  };

  const handleCopyDraft = async () => {
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(aiDraftContent);
        setDraftCopied(true);
        setTimeout(() => setDraftCopied(false), 3000);
      }
    } catch {
      // Fallback
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedItems((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const handleGateToggle = (ticketId: string, gateId: string) => {
    const wasChecked = !!checkedGates[ticketId]?.[gateId];
    setCheckedGates((prev) => ({
      ...prev,
      [ticketId]: {
        ...(prev[ticketId] || {}),
        [gateId]: !wasChecked,
      },
    }));
    if (!wasChecked) {
      setGateTimestamps((prev) => ({
        ...prev,
        [ticketId]: {
          ...(prev[ticketId] || {}),
          [gateId]: new Date().toISOString(),
        },
      }));
      const gate = INTAKE_CHECKLIST_GATES.find((g) => g.id === gateId);
      addAuditEntry(ticketId, "GATE_CHECK", `Đã xác nhận: ${gate?.label || gateId}`);
    } else {
      setGateTimestamps((prev) => {
        const copy = { ...(prev[ticketId] || {}) };
        delete copy[gateId];
        return { ...prev, [ticketId]: copy };
      });
      const gate = INTAKE_CHECKLIST_GATES.find((g) => g.id === gateId);
      addAuditEntry(ticketId, "GATE_UNCHECK", `Bỏ xác nhận: ${gate?.label || gateId}`);
    }
  };

  const handleAiAutoCheck = (ticketId: string) => {
    addAuditEntry(ticketId, "AI_UNAVAILABLE", "Chưa có consumer kiểm chứng; cán bộ cần đối chiếu từng mục, không tự đánh dấu kiểm tra.");
  };

  const isChecklistComplete = (ticketId: string) => {
    const ticketGates = checkedGates[ticketId] || {};
    const checkedCount = INTAKE_CHECKLIST_GATES.filter((g) => !!ticketGates[g.id]).length;
    return checkedCount === INTAKE_CHECKLIST_GATES.length;
  };

  const handleFinalize = (ticketId: string) => {
    if (!businessActionsAvailable || !onFinalizeIntake) return;
    const complete = isChecklistComplete(ticketId);
    if (!complete) return;
    onFinalizeIntake?.(ticketId, {
      checklistPassed: true,
      exceptionReason: exceptionReasons[ticketId] || undefined,
    });
    setFinalizedTickets((prev) => ({ ...prev, [ticketId]: true }));
    addAuditEntry(ticketId, "FINALIZE_INTAKE", `Hoàn tất tiếp nhận. ${exceptionReasons[ticketId] ? `Ngoại lệ: ${exceptionReasons[ticketId]}` : "Đủ 6/6 cổng"}`);
  };

  const handleConfirmTransfer = (ticketId: string) => {
    if (!businessActionsAvailable || !onTransferTicket) return;
    onTransferTicket?.(ticketId, {
      targetDepartment: targetDept,
      transferReason: transferReason || undefined,
    });
    addAuditEntry(ticketId, "TRANSFER", `Chuyển sang ${targetDept}. Lý do: ${transferReason || "Theo thẩm quyền"}`);
    setTransferModalId(null);
    setTransferReason("");
  };

  const handleConfirmSupplement = (ticketId: string) => {
    if (!businessActionsAvailable || !onRequestSupplement) return;
    if (!supplementMsg.trim()) return;
    onRequestSupplement?.(ticketId, { requestMessage: supplementMsg.trim() });
    addAuditEntry(ticketId, "SUPPLEMENT_REQUEST", `Yêu cầu SV bổ sung: ${supplementMsg.trim().slice(0, 80)}...`);
    setSupplementModalId(null);
    setSupplementMsg("");
  };

  const filteredItems = items
    .filter((item) => {
      if (filter === "unassigned") return item.status === "unassigned";
      if (filter === "my") return item.assignedStaffId === currentStaffId;
      if (filter === "urgent") return item.priority === "urgent";
      return true;
    })
    .filter((item) => {
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        item.ticketCode.toLowerCase().includes(q) ||
        item.studentName.toLowerCase().includes(q) ||
        item.studentId.toLowerCase().includes(q) ||
        item.title.toLowerCase().includes(q) ||
        (item.publicContent && item.publicContent.toLowerCase().includes(q))
      );
    })
    .sort((a, b) => {
      if (sortBy === "urgent") {
        const priorityOrder: Record<StaffQueueItem["priority"], number> = { urgent: 0, high: 1, normal: 2 };
        return priorityOrder[a.priority] - priorityOrder[b.priority];
      }
      return 0;
    });

  const getPriorityBadge = (priority: StaffQueueItem["priority"]) => {
    switch (priority) {
      case "urgent":
        return {
          text: "[!] Khẩn cấp",
          className: "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/60 dark:text-red-300 dark:border-red-800",
        };
      case "high":
        return {
          text: "[▲] Cao",
          className: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800",
        };
      case "normal":
      default:
        return {
          text: "[•] Thường",
          className: "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
        };
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm text-amber-800 dark:text-amber-200">Checklist cục bộ cần đối chiếu nguồn trước khi xử lý. Dữ liệu mô phỏng phải được nhận diện theo hồ sơ; trạng thái chưa có bằng chứng luôn là chưa xác minh.</p>
      {!businessActionsAvailable && <p role="status" className="text-sm">Hàng đợi này chưa có consumer nghiệp vụ bền vững. Tiếp nhận, chuyển, yêu cầu bổ sung và hoàn tất đang khóa; mở workspace nghiệp vụ có hỗ trợ hoặc liên hệ đơn vị phụ trách để xử lý thủ công.</p>}
      {/* Header and Staff Identity */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Hàng đợi tiếp nhận yêu cầu (Cán bộ một cửa)
          </h2>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Không gian phân loại mật độ cao với kiểm soát quyền sở hữu và giải quyết xung đột
          </p>
        </div>

        <div className="flex items-center gap-3">
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              aria-label="Làm mới hàng đợi"
              className={staffButton}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              <span>Làm mới</span>
            </button>
          )}

          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3.5 py-1.5 text-xs text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
            <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
            <span>
              Cán bộ trực: <strong>{currentStaffId || "Chưa xác định"}</strong>
            </span>
          </div>
        </div>
      </div>

      {/* Search & Sort Toolbar */}
      <div className={`${staffSurface} flex flex-wrap items-center justify-between gap-3 p-3 shadow-xs`}>
        <div className="relative min-w-[280px] flex-1">
          <span className="sr-only">Tìm theo mã, tên sinh viên hoặc tiêu đề...</span>
          <Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" aria-hidden="true" />
          <input
            type="search"
            placeholder="Tìm theo mã, tên sinh viên hoặc tiêu đề..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={`${staffField} pl-9`}
          />
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="sort-queue" className="whitespace-nowrap text-xs font-semibold text-slate-600 dark:text-slate-400">
            Sắp xếp:
          </label>
          <select
            id="sort-queue"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortType)}
            className="min-h-10 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="default">Theo thứ tự tiếp nhận</option>
            <option value="urgent">Độ khẩn cấp ưu tiên</option>
          </select>
        </div>
      </div>

      {/* Accessible Segmented Filter Tabs */}
      <div
        role="tablist"
        aria-label="Bộ lọc hàng đợi tiếp nhận"
        className="flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1 dark:bg-slate-800/80"
      >
        <button
          type="button"
          role="tab"
          id="tab-all"
          aria-selected={filter === "all"}
          aria-controls="queue-panel"
          onClick={() => setFilter("all")}
          className={`rounded-lg px-4 py-1.5 text-xs font-semibold transition ${
            filter === "all"
              ? "bg-white text-blue-700 shadow-xs dark:bg-slate-900 dark:text-blue-300"
              : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          Tất cả ({items.length})
        </button>
        <button
          type="button"
          role="tab"
          id="tab-unassigned"
          aria-selected={filter === "unassigned"}
          aria-controls="queue-panel"
          onClick={() => setFilter("unassigned")}
          className={`rounded-lg px-4 py-1.5 text-xs font-semibold transition ${
            filter === "unassigned"
              ? "bg-white text-blue-700 shadow-xs dark:bg-slate-900 dark:text-blue-300"
              : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          Chưa nhận
        </button>
        <button
          type="button"
          role="tab"
          id="tab-my"
          aria-selected={filter === "my"}
          aria-controls="queue-panel"
          onClick={() => setFilter("my")}
          className={`rounded-lg px-4 py-1.5 text-xs font-semibold transition ${
            filter === "my"
              ? "bg-white text-blue-700 shadow-xs dark:bg-slate-900 dark:text-blue-300"
              : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          Ca của tôi
        </button>
        <button
          type="button"
          role="tab"
          id="tab-urgent"
          aria-selected={filter === "urgent"}
          aria-controls="queue-panel"
          onClick={() => setFilter("urgent")}
          className={`rounded-lg px-4 py-1.5 text-xs font-semibold transition ${
            filter === "urgent"
              ? "bg-white text-blue-700 shadow-xs dark:bg-slate-900 dark:text-blue-300"
              : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
          }`}
        >
          Khẩn cấp
        </button>
      </div>

      {/* Queue Table */}
      <div
        id="queue-panel"
        role="region"
        aria-label="Danh sách yêu cầu tiếp nhận"
        className={`${staffSurface} overflow-x-auto shadow-xs`}
      >
        <table className="campus-staff-table w-full text-left text-sm fluent-table">
          <thead className="bg-slate-50 text-xs font-medium uppercase tracking-wider text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            <tr>
              <th scope="col" className="px-4 py-3.5">Mã yêu cầu</th>
              <th scope="col" className="px-4 py-3.5">Sinh viên</th>
              <th scope="col" className="px-4 py-3.5">Nội dung & Thời gian chờ</th>
              <th scope="col" className="px-4 py-3.5">Ưu tiên</th>
              <th scope="col" className="px-4 py-3.5">Trạng thái</th>
              <th scope="col" className="px-4 py-3.5">Hành động</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {filteredItems.map((item) => {
              const isUnassigned = item.status === "unassigned";
              const isMyItem = item.assignedStaffId === currentStaffId;
              const hasConflict = item.hasConflict === true;
              const isRestricted = item.isRestricted === true;
              const isStale = item.isStale === true;
              const isUnknown = item.actionOutcome === "unknown";
              const canClaim = businessActionsAvailable && isUnassigned && !hasConflict && !isRestricted && !isStale && !isUnknown;
              const isExpanded = !!expandedItems[item.id];
              const priorityBadge = getPriorityBadge(item.priority);

              const ticketGates = checkedGates[item.id] || {};
              const checkedCount = INTAKE_CHECKLIST_GATES.filter((g) => !!ticketGates[g.id]).length;
              const checklistDone = isChecklistComplete(item.id);
              const isFinalized = !!finalizedTickets[item.id];
              const sla = getSlaInfo(item);

              return (
                <React.Fragment key={item.id}>
                  <tr
                    className={`align-top transition ${
                      hasConflict || isStale
                        ? "bg-amber-50/50 dark:bg-amber-950/30"
                        : isRestricted
                        ? "bg-slate-50/60 dark:bg-slate-900/60"
                        : "hover:bg-slate-50/60 dark:hover:bg-slate-800/40"
                    }`}
                  >
                    <td className="px-4 py-3.5 font-bold text-blue-700 dark:text-blue-300">
                      <div>{item.ticketCode}</div>
                      <p className="text-xs text-slate-500">{item.classification === "synthetic" ? "Dữ liệu mô phỏng" : item.classification === "live" ? "Hồ sơ nghiệp vụ" : "Chưa xác minh phân loại dữ liệu"}</p>
                      <button
                        type="button"
                        onClick={() => toggleExpand(item.id)}
                        aria-expanded={isExpanded}
                        aria-label={`Chi tiết ${item.ticketCode}`}
                        className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-blue-600 hover:underline dark:text-slate-400"
                      >
                        {isExpanded ? (
                          <>
                            <ChevronUp className="h-3 w-3" aria-hidden="true" />
                            <span>▲ Thu gọn</span>
                          </>
                        ) : (
                          <>
                            <ChevronDown className="h-3 w-3" aria-hidden="true" />
                            <span>▼ Xem chi tiết</span>
                          </>
                        )}
                      </button>
                    </td>

                    <td className="px-4 py-3.5 font-medium text-slate-900 dark:text-slate-100">
                      {isRestricted ? (
                        <span className="italic text-slate-500 dark:text-slate-400">
                          [Bảo mật danh tính]
                        </span>
                      ) : (
                        `${item.studentName} (${item.studentId})`
                      )}
                    </td>

                    <td className="px-4 py-3.5 text-slate-700 dark:text-slate-300">
                      {isRestricted ? (
                        <div className="font-semibold text-amber-700 dark:text-amber-400">
                          Hồ sơ hạn chế truy cập (Chỉ dành cho cán bộ thẩm quyền)
                        </div>
                      ) : (
                        <div>
                          <div className="font-medium text-slate-900 dark:text-slate-100">{item.title}</div>
                          {item.age && (
                            <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                              Thời gian chờ: <strong>{item.age}</strong>
                            </div>
                          )}
                          <div className="mt-2 flex items-center gap-2 text-xs">
                            <span className={`font-bold ${sla.urgencyColor}`}>
                              ⏱ SLA: {sla.remaining}
                            </span>
                            <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                              <div
                                className="h-full bg-blue-600 transition-all duration-500"
                                style={{ width: `${sla.percentUsed}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      )}

                      {hasConflict && (
                        <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/60 dark:text-amber-300">
                          <strong>Xung đột tiếp nhận:</strong> Ca này đã được cán bộ{" "}
                          <strong>{item.conflictStaffId || "khác"}</strong> nhận xử lý trước đó.
                        </div>
                      )}

                      {isStale && (
                        <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/60 dark:text-amber-300">
                          <strong>Xung đột phiên bản:</strong> Dữ liệu đã thay đổi trên máy chủ. Vui lòng làm mới hàng đợi.
                        </div>
                      )}

                      {isUnknown && (
                        <div className="mt-2 rounded-lg border border-orange-200 bg-orange-50 p-2 text-xs text-orange-800 dark:border-orange-900/60 dark:bg-orange-950/60 dark:text-orange-300">
                          <strong>Chưa rõ kết quả:</strong> Đang đối soát kết quả ghi nhận từ máy chủ. Vui lòng thử lại.
                        </div>
                      )}
                    </td>

                    <td className="whitespace-nowrap px-4 py-3.5">
                      <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${priorityBadge.className}`}>
                        {priorityBadge.text}
                      </span>
                    </td>

                    <td className="whitespace-nowrap px-4 py-3.5 text-xs text-slate-600 dark:text-slate-400">
                      {isStale
                        ? "Xung đột phiên bản"
                        : isUnknown
                        ? "Đang đối soát"
                        : hasConflict
                        ? "Xung đột ghi nhận"
                        : isRestricted
                        ? "Hạn chế quyền"
                        : isFinalized
                        ? "Đã tiếp nhận"
                        : isUnassigned
                        ? "Chờ tiếp nhận"
                        : isMyItem
                        ? "Đang xử lý"
                        : `Đã nhận (${item.assignedStaffId})`}
                    </td>

                    <td className="whitespace-nowrap px-4 py-3.5">
                      {isUnknown ? (
                        <button
                          type="button"
                          onClick={() => onReconcile?.(item.id)}
                          className="inline-flex min-h-10 items-center justify-center rounded-xl bg-orange-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-orange-700"
                        >
                          <RotateCcw className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                          <span>Thử đối soát lại</span>
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => onClaimTicket?.(item.id)}
                          disabled={!canClaim}
                          aria-label={
                            !businessActionsAvailable
                              ? `Chưa có consumer - ${item.ticketCode}`
                              : isStale
                              ? `Xung đột phiên bản - ${item.ticketCode}`
                              : hasConflict
                              ? `Xung đột - ${item.ticketCode}`
                              : isRestricted
                              ? `Hạn chế truy cập - ${item.ticketCode}`
                              : canClaim
                              ? `Nhận xử lý ${item.ticketCode}`
                              : `Đã nhận - ${item.ticketCode}`
                          }
                          className={canClaim ? staffPrimary : staffButton}
                        >
                          {isStale
                            ? "Xung đột phiên bản"
                            : hasConflict
                            ? "Xung đột"
                            : isRestricted
                            ? "Hạn chế"
                            : canClaim
                            ? "Nhận xử lý"
                            : !businessActionsAvailable ? "Chưa có consumer" : "Đã nhận"}
                        </button>
                      )}
                    </td>
                  </tr>

                  {/* Expandable detail region with Intake Checklist & AI Copilot */}
                  {isExpanded && !isRestricted && (
                    <tr className="bg-slate-50/80 dark:bg-slate-900/80">
                      <td colSpan={6} className="border-t border-slate-200 p-5 dark:border-slate-800">
                        <div className="flex flex-col gap-5">
                          {/* Public Context & Internal Staff Notes */}
                          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                            <div className={`${staffSurface} p-4 shadow-xs`}>
                              <div className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase text-blue-600 dark:text-blue-400">
                                <span>●</span>
                                <span>Nội dung công khai (Sinh viên thấy)</span>
                              </div>
                              <p className="text-sm leading-relaxed text-slate-800 dark:text-slate-200">
                                {item.publicContent || item.title}
                              </p>
                            </div>

                            <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4 shadow-xs dark:border-amber-900/60 dark:bg-amber-950/40">
                              <div className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase text-amber-800 dark:text-amber-400">
                                <span>🔒</span>
                                <span>Ghi chú nội bộ (Chỉ lưu hành nội bộ)</span>
                              </div>
                              <p className="text-sm leading-relaxed text-amber-900 dark:text-amber-200">
                                {item.internalNotes || "Không có ghi chú nội bộ cho ca này."}
                              </p>
                            </div>
                          </div>

                          {/* AI Copilot Triage Assistant Card */}
                          <div className="rounded-2xl border border-purple-200 bg-purple-50/60 p-5 shadow-xs dark:border-purple-900/60 dark:bg-purple-950/40">
                            <div className="mb-3 flex items-center gap-2 text-purple-800 dark:text-purple-300">
                              <Sparkles className="h-5 w-5 text-purple-600 dark:text-purple-400" aria-hidden="true" />
                              <h4 className="text-sm font-bold">
                                Trợ lý AI Tiếp nhận & Phân loại thông minh
                              </h4>
                            </div>

                            <div className="space-y-2 text-sm text-purple-900 dark:text-purple-200">
                              <div>
                                <strong>Tóm tắt AI:</strong> Hồ sơ Một cửa: {item.title}{item.priority === "urgent" ? " (được đánh dấu khẩn)" : ""}. Hạn xử lý theo quy trình của đơn vị; hệ thống chưa có căn cứ thời hạn cho loại hồ sơ này.
                              </div>
                              <div>
                                <strong>Kiểm tra trùng lặp:</strong> Chưa kết nối dữ liệu hồ sơ để kiểm trùng; cán bộ đối chiếu trực tiếp.
                              </div>
                              <div className="flex flex-wrap items-center gap-2 pt-1">
                                <strong>Đề xuất câu trả lời nhanh:</strong>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setSupplementModalId(item.id);
                                    setSupplementMsg("Chào bạn, Nhà trường đã tiếp nhận hồ sơ. Vui lòng bổ sung bản chụp CCCD hai mặt để hoàn thiện thủ tục.");
                                  }}
                                  className="rounded-lg border border-purple-300 bg-white px-3 py-1 text-xs font-semibold text-purple-800 shadow-xs hover:bg-purple-50 dark:border-purple-700 dark:bg-slate-900 dark:text-purple-300"
                                >
                                  Mẫu: Yêu cầu bổ sung CCCD
                                </button>
                              </div>
                            </div>
                          </div>

                          {/* Student Attachments with OCR Badges */}
                          {item.attachments && item.attachments.length > 0 && (
                            <div className={`${staffSurface} p-5 shadow-xs`}>
                              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                                <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                                  📎 Minh chứng & Hồ sơ sinh viên đính kèm ({item.attachments.length})
                                </h4>
                                <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                                  OCR chưa được xác minh
                                </span>
                              </div>
                              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                                {item.attachments.map((att, attIdx) => (
                                  <div
                                    key={attIdx}
                                    className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-900"
                                  >
                                    <div className="flex items-center gap-2">
                                      <span className="text-base">{att.type === "pdf" ? "📄" : "🖼️"}</span>
                                      <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{att.name}</span>
                                    </div>
                                    <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                                      {att.evidence?.state === "checked" && att.evidence.locator && att.evidence.version
                                        ? `Đã kiểm · ${att.evidence.locator} · ${att.evidence.version}`
                                        : att.evidence?.state === "conflicting" ? "Xung đột" : att.evidence?.state === "error" ? "Lỗi kiểm tra" : att.evidence?.state === "missing_source" ? "Thiếu nguồn" : "Chưa kiểm"}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Adaptive Intake Checklist */}
                          <div className={`${staffSurface} p-5 shadow-xs`}>
                            {/* Preset Actions Bar */}
                            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50/70 p-3 dark:border-blue-900/60 dark:bg-blue-950/40">
                              <div className="flex items-center gap-1.5 text-xs font-bold text-blue-900 dark:text-blue-300">
                                <Sparkles className="h-4 w-4 text-blue-600 dark:text-blue-400" aria-hidden="true" />
                                <span>Thao tác chuẩn 1-chạm:</span>
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleAiAutoCheck(item.id)}
                                  className="rounded-lg border border-blue-400 bg-white px-3 py-1.5 text-xs font-bold text-blue-700 shadow-xs hover:bg-blue-50 dark:border-blue-700 dark:bg-slate-900 dark:text-blue-300"
                                >
                                  Cán bộ đối chiếu từng mục
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setSupplementModalId(item.id);
                                    setSupplementMsg("Chào em, hồ sơ còn thiếu bản scan có con dấu tròn đỏ xác nhận. Vui lòng bổ sung.");
                                  }}
                                  className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                                >
                                  ⚠️ Mẫu: Yêu cầu bổ sung dấu đỏ
                                </button>
                              </div>
                            </div>

                            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                              <div>
                                <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                                  Checklist tiếp nhận hồ sơ (Bắt buộc {checkedCount}/{INTAKE_CHECKLIST_GATES.length})
                                </h4>
                                <span className={`text-xs font-medium ${checkedCount === INTAKE_CHECKLIST_GATES.length ? "text-emerald-600 dark:text-emerald-400" : "text-slate-500 dark:text-slate-400"}`}>
                                  {checkedCount === INTAKE_CHECKLIST_GATES.length ? "Đã đạt 100% tiêu chí hợp lệ" : `Tiến độ thẩm định: ${Math.round((checkedCount / INTAKE_CHECKLIST_GATES.length) * 100)}%`}
                                </span>
                              </div>
                              <div className="flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleAiAutoCheck(item.id)}
                                  disabled={isFinalized}
                                  className="rounded-lg border border-purple-300 bg-purple-50 px-3 py-1 text-xs font-semibold text-purple-700 hover:bg-purple-100 disabled:opacity-50 dark:border-purple-800 dark:bg-purple-950 dark:text-purple-300"
                                >
                                  Kiểm tra khả năng đối chiếu
                                </button>
                                {isFinalized && (
                                  <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                                    Đánh dấu cục bộ · chưa có receipt nghiệp vụ
                                  </span>
                                )}
                              </div>
                            </div>

                            <div className="mb-4 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                              <div
                                className={`h-full transition-all duration-300 ${
                                  checkedCount === INTAKE_CHECKLIST_GATES.length ? "bg-emerald-600" : "bg-blue-600"
                                }`}
                                style={{ width: `${(checkedCount / INTAKE_CHECKLIST_GATES.length) * 100}%` }}
                              />
                            </div>

                            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                              {INTAKE_CHECKLIST_GATES.map((gate) => (
                                <label
                                  key={gate.id}
                                  className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-sm transition ${
                                    ticketGates[gate.id]
                                      ? "border-blue-500 bg-blue-50/50 shadow-xs dark:border-blue-700 dark:bg-blue-950/30"
                                      : "border-slate-200 bg-white hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900"
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={!!ticketGates[gate.id]}
                                    onChange={() => handleGateToggle(item.id, gate.id)}
                                    className="mt-0.5 h-4 w-4 cursor-pointer rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                                  />
                                  <div className="flex flex-1 flex-col gap-1">
                                    <div className="flex flex-wrap items-center justify-between gap-1.5">
                                      <span className="font-semibold text-slate-900 dark:text-slate-100">{gate.label}</span>
                                      <span className={`rounded-md border px-2 py-0.5 text-[10px] font-bold ${gate.sourceBadgeClass}`}>
                                        {gate.sourceBadge}
                                      </span>
                                    </div>
                                    <span className="text-xs text-slate-500 dark:text-slate-400">
                                      {gate.aiEvidence} <strong className="text-emerald-600 dark:text-emerald-400">({gate.confidence})</strong>
                                    </span>
                                  </div>
                                </label>
                              ))}
                            </div>

                            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3 dark:border-slate-800">
                              <div className="flex flex-wrap items-center gap-2">
                                <label htmlFor={`ex-${item.id}`} className="text-xs text-slate-600 dark:text-slate-400">
                                  Ghi chú vấn đề cần xử lý (không thay kiểm tra bắt buộc):
                                </label>
                                <input
                                  id={`ex-${item.id}`}
                                  type="text"
                                  placeholder="Ví dụ: Lãnh đạo phê duyệt trực tiếp qua giấy..."
                                  value={exceptionReasons[item.id] || ""}
                                  onChange={(e) =>
                                    setExceptionReasons((prev) => ({ ...prev, [item.id]: e.target.value }))
                                  }
                                  className="w-64 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-900 shadow-xs dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                                />
                              </div>

                              <button
                                type="button"
                                onClick={() => handleFinalize(item.id)}
                                disabled={!businessActionsAvailable || !checklistDone || isFinalized}
                                className={checklistDone && !isFinalized ? staffPrimary : staffButton}
                              >
                                {isFinalized ? "Đánh dấu cục bộ" : "Xác nhận hoàn tất tiếp nhận"}
                              </button>
                            </div>
                          </div>

                          {/* Quick Staff Workflow Actions */}
                          <div className="flex flex-wrap items-center justify-end gap-2.5">
                            <button
                              type="button"
                              onClick={() => handleOpenAiDraft(item)}
                              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-purple-200 bg-purple-50 px-4 py-2 text-sm font-semibold text-purple-700 hover:bg-purple-100 dark:border-purple-800 dark:bg-purple-950/60 dark:text-purple-300"
                            >
                              <Sparkles className="h-4 w-4" aria-hidden="true" />
                              <span>AI Dự thảo phản hồi cho SV</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => setReceiptModalId(item.id)}
                              className={staffButton}
                            >
                              <Printer className="h-4 w-4 text-slate-500" aria-hidden="true" />
                              <span>In Phiếu Tiếp Nhận (Mẫu 01/MC)</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => setSupplementModalId(item.id)}
                              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-800 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                            >
                              <span>Yêu cầu bổ sung thông tin</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => setTransferModalId(item.id)}
                              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-950/60 dark:text-blue-300"
                            >
                              <span>Chuyển đơn vị chuyên môn</span>
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Transfer Department Modal */}
      {transferModalId && (
        <AccessibleDialog open onClose={() => setTransferModalId(null)} labelledBy="transfer-title" className="campus-decision-sheet">
          <div className="w-full max-w-md space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-900">
            <h3 id="transfer-title" className="text-base font-bold text-slate-900 dark:text-slate-100">
              Chuyển hồ sơ sang đơn vị chuyên môn
            </h3>

            <div className="space-y-1.5">
              <label htmlFor="dept-select" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Đơn vị tiếp nhận mới
              </label>
              <select
                id="dept-select"
                value={targetDept}
                onChange={(e) => setTargetDept(e.target.value)}
                className={staffField}
              >
                <option value="phong_dao_tao">Phòng Quản lý Đào tạo</option>
                <option value="phong_ctsv">Phòng Công tác Sinh viên (CTSV)</option>
                <option value="phong_khao_thi">Phòng Khảo thí & Đảm bảo chất lượng</option>
                <option value="khoa_cntt">Văn phòng Khoa Công nghệ Thông tin</option>
                <option value="tram_y_te">Trạm Y tế Trường</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="transfer-reason" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Lý do chuyển tiếp (Lưu lịch sử kiểm toán)
              </label>
              <textarea
                id="transfer-reason"
                rows={3}
                placeholder="Nhập ghi chú chuyển ca giải thích thẩm quyền..."
                value={transferReason}
                onChange={(e) => setTransferReason(e.target.value)}
                className={staffField}
              />
            </div>

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setTransferModalId(null)}
                className={staffButton}
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={() => handleConfirmTransfer(transferModalId)}
                disabled={!businessActionsAvailable}
                className={staffPrimary}
              >
                Xác nhận chuyển đơn
              </button>
            </div>
          </div>
        </AccessibleDialog>
      )}

      {/* Request Supplement Modal */}
      {supplementModalId && (
        <AccessibleDialog open onClose={() => setSupplementModalId(null)} labelledBy="supp-title" className="campus-decision-sheet">
          <div className="w-full max-w-md space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-900">
            <h3 id="supp-title" className="text-base font-bold text-slate-900 dark:text-slate-100">
              Yêu cầu sinh viên bổ sung thông tin hồ sơ
            </h3>

            <div className="space-y-1.5">
              <label htmlFor="supp-msg" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Nội dung yêu cầu gửi tới sinh viên
              </label>
              <textarea
                id="supp-msg"
                rows={4}
                placeholder="Nêu rõ loại giấy tờ hoặc thông tin cần bổ sung..."
                value={supplementMsg}
                onChange={(e) => setSupplementMsg(e.target.value)}
                className={staffField}
              />
            </div>

            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setSupplementModalId(null)}
                className={staffButton}
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={() => handleConfirmSupplement(supplementModalId)}
                disabled={!businessActionsAvailable}
                className="inline-flex min-h-11 items-center justify-center rounded-xl bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 shadow-xs"
              >
                Gửi yêu cầu bổ sung
              </button>
            </div>
          </div>
        </AccessibleDialog>
      )}

      {/* AI Draft Response Modal */}
      {aiDraftModalId && (() => {
        const item = items.find((i) => i.id === aiDraftModalId);
        if (!item) return null;
        return (
          <AccessibleDialog open onClose={() => setAiDraftModalId(null)} labelledBy="ai-draft-title" className="campus-decision-sheet">
            <div className="flex max-h-[90vh] w-full max-w-2xl flex-col gap-4 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-slate-800">
                <div className="flex items-center gap-2 text-purple-700 dark:text-purple-300">
                  <Sparkles className="h-5 w-5" aria-hidden="true" />
                  <h3 id="ai-draft-title" className="text-base font-bold">
                    Trợ lý AI Soạn Thảo Phản Hồi Cho Sinh Viên
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setAiDraftModalId(null)}
                  className="rounded-lg p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  aria-label="Đóng hộp thoại"
                >
                  <X className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>

              <div className="text-xs text-slate-600 dark:text-slate-400">
                Hồ sơ: <strong>{item.ticketCode}</strong> — {item.studentName} ({item.studentId})
              </div>

              {/* Template selector tabs */}
              <div className="flex flex-wrap gap-2 border-b border-slate-100 pb-2 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => handleAiDraftTypeChange("approve", item)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    aiDraftType === "approve"
                      ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                      : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                  }`}
                >
                  ✓ Tiếp nhận & Hẹn trả kết quả
                </button>
                <button
                  type="button"
                  onClick={() => handleAiDraftTypeChange("supplement", item)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    aiDraftType === "supplement"
                      ? "bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                      : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                  }`}
                >
                  ⚠️ Yêu cầu bổ sung hồ sơ
                </button>
                <button
                  type="button"
                  onClick={() => handleAiDraftTypeChange("forward", item)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    aiDraftType === "forward"
                      ? "bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-300"
                      : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                  }`}
                >
                  ↗ Hướng dẫn chuyển tuyến
                </button>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="ai-draft-content" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Nội dung phản hồi (có thể chỉnh sửa trực tiếp)
                </label>
                <textarea
                  id="ai-draft-content"
                  rows={8}
                  value={aiDraftContent}
                  onChange={(e) => setAiDraftContent(e.target.value)}
                  className={`${staffField} font-sans leading-relaxed`}
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                  {draftCopied ? "✓ Đã sao chép vào bộ nhớ tạm!" : "Mẫu nháp tham khảo; chưa có nguồn để kết luận nghiệp vụ"}
                </span>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleCopyDraft}
                    className={staffButton}
                  >
                    <Copy className="h-4 w-4" aria-hidden="true" />
                    <span>{draftCopied ? "✓ Đã sao chép" : "📋 Sao chép văn bản"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (aiDraftType === "supplement") {
                        setSupplementMsg(aiDraftContent);
                        setSupplementModalId(item.id);
                      }
                      setAiDraftModalId(null);
                    }}
                    className="inline-flex min-h-11 items-center justify-center rounded-xl bg-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-xs hover:bg-purple-700"
                  >
                    Áp dụng phản hồi này
                  </button>
                </div>
              </div>
            </div>
          </AccessibleDialog>
        );
      })()}

      {/* Official Receipt Print Modal (Mẫu 01/MC) */}
      {receiptModalId && (() => {
        const item = items.find((i) => i.id === receiptModalId);
        if (!item) return null;
        return (
          <AccessibleDialog open onClose={() => setReceiptModalId(null)} labelledBy="receipt-title" className="campus-decision-sheet">
            <div className="flex max-h-[90vh] w-full max-w-2xl flex-col gap-5 overflow-y-auto rounded-2xl border-2 border-slate-900 bg-white p-8 shadow-2xl dark:border-slate-100 dark:bg-slate-900">
              {/* Official Header */}
              <div className="border-b-2 border-slate-900 pb-4 text-center dark:border-slate-100">
                <div className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                  TRƯỜNG ĐẠI HỌC XÂY DỰNG HÀ NỘI
                </div>
                <div className="text-xs font-medium text-slate-600 dark:text-slate-400">
                  BỘ PHẬN TIẾP NHẬN VÀ TRẢ KẾT QUẢ MỘT CỬA SỐ
                </div>
                <div className="mx-auto my-2 h-0.5 w-20 bg-slate-900 dark:bg-slate-100" />
                <h2 id="receipt-title" className="text-lg font-extrabold uppercase tracking-tight text-slate-900 dark:text-slate-100">
                  GIẤY TIẾP NHẬN HỒ SƠ VÀ HẸN TRẢ KẾT QUẢ
                </h2>
                <div className="text-xs italic text-slate-500 dark:text-slate-400">
                  Bản tham khảo cục bộ · chưa xác minh mẫu chính thức hoặc receipt nghiệp vụ
                </div>
                <div className="mt-2 text-xs font-bold text-blue-700 dark:text-blue-300">
                  Mã số biên nhận: {item.ticketCode}
                </div>
              </div>

              {/* Receipt Body */}
              <div className="space-y-2.5 text-sm leading-relaxed text-slate-800 dark:text-slate-200">
                <div><strong>Người nộp hồ sơ:</strong> {item.studentName} — MSSV: <strong>{item.studentId}</strong></div>
                <div><strong>Nội dung thủ tục:</strong> {item.title}</div>
                <div><strong>Đơn vị chuyên môn xử lý:</strong> {item.targetDepartment || "Phòng Quản lý Đào tạo"}</div>
                <div><strong>Thời điểm tiếp nhận:</strong> {item.createdAt} (Ghi nhận trên CSDL số)</div>
                <div><strong>Thời hạn xử lý:</strong> {item.sla?.locator && item.sla.version ? `${item.sla.deadline} · ${item.sla.locator} · ${item.sla.version}` : "Chưa có căn cứ được xác minh"}</div>
                <div>
                  <strong>Checklist cục bộ cần cán bộ đối chiếu với bằng chứng:</strong>
                  <ul className="mt-1 list-none space-y-1 pl-4 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                    {INTAKE_CHECKLIST_GATES.map(g => <li key={g.id}>{checkedGates[item.id]?.[g.id] ? "Cán bộ đánh dấu cục bộ" : "Chưa kiểm"} · {g.label}</li>)}
                  </ul>
                </div>
              </div>

              {/* Signature block */}
              <div className="flex items-center justify-between border-t border-dashed border-slate-300 pt-4 dark:border-slate-700">
                <div className="w-1/2 text-center">
                  <div className="text-xs font-semibold text-slate-700 dark:text-slate-300">NGƯỜI NỘP HỒ SƠ</div>
                  <div className="text-[11px] italic text-slate-500">(Chưa xác minh chữ ký điện tử)</div>
                  <div className="mt-6 font-bold text-slate-900 dark:text-slate-100">{item.studentName}</div>
                </div>

                <div className="w-1/2 text-center">
                  <div className="text-xs font-semibold text-slate-700 dark:text-slate-300">CÁN BỘ TIẾP NHẬN</div>
                  <div className="text-[11px] italic text-slate-500">(Cần receipt xác nhận nghiệp vụ)</div>
                  <div className="mt-6 font-bold text-blue-700 dark:text-blue-300">{item.assignedStaffId || "Cán bộ Một cửa HUCE"}</div>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setReceiptModalId(null)}
                  className={staffButton}
                >
                  Đóng
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (typeof window !== "undefined") {
                      window.print();
                    }
                  }}
                  className={staffPrimary}
                >
                  <Printer className="h-4 w-4" aria-hidden="true" />
                  <span>In Biên Nhận / Lưu PDF</span>
                </button>
              </div>
            </div>
          </AccessibleDialog>
        );
      })()}

      {/* Audit Log Drawer / Panel */}
      <div className={`${staffSurface} overflow-hidden shadow-xs`}>
        <button
          type="button"
          onClick={() => setShowAuditLog((prev) => !prev)}
          className="flex w-full items-center justify-between px-5 py-3.5 text-left text-sm font-bold text-slate-800 transition hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-800/50"
        >
          <span>📋 Nhật ký thao tác (Audit Trail) — {auditLog.length} bản ghi</span>
          <span className="text-xs font-normal text-slate-500">
            {showAuditLog ? "▲ Thu gọn" : "▼ Mở rộng"}
          </span>
        </button>

        {showAuditLog && (
          <div className="border-t border-slate-100 p-5 dark:border-slate-800">
            {auditLog.length === 0 ? (
              <div className="py-6 text-center text-xs text-slate-500">
                Chưa có thao tác nào được ghi nhận.
              </div>
            ) : (
              <div className="max-h-72 overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                    <tr>
                      <th scope="col" className="px-3 py-2">Thời điểm</th>
                      <th scope="col" className="px-3 py-2">Cán bộ</th>
                      <th scope="col" className="px-3 py-2">Mã hồ sơ</th>
                      <th scope="col" className="px-3 py-2">Hành động</th>
                      <th scope="col" className="px-3 py-2">Chi tiết</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {auditLog.slice(0, 50).map((entry, idx) => (
                      <tr key={`audit-${idx}`} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                        <td className="whitespace-nowrap px-3 py-2 font-mono text-slate-500">
                          {new Date(entry.timestamp).toLocaleString("vi-VN", {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                            day: "2-digit",
                            month: "2-digit",
                          })}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 font-semibold text-blue-700 dark:text-blue-300">
                          {entry.staffId}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 font-semibold">
                          {entry.ticketId.slice(0, 8)}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2">
                          <span
                            className={`rounded-md px-2 py-0.5 font-mono text-[10px] font-bold ${
                              entry.action === "FINALIZE_INTAKE"
                                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                                : entry.action === "AI_AUTO_CHECK"
                                ? "bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-300"
                                : entry.action === "TRANSFER"
                                ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                                : entry.action === "GATE_UNCHECK"
                                ? "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                                : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                            }`}
                          >
                            {entry.action}
                          </span>
                        </td>
                        <td className="max-w-xs truncate px-3 py-2 text-slate-600 dark:text-slate-400">
                          {entry.detail}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
