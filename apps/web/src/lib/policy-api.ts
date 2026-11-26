import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient } from "./api/client";

export interface PolicyTopic { topic: string; label: string; description: string; rule_count: number; effective_from: string | null }
export interface PolicyField {
  var: string; label: string; type: "number" | "integer" | "boolean" | "enum" | "string" | "date"; unit: string | null;
  min: number | null; max: number | null; step: number | null; values: string[]; input: string; help: string; source: { path: string | null };
}
export interface PolicyForm { topic: string; fields: PolicyField[]; conclusion: string; needs_cohort: boolean }
export type TriValue = "T" | "F" | "U";
export interface ProofNode {
  id: string; kind: "pred" | "all" | "any" | "not"; value: TriValue; text?: string; var?: string;
  source?: { unit_id: string; path: string; quote: string } | null; children?: ProofNode[];
}
export interface PolicyThreshold { var: string; flip_at: number; direction: "<=" | ">="; text: string }
export interface PolicyResult {
  topic: string; outcome: "SATISFIED" | "NOT_SATISFIED" | "UNDETERMINED"; reason: string | null; as_of: string;
  conclusion: { code: string; label: string } | null; proof: ProofNode | null; missing: string[]; thresholds: PolicyThreshold[];
  exceptions: { rule_id: string; value: TriValue; effect: string }[]; refer_to: { refer_to?: string; service_kind?: string } | null;
  rule: { rule_id: string; version: number } | null; disclaimer_code: string;
}

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });

export const policyApi = {
  topics: () => client().get<{ topics: PolicyTopic[] }>("/v1/policy-simulator/topics"),
  form: (topic: string, cohort?: string) =>
    client().get<PolicyForm>(`/v1/policy-simulator/topics/${encodeURIComponent(topic)}/form${cohort ? `?cohort=${encodeURIComponent(cohort)}` : ""}`),
  evaluate: (topic: string, inputs: Record<string, unknown>, cohort?: string) =>
    client().post<PolicyResult>("/v1/policy-simulator/evaluate", { topic, inputs, cohort: cohort || null }),
};
