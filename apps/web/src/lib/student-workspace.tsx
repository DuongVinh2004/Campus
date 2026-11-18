"use client";

import { createContext, useContext, useState, useSyncExternalStore, type ReactNode } from "react";

export type ReceiveMethod = "digital_pdf" | "paper_stamped";
export type StudentTask = "home" | "certificate" | "complaint" | "lookup";

export interface CertificateData {
  purpose: string;
  destinationOrg: string;
  receiveMethod: ReceiveMethod;
}

export interface ComplaintData {
  course: string;
  assessment: string;
  description: string;
  requestedOutcome: string;
  evidence: string;
}

export interface StudentDraft<T> {
  id: string;
  data: T;
  step: "details" | "review";
  updatedAt: string;
  submission?: { ticketId: string; ticketCode: string };
}

interface WorkspaceData {
  version: 1;
  certificates: StudentDraft<CertificateData>[];
  complaints: StudentDraft<ComplaintData>[];
  lookupQuery: string;
}

function newDraft<T>(data: T): StudentDraft<T> {
  return { id: crypto.randomUUID(), data, step: "details", updatedAt: new Date().toISOString() };
}

const emptyCertificate = (): CertificateData => ({ purpose: "", destinationOrg: "", receiveMethod: "digital_pdf" });
const emptyComplaint = (): ComplaintData => ({ course: "", assessment: "Điểm thi cuối kỳ", description: "", requestedOutcome: "", evidence: "" });

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isDraft<T>(value: unknown, isData: (data: unknown) => data is T): value is StudentDraft<T> {
  return isRecord(value) && typeof value.id === "string" && typeof value.updatedAt === "string"
    && (value.step === "details" || value.step === "review") && isData(value.data)
    && (value.submission === undefined || (isRecord(value.submission)
      && typeof value.submission.ticketId === "string" && typeof value.submission.ticketCode === "string"));
}

function isCertificate(value: unknown): value is CertificateData {
  return isRecord(value) && typeof value.purpose === "string" && typeof value.destinationOrg === "string"
    && (value.receiveMethod === "digital_pdf" || value.receiveMethod === "paper_stamped");
}

function isComplaint(value: unknown): value is ComplaintData {
  return isRecord(value) && ["course", "assessment", "description", "requestedOutcome", "evidence"]
    .every((field) => typeof value[field] === "string");
}

function isWorkspace(value: unknown): value is WorkspaceData {
  return isRecord(value) && value.version === 1 && typeof value.lookupQuery === "string"
    && Array.isArray(value.certificates) && value.certificates.length > 0
    && value.certificates.every((draft) => isDraft(draft, isCertificate))
    && Array.isArray(value.complaints) && value.complaints.length > 0
    && value.complaints.every((draft) => isDraft(draft, isComplaint));
}

function createWorkspaceStore(userId: string, mode: string) {
  const storageKey = `campus247_student_workspace_v1:${mode}:${encodeURIComponent(userId)}`;
  let workspace: WorkspaceData = {
    version: 1, certificates: [newDraft(emptyCertificate())], complaints: [newDraft(emptyComplaint())], lookupQuery: "",
  };
  let storageIssue: string | null = null;
  let preserveExistingStorage = false;
  try {
    const saved = localStorage.getItem(storageKey);
    if (saved !== null) {
      const parsed: unknown = JSON.parse(saved);
      if (!isWorkspace(parsed)) throw new Error("Unsupported draft data");
      workspace = parsed;
    }
  } catch {
    preserveExistingStorage = true;
    storageIssue = "Không thể đọc bản nháp đã lưu. Nội dung mới được giữ trong phiên này; dữ liệu đã lưu vẫn được giữ nguyên.";
  }

  let snapshot = { workspace, storageIssue };
  const listeners = new Set<() => void>();
  const pendingDrafts = new Set<string>();
  return {
    getSnapshot: () => snapshot,
    isPending: (id: string) => pendingDrafts.has(id),
    beginSubmission(id: string) {
      if (pendingDrafts.has(id)) return false;
      pendingDrafts.add(id);
      return true;
    },
    endSubmission: (id: string) => { pendingDrafts.delete(id); },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
    update(change: (current: WorkspaceData) => WorkspaceData) {
      const next = change(snapshot.workspace);
      let issue = snapshot.storageIssue;
      if (!preserveExistingStorage) {
        try {
          localStorage.setItem(storageKey, JSON.stringify(next));
          issue = null;
        } catch {
          issue = "Chưa lưu được bản nháp trên thiết bị. Hãy giữ trang này mở để tiếp tục.";
        }
      }
      snapshot = { workspace: next, storageIssue: issue };
      listeners.forEach((listener) => listener());
    },
  };
}

export interface CertificateProposal {
  draftId: string;
  field: keyof CertificateData;
  before: string;
  value: string;
  label: string;
}

interface WorkspaceContextValue {
  certificate: StudentDraft<CertificateData>;
  complaint: StudentDraft<ComplaintData>;
  lookupQuery: string;
  storageIssue: string | null;
  updateCertificate: (fields: Partial<CertificateData>) => void;
  updateComplaint: (fields: Partial<ComplaintData>) => void;
  setStep: (task: "certificate" | "complaint", step: "details" | "review") => void;
  recordSubmission: (task: "certificate" | "complaint", ticketId: string, ticketCode: string) => void;
  startNew: (task: "certificate" | "complaint") => void;
  setLookupQuery: (query: string) => void;
  applyProposal: (proposal: CertificateProposal) => boolean;
  beginSubmission: (draftId: string) => boolean;
  endSubmission: (draftId: string) => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function StudentWorkspaceProvider({ userId, mode, children }: { userId: string; mode: string; children: ReactNode }) {
  const [store] = useState(() => createWorkspaceStore(userId, mode));
  const { workspace, storageIssue } = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  const certificate = workspace.certificates[workspace.certificates.length - 1];
  const complaint = workspace.complaints[workspace.complaints.length - 1];

  function updateCertificate(fields: Partial<CertificateData>) {
    store.update((current) => ({ ...current, certificates: current.certificates.map((draft, index) =>
      index === current.certificates.length - 1 && !draft.submission && !store.isPending(draft.id)
        ? { ...draft, data: { ...draft.data, ...fields }, step: "details", updatedAt: new Date().toISOString() }
        : draft) }));
  }

  function updateComplaint(fields: Partial<ComplaintData>) {
    store.update((current) => ({ ...current, complaints: current.complaints.map((draft, index) =>
      index === current.complaints.length - 1 && !draft.submission && !store.isPending(draft.id)
        ? { ...draft, data: { ...draft.data, ...fields }, step: "details", updatedAt: new Date().toISOString() }
        : draft) }));
  }

  function changeLatest(task: "certificate" | "complaint", fields: Partial<Pick<StudentDraft<CertificateData>, "step" | "submission">>) {
    store.update((current) => task === "certificate"
      ? { ...current, certificates: current.certificates.map((draft, index) => index === current.certificates.length - 1 ? { ...draft, ...fields } : draft) }
      : { ...current, complaints: current.complaints.map((draft, index) => index === current.complaints.length - 1 ? { ...draft, ...fields } : draft) });
  }

  function applyProposal(proposal: CertificateProposal) {
    const drafts = store.getSnapshot().workspace.certificates;
    const latest = drafts[drafts.length - 1];
    if (latest.id !== proposal.draftId || latest.submission || store.isPending(latest.id) || latest.data[proposal.field] !== proposal.before) return false;
    if (proposal.field === "receiveMethod" && proposal.value !== "digital_pdf" && proposal.value !== "paper_stamped") return false;
    updateCertificate({ [proposal.field]: proposal.value });
    return true;
  }

  return <WorkspaceContext.Provider value={{
    certificate, complaint, lookupQuery: workspace.lookupQuery, storageIssue, updateCertificate, updateComplaint,
    setStep: (task, step) => changeLatest(task, { step }),
    recordSubmission: (task, ticketId, ticketCode) => changeLatest(task, { submission: { ticketId, ticketCode } }),
    startNew: (task) => store.update((current) => task === "certificate"
      ? { ...current, certificates: [...current.certificates, newDraft(emptyCertificate())] }
      : { ...current, complaints: [...current.complaints, newDraft(emptyComplaint())] }),
    setLookupQuery: (lookupQuery) => store.update((current) => ({ ...current, lookupQuery })),
    applyProposal, beginSubmission: store.beginSubmission, endSubmission: store.endSubmission,
  }}>{children}</WorkspaceContext.Provider>;
}

export function useStudentWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error("Student workspace must be used inside its provider");
  return context;
}

export function hasCertificateDraft(draft: StudentDraft<CertificateData>) {
  return !draft.submission && Boolean(draft.data.purpose.trim() || draft.data.destinationOrg.trim() || draft.data.receiveMethod === "paper_stamped");
}

export function hasComplaintDraft(draft: StudentDraft<ComplaintData>) {
  return !draft.submission && Boolean(draft.data.course.trim() || draft.data.description.trim() || draft.data.evidence.trim() || draft.data.requestedOutcome.trim());
}
