import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient } from "./api/client";

export interface ProcedureField { key: string; label: string; type: string; required: boolean; values: string[]; min: number | null; max: number | null }
export interface ProcedureInfo { id: string; title: string; description: string; fields: ProcedureField[]; sources: string[] }
export interface ProcedureRun {
  id: string; procedure_id: string; title: string; state: string; fields: Record<string, unknown>; field_origin: Record<string, string>;
  blocked: { text?: string; path?: string; quote?: string }[]; missing: string[]; row_version: number; next_step: string;
  ticket: { id: string; code?: string; status?: string } | null; expires_at: string;
}
export interface ProcedureText { suggestions: { procedure_id: string; title: string }[]; procedure_id: string | null; extracted: { field: string; value: unknown; span?: number[] }[]; dropped: unknown[] }
export interface ProcedurePreview { preview_id: string; confirmation_token: string; expires_at: string; ticket_preview: { title: string; summary: string; fields: Record<string, string> } }

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });

export const proceduresApi = {
  catalog: () => client().get<{ items: ProcedureInfo[] }>("/v1/procedures"),
  fromText: (text: string) => client().post<ProcedureText>("/v1/procedures/runs:from-text", { text }),
  start: (procedureId: string) => client().post<ProcedureRun>("/v1/procedures/runs", { procedure_id: procedureId }),
  get: (id: string) => client().get<ProcedureRun>(`/v1/procedures/runs/${encodeURIComponent(id)}`),
  list: () => client().get<{ items: ProcedureRun[] }>("/v1/procedures/runs"),
  putFields: (id: string, fields: Record<string, unknown>, rowVersion: number, confirmExtracted: string[] = []) =>
    client().put<ProcedureRun>(`/v1/procedures/runs/${encodeURIComponent(id)}/fields`, { fields, row_version: rowVersion, confirm_extracted: confirmExtracted }),
  preview: (id: string) => client().post<ProcedurePreview>(`/v1/procedures/runs/${encodeURIComponent(id)}:submit-preview`),
  confirm: (previewId: string, token: string, idempotencyKey: string) =>
    client().post<ProcedureRun>("/v1/procedures/runs:submit-confirm", { preview_id: previewId, confirmation_token: token }, { "Idempotency-Key": idempotencyKey }),
  cancel: (id: string) => client().post<ProcedureRun>(`/v1/procedures/runs/${encodeURIComponent(id)}:cancel`),
};
