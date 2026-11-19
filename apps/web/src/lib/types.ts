export type UserRole = "student" | "officer";

export interface User {
  id: string; // "SV001", "OF001", "SV024"
  name: string;
  role: UserRole;
  email: string;
  mssv?: string;
  classYear?: string;
  major?: string;
  title?: string;
  department?: string;
  credits?: string;
  academicStatus?: string;
}

export type TicketStatus = "open" | "pending_officer" | "resolved";
export type TicketPriority = "normal" | "high";
export type TicketType = "certificate" | "transcript" | "complaint" | "lookup";

export interface StoredAttachment {
  id: string;
  name: string;
  size: number;
  contentType: string;
  field?: string;
}

export interface TicketMessage {
  id: string;
  senderId: string;
  senderName: string;
  senderRole: UserRole | "system" | "ai";
  content: string;
  timestamp: string;
  attachments?: { name: string; url?: string; size?: string }[];
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  source: string; // e.g. "Cổng 1 (Sinh viên)", "Campus AI Engine v4.2", "Bàn làm việc Cán bộ"
  action: string;
  actor: string;
  details?: string;
}

export interface FactItem {
  id: string;
  key: string;
  source: string;
  value: string;
  status: "verified" | "unverified" | "disputed";
  statusText: string;
  notes?: string;
}

export interface ChecklistItem {
  id: string;
  label: string;
  description: string;
  checked: boolean;
}

export type VerificationResultStatus = "passed" | "failed" | "insufficient" | "error";

export interface SystemVerificationItem {
  id: string;
  criterionKey: string;
  criterionLabel: string;
  conditionApplied: string;
  dataChecked: string;
  sourceSystem: string;
  lookupTimestamp: string;
  status: VerificationResultStatus;
  reason: string;
  evidenceDetails?: {
    rawSnippet: string;
    systemUrl?: string;
    verifiedFields?: Record<string, string>;
  };
  officerReviewStatus: "pending" | "confirmed" | "overridden";
  officerReviewNote?: string;
}

export interface IssuedCertificateDocument {
  id: string; // e.g. "CERT-2026-00318"
  docNumber: string; // e.g. "142/XNSV-ĐT-2026"
  templateCode: string; // "BM-03"
  templateName: string; // "Giấy xác nhận sinh viên chính quy"
  templateVersion: string; // "v2.1"
  issuedAt: string; // ISO string
  issuedAtFormatted: string; // "14:30 · 26/09/2026"
  issuedByOfficerId: string; // "OF001"
  issuedByOfficerName: string; // "ThS. Trần Thu Hà"
  studentId: string;
  studentName: string;
  studentMssv: string;
  studentDob: string;
  studentGender: string;
  studentMajor: string;
  studentClassYear: string;
  studentFaculty: string;
  studentAcademicStatus: string;
  purpose: string;
  destinationOrg: string;
  validUntil: string;
  customOfficerNotes?: string;
  status: "draft" | "approved" | "issued";
  fileName: string;
  isDemoSample: boolean; // Trạng thái xác thực tài liệu số
}

export interface Ticket {
  id: string; // e.g. "TKT-2026-0142", "TKT-2026-0098", "TKT-2026-0139"
  code: string;
  title: string;
  type: TicketType;
  studentId: string;
  studentName: string;
  studentMssv: string;
  studentMajor: string;
  studentClassYear: string;
  studentEmail: string;
  status: TicketStatus;
  priority: TicketPriority;
  priorityReason?: string;
  createdAt: string;
  submittedAt: string;
  slaDeadline: string;
  slaRemaining?: string;
  
  // Declaration fields from Gate 1
  certificateType: string;
  receiveMethod: "digital_pdf" | "paper_stamped";
  destinationOrg: string;
  purpose: string;
  notes?: string;
  submissionKey?: string;
  attachments?: StoredAttachment[];

  requestPayload?: {
    schemaVersion: 1;
    task: "certificate" | "complaint";
    documentType?: string;
    submittedFields: { name: string; label: string; value: string }[];
  };

  // AI Preparation for Officer (L3)
  aiSummary: {
    target: string;
    context: string;
    categorySla: string;
    confidence: string;
    nextBestAction: string;
    nextBestActionReason: string;
  };
  
  facts: FactItem[];
  checklist: ChecklistItem[];
  sopReference: string;
  sopDeadline: string;
  
  // Officer Draft for Submit 2
  officerDraft: string;
  officerDraftDefault: string;
  officerDrafts?: Record<string, string>;
  assignedOfficerId?: string;
  assignedOfficerName?: string;
  
  // L4 Special Fields
  isL4?: boolean;
  l4TriggerReason?: string;
  l4EvidenceVerification?: {
    source1StudentClaim: string;
    source2DbSync: {
      grade: string;
      scale: string;
      room: string;
      lecturer: string;
      syncTime: string;
    };
    source3ExamMinutes: {
      fileName: string;
      scanTime: string;
      verifier: string;
      note: string;
    };
    gradeDiff: {
      oldGrade: number;
      suggestedGrade: number;
      diffText: string;
    };
  };

  messages: TicketMessage[];
  auditLogs: AuditLogEntry[];

  // Real Certificate Issuance & Pre-check Verification
  systemVerifications?: SystemVerificationItem[];
  issuedCertificate?: IssuedCertificateDocument;
  documentStatus?: "not_generated" | "draft" | "approved" | "issued";
  dataChangedSinceLastCheck?: boolean;
}

export interface ChatMessage {
  id: string;
  sender: "user" | "bot" | "system";
  text: string;
  timestamp: string;
  level?: "L1" | "L2" | "L4";
  citation?: {
    code: string;
    title: string;
    quote: string;
    source: string;
  };
  actionCard?: "submit1_prompt" | "submit1_success" | "l4_handover";
  ticketId?: string;
  ticketData?: Partial<Ticket>;
}

export interface ChatSession {
  id: string;
  title: string;
  preview: string;
  updatedAt: string;
  tag: "L1" | "L2" | "L4" | "Chung";
  messages: ChatMessage[];
  isL4HandoverActive?: boolean;
  gate1FormData?: {
    fullName: string;
    mssv: string;
    classYear: string;
    department: string;
    reason: string;
    destinationOrg: string;
    receiveMethod: "digital_pdf" | "paper_stamped";
    academicStatus: string;
  };
}

// ========================================================
// ACADEMIC REVIEW ASSISTANT TYPES (Rà soát công nhận học phần)
// ========================================================

export type ReviewCaseStatus = "draft" | "in_review" | "waiting_supplement" | "completed";
export type AiTaskStatus = "idle" | "running" | "ready" | "stale_needs_update" | "error";

export type FindingAiLabel =
  | "has_evidence"          // Có bằng chứng tương ứng
  | "has_difference"        // Có khác biệt cần xem xét
  | "insufficient_evidence" // Chưa đủ căn cứ
  | "contradiction";        // Dữ liệu mâu thuẫn

export type FindingOfficerStatus =
  | "unverified" // Chưa kiểm tra
  | "confirmed"  // Cán bộ xác nhận
  | "edited";     // Cán bộ đã chỉnh sửa

export type DocumentLegibility = "good" | "partial_blurry" | "unreadable" | "missing_pages";

export interface DocumentSection {
  id: string;
  title: string;
  pageNumber: number;
  content: string;
}

export interface DocumentVersion {
  version: number;
  uploadedAt: string;
  uploadedBy: "student" | "officer";
  fileName: string;
  fileSize?: string;
  attachment?: StoredAttachment;
  legibility: DocumentLegibility;
  legibilityNote?: string;
  sections: DocumentSection[];
  isLatest: boolean;
}

export interface ReviewDocument {
  id: string;
  type: "application" | "transcript" | "syllabus_old" | "syllabus_target" | "supplement";
  title: string;
  institution: string;
  versions: DocumentVersion[];
  currentVersion: number;
  required: boolean;
}

export interface EvidenceCitation {
  documentId: string;
  documentTitle: string;
  version: number;
  sectionId?: string;
  sectionTitle?: string;
  pageNumber: number;
  snippet: string;
  highlightColor?: string;
}

export interface ReviewCriterion {
  id: string;
  code: string;
  category: "credit" | "prerequisite" | "core_content" | "lab_practice" | "learning_outcomes";
  title: string;
  description: string;
  targetRequirement: string;
  isMandatory: boolean;
}

export interface ReviewFinding {
  id: string;
  criterionId: string;
  criterionTitle: string;
  category: "credit" | "prerequisite" | "core_content" | "lab_practice" | "learning_outcomes";
  targetRequirement: string;
  extractedEvidence: string;
  citations: EvidenceCitation[];
  aiLabel: FindingAiLabel;
  aiExplanation: string;
  aiSuggestedAction?: string;
  officerStatus: FindingOfficerStatus;
  officerAdjustedLabel?: FindingAiLabel;
  officerNote?: string;
  officerReviewedAt?: string;
  officerReviewedBy?: string;
  officerSourceVersion?: string;
}

export interface SupplementRequest {
  id: string;
  createdAt: string;
  sentAt?: string;
  sentBy: string;
  targetStudentId: string;
  status: "draft" | "sent" | "responded";
  subject: string;
  messageBody: string;
  requestedDocuments: string[];
  findingsInvolved: string[];
  studentReply?: {
    submittedAt: string;
    note: string;
    supplementedDocumentIds: string[];
  };
}

export interface ReviewCaseAuditLog {
  id: string;
  timestamp: string;
  actorName: string;
  actorRole: "officer" | "student" | "ai" | "system";
  action: string;
  details?: string;
}

export interface ReviewCase {
  id: string;
  code: string;
  createdAt: string;
  updatedAt: string;
  status: ReviewCaseStatus;
  studentId: string;
  studentName: string;
  studentMssv: string;
  studentMajor: string;
  studentClassYear: string;
  studentEmail: string;
  targetCourseCode: string;
  targetCourseName: string;
  targetCourseCredits: number;
  targetDepartment: string;
  priorCourseCode: string;
  priorCourseName: string;
  priorCourseCredits: number;
  priorInstitution: string;
  priorAcademicYear: string;
  priorGrade: string;
  criteriaSetId: string;
  criteriaSetName: string;
  criteria: ReviewCriterion[];
  documents: ReviewDocument[];
  aiStatus: AiTaskStatus;
  aiLastRunAt?: string;
  aiSummary: {
    overallRecommendation: string;
    totalCriteria: number;
    matchCount: number;
    differenceCount: number;
    insufficientCount: number;
    contradictionCount: number;
    isStale: boolean;
    staleReason?: string;
  };
  findings: ReviewFinding[];
  supplementRequests: SupplementRequest[];
  finalReport?: {
    completedAt: string;
    officerId: string;
    officerName: string;
    decisionRecommendation: "propose_recognition" | "propose_conditional" | "propose_rejection";
    conclusionSummary: string;
    disclaimer: string;
  };
  auditLogs: ReviewCaseAuditLog[];
}


