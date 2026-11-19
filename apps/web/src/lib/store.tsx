"use client";

import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";
import {
  User,
  Ticket,
  TicketStatus,
  ChatMessage,
  ChatSession,
  ReviewCase,
  FindingOfficerStatus,
  FindingAiLabel,
  SupplementRequest,
  IssuedCertificateDocument,
  StoredAttachment,
} from "./types";
import { createGateway } from "./data/create-gateway";
import { getDataConfig, DataConfig } from "./data/config";
import { CampusDataGateway } from "./data/gateway";
import { officerDraftFor } from "./staff-policy";
import { useTheme } from "./theme";
import {
  ConfigurationError,
  DataGatewayError,
  UnsupportedOperationError,
} from "./data/errors";

export type DataStatus =
  | "loading"
  | "ready"
  | "configuration_error"
  | "unsupported"
  | "connection_error"
  | "data_error";

function toDataGatewayError(error: unknown): DataGatewayError {
  if (error instanceof DataGatewayError) return error;
  return new DataGatewayError(
    "unknown",
    error instanceof Error ? error.message : String(error),
    error
  );
}

export function statusForError(error: DataGatewayError): DataStatus {
  if (error.reason === "configuration") return "configuration_error";
  if (error.reason === "unsupported") return "unsupported";
  if (error.reason === "network" || error.reason === "server") return "connection_error";
  return "data_error";
}

export function requireGateway(
  gateway: CampusDataGateway | null,
  dataError: DataGatewayError | null
): CampusDataGateway {
  if (gateway) return gateway;
  if (dataError) throw dataError;
  throw new ConfigurationError("Data gateway is not initialized.");
}

interface InitialDataState {
  config: DataConfig | null;
  gateway: CampusDataGateway | null;
  error: DataGatewayError | null;
  status: DataStatus;
}

export function initializeDataState(): InitialDataState {
  try {
    const config = getDataConfig();
    try {
      return {
        config,
        gateway: createGateway(config),
        error: null,
        status: "loading",
      };
    } catch (error: unknown) {
      const dataError = toDataGatewayError(error);
      return {
        config,
        gateway: null,
        error: dataError,
        status: statusForError(dataError),
      };
    }
  } catch (error: unknown) {
    const dataError = toDataGatewayError(error);
    return {
      config: null,
      gateway: null,
      error: dataError,
      status: "configuration_error",
    };
  }
}

interface BootstrapData {
  tickets: Ticket[];
  chatSessions: ChatSession[];
  reviewCases: ReviewCase[];
  demoUsers: User[];
  currentUser: User;
  status: "ready";
}

export async function bootstrapData(
  config: DataConfig | null,
  gateway: CampusDataGateway | null
): Promise<BootstrapData> {
  if (!config || !gateway) {
    throw new ConfigurationError("Data bootstrap requires a valid configuration and gateway.");
  }
  if (config.mode === "api") {
    throw new UnsupportedOperationError("API data bootstrap");
  }

  const activeGateway = requireGateway(gateway, null);
  const [tickets, chatSessions, reviewCases, demoUsers] = await Promise.all([
    activeGateway.getTickets(),
    activeGateway.getChatSessions(),
    activeGateway.getReviewCases(),
    activeGateway.getDemoUsers(),
  ]);
  const currentUser = await activeGateway.login("SV001");
  return {
    tickets,
    chatSessions,
    reviewCases,
    demoUsers,
    currentUser,
    status: "ready",
  };
}

interface StoreContextType {
  // Theme
  theme: "light" | "dark";
  toggleTheme: () => void;

  // Data Layer State
  isDataLoading: boolean;
  dataError: DataGatewayError | null;
  dataStatus: DataStatus;
  dataConfig: DataConfig | null;

  reloadData: () => Promise<void>;

  // Auth / Current User
  currentUser: User | null;
  setCurrentUser: (user: User) => void;
  login: (userId: string, remember?: boolean) => Promise<boolean>;
  logout: () => void;
  demoUsers: User[];

  // Tickets
  tickets: Ticket[];
  getTicket: (id: string) => Ticket | undefined;
  createTicket: (data: Partial<Ticket>) => Promise<Ticket>;
  updateTicketStatus: (id: string, status: TicketStatus, actorName: string) => Promise<void>;
  updateOfficerDraft: (id: string, draft: string) => Promise<void>;
  resetOfficerDraft: (id: string) => Promise<void>;
  toggleChecklistItem: (ticketId: string, itemId: string) => Promise<void>;
  addTicketMessage: (
    ticketId: string,
    message: { senderId: string; senderName: string; senderRole: "student" | "officer" | "system"; content: string }
  ) => Promise<void>;
  submitGate2Response: (
    ticketId: string,
    actionType: "respond" | "request_info" | "resolve",
    customContent?: string,
    expectedSnapshot?: string
  ) => Promise<void>;
  resetAllDemoData: () => Promise<void>;

  // Certificate Verification & BM-03 Issuance
  runTicketVerification: (ticketId: string) => Promise<void>;
  retryCriterionVerification: (ticketId: string, criterionId: string) => Promise<void>;
  confirmCriterionReview: (ticketId: string, criterionId: string, note?: string) => Promise<void>;
  updateCertificateDraft: (ticketId: string, edits: Partial<IssuedCertificateDocument>) => Promise<void>;
  issueCertificate: (ticketId: string) => Promise<IssuedCertificateDocument | null>;

  // Chat Assistant State & Sessions
  chatSessions: ChatSession[];
  activeSessionId: string;
  selectChatSession: (sessionId: string) => void;
  createNewChatSession: () => Promise<void>;
  deleteChatSession: (sessionId: string) => Promise<void>;
  chatMessages: ChatMessage[];
  addChatMessage: (msg: Omit<ChatMessage, "id" | "timestamp">) => Promise<void>;
  isL4HandoverActive: boolean;
  setL4HandoverActive: (active: boolean) => void;
  isGate1Open: boolean;
  setGate1Open: (open: boolean) => void;
  gate1FormData: {
    fullName: string;
    mssv: string;
    classYear: string;
    department: string;
    reason: string;
    destinationOrg: string;
    receiveMethod: "digital_pdf" | "paper_stamped";
    academicStatus: string;
  };
  setGate1FormData: React.Dispatch<
    React.SetStateAction<{
      fullName: string;
      mssv: string;
      classYear: string;
      department: string;
      reason: string;
      destinationOrg: string;
      receiveMethod: "digital_pdf" | "paper_stamped";
      academicStatus: string;
    }>
  >;
  lastUpdatedField: "reason" | "receiveMethod" | null;
  updateGate1Field: (field: "reason" | "receiveMethod" | "destinationOrg", value: string) => void;

  // Academic Review Cases (Rà soát học phần)
  reviewCases: ReviewCase[];
  getReviewCase: (id: string) => ReviewCase | undefined;
  createReviewCase: (data: Partial<ReviewCase>) => Promise<ReviewCase>;
  runAiReview: (caseId: string) => Promise<void>;
  updateFindingReview: (
    caseId: string,
    findingId: string,
    updates: {
      officerStatus: FindingOfficerStatus;
      officerAdjustedLabel?: FindingAiLabel;
      officerNote?: string;
    },
    expectedSnapshot?: string
  ) => Promise<void>;
  sendSupplementRequest: (caseId: string, request: SupplementRequest, expectedSnapshot?: string) => Promise<void>;
  submitStudentSupplement: (
    caseId: string,
    payload: {
      note: string;
      docTitle?: string;
      fileName?: string;
      versionToActivate?: number;
      attachment?: StoredAttachment;
    }
  ) => Promise<void>;
  finalizeReviewCase: (caseId: string, report: NonNullable<ReviewCase["finalReport"]>, expectedSnapshot?: string) => Promise<void>;
  resetReviewDemo: () => Promise<void>;
  isAiAnalyzing: boolean;
  aiAnalyzingStep: number;
}

const StoreContext = createContext<StoreContextType | undefined>(undefined);

const LOCAL_STORAGE_KEY_USER = "campus247_current_user_v1";

// Demo users moved to gateway

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const { theme, toggleTheme } = useTheme();

  // Storage is initialized after hydration, never during server/client rendering.
  const [dataConfig, setDataConfig] = useState<DataConfig | null>(null);
  const [gateway, setGateway] = useState<CampusDataGateway | null>(null);
  const [isDataLoading, setIsDataLoading] = useState(true);
  const [dataError, setDataError] = useState<DataGatewayError | null>(null);
  const [dataStatus, setDataStatus] = useState<DataStatus>("loading");
  const [hasDataLoaded, setHasDataLoaded] = useState(false);
  const authGeneration = useRef(0);
  const authRestored = useRef(false);
  const loadGeneration = useRef(0);

  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [reviewCases, setReviewCases] = useState<ReviewCase[]>([]);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [demoUsers, setDemoUsers] = useState<User[]>([]);

  const [isAiAnalyzing, setIsAiAnalyzing] = useState(false);
  const [aiAnalyzingStep, setAiAnalyzingStep] = useState(1);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const [isL4HandoverActive, setL4HandoverActive] = useState<boolean>(false);
  const [isGate1Open, setGate1Open] = useState(false);
  const [gate1FormData, setGate1FormData] = useState<StoreContextType["gate1FormData"]>({
    fullName: "Nguyễn Văn An",
    mssv: "20210018",
    classYear: "Khóa 18 (2021 - 2025) · K18 KTPM",
    department: "Khoa Công nghệ Phần mềm",
    reason: "Nộp Ngân hàng Chính sách Xã hội Chi nhánh Q. Thủ Đức (Học kỳ 2)",
    destinationOrg: "Ngân hàng Chính sách Xã hội Chi nhánh Q. Thủ Đức",
    receiveMethod: "digital_pdf",
    academicStatus: "Bình thường",
  });
  const [lastUpdatedField, setLastUpdatedField] = useState<"reason" | "receiveMethod" | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  const loadAllData = useCallback(async () => {
    const run = ++loadGeneration.current;
    const authAtStart = authGeneration.current;
    setIsDataLoading(true);
    setHasDataLoaded(false);
    setDataStatus("loading");
    setDataError(null);
    try {
      // Retry recreates a gateway that may have failed while reading storage.
      const initialized = initializeDataState();
      setDataConfig(initialized.config);
      setGateway(initialized.gateway);
      if (initialized.error) throw initialized.error;
      const bootstrap = await bootstrapData(initialized.config, initialized.gateway);
      if (run !== loadGeneration.current) return;
      setTickets(bootstrap.tickets);
      setChatSessions(bootstrap.chatSessions);
      setReviewCases(bootstrap.reviewCases);
      setDemoUsers(bootstrap.demoUsers);

      if (bootstrap.chatSessions.length > 0) {
        setActiveSessionId(bootstrap.chatSessions[0].id);
        setChatMessages(bootstrap.chatSessions[0].messages || []);
        setL4HandoverActive(!!bootstrap.chatSessions[0].isL4HandoverActive);
        if (bootstrap.chatSessions[0].gate1FormData) {
          setGate1FormData(bootstrap.chatSessions[0].gate1FormData);
        }
      }

      if (!authRestored.current) {
        let restoredUser: User | null = null;
        const persistedUserId = localStorage.getItem(LOCAL_STORAGE_KEY_USER);
        if (persistedUserId) {
          restoredUser = await initialized.gateway!.login(persistedUserId);
        }
        if (run !== loadGeneration.current) return;
        // Login/logout during bootstrap owns the newer in-memory session.
        if (authAtStart === authGeneration.current) setCurrentUser(restoredUser);
        authRestored.current = true;
      }
      setHasDataLoaded(true);
      setDataStatus(bootstrap.status);
    } catch (e: unknown) {
      if (run !== loadGeneration.current) return;
      const dataGatewayError = toDataGatewayError(e);
      setDataError(dataGatewayError);
      setDataStatus(statusForError(dataGatewayError));
      throw dataGatewayError;
    } finally {
      if (run === loadGeneration.current) setIsDataLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAllData().catch(() => { /* The retry state displays the error. */ });
  }, [loadAllData]);

  const executeGateway = useCallback(
    async <T,>(operation: (activeGateway: CampusDataGateway) => Promise<T>): Promise<T> => {
      try {
        const activeGateway = requireGateway(gateway, dataError);
        const result = await operation(activeGateway);
        if (dataConfig?.mode === "mock" && hasDataLoaded) {
          setDataError(null);
          setDataStatus("ready");
        }
        return result;
      } catch (error: unknown) {
        const dataGatewayError = toDataGatewayError(error);
        setDataError(dataGatewayError);
        setDataStatus(statusForError(dataGatewayError));
        throw dataGatewayError;
      }
    },
    [dataConfig, dataError, gateway, hasDataLoaded]
  );

  const login = async (userId: string, remember = true): Promise<boolean> => {
    const generation = ++authGeneration.current;
    try {
      const user = await executeGateway((activeGateway) => activeGateway.login(userId));
      if (generation !== authGeneration.current) return false;
      if (typeof window !== "undefined") {
        if (remember) localStorage.setItem(LOCAL_STORAGE_KEY_USER, user.id);
        else localStorage.removeItem(LOCAL_STORAGE_KEY_USER);
      }
      setCurrentUser(user);
      authRestored.current = true;
      return true;
    } catch {
      return false;
    }
  };

  const logout = () => {
    ++authGeneration.current;
    authRestored.current = true;
    setCurrentUser(null);
    if (typeof window !== "undefined") localStorage.removeItem(LOCAL_STORAGE_KEY_USER);
  };

  const getTicket = (id: string) => tickets.find((t) => t.id === id || t.code === id);

  const reloadData = async () => {
    if (!hasDataLoaded) { await loadAllData(); return; }
    await executeGateway(async (activeGateway) => {
      const [nextTickets, nextReviews] = await Promise.all([activeGateway.getTickets(), activeGateway.getReviewCases()]);
      setTickets(nextTickets);
      setReviewCases(nextReviews);
    });
  };

  const createTicket = async (data: Partial<Ticket>): Promise<Ticket> => {
    if (!currentUser) throw new DataGatewayError("unauthorized", "Not logged in");
    return executeGateway(async (activeGateway) => {
      const ticket = await activeGateway.createTicket(currentUser, data);
      setTickets(await activeGateway.getTickets());
      return ticket;
    });
  };

  const updateTicketStatus = async (id: string, status: TicketStatus, actorName: string) => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.updateTicketStatus(id, status, actorName);
      setTickets(await activeGateway.getTickets());
    });
  };

  const updateOfficerDraft = async (id: string, draft: string) => {
    if (currentUser?.role !== "officer") throw new DataGatewayError("unauthorized", "Chỉ cán bộ được lưu nháp phản hồi.");
    const ticket = getTicket(id);
    if (!ticket) throw new DataGatewayError("not_found", "Không tìm thấy hồ sơ.");
    await executeGateway(async (activeGateway) => {
      await activeGateway.updateOfficerDraft(id, draft, currentUser, officerDraftFor(ticket, currentUser.id));
      setTickets(await activeGateway.getTickets());
    });
  };

  const resetOfficerDraft = async (id: string) => {
    const ticket = getTicket(id);
    if (!ticket) throw new DataGatewayError("not_found", "Không tìm thấy hồ sơ.");
    await updateOfficerDraft(id, ticket.officerDraftDefault);
  };

  const toggleChecklistItem = async (ticketId: string, itemId: string) => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.toggleChecklistItem(ticketId, itemId);
      setTickets(await activeGateway.getTickets());
    });
  };

  const addTicketMessage = async (ticketId: string, message: { senderId: string; senderName: string; senderRole: "student" | "officer" | "system"; content: string }) => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.addTicketMessage(ticketId, message);
      setTickets(await activeGateway.getTickets());
    });
  };

  const submitGate2Response = async (ticketId: string, actionType: "respond" | "request_info" | "resolve", customContent?: string, expectedSnapshot?: string) => {
    if (currentUser?.role !== "officer") throw new DataGatewayError("unauthorized", "Chỉ cán bộ được xử lý hồ sơ.");
    await executeGateway(async (activeGateway) => {
      await activeGateway.submitGate2Response(ticketId, actionType, customContent, currentUser, expectedSnapshot);
      setTickets(await activeGateway.getTickets());
    });
  };

  const runTicketVerification = async (ticketId: string) => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.runTicketVerification(ticketId);
      setTickets(await activeGateway.getTickets());
    });
  };

  const retryCriterionVerification = async (ticketId: string, criterionId: string) => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.retryCriterionVerification(ticketId, criterionId);
      setTickets(await activeGateway.getTickets());
    });
  };

  const confirmCriterionReview = async (ticketId: string, criterionId: string, note?: string) => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.confirmCriterionReview(ticketId, criterionId, note);
      setTickets(await activeGateway.getTickets());
    });
  };

  const updateCertificateDraft = async (ticketId: string, edits: Partial<IssuedCertificateDocument>) => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.updateCertificateDraft(ticketId, edits);
      setTickets(await activeGateway.getTickets());
    });
  };

  const issueCertificate = async (ticketId: string): Promise<IssuedCertificateDocument | null> => {
    throw new UnsupportedOperationError(`Phát hành tài liệu chính thức cho ${ticketId}`);
  };

  const selectChatSession = (sessionId: string) => {
    const session = chatSessions.find((s) => s.id === sessionId);
    if (!session) return;
    setActiveSessionId(sessionId);
    setChatMessages(session.messages || []);
    setL4HandoverActive(!!session.isL4HandoverActive);
    if (session.gate1FormData) setGate1FormData(session.gate1FormData);
  };

  const createNewChatSession = async () => {
    await executeGateway(async (activeGateway) => {
      const session = await activeGateway.createChatSession();
      setChatSessions(await activeGateway.getChatSessions());
      setActiveSessionId(session.id);
      setChatMessages(session.messages || []);
      setL4HandoverActive(false);
      setGate1Open(false);
    });
  };

  const deleteChatSession = async (sessionId: string) => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.deleteChatSession(sessionId);
      let remaining = await activeGateway.getChatSessions();
      if (remaining.length === 0) {
        const session = await activeGateway.createChatSession();
        remaining = await activeGateway.getChatSessions();
        setActiveSessionId(session.id);
        setChatMessages(session.messages || []);
        setL4HandoverActive(false);
      } else if (activeSessionId === sessionId) {
        setActiveSessionId(remaining[0].id);
        setChatMessages(remaining[0].messages || []);
        setL4HandoverActive(!!remaining[0].isL4HandoverActive);
        if (remaining[0].gate1FormData) setGate1FormData(remaining[0].gate1FormData);
      }
      setChatSessions(remaining);
    });
  };

  const addChatMessage = async (msg: Omit<ChatMessage, "id" | "timestamp">) => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.addChatMessage(activeSessionId, msg);
      const remaining = await activeGateway.getChatSessions();
      setChatSessions(remaining);
      const current = remaining.find((session) => session.id === activeSessionId);
      if (current) setChatMessages(current.messages);
    });
  };

  const updateGate1Field = (field: "reason" | "receiveMethod" | "destinationOrg", value: string) => {
    setGate1FormData((prev) => ({
      ...prev,
      [field]: value,
      ...(field === "reason" && (!prev.destinationOrg || prev.destinationOrg.includes("Ngân hàng"))
        ? { destinationOrg: value }
        : {}),
    }));
    if (field === "reason" || field === "receiveMethod") {
      setLastUpdatedField(field);
      setTimeout(() => setLastUpdatedField(null), 3500);
    }
  };

  // Review Cases
  const getReviewCase = (id: string) => reviewCases.find((c) => c.id === id || c.code === id);

  const createReviewCase = async (data: Partial<ReviewCase>): Promise<ReviewCase> => {
    return executeGateway(async (activeGateway) => {
      const reviewCase = await activeGateway.createReviewCase(data);
      setReviewCases(await activeGateway.getReviewCases());
      return reviewCase;
    });
  };

  const runAiReview = async (caseId: string) => {
    setIsAiAnalyzing(true);
    setAiAnalyzingStep(1);
    try {
      await new Promise((r) => setTimeout(r, 220));
      setAiAnalyzingStep(2);
      await new Promise((r) => setTimeout(r, 220));
      setAiAnalyzingStep(3);
      await new Promise((r) => setTimeout(r, 220));
      setAiAnalyzingStep(4);
      await executeGateway(async (activeGateway) => {
        await activeGateway.runAiReview(caseId);
        setReviewCases(await activeGateway.getReviewCases());
      });
    } finally {
      setIsAiAnalyzing(false);
      setAiAnalyzingStep(1);
    }
  };

  const updateFindingReview = async (
    caseId: string,
    findingId: string,
    updates: { officerStatus: FindingOfficerStatus; officerAdjustedLabel?: FindingAiLabel; officerNote?: string },
    expectedSnapshot?: string
  ) => {
    if (currentUser?.role !== "officer") throw new DataGatewayError("unauthorized", "Chỉ cán bộ được xác nhận nhận định.");
    await executeGateway(async (activeGateway) => {
      await activeGateway.updateFindingReview(caseId, findingId, updates, currentUser, expectedSnapshot);
      setReviewCases(await activeGateway.getReviewCases());
    });
  };

  const sendSupplementRequest = async (caseId: string, request: SupplementRequest, expectedSnapshot?: string) => {
    if (currentUser?.role !== "officer" || request.sentBy !== currentUser.id) throw new DataGatewayError("unauthorized", "Chỉ cán bộ hiện tại được gửi yêu cầu bổ sung.");
    await executeGateway(async (activeGateway) => {
      await activeGateway.sendSupplementRequest(caseId, request, currentUser, expectedSnapshot);
      setReviewCases(await activeGateway.getReviewCases());
    });
  };

  const submitStudentSupplement = async (
    caseId: string,
    payload: { note: string; docTitle?: string; fileName?: string; versionToActivate?: number; attachment?: StoredAttachment }
  ) => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.submitStudentSupplement(caseId, payload);
      setReviewCases(await activeGateway.getReviewCases());
    });
  };

  const finalizeReviewCase = async (caseId: string, report: NonNullable<ReviewCase["finalReport"]>, expectedSnapshot?: string) => {
    if (currentUser?.role !== "officer" || report.officerId !== currentUser.id) throw new DataGatewayError("unauthorized", "Không có quyền hoàn tất phiếu này.");
    await executeGateway(async (activeGateway) => {
      await activeGateway.finalizeReviewCase(caseId, report, expectedSnapshot);
      setReviewCases(await activeGateway.getReviewCases());
    });
  };

  const resetReviewDemo = async () => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.resetDemoData();
    });
    await loadAllData();
  };

  const resetAllDemoData = async () => {
    await executeGateway(async (activeGateway) => {
      await activeGateway.resetDemoData();
    });
    await loadAllData();
  };

  return (
    <StoreContext.Provider
      value={{
        theme,
        toggleTheme,
        isDataLoading,
        dataError,
        dataStatus,
        dataConfig,
        reloadData,
        currentUser,
        setCurrentUser: user => { ++authGeneration.current; authRestored.current = true; setCurrentUser(user); },
        login,
        logout,
        demoUsers,
        tickets,
        getTicket,
        createTicket,
        updateTicketStatus,
        updateOfficerDraft,
        resetOfficerDraft,
        toggleChecklistItem,
        addTicketMessage,
        submitGate2Response,
        resetAllDemoData,
        runTicketVerification,
        retryCriterionVerification,
        confirmCriterionReview,
        updateCertificateDraft,
        issueCertificate,
        chatSessions,
        activeSessionId,
        selectChatSession,
        createNewChatSession,
        deleteChatSession,
        chatMessages,
        addChatMessage,
        isL4HandoverActive,
        setL4HandoverActive,
        isGate1Open,
        setGate1Open,
        gate1FormData,
        setGate1FormData,
        lastUpdatedField,
        updateGate1Field,
        reviewCases,
        getReviewCase,
        createReviewCase,
        runAiReview,
        updateFindingReview,
        sendSupplementRequest,
        submitStudentSupplement,
        finalizeReviewCase,
        resetReviewDemo,
        isAiAnalyzing,
        aiAnalyzingStep,
      }}
    >
      {children}
    </StoreContext.Provider>
  );
}

const defaultStoreContext: StoreContextType = {
  theme: "light",
  toggleTheme: () => {},
  isDataLoading: false,
  dataError: null,
  dataStatus: "ready",
  dataConfig: null,
  reloadData: async () => {},
  currentUser: null,
  setCurrentUser: () => {},
  login: async () => true,
  logout: () => {},
  demoUsers: [],
  tickets: [],
  getTicket: () => undefined,
  createTicket: async () => ({} as any),
  updateTicketStatus: async () => {},
  updateOfficerDraft: async () => {},
  resetOfficerDraft: async () => {},
  toggleChecklistItem: async () => {},
  addTicketMessage: async () => {},
  submitGate2Response: async () => {},
  resetAllDemoData: async () => {},
  runTicketVerification: async () => {},
  retryCriterionVerification: async () => {},
  confirmCriterionReview: async () => {},
  updateCertificateDraft: async () => {},
  issueCertificate: async () => null,
  chatSessions: [],
  activeSessionId: "",
  selectChatSession: () => {},
  createNewChatSession: async () => {},
  deleteChatSession: async () => {},
  chatMessages: [],
  addChatMessage: async () => {},
  isL4HandoverActive: false,
  setL4HandoverActive: () => {},
  isGate1Open: false,
  setGate1Open: () => {},
  gate1FormData: {
    fullName: "Nguyễn Văn An",
    mssv: "20210018",
    classYear: "K18",
    department: "CNTT",
    reason: "",
    destinationOrg: "",
    receiveMethod: "digital_pdf",
    academicStatus: "Bình thường",
  },
  setGate1FormData: () => {},
  lastUpdatedField: null,
  updateGate1Field: () => {},
  reviewCases: [],
  getReviewCase: () => undefined,
  createReviewCase: async () => ({} as any),
  runAiReview: async () => {},
  updateFindingReview: async () => {},
  sendSupplementRequest: async () => {},
  submitStudentSupplement: async () => {},
  finalizeReviewCase: async () => {},
  resetReviewDemo: async () => {},
  isAiAnalyzing: false,
  aiAnalyzingStep: 1,
};

export function useStore() {
  const context = useContext(StoreContext);
  return context || defaultStoreContext;
}
