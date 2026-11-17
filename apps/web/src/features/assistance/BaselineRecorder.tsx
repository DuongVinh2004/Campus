"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import React, { useEffect, useRef, useState } from "react";

const base = CAMPUS_API_BASE_URL;
type Metric = "pause" | "resume" | "wait" | "finish" | "field_edit" | "correction" | "manual_action" | "check_source" | "assistant_request" | "preview" | "receipt_observed";
type Field = "reason" | "course_record_id" | "purpose" | "recipient" | "staff_note" | "target" | "outcome" | "contact_preference";
interface Session {
  id: string; version: number; case_id: string; operator_kind: "human_declared" | "automation";
  state: "active" | "paused" | "waiting" | "finished";
  active_ms: number; wait_ms: number; paused_ms: number; unattributed_ms: number;
  counts: Record<string, number>; fields: Record<string, number>;
}
interface Case { id: string; category: string; expected: string }
class MeasurementError extends Error { constructor(message: string, readonly code: string) { super(message); } }

function decodeSession(value: unknown): Session {
  const s = value as Session;
  if (!s || !/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(s.id) || !Number.isInteger(s.version) || s.version < 1 ||
      !["active", "paused", "waiting", "finished"].includes(s.state) ||
      !["human_declared", "automation"].includes(s.operator_kind) || typeof s.case_id !== "string" ||
      ![s.active_ms, s.wait_ms, s.paused_ms, s.unattributed_ms].every(n => Number.isInteger(n) && n >= 0) ||
      !s.counts || !s.fields || ![...Object.values(s.counts), ...Object.values(s.fields)].every(n => Number.isInteger(n) && n >= 0)) {
    throw new Error("Số đo trả về chưa đúng hợp đồng; chưa thể báo đã ghi.");
  }
  return s;
}

async function call(path: string, body?: unknown, signal?: AbortSignal) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const response = await fetch(`${base}/v1/assistant/baseline${path}`, {
    method: body ? "POST" : "GET", headers, credentials: "include", cache: "no-store", signal,
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    throw new MeasurementError(response.status === 409 ? "Phiên đo đã thay đổi. Số đo chưa ghi vẫn được giữ để thử lại."
      : response.status === 401 ? "Phiên đăng nhập đã hết hạn; chưa ghi số đo." : "Chưa ghi được số đo. Thao tác hồ sơ vẫn dùng được.",
      typeof problem.code === "string" ? problem.code : "UNKNOWN");
  }
  return response.json();
}

export function useBaselineMeasurement(actorId?: string) {
  const [session, setSession] = useState<Session | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [saved, setSaved] = useState<Session[]>([]);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [stale, setStale] = useState(false);
  const latest = useRef<Session | null>(null);
  const epoch = useRef(0);
  const queue = useRef(Promise.resolve());
  const dirty = useRef(new Set<Field>());
  const unknown = useRef<{ path: string; body: Record<string, unknown> } | null>(null);
  const activeRequest = useRef<AbortController | null>(null);

  function publish(s: Session) { latest.current = s; setSession(s); }
  useEffect(() => {
    epoch.current += 1; latest.current = null; unknown.current = null; dirty.current.clear();
    activeRequest.current?.abort(); setSession(null); setSaved([]); setCases([]); setError(""); setPending(false); setStale(false);
    if (!actorId) return;
    const generation = epoch.current;
    const controller = new AbortController(); activeRequest.current = controller;
    void Promise.all([call("/cases", undefined, controller.signal), call("/sessions", undefined, controller.signal)])
      .then(([c, s]) => {
        if (epoch.current !== generation || controller.signal.aborted) return;
        if (!Array.isArray(c.items) || !Array.isArray(s.items)) throw new Error("Không đọc được danh sách ca/phiên đo.");
        setCases(c.items); setSaved(s.items.map(decodeSession));
      }).catch(e => { if (!controller.signal.aborted && epoch.current === generation) setError(e.message); });
    return () => { epoch.current += 1; activeRequest.current?.abort(); latest.current = null; };
  }, [actorId]);

  function enqueue(operation: () => Promise<void>) {
    const generation = epoch.current;
    queue.current = queue.current.then(async () => {
      if (epoch.current !== generation) return;
      setPending(true); setError("");
      try { await operation(); } catch (e) { if (epoch.current === generation) setError(e instanceof Error ? e.message : "Chưa ghi số đo."); }
      finally { if (epoch.current === generation) setPending(false); }
    });
  }
  async function write(path: string, body: Record<string, unknown>) {
    const generation = epoch.current;
    unknown.current = { path, body };
    const controller = new AbortController(); activeRequest.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    try {
      const result = await call(path, body, controller.signal);
      if (generation !== epoch.current || controller.signal.aborted) return;
      const received = decodeSession(result.session);
      if (path === "/sessions" ? received.case_id !== body.case_id || received.operator_kind !== body.operator_kind
        : received.id !== latest.current?.id || result.receipt?.event_id !== body.event_id || received.version <= Number(body.expected_version)) {
        throw new Error("Biên nhận không khớp phiên/event đang ghi. Chưa thể báo đã ghi.");
      }
      publish(received); unknown.current = null; setStale(false);
    } catch (e) {
      if (generation === epoch.current) setStale(e instanceof MeasurementError && e.code === "STALE_VERSION");
      throw e;
    } finally { window.clearTimeout(timeout); }
  }
  function start(caseId: string, operator: "human_declared" | "automation") {
    enqueue(async () => {
      if (unknown.current) throw new Error("Kết quả lần ghi trước chưa rõ. Đọc lại hoặc thử lại cùng event trước.");
      await write("/sessions", { client_id: `baseline:${crypto.randomUUID()}`, case_id: caseId, operator_kind: operator });
    });
  }
  function record(kind: Metric, field?: Field) {
    if (!latest.current || latest.current.state === "finished" || (!["pause","resume","wait","finish"].includes(kind) && latest.current.state !== "active")) return;
    enqueue(async () => {
      if (unknown.current) throw new Error("Có event chưa nhận được biên nhận. Thử lại cùng event trước khi ghi tiếp.");
      const s = latest.current;
      if (!s || s.state === "finished") return;
      await write(`/sessions/${s.id}/events`, { event_id: `event:${crypto.randomUUID()}`, expected_version: s.version, kind, ...(field ? { field } : {}) });
    });
  }
  function reopen(id: string) {
    enqueue(async () => {
      if (unknown.current) throw new Error("Event chưa rõ kết quả đang được giữ. Thử lại event trước khi đổi phiên.");
      const generation = epoch.current;
      const result = await call(`/sessions/${id}`);
      if (generation === epoch.current) publish(decodeSession(result));
    });
  }
  function retry() { enqueue(async () => { const request = unknown.current; if (request) await write(request.path, request.body); }); }
  function retryStale() { enqueue(async () => {
    const request = unknown.current, s = latest.current;
    if (!stale || !request || !s) return;
    const generation = epoch.current;
    const current = decodeSession(await call(`/sessions/${s.id}`));
    if (generation !== epoch.current) return;
    publish(current);
    // Explicit user retry after a server-declared no-commit conflict. Keep the
    // same event ID and intent; only expected_version is refreshed.
    await write(request.path, { ...request.body, expected_version: current.version });
  }); }
  function newSession() { const completed = latest.current; if (completed?.state === "finished" && !unknown.current) { setSaved(previous => [completed, ...previous.filter(r => r.id !== completed.id)]); latest.current = null; setSession(null); dirty.current.clear(); } }
  function markField(field: Field) { if (latest.current?.state === "active") dirty.current.add(field); }
  function flushField(field: Field) { if (dirty.current.delete(field)) record("field_edit", field); }
  return { session, cases, saved, error, pending, stale, start, record, reopen, retry, retryStale, newSession, markField, flushField };
}

export function BaselineRecorder({ measurement }: { measurement: ReturnType<typeof useBaselineMeasurement> }) {
  const [caseId, setCaseId] = useState("");
  const [operator, setOperator] = useState<"human_declared" | "automation">("human_declared");
  const m = measurement, s = m.session;
  return <details className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
    <summary className="cursor-pointer font-semibold">Đo phiên thử thao tác (tùy chọn)</summary>
    <p className="my-3 text-sm">Bạn chọn bắt đầu và tạm dừng. Chỉ lưu loại thao tác, số lần và thời gian; không lưu nội dung trường hoặc ghi chú. Người thử tự khai chưa phải nghiệm thu usefulness.</p>
    {!s && <div className="flex flex-wrap gap-3">
      <label>Ca thử<select className="fluent-input" value={caseId} onChange={e => setCaseId(e.target.value)}><option value="">Chọn ca</option>{m.cases.map(c => <option key={c.id} value={c.id}>{c.id} · {c.category}</option>)}</select></label>
      <label>Loại phiên<select className="fluent-input" value={operator} onChange={e => setOperator(e.target.value as typeof operator)}><option value="human_declared">Người thử (tự khai)</option><option value="automation">Kiểm tra tự động</option></select></label>
      <button type="button" disabled={!caseId || m.pending} onClick={() => m.start(caseId, operator)}>Bắt đầu đo</button>
      {!!m.saved.length && <label>Mở phiên gần đây<select className="fluent-input" defaultValue="" onChange={e => { if (e.target.value) m.reopen(e.target.value); }}><option value="">Chọn phiên</option>{m.saved.map(r => <option key={r.id} value={r.id}>{r.case_id} · {r.state} · {r.operator_kind} · {r.id.slice(-8)}</option>)}</select></label>}
    </div>}
    {s && <div className="space-y-3 text-sm">
      <p role="status">{s.case_id} · {s.operator_kind === "automation" ? "Kiểm tra tự động" : "Người thử tự khai"} · {s.state} · Phiên bản {s.version}</p>
      <dl className="grid grid-cols-2 gap-2"><dt>Thời gian ghi hoạt động</dt><dd>{(s.active_ms/1000).toFixed(1)} giây</dd><dt>Chờ</dt><dd>{(s.wait_ms/1000).toFixed(1)} giây</dd><dt>Tạm dừng</dt><dd>{(s.paused_ms/1000).toFixed(1)} giây</dd><dt>Chưa phân loại (khoảng dài)</dt><dd>{(s.unattributed_ms/1000).toFixed(1)} giây</dd><dt>Lượt nhập trường</dt><dd>{s.counts.field_edit || 0}</dd><dt>Thao tác thủ công</dt><dd>{s.counts.manual_action || 0}</dd></dl>
      {s.state !== "finished" && <div className="flex flex-wrap gap-3"><button type="button" disabled={m.pending} onClick={() => m.record(s.state === "active" ? "pause" : "resume")}>{s.state === "active" ? "Tạm dừng đo" : "Tiếp tục đo"}</button><button type="button" disabled={m.pending || s.state === "waiting"} onClick={() => m.record("wait")}>Bắt đầu chờ</button><button type="button" disabled={m.pending} onClick={() => m.record("finish")}>Kết thúc đo</button></div>}
      <p className="break-all text-xs">Phiên đo {s.id}. Kết thúc đo không gửi hay xử lý hồ sơ.</p>
      {s.state === "finished" && <button type="button" onClick={m.newSession}>Đo phiên mới, giữ phiên cũ</button>}
    </div>}
    {m.pending && <p role="status" className="mt-3 text-sm">Đang chờ biên nhận số đo…</p>}
    {m.error && <p role="alert" className="mt-3 text-sm text-red-700 dark:text-red-300">{m.error} <button type="button" disabled={m.pending} onClick={m.retry}>Thử lại event đang giữ</button>{m.stale && <button type="button" disabled={m.pending} onClick={m.retryStale}>Đọc phiên mới và thử lại thao tác đo</button>}</p>}
  </details>;
}
