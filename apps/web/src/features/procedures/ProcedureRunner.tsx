"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { proceduresApi, type ProcedureField, type ProcedureInfo, type ProcedurePreview, type ProcedureRun } from "../../lib/procedures-api";

const STEP_LABEL: Record<string, string> = {
  fill: "Điền thông tin", fix_or_ask: "Chưa đủ điều kiện", preview: "Sẵn sàng xem trước", confirm: "Xác nhận gửi", track: "Đã gửi", none: "Đã kết thúc",
};
const ORIGIN_NOTE = "Trợ lý điền từ câu của bạn — kiểm tra lại";

export const EXTRACTED_KEY = (runId: string) => `procedure-extracted:${runId}`;

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Không thực hiện được.";
}

function readExtracted(runId: string): Record<string, unknown> {
  try { return JSON.parse(window.sessionStorage.getItem(EXTRACTED_KEY(runId)) ?? "{}"); } catch { return {}; }
}

function FieldInput({ field, value, assistant, onChange }: { field: ProcedureField; value: unknown; assistant: boolean; onChange: (v: unknown) => void }) {
  const id = `proc-${field.key}`;
  const numeric = field.type === "integer" || field.type === "number";
  return (
    <div>
      <label htmlFor={id}>{field.label}{field.required ? " *" : ""}</label>
      {field.type === "enum" ? (
        <select id={id} value={value === undefined ? "" : String(value)} onChange={e => onChange(e.target.value || undefined)}>
          <option value="">Chọn…</option>
          {field.values.map(v => <option key={v} value={v}>{v}</option>)}
        </select>
      ) : (
        <input id={id} type={numeric ? "number" : "text"} min={field.min ?? undefined} max={field.max ?? undefined}
          value={value === undefined ? "" : String(value)} onChange={e => onChange(e.target.value === "" ? undefined : e.target.value)} />
      )}
      {assistant && <small>{ORIGIN_NOTE}</small>}
    </div>
  );
}

/** Guides one procedure run: fill, preview, explicit confirm. The assistant never submits; only the confirm button does. */
export function ProcedureRunner({ runId, procedureId }: { runId?: string; procedureId?: string }) {
  const [run, setRun] = useState<ProcedureRun | null>(null);
  const [info, setInfo] = useState<ProcedureInfo | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [assisted, setAssisted] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<ProcedurePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const idempotency = useRef<string>("");

  const adopt = useCallback((next: ProcedureRun, catalogItems: ProcedureInfo[]) => {
    setRun(next);
    setInfo(catalogItems.find(p => p.id === next.procedure_id) ?? null);
    const fromRun = next.fields ?? {};
    const extracted = readExtracted(next.id);
    setValues({ ...extracted, ...fromRun });
    setAssisted(new Set(Object.keys(extracted).filter(k => !(k in fromRun))));
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const catalog = await proceduresApi.catalog();
        const current = runId ? await proceduresApi.get(runId) : procedureId ? await proceduresApi.start(procedureId) : null;
        if (!alive) return;
        if (!current) { setError("Chưa chọn thủ tục."); return; }
        adopt(current, catalog.items);
      } catch (e) { if (alive) setError(message(e)); }
    })();
    return () => { alive = false; };
  }, [runId, procedureId, adopt]);

  const act = async (action: () => Promise<void>) => {
    setBusy(true); setError(null);
    try { await action(); } catch (e) { setError(message(e)); } finally { setBusy(false); }
  };

  const save = () => act(async () => {
    if (!run || !info) return;
    const clean: Record<string, unknown> = {};
    for (const f of info.fields) if (values[f.key] !== undefined) clean[f.key] = f.type === "integer" || f.type === "number" ? Number(values[f.key]) : values[f.key];
    const next = await proceduresApi.putFields(run.id, clean, run.row_version, [...assisted].filter(k => k in clean));
    setRun(next); setAssisted(new Set()); setPreview(null);
    try { window.sessionStorage.removeItem(EXTRACTED_KEY(run.id)); } catch { /* storage is optional */ }
  });
  const showPreview = () => act(async () => { if (run) setPreview(await proceduresApi.preview(run.id)); });
  const confirm = () => act(async () => {
    if (!run || !preview) return;
    if (!idempotency.current) idempotency.current = crypto.randomUUID();
    setRun(await proceduresApi.confirm(preview.preview_id, preview.confirmation_token, idempotency.current));
    setPreview(null);
  });
  const cancel = () => act(async () => { if (run) setRun(await proceduresApi.cancel(run.id)); });

  if (error && !run) return <p role="alert">{error}</p>;
  if (!run || !info) return <p role="status">Đang tải thủ tục…</p>;
  const editable = ["STARTED", "COLLECTING", "BLOCKED", "READY_FOR_PREVIEW", "PREVIEWED"].includes(run.state);

  return (
    <section aria-labelledby="proc-title" className="campus-card space-y-3">
      <h2 id="proc-title">{run.title}</h2>
      <p role="status">Bước hiện tại: {STEP_LABEL[run.next_step] ?? run.next_step}</p>
      {error && <p role="alert">{error}</p>}
      {run.state === "BLOCKED" && (
        <div role="alert">
          <p>Theo quy định, bạn chưa đủ điều kiện để làm thủ tục này:</p>
          <ul>{run.blocked.map((b, i) => <li key={i}>{b.text ?? b.path}{b.quote ? <blockquote>{b.quote}</blockquote> : null}</li>)}</ul>
          <p>Bạn có thể sửa thông tin nếu nhập nhầm, hoặc hỏi phòng chức năng.</p>
        </div>
      )}
      {editable && (
        <form onSubmit={e => { e.preventDefault(); void save(); }} className="space-y-2">
          {info.fields.map(f => <FieldInput key={f.key} field={f} value={values[f.key]} assistant={assisted.has(f.key)}
            onChange={v => { setValues(prev => ({ ...prev, [f.key]: v })); }} />)}
          <button type="submit" disabled={busy}>Lưu thông tin</button>
        </form>
      )}
      {run.missing.length > 0 && editable && <p>Còn thiếu: {run.missing.join(", ")}</p>}
      {(run.state === "READY_FOR_PREVIEW" || run.state === "PREVIEWED") && !preview && <button onClick={() => void showPreview()} disabled={busy}>Xem trước hồ sơ</button>}
      {preview && (
        <div aria-label="Xem trước hồ sơ" className="space-y-2">
          <h3>{preview.ticket_preview.title}</h3>
          <pre>{preview.ticket_preview.summary}</pre>
          <button onClick={() => void confirm()} disabled={busy}>Gửi hồ sơ</button>
        </div>
      )}
      {run.state === "SUBMITTED" && <p role="status">Đã gửi hồ sơ{run.ticket?.code ? ` (mã ${run.ticket.code})` : ""}. Theo dõi tại mục Yêu cầu của tôi.</p>}
      {run.state === "CANCELLED" && <p role="status">Đã hủy thủ tục này.</p>}
      {editable && <button onClick={() => void cancel()} disabled={busy}>Hủy thủ tục</button>}
    </section>
  );
}
