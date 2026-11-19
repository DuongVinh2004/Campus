/** Planned/preparation contracts. References and proposals never grant authority. */
export type UUID7 = string;
export type Workflow = "STUDENT_CERTIFICATE" | "GRADE_APPEAL" | "GENERAL_SUPPORT";
export interface ResourceRef { kind: "service_request" | "certificate_request"; id: UUID7; expected_version: number }
export interface EvidenceRef { source_id: string; version_id: string; locator: string; sha256: string; classification: "synthetic" | "public_snapshot" }
export interface WorkflowBinding { workflow: Workflow; version: string; source: EvidenceRef; effective_from: string; effective_until?: string | null }
export type Scalar = string | number | boolean | null;
export interface CandidateFact { key: string; value: Scalar; origin: "user_statement" | "profile_reference" | "document_candidate" | "inference"; evidence?: EvidenceRef | null; status: "candidate" }
export interface IntentProposal { schema_version: "unified-intent.v1"; goal: string; workflow?: Workflow | null; purpose?: string | null; resource?: ResourceRef | null; constraints: string[]; facts: CandidateFact[]; missing_fields: string[]; clarification?: string | null; status: "candidate" | "needs_clarification" | "out_of_scope"; action_authority: "none" }
export interface FieldChange { field: "purpose" | "recipient" | "quantity" | "delivery_method" | "reason" | "course_record_id" | "contact_preference" | "public_response" | "internal_note"; before: Scalar; candidate: Scalar; origin: "user_statement" | "source_reference" | "inference"; evidence?: EvidenceRef | null }
export interface DraftProposal { schema_version: "unified-proposal.v1"; client_id: UUID7; target: ResourceRef; workflow_binding: WorkflowBinding; audience: "student" | "staff_internal"; operation: "revise_draft" | "prepare_response" | "prepare_internal_note"; changes: FieldChange[]; action_authority: "none" }
export interface PreferencesPatch { expected_version: number; locale?: "vi" | "en" | null; reply_style?: "concise" | "steps" | "detailed" | null; format?: "text" | "markdown" | null; custom_instructions?: string | null }
export interface GrantRequest { client_id: UUID7; purpose: "source_assistance" | "personalization" | "notifications"; capability: "read_source" | "read_own_resource" | "prepare_draft" | "remember_preference" | "notify_resource"; resource: ResourceRef; requested_lifetime_seconds: number; state: "requested" }
export interface TaskPlanProposal { items: Array<{ id: string; question: string; requirements: Array<{ id: string; question: string }> }>; tasks: Array<{ id: string; role: "research" | "verifier"; goal: string; coverage_ids: string[]; dependencies?: string[] }>; clarification?: string | null }
export interface TaskRequest { schema_version: "unified-task.v1"; client_id: UUID7; goal: string; resources: ResourceRef[]; plan: TaskPlanProposal; action_authority: "none" }
export interface SupplementItem { id: string; criterion_id: string; field: "purpose" | "recipient" | "reason" | "course_record_id" | "attachment"; public_reason: string; required_evidence: EvidenceRef }
export interface SupplementProposal { client_id: UUID7; target: ResourceRef; workflow_binding: WorkflowBinding; items: SupplementItem[]; state: "draft"; action_authority: "none" }
export interface BatchPreparationRequest { client_id: UUID7; items: DraftProposal[]; mode: "prepare_only" }
export interface MessagePageRequest { conversation_id: UUID7; cursor?: string | null; limit?: number }
export interface ConversationMetadataPatch { expected_version: number; title?: string | null; pinned?: boolean | null; archived?: boolean | null }
export interface CommitAcknowledgement { client_id: UUID7; resource: ResourceRef; receipt_id: UUID7; state: "committed" | "replayed"; committed_at: string }
export interface AssistanceProblem { schema_version: "unified-error.v1"; status: number; code: string; request_id: UUID7; retryable: boolean; detail: string }

export interface CoordinationRun {
  id: UUID7; version: number;
  status: "running" | "waiting_user" | "partial" | "completed" | "cancelled" | "failed" | "interrupted" | "uncertain";
  continuation?: { schema_version: "coordination-checkpoint.v1"; state: string; blockers: string[];
    next_action: "wait" | "clarify" | "read_receipt" | "read_sources" | "new_run" | "none"; receipt_id: string | null };
  transition_receipt?: { id: string; run_id: UUID7; version: number; state: string; result_sha256: string };
  tasks: Array<{ id: string; role: "research" | "verifier"; status: string; attempt: number; version: number }>;
  usage?: { model_calls: number; tool_calls: number; reserved_tokens: number; elapsed_ms: number; cost_usd: number | null; usage_complete: boolean };
}
