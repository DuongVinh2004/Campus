import type { ReviewCase, ReviewFinding, Ticket, TicketType } from "./types";

export const ticketTypeLabels: Record<TicketType, string> = {
  certificate: "Yêu cầu tài liệu", transcript: "Bảng điểm", complaint: "Khiếu nại điểm", lookup: "Hỗ trợ học vụ",
};
export const findingLabels = {
  has_evidence: "Có bằng chứng", has_difference: "Có khác biệt", insufficient_evidence: "Chưa đủ căn cứ", contradiction: "Có mâu thuẫn",
} as const;
export function effectiveFinding(finding: ReviewFinding) {
  return finding.officerStatus === "edited" && finding.officerAdjustedLabel ? finding.officerAdjustedLabel : finding.aiLabel;
}
export function ticketSnapshot(ticket: Ticket): string {
  return JSON.stringify([ticket.status, ticket.messages, ticket.checklist, ticket.systemVerifications, ticket.notes, ticket.attachments, ticket.requestPayload, ticket.issuedCertificate]);
}
export function officerDraftFor(ticket: Ticket, officerId: string): string {
  const saved = ticket.officerDrafts?.[officerId];
  if (saved !== undefined) return saved;
  // The original single-officer mock stored OF001's draft on the ticket.
  return officerId === (ticket.assignedOfficerId || "OF001")
    ? ticket.officerDraft || ""
    : ticket.officerDraftDefault || "";
}
export function reviewSources(record: ReviewCase): string {
  return JSON.stringify(record.documents.map(document => [document.id, document.currentVersion, document.versions.find(version => version.version === document.currentVersion)]));
}
export function reviewSnapshot(record: ReviewCase): string {
  return JSON.stringify([record.status, record.updatedAt, reviewSources(record), record.findings, record.aiSummary.isStale]);
}
export function reviewReadiness(record: ReviewCase) {
  const missing = record.criteria.filter(criterion => criterion.isMandatory && !record.findings.some(f => f.criterionId === criterion.id));
  const outdated = record.findings.filter(f => f.officerSourceVersion ? f.officerSourceVersion !== reviewSources(record) : record.aiSummary.isStale || f.citations.some(c => record.documents.find(d => d.id === c.documentId)?.currentVersion !== c.version));
  const unchecked = record.findings.filter(f => f.officerStatus === "unverified");
  const issues = record.findings.filter(f => effectiveFinding(f) !== "has_evidence");
  const reason = missing.length ? "Thiếu kết quả cho tiêu chí bắt buộc." : unchecked.length ? `Còn ${unchecked.length} tiêu chí chưa được cán bộ kiểm tra.` : outdated.length ? `Cần kiểm tra lại ${outdated.length} tiêu chí theo nguồn hiện hành.` : "";
  return { missing, outdated, unchecked, issues, reason };
}
export function actionBlock(ticket: Ticket, action: "respond" | "request_info" | "resolve", content: string): string {
  if (ticket.status === "resolved") return "Hồ sơ đã hoàn tất; không thể gửi thêm hoặc thực hiện lại.";
  if (!content.trim()) return action === "resolve" ? "Nhập kết quả xử lý trước khi hoàn tất." : "Nhập nội dung gửi sinh viên.";
  if (content.trim().length > 10000) return "Nội dung tối đa 10.000 ký tự.";
  if (action === "resolve" && ticket.checklist.some(item => !item.checked)) return "Còn mục kiểm tra chưa xác nhận. Hãy kiểm tra hoặc yêu cầu bổ sung.";
  if (action === "resolve" && ticket.dataChangedSinceLastCheck) return "Dữ liệu đã thay đổi; cần kiểm tra lại trước khi hoàn tất.";
  return "";
}
export function filterTickets(tickets: Ticket[], query: string, status: string, priority: string, type: string) {
  const needle = query.trim().toLocaleLowerCase("vi");
  return tickets.filter(t => (!needle || [t.code, t.studentName, t.studentMssv, t.title].some(v => v.toLocaleLowerCase("vi").includes(needle)))
    && (status === "all" || (status === "active" ? t.status !== "resolved" : t.status === status))
    && (priority === "all" || t.priority === priority) && (type === "all" || t.type === type))
    .sort((a, b) => Number(b.priority === "high") - Number(a.priority === "high") || (Date.parse(a.createdAt) || 0) - (Date.parse(b.createdAt) || 0) || a.id.localeCompare(b.id));
}
