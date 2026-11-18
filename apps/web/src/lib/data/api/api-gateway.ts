/* eslint-disable @typescript-eslint/no-unused-vars */
import { CampusDataGateway } from "../gateway";
import {
  User,
  UserRole,
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
} from "../../types";
import { UnsupportedOperationError, DataGatewayError } from "../errors";
import { ApiClient } from "./api-client";

export class ApiCampusDataGateway implements CampusDataGateway {
  private client: ApiClient;

  constructor(baseUrl: string) {
    this.client = new ApiClient(baseUrl);
  }

  private isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null;
  }

  private isUserRole(value: unknown): value is UserRole {
    return value === "student" || value === "officer";
  }

  private mapToUser(data: unknown): User {
    if (!this.isRecord(data)) {
      throw new DataGatewayError("validation", "Invalid user data received from API");
    }
    if (typeof data.id !== "string" || typeof data.name !== "string") {
      throw new DataGatewayError("validation", "Missing required user fields");
    }
    if (!this.isUserRole(data.role)) {
      throw new DataGatewayError("validation", `Invalid user role: ${String(data.role)}`);
    }

    return {
      id: data.id,
      name: data.name,
      role: data.role,
      email: typeof data.email === "string" ? data.email : "",
      mssv: typeof data.mssv === "string" ? data.mssv : undefined,
      major: typeof data.major === "string" ? data.major : undefined,
      classYear: typeof data.classYear === "string" ? data.classYear : undefined,
    };
  }

  async login(userId: string): Promise<User> {
    try {
      // P0 contract has /api/v1/auth/demo-login and /api/v1/me
      await this.client.post("/api/v1/auth/demo-login", { userId });
      const user = await this.client.get("/api/v1/me");
      return this.mapToUser(user);
    } catch (err) {
      if (err instanceof DataGatewayError && err.reason === "not_found") {
        throw new DataGatewayError("unauthorized", "User not found (HTTP 404)");
      }
      throw err;
    }
  }

  async resetDemoData(): Promise<void> {
    throw new UnsupportedOperationError("resetDemoData");
  }

  // --- Tickets ---
  async getTickets(): Promise<Ticket[]> {
    throw new UnsupportedOperationError("getTickets");
  }

  async getTicket(id: string): Promise<Ticket | undefined> {
    throw new UnsupportedOperationError("getTicket");
  }

  async createTicket(currentUser: User, data: Partial<Ticket>): Promise<Ticket> {
    throw new UnsupportedOperationError("createTicket");
  }

  async updateTicketStatus(id: string, status: TicketStatus, actorName: string): Promise<void> {
    throw new UnsupportedOperationError("updateTicketStatus");
  }

  async updateOfficerDraft(id: string, draft: string): Promise<void> {
    throw new UnsupportedOperationError("updateOfficerDraft");
  }

  async resetOfficerDraft(id: string): Promise<void> {
    throw new UnsupportedOperationError("resetOfficerDraft");
  }

  async toggleChecklistItem(ticketId: string, itemId: string): Promise<void> {
    throw new UnsupportedOperationError("toggleChecklistItem");
  }

  async addTicketMessage(
    ticketId: string,
    message: Omit<TicketMessage, "id" | "timestamp">
  ): Promise<void> {
    throw new UnsupportedOperationError("addTicketMessage");
  }

  async submitGate2Response(
    ticketId: string,
    actionType: "respond" | "request_info" | "resolve",
    customContent?: string
  ): Promise<void> {
    throw new UnsupportedOperationError("submitGate2Response");
  }

  // --- Certificates ---
  async runTicketVerification(ticketId: string): Promise<void> {
    throw new UnsupportedOperationError("runTicketVerification");
  }

  async retryCriterionVerification(ticketId: string, criterionId: string): Promise<void> {
    throw new UnsupportedOperationError("retryCriterionVerification");
  }

  async confirmCriterionReview(ticketId: string, criterionId: string, note?: string): Promise<void> {
    throw new UnsupportedOperationError("confirmCriterionReview");
  }

  async updateCertificateDraft(ticketId: string, edits: Partial<IssuedCertificateDocument>): Promise<void> {
    throw new UnsupportedOperationError("updateCertificateDraft");
  }

  // --- Chat ---
  async getChatSessions(): Promise<ChatSession[]> {
    // /api/v1/conversations exists but mapping might be complex, failing safe
    throw new UnsupportedOperationError("getChatSessions");
  }

  async createChatSession(): Promise<ChatSession> {
    throw new UnsupportedOperationError("createChatSession");
  }

  async deleteChatSession(sessionId: string): Promise<void> {
    throw new UnsupportedOperationError("deleteChatSession");
  }

  async addChatMessage(sessionId: string, msg: Omit<ChatMessage, "id" | "timestamp">): Promise<void> {
    throw new UnsupportedOperationError("addChatMessage");
  }

  async updateChatSessionGate1(
    sessionId: string,
    formData: NonNullable<ChatSession["gate1FormData"]>
  ): Promise<void> {
    throw new UnsupportedOperationError("updateChatSessionGate1");
  }

  async updateChatSessionL4(sessionId: string, isActive: boolean): Promise<void> {
    throw new UnsupportedOperationError("updateChatSessionL4");
  }

  // --- Reviews ---
  async getReviewCases(): Promise<ReviewCase[]> {
    throw new UnsupportedOperationError("getReviewCases");
  }

  async getReviewCase(id: string): Promise<ReviewCase | undefined> {
    throw new UnsupportedOperationError("getReviewCase");
  }

  async createReviewCase(data: Partial<ReviewCase>): Promise<ReviewCase> {
    throw new UnsupportedOperationError("createReviewCase");
  }

  async runAiReview(caseId: string): Promise<void> {
    throw new UnsupportedOperationError("runAiReview");
  }

  async updateFindingReview(
    caseId: string,
    findingId: string,
    updates: {
      officerStatus: FindingOfficerStatus;
      officerAdjustedLabel?: FindingAiLabel;
      officerNote?: string;
    }
  ): Promise<void> {
    throw new UnsupportedOperationError("updateFindingReview");
  }

  async sendSupplementRequest(caseId: string, request: SupplementRequest): Promise<void> {
    throw new UnsupportedOperationError("sendSupplementRequest");
  }

  async submitStudentSupplement(
    caseId: string,
    payload: { note: string; docTitle?: string; fileName?: string; versionToActivate?: number }
  ): Promise<void> {
    throw new UnsupportedOperationError("submitStudentSupplement");
  }

  async finalizeReviewCase(caseId: string, report: NonNullable<ReviewCase["finalReport"]>): Promise<void> {
    throw new UnsupportedOperationError("finalizeReviewCase");
  }

  async getDemoUsers(): Promise<User[]> {
    throw new UnsupportedOperationError("getDemoUsers");
  }
}
