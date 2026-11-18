import {
  User,
  Ticket,
  TicketStatus,
  TicketMessage,
  ChatMessage,
  ChatSession,
  ReviewCase,
  FindingOfficerStatus,
  FindingAiLabel,
  SupplementRequest,
  IssuedCertificateDocument,
  StoredAttachment,
} from "../types";

export interface CampusDataGateway {
  // Auth
  login(userId: string): Promise<User>;

  // Tickets
  getTickets(): Promise<Ticket[]>;
  getTicket(id: string): Promise<Ticket | undefined>;
  createTicket(student: User, data: Partial<Ticket>): Promise<Ticket>;
  updateTicketStatus(id: string, status: TicketStatus, actorName: string): Promise<void>;
  updateOfficerDraft(id: string, draft: string, actor?: User, expectedDraft?: string): Promise<void>;
  resetOfficerDraft(id: string): Promise<void>;
  toggleChecklistItem(ticketId: string, itemId: string): Promise<void>;
  addTicketMessage(
    ticketId: string,
    message: Omit<TicketMessage, "id" | "timestamp">
  ): Promise<void>;
  submitGate2Response(
    ticketId: string,
    actionType: "respond" | "request_info" | "resolve",
    customContent?: string,
    actor?: User,
    expectedSnapshot?: string
  ): Promise<void>;

  // Certificate Verification & BM-03 Issuance
  runTicketVerification(ticketId: string): Promise<void>;
  retryCriterionVerification(ticketId: string, criterionId: string): Promise<void>;
  confirmCriterionReview(ticketId: string, criterionId: string, note?: string): Promise<void>;
  updateCertificateDraft(ticketId: string, edits: Partial<IssuedCertificateDocument>): Promise<void>;

  // Chat Assistant State & Sessions
  getChatSessions(): Promise<ChatSession[]>;
  createChatSession(): Promise<ChatSession>;
  deleteChatSession(sessionId: string): Promise<void>;
  addChatMessage(sessionId: string, msg: Omit<ChatMessage, "id" | "timestamp">): Promise<void>;
  updateChatSessionGate1(
    sessionId: string,
    formData: NonNullable<ChatSession["gate1FormData"]>
  ): Promise<void>;
  updateChatSessionL4(sessionId: string, isActive: boolean): Promise<void>;

  // Academic Review Cases
  getReviewCases(): Promise<ReviewCase[]>;
  getReviewCase(id: string): Promise<ReviewCase | undefined>;
  createReviewCase(data: Partial<ReviewCase>): Promise<ReviewCase>;
  runAiReview(caseId: string): Promise<void>;
  updateFindingReview(
    caseId: string,
    findingId: string,
    updates: {
      officerStatus: FindingOfficerStatus;
      officerAdjustedLabel?: FindingAiLabel;
      officerNote?: string;
    },
    actor?: User,
    expectedSnapshot?: string
  ): Promise<void>;
  sendSupplementRequest(caseId: string, request: SupplementRequest, actor?: User, expectedSnapshot?: string): Promise<void>;
  submitStudentSupplement(
    caseId: string,
    payload: {
      note: string;
      docTitle?: string;
      fileName?: string;
      versionToActivate?: number;
      attachment?: StoredAttachment;
    }
  ): Promise<void>;
  finalizeReviewCase(caseId: string, report: NonNullable<ReviewCase["finalReport"]>, expectedSnapshot?: string): Promise<void>;

  // Demo / UAT Utilities
  getDemoUsers(): Promise<User[]>;
  resetDemoData(): Promise<void>;
}
