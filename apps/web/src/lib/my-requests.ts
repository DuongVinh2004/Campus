import type { ReviewCase, Ticket } from "./types";
import { formatDate } from "./format-date";
import { validateAttachment } from "./local-attachments";

export type RequestState = "new" | "processing" | "supplement" | "completed" | "draft";
export type RequestItem = {
  id: string; code: string; title: string; type: string; submittedAt: string;
  updatedAt?: string; state: RequestState;
} & ({ kind: "ticket"; record: Ticket } | { kind: "review"; record: ReviewCase });

export const requestStates: Record<RequestState, { label: string; description: string; classes: string }> = {
  new: { label: "Mới nộp", description: "Hồ sơ đã được ghi nhận. Chưa có xác nhận cán bộ đang xử lý hoặc phê duyệt.", classes: "bg-blue-50 text-blue-800 dark:bg-blue-950 dark:text-blue-200" },
  processing: { label: "Đang xử lý", description: "Hồ sơ đang ở bước xử lý. Theo dõi phản hồi bên dưới; chưa có kết quả cuối cùng.", classes: "bg-indigo-50 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200" },
  supplement: { label: "Cần bổ sung", description: "Đọc yêu cầu của cán bộ và chuẩn bị thông tin, tài liệu được yêu cầu.", classes: "bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-200" },
  completed: { label: "Hoàn tất", description: "Bước xử lý hồ sơ đã kết thúc. Xem kết quả bên dưới; trạng thái này không tự xác nhận giấy đã phát hành.", classes: "bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200" },
  draft: { label: "Bản nháp", description: "Hồ sơ chưa được nộp. Chưa có xử lý của cán bộ.", classes: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200" },
};

export function requestStatusLabel(item: RequestItem, localOnly = false): string {
  if (item.kind === "review" && item.state === "completed") return "Hoàn tất rà soát sơ bộ";
  if (item.kind === "ticket" && item.record.status === "pending_officer") return "Chờ cán bộ";
  if (localOnly && item.state === "new") return "Đã tiếp nhận";
  return requestStates[item.state].label;
}

export function collectRequests(tickets: Ticket[], reviews: ReviewCase[], studentId: string, now = Date.now()): RequestItem[] {
  const items: RequestItem[] = [
    ...tickets.filter((t) => t.studentId === studentId).map((t): RequestItem => ({
      kind: "ticket", record: t, id: t.id, code: t.code, title: t.title,
      type: ({ certificate: "Yêu cầu giấy xác nhận", transcript: "Yêu cầu bảng điểm", complaint: "Khiếu nại điểm", lookup: "Câu hỏi học vụ" })[t.type],
      submittedAt: t.createdAt || t.submittedAt,
      state: t.status === "resolved" ? "completed" : t.status === "pending_officer" ? "processing" : "new",
    })),
    ...reviews.filter((r) => r.studentId === studentId).map((r): RequestItem => ({
      kind: "review", record: r, id: r.id, code: r.code,
      title: `${r.targetCourseCode} · ${r.targetCourseName}`, type: "Rà soát công nhận học phần",
      submittedAt: r.createdAt, updatedAt: r.updatedAt,
      state: ({ draft: "draft", in_review: "processing", waiting_supplement: "supplement", completed: "completed" } as const)[r.status],
    })),
  ];
  // Future-dated fixtures must not bury a request that the student just submitted.
  const timestamp = (value: string) => Number.isFinite(Date.parse(value)) ? Date.parse(value) : 0;
  return items.sort((a, b) => {
    const aTime = timestamp(a.submittedAt); const bTime = timestamp(b.submittedAt);
    return Number(aTime > now) - Number(bTime > now) || bTime - aTime || a.id.localeCompare(b.id);
  });
}

export function normalizeFilter(value: string | null): "all" | RequestState {
  if (value === "in_progress") return "processing";
  if (value === "resolved") return "completed";
  return value && Object.hasOwn(requestStates, value) ? value as RequestState : "all";
}

export function filterRequests(items: RequestItem[], filter: "all" | RequestState, query: string, category = "all") {
  const search = query.trim().toLocaleLowerCase("vi");
  return items.filter((item) => (filter === "all" || item.state === filter || (filter === "processing" && item.state === "new"))
    && (category === "all" || (category === "tickets" ? item.kind === "ticket" : item.kind === "review"))
    && (!search || `${item.code} ${item.title} ${item.type}`.toLocaleLowerCase("vi").includes(search)));
}

export function hasIssuedDocument(ticket: Ticket): boolean {
  const document = ticket.issuedCertificate;
  return (ticket.type === "certificate" || ticket.type === "transcript")
    && ticket.status === "resolved" && ticket.documentStatus === "issued" && document?.status === "issued"
    && !document.isDemoSample && Boolean(document.docNumber && document.issuedAt && document.issuedByOfficerName);
}

export function latestOfficerReply(item: RequestItem) {
  if (item.kind === "ticket") return [...item.record.messages].reverse().find((message) => message.senderRole === "officer")?.content;
  const request = [...item.record.supplementRequests].reverse().find((entry) => entry.status !== "draft");
  return item.record.finalReport?.conclusionSummary || request?.messageBody;
}

export function requestDate(value: string): string {
  if (/^\d{2}:\d{2}(?::\d{2})?$/.test(value)) return `${value} (chưa có ngày trong dữ liệu)`;
  const legacy = value.match(/^(\d{2}:\d{2}(?::\d{2})?) · (\d{2})\/(\d{2})\/(\d{4})$/);
  const dayFirst = value.match(/^(\d{2})\/(\d{2})\/(\d{4}) (\d{2}:\d{2}(?::\d{2})?)$/);
  return formatDate(legacy ? `${legacy[4]}-${legacy[3]}-${legacy[2]}T${legacy[1]}` : dayFirst ? `${dayFirst[3]}-${dayFirst[2]}-${dayFirst[1]}T${dayFirst[4]}` : value);
}

export function validateSupplementFile(file: { name: string; size: number; type: string } | null): string {
  return file ? validateAttachment(file) : "";
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]!);
}

/** A receipt of declared information, never an issued academic document. */
export function receiptHtml(item: RequestItem, localOnly: boolean): string {
  const record = item.record;
  const content = item.kind === "ticket" ? item.record.notes || item.record.purpose : `${item.record.priorCourseCode} · ${item.record.priorCourseName}\n${item.record.priorInstitution.replace(/\s*\(Minh họa\)/gi, "")}\nHọc phần đích: ${item.title}`;
  return `<!doctype html><html lang="vi"><meta charset="utf-8"><title>Thông tin hồ sơ ${escapeHtml(item.code)}</title><style>body{max-width:760px;margin:40px auto;padding:24px;font:16px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}h1{font-size:24px}</style><h1>Thông tin hồ sơ</h1><p>Bản xác nhận tiếp nhận thông tin khai trực tuyến. Không phải giấy xác nhận, bảng điểm hay quyết định phê duyệt chính thức.</p><p>Mã: ${escapeHtml(item.code)}<br>Loại: ${escapeHtml(item.type)}<br>Ngày ghi nhận: ${escapeHtml(requestDate(item.submittedAt))}<br>Sinh viên: ${escapeHtml(record.studentName)}<br>Mã sinh viên: ${escapeHtml(record.studentMssv)}</p><pre>${escapeHtml(content)}</pre></html>`;
}
