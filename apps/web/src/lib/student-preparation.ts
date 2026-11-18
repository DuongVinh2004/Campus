import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { ApiClient } from "./api/client";
import type { ResourceRef } from "./unified-ai-contracts";
export type StudentWorkflow = "STUDENT_CERTIFICATE" | "GRADE_APPEAL" | "GENERAL_SUPPORT";
export interface StudentGoalRequest {
  goal: string; workflow?: StudentWorkflow; resource?: ResourceRef;
  statements: Record<string, string | number>; constraints: string[]; operation_id: string;
}
export interface StudentPreparation {
  intent: { workflow: StudentWorkflow | null; clarification: string | null; missing_fields: string[]; purpose: string | null };
  next_action: string; sha256?: string; form: Record<string, unknown> | null;
  candidates: Array<ResourceRef & { status: string }>;
  diff: Array<{ field: string; before: unknown; candidate: unknown }>;
  field_errors: Array<{ field: string; code: string; detail: string; source?: string }>;
  provenance: Record<string, { origin: string }>;
  binding: { workflow_version: string; template_version: string; queue: string } | null;
}
export interface StudentPreparationState {
  goal: string; workflow: StudentWorkflow | ""; statements: Record<string, string | number>;
  resource?: ResourceRef; request?: StudentGoalRequest; prepared?: StudentPreparation;
  saved?: ResourceRef; uncertain?: boolean;
}
const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });
export const prepareStudent = (request: StudentGoalRequest) => client().post<StudentPreparation>("/v1/assistant/student:prepare", request);
export const saveStudentDraft = (request: StudentGoalRequest, expected_sha256: string) => client().post<{
  document_request: { id: string; version: number; status: string; document_type: StudentWorkflow };
  receipt: { document_request_id: string; version: number; effect: "draft_saved" }; is_replay: boolean;
}>("/v1/assistant/student:save-draft", { request, expected_sha256, reviewed: true });
