import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient } from "./api/client";

/** One time window of the operations status. `*_s_le` are bucket upper bounds in seconds; null means no data or above the last bound. */
export interface OpsWindow {
  minutes: number;
  turns: number;
  ok: number;
  abstained: number;
  errors: Record<string, number>;
  error_rate: number;
  p50_s_le: number | null;
  p95_s_le: number | null;
  p95_s_le_over?: number;
  first_token_p95_s_le: number | null;
  admission_rejected: number;
  admission_rejected_rate: number;
  rate_limited: Record<string, number>;
  loop_blocked: number;
  loop_blocked_max_ms: number;
}

export interface OpsGatewayToday {
  usd: string;
  calls: number;
  usd_cap: string;
  call_cap: number;
  cap_enabled: boolean;
  cap_reached: boolean;
}

export interface OpsBackupRecord {
  at: string | null;
  ok: boolean;
  age_hours: number | null;
}

export interface OpsStatus {
  generated_at: string;
  workers_reporting: number;
  window_minutes: number;
  turns: { last_5m: OpsWindow; last_10m: OpsWindow; last_60m: OpsWindow };
  load: { in_flight: number; waiting: number; limit: number };
  retrieval: { retrievals: number; failed: number; timeouts: number; failed_rate: number; vector_ms_max: number };
  models: Record<string, "up" | "down">;
  gateway: { reachable: boolean | null; reason?: string; counters?: Record<string, number>; today?: OpsGatewayToday | null };
  background: { leader?: boolean; learning_worker?: string };
  storage: { data_free_pct: number | null; backup_free_pct: number | null };
  backup: { configured: boolean; last?: OpsBackupRecord | null; offsite?: OpsBackupRecord | null; rehearsal?: OpsBackupRecord | null };
  series: { minute: number[]; turns: number[]; errors: number[]; p95_s_le: Array<number | null> };
}

export const opsStatusApi = {
  get: () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL }).get<OpsStatus>("/v1/admin/operations/status"),
};
