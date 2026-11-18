import { CampusDataGateway } from "../gateway";
import {
  User,
  Ticket,
  TicketStatus,
  TicketMessage,
  ChatMessage,
  ChatSession,
  ReviewCase,
  ReviewDocument,
  FindingOfficerStatus,
  FindingAiLabel,
  SupplementRequest,
  IssuedCertificateDocument,
  StoredAttachment,
} from "../../types";
import {
  DEMO_USERS,
  INITIAL_TICKETS,
  INITIAL_CHAT_SESSIONS,
  INITIAL_REVIEW_CASES,
} from "./fixtures";
import { runCertificateVerification, buildDefaultCertificate } from "../../certificate-service";
import { DataGatewayError } from "../errors";
import { actionBlock, effectiveFinding, officerDraftFor, reviewReadiness, reviewSnapshot, reviewSources, ticketSnapshot } from "../../staff-policy";

const MOCK_DB_KEY = "campus247_mock_db_v1";

interface MockDatabase {
  tickets: Ticket[];
  chatSessions: ChatSession[];
  reviewCases: ReviewCase[];
}

export interface MockGatewayDependencies {
  generateId?: (prefix: string) => string;
  now?: () => Date;
  latencyMs?: number;
}

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value));

function formatClock(now: Date): string {
  return `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
}

function formatDateTime(now: Date): string {
  return `${formatClock(now)} · ${String(now.getDate()).padStart(2, "0")}/${String(
    now.getMonth() + 1
  ).padStart(2, "0")}/${now.getFullYear()}`;
}

export class MockCampusDataGateway implements CampusDataGateway {
  private db: MockDatabase;
  private savedDb: MockDatabase;
  private persistedSnapshot: string | null = null;
  private latencyMs: number;
  private seqCounter = 0;

  private generateIdFn: (prefix: string) => string;
  private nowFn: () => Date;

  constructor(deps?: MockGatewayDependencies) {
    this.nowFn = deps?.now ?? (() => new globalThis.Date());
    this.latencyMs = deps?.latencyMs ?? 300;
    if (deps?.generateId) {
      this.generateIdFn = deps.generateId;
    } else {
      this.generateIdFn = (prefix: string) => {
        this.seqCounter++;
        return `${prefix}-${Date.now().toString(36)}-${this.seqCounter}`;
      };
    }
    this.db = this.loadDb();
    this.savedDb = clone(this.db);
  }

  private loadDb(): MockDatabase {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(MOCK_DB_KEY);
        this.persistedSnapshot = saved;
        if (saved) {
          return this.normalizeMessageIds(JSON.parse(saved) as MockDatabase);
        }
      } catch (e) {
        throw new DataGatewayError("validation", "Không đọc được hồ sơ đã lưu. Dữ liệu cũ được giữ nguyên; hãy kiểm tra quyền lưu trữ của trình duyệt.", e);
      }
    }
    return this.getInitialDb();
  }

  private normalizeMessageIds(database: MockDatabase): MockDatabase {
    const normalize = <T extends { id: string }>(messages: T[], scope: string): T[] => {
      const seen = new Set<string>();
      return messages.map((message, index) => {
        if (!seen.has(message.id)) {
          seen.add(message.id);
          return message;
        }
        const uniqueId = `${message.id}-${scope}-${index}`;
        seen.add(uniqueId);
        return { ...message, id: uniqueId };
      });
    };

    return {
      ...database,
      chatSessions: database.chatSessions.map((session) => ({
        ...session,
        messages: normalize(session.messages, session.id),
      })),
      tickets: database.tickets.map((ticket) => ({
        ...ticket,
        messages: normalize(ticket.messages, ticket.id),
      })),
    };
  }

  private saveDb() {
    if (typeof window !== "undefined") {
      try {
        if (localStorage.getItem(MOCK_DB_KEY) !== this.persistedSnapshot) {
          throw new DataGatewayError("conflict", "Hồ sơ đã thay đổi ở tab khác. Hãy tải lại và kiểm tra; nháp được giữ nguyên.");
        }
        const next = JSON.stringify(this.db);
        localStorage.setItem(MOCK_DB_KEY, next);
        this.persistedSnapshot = next;
      } catch (e) {
        this.db = clone(this.savedDb);
        if (e instanceof DataGatewayError) throw e;
        throw new DataGatewayError("validation", "Chưa lưu được hồ sơ trên thiết bị. Nội dung đã lưu trước đó vẫn được giữ; hãy kiểm tra dung lượng và thử lại.", e);
      }
    }
    this.savedDb = clone(this.db);
  }

  private refreshDb() {
    if (typeof window === "undefined") return;
    this.db = this.loadDb();
    this.savedDb = clone(this.db);
  }

  /** Read, validate and commit while holding one lock shared by all local tabs. */
  private async mutate<T>(operation: () => T): Promise<T> {
    const commit = () => {
      this.refreshDb();
      try { return operation(); }
      catch (error) { this.db = clone(this.savedDb); throw error; }
    };
    if (typeof window !== "undefined" && window.navigator) {
      if (!window.navigator.locks) {
        throw new DataGatewayError("unsupported", "Trình duyệt chưa hỗ trợ lưu an toàn giữa các tab. Hãy dùng Chrome hoặc Edge trên HTTPS để tiếp tục.");
      }
      return window.navigator.locks.request(MOCK_DB_KEY, commit);
    }
    return commit();
  }

  private generateUniqueId(prefix: string, existingIds: Iterable<string>): string {
    const existing = new Set(existingIds);
    let candidate = this.generateIdFn(prefix);
    while (existing.has(candidate)) {
      candidate = this.generateIdFn(prefix);
    }
    return candidate;
  }

  private allMessageIds(): string[] {
    return this.db.chatSessions.flatMap((session) => session.messages.map((message) => message.id));
  }

  private allAuditIds(): string[] {
    return [
      ...this.db.tickets.flatMap((ticket) => ticket.auditLogs.map((entry) => entry.id)),
      ...this.db.reviewCases.flatMap((reviewCase) => reviewCase.auditLogs.map((entry) => entry.id)),
    ];
  }

  private getInitialDb(): MockDatabase {
    return {
      tickets: clone(INITIAL_TICKETS),
      chatSessions: clone(INITIAL_CHAT_SESSIONS || []),
      reviewCases: clone(INITIAL_REVIEW_CASES),
    };
  }

  private requireTicket(id: string): Ticket {
    const ticket = this.db.tickets.find((item) => item.id === id || item.code === id);
    if (!ticket) throw new DataGatewayError("not_found", "Ticket not found");
    return ticket;
  }

  private requireChatSession(sessionId: string): ChatSession {
    const session = this.db.chatSessions.find((item) => item.id === sessionId);
    if (!session) throw new DataGatewayError("not_found", "Chat session not found");
    return session;
  }

  private requireReviewCase(caseId: string): ReviewCase {
    const reviewCase = this.db.reviewCases.find((item) => item.id === caseId || item.code === caseId);
    if (!reviewCase) throw new DataGatewayError("not_found", "Review case not found");
    return reviewCase;
  }

  private async simulateLatency() {
    if (this.latencyMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, this.latencyMs));
    }
  }

  async resetDemoData(): Promise<void> {
    return this.mutate(() => {
      this.db = this.getInitialDb();
      this.saveDb();
      if (typeof window !== "undefined") {
        localStorage.removeItem("campus247_tickets_v2");
        localStorage.removeItem("campus247_reviews_v2");
        localStorage.removeItem("campus247_user_v2");
      }
    });
  }

  async login(userId: string): Promise<User> {
    await this.simulateLatency();
    const user = DEMO_USERS[userId];
    if (!user) {
      throw new DataGatewayError("unauthorized", "User not found in mock data");
    }
    return clone(user);
  }

  async getTickets(): Promise<Ticket[]> {
    await this.simulateLatency();
    this.refreshDb();
    return clone(this.db.tickets);
  }

  async getTicket(id: string): Promise<Ticket | undefined> {
    await this.simulateLatency();
    this.refreshDb();
    return clone(this.requireTicket(id));
  }

  async createTicket(currentUser: User, data: Partial<Ticket>): Promise<Ticket> {
    await this.simulateLatency();
    return this.mutate(() => {
      if (currentUser.role !== "student") {
        throw new DataGatewayError("unauthorized", "Only students can create tickets");
      }
      if (data.submissionKey) {
        const existing = this.db.tickets.find((ticket) => ticket.studentId === currentUser.id && ticket.submissionKey === data.submissionKey);
        if (existing) return clone(existing);
      }
      const ticketType = data.type || "certificate";
      const purpose = data.purpose?.trim();
      if (ticketType === "certificate" && !purpose) {
        throw new DataGatewayError("validation", "Purpose is required for a certificate request");
      }
      const newId = this.generateUniqueId(
        "TKT",
        this.db.tickets.flatMap((ticket) => [ticket.id, ticket.code])
      );
      const now = this.nowFn();
      const timestamp = now.toISOString();

      const newTicket: Ticket = {
        id: newId,
        code: newId,
        title: data.title || "Cấp Giấy xác nhận sinh viên (BM-03)",
        type: ticketType,
        studentId: currentUser.id,
        studentName: currentUser.name,
        studentMssv: currentUser.mssv || currentUser.id,
        studentMajor: currentUser.major || "K18 Kỹ thuật Phần mềm",
        studentClassYear: currentUser.classYear || "Khóa 18 (2021 - 2025)",
        studentEmail: currentUser.email,
        status: "open",
        priority: data.priority || "normal",
        priorityReason: data.priorityReason || "Hồ sơ tạo từ Cổng 1, sinh viên đã xác thực thông tin khai báo.",
        createdAt: now.toISOString(),
        submittedAt: timestamp,
        slaDeadline: data.slaDeadline || "24h - 48h",
        certificateType: data.certificateType || "Giấy xác nhận sinh viên chính quy (BM-03)",
        receiveMethod: data.receiveMethod || "digital_pdf",
        destinationOrg: data.destinationOrg || "Ngân hàng Chính sách Xã hội",
        purpose: purpose || data.priorityReason?.trim() || "Yêu cầu học vụ",
        notes: data.notes,
        requestPayload: data.requestPayload ? clone(data.requestPayload) : undefined,
        submissionKey: data.submissionKey,
        attachments: data.attachments ? clone(data.attachments) : undefined,
        isL4: ticketType === "complaint" || data.isL4,
        l4TriggerReason: data.l4TriggerReason,
        aiSummary: {
          target: `Sinh viên cần ${ticketType === "certificate" ? "cấp" : "xử lý"} ${data.certificateType || data.title || "yêu cầu học vụ"} cho mục đích: ${purpose || data.priorityReason || "Yêu cầu học vụ"}.`,
          context: "Hồ sơ được gửi trực tuyến qua Cổng 1; chưa có ghi nhận nợ đọng hoặc cảnh cáo học vụ.",
          categorySla: "Ca cấp giấy tiêu chuẩn (L2). SLA phản hồi: 24h - 48h.",
          confidence: "98.5%",
          nextBestAction: "Kiểm tra tình trạng sinh viên và học phí trên hệ thống đào tạo trước khi phản hồi tiếp nhận.",
          nextBestActionReason: "Đảm bảo tuân thủ Điều 14 Quy chế Đào tạo & CTSV.",
        },
        facts: [],
        checklist: [],
        sopReference: "SOP-CTSV-01 (Mẫu tham khảo)",
        sopDeadline: "Thời hạn xử lý: Trong vòng 48 giờ làm việc.",
        officerDraftDefault: `Chào bạn ${currentUser.name}, Phòng Đào tạo & CTSV đã tiếp nhận yêu cầu ${data.title || "cấp Giấy xác nhận sinh viên"} của bạn. Hồ sơ đang được đối soát với CSDL Đào tạo.`,
        officerDraft: `Chào bạn ${currentUser.name}, Phòng Đào tạo & CTSV đã tiếp nhận yêu cầu ${data.title || "cấp Giấy xác nhận sinh viên"} của bạn. Hồ sơ đang được đối soát với CSDL Đào tạo.`,
        assignedOfficerId: "OF001",
        assignedOfficerName: "ThS. Trần Thu Hà",
        messages: [
          {
            id: this.generateUniqueId("msg", [
              ...this.allMessageIds(),
              ...this.db.tickets.flatMap((ticket) => ticket.messages.map((message) => message.id)),
            ]),
            senderId: "system",
            senderName: "Hệ thống AI tự động",
            senderRole: "system",
            content: "Hồ sơ tạo thành công từ Cổng 1 và đã chuyển vào hàng chờ Cán bộ Phòng Đào tạo & CTSV.",
            timestamp,
          },
        ],
        auditLogs: [
          {
            id: this.generateUniqueId("aud", this.allAuditIds()),
            timestamp: timestamp,
            source: "Cổng 1 (Sinh viên)",
            action: `Sinh viên nộp yêu cầu ${data.title || "Cấp giấy xác nhận sinh viên"}`,
            actor: `${currentUser.name} (${currentUser.mssv || currentUser.id})`,
          },
        ],
      };

      if (ticketType !== "certificate" || newTicket.requestPayload) {
        newTicket.aiSummary = {
          target: data.title || "Yêu cầu hỗ trợ học vụ",
          context: data.notes || purpose || "Sinh viên gửi yêu cầu để cán bộ xem xét.",
          categorySla: ticketType === "complaint" ? "Khiếu nại điểm thi cần cán bộ xác minh." : ticketType === "lookup" ? "Câu hỏi học vụ cần cán bộ hỗ trợ." : "Yêu cầu tài liệu cần cán bộ kiểm tra theo loại đã nộp.",
          confidence: "Chưa xác minh",
          nextBestAction: "Kiểm tra nội dung sinh viên cung cấp và phản hồi trong hồ sơ.",
          nextBestActionReason: "Thông tin cần được cán bộ đối chiếu trước khi kết luận.",
        };
        newTicket.sopReference = "Hướng dẫn tiếp nhận học vụ";
        newTicket.sopDeadline = "Theo thời hạn được cán bộ xác nhận.";
        newTicket.slaDeadline = data.slaDeadline || "Chờ cán bộ xác nhận";
      }

      if (newTicket.type === "certificate" && !newTicket.requestPayload) {
        newTicket.systemVerifications = runCertificateVerification(newTicket);
        newTicket.issuedCertificate = buildDefaultCertificate(newTicket);
        newTicket.documentStatus = "draft";
      }

      this.db.tickets = [newTicket, ...this.db.tickets];
      this.saveDb();
      return clone(newTicket);
    });
  }

  async updateTicketStatus(id: string, status: TicketStatus, actorName: string): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const idx = this.db.tickets.findIndex((t) => t.id === id);
      if (idx === -1) throw new DataGatewayError("not_found", "Ticket not found");

      const t = this.db.tickets[idx];
      const now = this.nowFn();
      const timestamp = now.toISOString();
      const newLog = {
        id: this.generateUniqueId("aud", this.allAuditIds()),
        timestamp,
        source: "Bàn làm việc Cán bộ",
        action: `Cập nhật trạng thái sang: ${status === "open" ? "Mới tiếp nhận" : status === "pending_officer" ? "Chờ cán bộ" : "Đã hoàn tất"}`,
        actor: actorName,
      };
      t.status = status;
      t.auditLogs.push(newLog);
      this.saveDb();
    });
  }

  async updateOfficerDraft(id: string, draft: string, actor?: User, expectedDraft?: string): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const t = this.requireTicket(id);
      if (actor) {
        if (actor.role !== "officer") throw new DataGatewayError("unauthorized", "Chỉ cán bộ được lưu nháp phản hồi.");
        if (t.status === "resolved") throw new DataGatewayError("conflict", "Hồ sơ đã hoàn tất; nháp đang soạn được giữ nguyên.");
        if (expectedDraft !== undefined && officerDraftFor(t, actor.id) !== expectedDraft) throw new DataGatewayError("conflict", "Nháp đã được lưu ở tab khác. Nội dung đang sửa được giữ; hãy đối chiếu trước khi lưu lại.");
        t.officerDrafts = { ...t.officerDrafts, [actor.id]: draft };
      } else {
        t.officerDraft = draft;
      }
      this.saveDb();
    });
  }

  async resetOfficerDraft(id: string): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const t = this.requireTicket(id);
      t.officerDraft = t.officerDraftDefault;
      this.saveDb();
    });
  }

  async toggleChecklistItem(ticketId: string, itemId: string): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const t = this.requireTicket(ticketId);
      const checklistItem = t.checklist.find((item) => item.id === itemId);
      if (!checklistItem) throw new DataGatewayError("not_found", "Checklist item not found");
      checklistItem.checked = !checklistItem.checked;
      this.saveDb();
    });
  }

  async addTicketMessage(ticketId: string, message: Omit<TicketMessage, "id" | "timestamp">): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const t = this.requireTicket(ticketId);
      const now = this.nowFn();
      t.messages.push({
        id: this.generateUniqueId("msg", [
          ...this.allMessageIds(),
          ...this.db.tickets.flatMap((ticket) => ticket.messages.map((item) => item.id)),
        ]),
        ...message,
        timestamp: now.toISOString(),
      });
      this.saveDb();
    });
  }

  async submitGate2Response(
    ticketId: string,
    actionType: "respond" | "request_info" | "resolve",
    customContent?: string,
    actor?: User,
    expectedSnapshot?: string
  ): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const t = this.requireTicket(ticketId);

      if (!actor || actor.role !== "officer") throw new DataGatewayError("unauthorized", "Chưa xác định được cán bộ xử lý.");
      if (expectedSnapshot && expectedSnapshot !== ticketSnapshot(t)) throw new DataGatewayError("conflict", "Hồ sơ đã thay đổi. Hãy kiểm tra lại; nháp được giữ nguyên.");
      const blocked = actionBlock(t, actionType, customContent || t.officerDraft);
      if (blocked) throw new DataGatewayError("validation", blocked);

      const now = this.nowFn();
      const timestampFull = now.toISOString();

      let messageContent = customContent || t.officerDraft;
      let nextStatus: TicketStatus = t.status;
      let auditAction = "";

      if (actionType === "respond") {
        nextStatus = "pending_officer";
        auditAction = "Cán bộ gửi phản hồi nghiệp vụ qua Cổng Kiểm duyệt 2";
      } else if (actionType === "request_info") {
        nextStatus = "pending_officer";
        messageContent = customContent || "Yêu cầu bổ sung hồ sơ chứng từ.";
        auditAction = "Cán bộ gửi yêu cầu bổ sung hồ sơ";
      } else if (actionType === "resolve") {
        nextStatus = "resolved";
        messageContent = customContent || t.officerDraft;
        auditAction = "Cán bộ hoàn tất xử lý hồ sơ; không phát hành tài liệu";
      }

      t.status = nextStatus;
      t.messages.push({
        id: this.generateUniqueId("msg", [
          ...this.allMessageIds(),
          ...this.db.tickets.flatMap((ticket) => ticket.messages.map((item) => item.id)),
        ]),
        senderId: actor.id,
        senderName: actor.name,
        senderRole: "officer",
        content: messageContent,
        timestamp: now.toISOString(),
      });
      t.auditLogs.push({
        id: this.generateUniqueId("aud", this.allAuditIds()),
        timestamp: timestampFull,
        source: "Cổng Kiểm duyệt Cán bộ",
        action: auditAction,
        actor: `${actor.name} (${actor.id})`,
      });

      this.saveDb();
    });
  }

  async runTicketVerification(ticketId: string): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const t = this.requireTicket(ticketId);
      if (t.type !== "certificate") {
        throw new DataGatewayError("validation", "Ticket does not support certificate verification");
      }
      t.systemVerifications = runCertificateVerification(t);
      t.dataChangedSinceLastCheck = false;
      this.saveDb();
    });
  }

  async retryCriterionVerification(ticketId: string, criterionId: string): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const t = this.requireTicket(ticketId);
      if (!t.systemVerifications) {
        throw new DataGatewayError("validation", "Ticket has no verification results");
      }

      const now = this.nowFn();
      const timestamp = formatDateTime(now);

      const item = t.systemVerifications.find((i) => i.id === criterionId || i.criterionKey === criterionId);
      if (!item) throw new DataGatewayError("not_found", "Verification criterion not found");
      item.status = "passed";
      item.lookupTimestamp = timestamp;
      item.reason = "Đã tái kết nối thành công CSDL Đào tạo [PORTAL-DB] (HTTP 200 OK). Kết quả: Dữ liệu đào tạo hợp lệ.";
      if (item.evidenceDetails) {
        item.evidenceDetails.rawSnippet = `RETRY SUCCESS: HTTP 200 OK at ${timestamp}`;
      }
      t.auditLogs.push({
        id: this.generateIdFn("aud"),
        timestamp,
        source: "Hệ thống Đối soát Tự động",
        action: "Cán bộ kích hoạt Thử lại tra cứu CSDL Đào tạo; hệ thống tái kết nối thành công.",
        actor: "OF001 (ThS. Trần Thu Hà)",
      });
      this.saveDb();
    });
  }

  async confirmCriterionReview(ticketId: string, criterionId: string, note?: string): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const t = this.requireTicket(ticketId);
      if (!t.systemVerifications) {
        throw new DataGatewayError("validation", "Ticket has no verification results");
      }

      const item = t.systemVerifications.find((i) => i.id === criterionId || i.criterionKey === criterionId);
      if (!item) throw new DataGatewayError("not_found", "Verification criterion not found");
      item.officerReviewStatus = "confirmed";
      item.officerReviewNote = note || "Cán bộ đã đối soát bằng chứng.";

      const allConfirmed = t.systemVerifications.every((v) => v.officerReviewStatus === "confirmed");
      t.documentStatus = allConfirmed ? "approved" : t.documentStatus || "draft";
      this.saveDb();
    });
  }

  async updateCertificateDraft(ticketId: string, edits: Partial<IssuedCertificateDocument>): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const t = this.requireTicket(ticketId);
      if (!t.issuedCertificate) {
        throw new DataGatewayError("validation", "Ticket has no certificate draft");
      }
      t.issuedCertificate = { ...t.issuedCertificate, ...edits };
      this.saveDb();
    });
  }

  async getChatSessions(): Promise<ChatSession[]> {
    await this.simulateLatency();
    this.refreshDb();
    return clone(this.db.chatSessions);
  }

  async createChatSession(): Promise<ChatSession> {
    await this.simulateLatency();
    return this.mutate(() => {
      const newId = this.generateUniqueId("sess", this.db.chatSessions.map((session) => session.id));
      const initialMsg: ChatMessage = {
        id: this.generateUniqueId("cm", this.allMessageIds()),
        sender: "bot",
        text: "Xin chào! Tôi là Trợ lý Học vụ Campus 24/7. Tôi có thể hỗ trợ bạn tra cứu quy chế học vụ (L1), tự động soạn thảo biểu mẫu BM-03 (L2), hoặc tiếp nhận chuyển tiếp khiếu nại đào tạo (L4). Bạn đang cần hỗ trợ vấn đề gì hôm nay?",
        timestamp: "Vừa xong",
      };
      const newSession: ChatSession = {
        id: newId,
        title: "Cuộc hội thoại mới",
        preview: "Bắt đầu cuộc trao đổi mới với Trợ lý AI...",
        updatedAt: "Vừa xong",
        tag: "Chung",
        messages: [initialMsg],
        isL4HandoverActive: false,
      };
      this.db.chatSessions.unshift(newSession);
      this.saveDb();
      return clone(newSession);
    });
  }

  async deleteChatSession(sessionId: string): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      this.requireChatSession(sessionId);
      this.db.chatSessions = this.db.chatSessions.filter((s) => s.id !== sessionId);
      this.saveDb();
    });
  }

  async addChatMessage(sessionId: string, msg: Omit<ChatMessage, "id" | "timestamp">): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const s = this.requireChatSession(sessionId);
      s.messages.push({
        id: this.generateUniqueId("cm", [
          ...this.allMessageIds(),
          ...this.db.tickets.flatMap((ticket) => ticket.messages.map((item) => item.id)),
        ]),
        timestamp: "Vừa xong",
        ...msg,
      });
      this.saveDb();
    });
  }

  async updateChatSessionGate1(sessionId: string, formData: NonNullable<ChatSession["gate1FormData"]>): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const s = this.requireChatSession(sessionId);
      s.gate1FormData = formData;
      this.saveDb();
    });
  }

  async updateChatSessionL4(sessionId: string, isActive: boolean): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const s = this.requireChatSession(sessionId);
      s.isL4HandoverActive = isActive;
      this.saveDb();
    });
  }

  async getReviewCases(): Promise<ReviewCase[]> {
    await this.simulateLatency();
    this.refreshDb();
    return clone(this.db.reviewCases);
  }

  async getReviewCase(id: string): Promise<ReviewCase | undefined> {
    await this.simulateLatency();
    this.refreshDb();
    return clone(this.requireReviewCase(id));
  }

  async createReviewCase(data: Partial<ReviewCase>): Promise<ReviewCase> {
    await this.simulateLatency();
    return this.mutate(() => {

      const studentId = data.studentId?.trim();
      const targetCourseCode = data.targetCourseCode?.trim();
      const targetCourseName = data.targetCourseName?.trim();
      const priorCourseCode = data.priorCourseCode?.trim();
      const priorCourseName = data.priorCourseName?.trim();
      if (!studentId) throw new DataGatewayError("validation", "studentId is required");
      if (!targetCourseCode) throw new DataGatewayError("validation", "targetCourseCode is required");
      if (!targetCourseName) throw new DataGatewayError("validation", "targetCourseName is required");
      if (!priorCourseCode) throw new DataGatewayError("validation", "priorCourseCode is required");
      if (!priorCourseName) throw new DataGatewayError("validation", "priorCourseName is required");

      const student = DEMO_USERS[studentId];
      const studentName = data.studentName?.trim() || student?.name;
      if (!studentName) throw new DataGatewayError("validation", "studentName is required");

      const newId = this.generateIdFn("RC");
      const now = this.nowFn();
      const nowStr = now.toISOString();
      const criteria = clone(data.criteria ?? []);
      const aiSummary = data.aiSummary
        ? clone(data.aiSummary)
        : {
            overallRecommendation: "",
            totalCriteria: criteria.length,
            matchCount: 0,
            differenceCount: 0,
            insufficientCount: 0,
            contradictionCount: 0,
            isStale: false,
          };

      const newCase: ReviewCase = {
        id: newId,
        code: newId,
        createdAt: nowStr,
        updatedAt: nowStr,
        status: "in_review",
        studentId,
        studentName,
        studentMssv: data.studentMssv || student?.mssv || studentId,
        studentMajor: data.studentMajor || student?.major || "",
        studentClassYear: data.studentClassYear || student?.classYear || "",
        studentEmail: data.studentEmail || student?.email || "",
        targetCourseCode,
        targetCourseName,
        targetCourseCredits: data.targetCourseCredits ?? 0,
        targetDepartment: data.targetDepartment || "",
        priorCourseCode,
        priorCourseName,
        priorCourseCredits: data.priorCourseCredits ?? 0,
        priorInstitution: data.priorInstitution || "",
        priorAcademicYear: data.priorAcademicYear || "",
        priorGrade: data.priorGrade || "",
        criteriaSetId: data.criteriaSetId || "",
        criteriaSetName: data.criteriaSetName || "",
        criteria,
        documents: clone(data.documents ?? []),
        aiStatus: "running",
        aiSummary,
        findings: clone(data.findings ?? []),
        supplementRequests: [],
        auditLogs: [{
          id: this.generateIdFn("aud"),
          timestamp: nowStr,
          actorName: "System",
          actorRole: "system",
          action: "Tạo hồ sơ rà soát",
        }],
      };
      this.db.reviewCases.unshift(newCase);
      this.saveDb();
      return clone(newCase);
    });
  }

  async runAiReview(caseId: string): Promise<void> {
    await this.simulateLatency();
    this.requireReviewCase(caseId);
    throw new DataGatewayError("unsupported", "Chưa kết nối chạy lại AI. Hãy kiểm tra nguồn hiện hành và ghi nhận nhận định cán bộ.");
  }

  async updateFindingReview(
    caseId: string,
    findingId: string,
    updates: { officerStatus: FindingOfficerStatus; officerAdjustedLabel?: FindingAiLabel; officerNote?: string },
    actor?: User,
    expectedSnapshot?: string
  ): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const c = this.requireReviewCase(caseId);
      if (c.status === "completed") throw new DataGatewayError("conflict", "Hồ sơ rà soát đã hoàn tất.");
      if (!actor || actor.role !== "officer") throw new DataGatewayError("unauthorized", "Chưa xác định được cán bộ thẩm định.");
      if (expectedSnapshot && expectedSnapshot !== reviewSnapshot(c)) throw new DataGatewayError("conflict", "Hồ sơ hoặc nguồn đã thay đổi. Hãy kiểm tra lại.");
      const f = c.findings.find((item) => item.id === findingId);
      if (!f) throw new DataGatewayError("not_found", "Review finding not found");
      f.officerStatus = updates.officerStatus;
      if (updates.officerAdjustedLabel !== undefined) f.officerAdjustedLabel = updates.officerAdjustedLabel;
      if (updates.officerNote !== undefined) f.officerNote = updates.officerNote;
      f.officerReviewedAt = this.nowFn().toISOString();
      f.officerReviewedBy = actor.id;
      f.officerSourceVersion = reviewSources(c);
      c.updatedAt = f.officerReviewedAt;
      c.auditLogs.push({ id: this.generateIdFn("aud"), timestamp: f.officerReviewedAt, actorName: actor.name, actorRole: "officer", action: `Kiểm tra tiêu chí: ${f.criterionTitle}`, details: `${effectiveFinding(f)} · ${f.officerNote || ""}` });
      this.saveDb();
    });
  }

  async sendSupplementRequest(caseId: string, request: SupplementRequest, actor?: User, expectedSnapshot?: string): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const c = this.requireReviewCase(caseId);
      if (c.status === "completed") throw new DataGatewayError("conflict", "Hồ sơ rà soát đã hoàn tất.");
      const officer = actor || DEMO_USERS[request.sentBy];
      if (!officer || officer.role !== "officer" || officer.id !== request.sentBy) throw new DataGatewayError("unauthorized", "Chưa xác định được cán bộ gửi yêu cầu.");
      if (expectedSnapshot && expectedSnapshot !== reviewSnapshot(c)) throw new DataGatewayError("conflict", "Hồ sơ đã thay đổi. Hãy kiểm tra lại yêu cầu; nháp được giữ nguyên.");
      if (request.targetStudentId !== c.studentId) throw new DataGatewayError("validation", "Người nhận không thuộc hồ sơ đang xử lý.");
      if (!request.id || !request.targetStudentId || !request.subject || !request.messageBody) {
        throw new DataGatewayError("validation", "Supplement request is missing required fields");
      }
      if (!request.messageBody.trim() || request.messageBody.length > 10000) throw new DataGatewayError("validation", "Nội dung bổ sung cần từ 1 đến 10.000 ký tự.");
      if (c.supplementRequests.some(item => item.id === request.id)) throw new DataGatewayError("conflict", "Yêu cầu này đã được gửi. Hãy tải lại hồ sơ.");
      c.supplementRequests.push(clone(request));
      c.status = "waiting_supplement";
      c.updatedAt = this.nowFn().toISOString();
      c.auditLogs.push({
        id: this.generateUniqueId("aud", this.allAuditIds()),
        timestamp: c.updatedAt,
        actorName: `${officer.name} (${officer.id})`,
        actorRole: "officer",
        action: "Cán bộ gửi yêu cầu bổ sung hồ sơ",
        details: `${request.subject} · ${request.messageBody}`,
      });
      this.saveDb();
    });
  }

  async submitStudentSupplement(caseId: string, payload: { note: string; docTitle?: string; fileName?: string; versionToActivate?: number; attachment?: StoredAttachment }): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const c = this.requireReviewCase(caseId);
      const note = payload.note.trim();
      if (!note) throw new DataGatewayError("validation", "Supplement note is required");
      if (
        payload.versionToActivate !== undefined &&
        (!Number.isInteger(payload.versionToActivate) || payload.versionToActivate < 1)
      ) {
        throw new DataGatewayError("validation", "versionToActivate must be a positive integer");
      }

      const req = c.supplementRequests.find((request) => request.status === "sent");
      if (!req) {
        throw new DataGatewayError("conflict", "No pending supplement request is available for this case");
      }

      const requestedTitle = payload.docTitle?.trim();
      const requestedFileName = payload.fileName?.trim();
      let document = requestedTitle
        ? c.documents.find((item) => item.title === requestedTitle)
        : undefined;
      if (!document && requestedFileName) {
        document = c.documents.find((item) =>
          item.versions.some((version) => version.fileName === requestedFileName)
        );
      }
      if (!document && !requestedTitle) {
        document = c.documents.find((item) => item.type === "syllabus_old");
      }

      const now = this.nowFn();
      const nowIso = now.toISOString();
      const versionNumber = payload.versionToActivate ?? (document?.currentVersion ?? 0) + 1;
      if (!Number.isInteger(versionNumber) || versionNumber < 1) {
        throw new DataGatewayError("validation", "Supplement version must be a positive integer");
      }

      if (!document) {
        if (!requestedFileName && !requestedTitle) {
          throw new DataGatewayError("validation", "A supplemental document needs a title or file name");
        }
        const initialFileName = requestedFileName || requestedTitle || `supplement-v${versionNumber}`;
        const newVersion: ReviewDocument["versions"][number] = {
          version: versionNumber,
          uploadedAt: formatDateTime(now),
          uploadedBy: "student",
          fileName: initialFileName,
          attachment: payload.attachment,
          legibility: "good",
          sections: [],
          isLatest: true,
        };
        document = {
          id: this.generateIdFn("doc"),
          type: "supplement",
          title: requestedTitle || initialFileName,
          institution: "Sinh viên nộp bổ sung",
          versions: [newVersion],
          currentVersion: versionNumber,
          required: false,
        };
        c.documents.push(document);
      } else {
        if (requestedTitle) document.title = requestedTitle;
        const existingVersion = document.versions.find((version) => version.version === versionNumber);
        if (existingVersion) {
          if (requestedFileName) existingVersion.fileName = requestedFileName;
          existingVersion.isLatest = true;
        } else {
          if (!requestedFileName) {
            throw new DataGatewayError(
              "validation",
              `fileName is required when document version ${versionNumber} does not exist`
            );
          }
          document.versions.push({
            version: versionNumber,
            uploadedAt: formatDateTime(now),
            uploadedBy: "student",
            fileName: requestedFileName,
            attachment: payload.attachment,
            legibility: "good",
            sections: [],
            isLatest: true,
          });
        }
        for (const version of document.versions) {
          version.isLatest = version.version === versionNumber;
        }
        document.currentVersion = versionNumber;
      }

      req.status = "responded";
      req.studentReply = {
        submittedAt: nowIso,
        note,
        supplementedDocumentIds: [document.id],
      };
      c.status = "in_review";
      c.updatedAt = nowIso;
      c.aiStatus = "stale_needs_update";
      c.aiSummary = {
        ...c.aiSummary,
        isStale: true,
        staleReason: "Hồ sơ có tài liệu bổ sung mới cần chạy lại rà soát AI.",
      };
      c.auditLogs.push({
        id: this.generateIdFn("aud"),
        timestamp: nowIso,
        actorName: c.studentName,
        actorRole: "student",
        action: `Sinh viên nộp bổ sung hồ sơ: ${note}`,
        details: requestedFileName || document.title,
      });
      this.saveDb();
    });
  }

  async finalizeReviewCase(caseId: string, report: NonNullable<ReviewCase["finalReport"]>, expectedSnapshot?: string): Promise<void> {
    await this.simulateLatency();
    return this.mutate(() => {
      const c = this.requireReviewCase(caseId);
      if (c.status === "completed") throw new DataGatewayError("conflict", "Hồ sơ rà soát đã hoàn tất.");
      if (expectedSnapshot && expectedSnapshot !== reviewSnapshot(c)) throw new DataGatewayError("conflict", "Hồ sơ đã thay đổi. Hãy xem lại phiếu trước khi hoàn tất.");
      const readiness = reviewReadiness(c);
      if (readiness.reason) throw new DataGatewayError("validation", readiness.reason);
      if (!report.conclusionSummary.trim()) throw new DataGatewayError("validation", "Cần nhập căn cứ kết luận.");
      if (report.decisionRecommendation === "propose_recognition" && readiness.issues.length) throw new DataGatewayError("validation", "Còn tiêu chí có vấn đề; cần đề xuất có điều kiện hoặc không công nhận với căn cứ cụ thể.");
      c.finalReport = clone(report);
      c.status = "completed";
      c.updatedAt = this.nowFn().toISOString();
      c.auditLogs.push({ id: this.generateUniqueId("aud", this.allAuditIds()), timestamp: c.updatedAt, actorName: `${report.officerName} (${report.officerId})`, actorRole: "officer", action: "Cán bộ hoàn tất phiếu đề xuất rà soát", details: report.conclusionSummary });
      this.saveDb();
    });
  }

  async getDemoUsers(): Promise<User[]> {
    await this.simulateLatency();
    return clone(Object.values(DEMO_USERS));
  }
}
