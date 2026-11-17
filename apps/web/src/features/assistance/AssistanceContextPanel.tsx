"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import React, { useEffect, useRef, useState } from "react";
import { WorkflowDefinitionPanel } from "./WorkflowDefinitionPanel";
import { ResourceAssistant } from "./ResourceAssistant";
import { AssistantContent } from "@/features/chat/ChatPanel";
import { sessionLoginHref } from "@/features/chat/local-session";

const base = CAMPUS_API_BASE_URL;
interface ContextResult {
  schema_version: "unified-assistance.v1";
  status: "observed" | "source_changed" | "missing_source";
  resource: { id: string; version: number; status: string; workflow: string; view: "student" | "staff" };
  guidance: string;
  evidence: Array<{ source_id: string; version_id: string; locator: string; sha256: string; classification: "synthetic" | "public_snapshot" }>;
  limitations: string[];
  action_authority: "none";
}

function decode(value: unknown, id: string, version: number): ContextResult {
  const r = value as ContextResult;
  if (!r || r.schema_version !== "unified-assistance.v1" || r.action_authority !== "none" ||
      !["observed", "source_changed", "missing_source"].includes(r.status) ||
      r.resource?.id !== id || r.resource.version !== version ||
      !["student", "staff"].includes(r.resource.view) || typeof r.guidance !== "string" || r.guidance.length > 20000 ||
      !Array.isArray(r.limitations) || r.limitations.length > 8 || !r.limitations.every(s => typeof s === "string") ||
      !Array.isArray(r.evidence) || r.evidence.length > 6 || !r.evidence.every(e => e &&
        typeof e.source_id === "string" && typeof e.version_id === "string" && typeof e.locator === "string" &&
        /^[0-9a-f]{64}$/.test(e.sha256) && ["synthetic", "public_snapshot"].includes(e.classification))) {
    throw new Error("Trợ giúp không khớp hồ sơ/phiên bản đang mở. Hãy tải lại hồ sơ.");
  }
  return r;
}

export function AssistanceContextPanel({ id, version, surface = "service" }: {
  id: string; version: number; surface?: "service" | "certificate";
}) {
  const [result, setResult] = useState<ContextResult | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [expired, setExpired] = useState(false);
  const active = useRef<AbortController | null>(null);
  useEffect(() => {
    active.current?.abort(); active.current = null; setResult(null); setError(""); setPending(false); setExpired(false);
    return () => { active.current?.abort(); active.current = null; };
  }, [id, version, surface]);

  async function inspect() {
    active.current?.abort();
    const controller = new AbortController(); active.current = controller;
    setPending(true); setError(""); setResult(null); setExpired(false);
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      const response = await fetch(`${base}/v1/assistant/surface:resolve`, {
        method: "POST", headers, credentials: "include", cache: "no-store", signal: controller.signal,
        body: JSON.stringify({ surface, resource: { kind: surface === "service" ? "service_request" : "certificate_request", id, expected_version: version } }),
      });
      if (active.current !== controller || controller.signal.aborted) return;
      if (response.status === 401) setExpired(true);
      if (!response.ok) throw new Error(response.status === 409 ? "Hồ sơ đã đổi phiên bản. Tải lại hồ sơ trước khi trợ giúp."
        : response.status === 401 ? "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại."
        : "Chưa đọc được hồ sơ hoặc nguồn trong quyền hiện tại. Hãy kiểm tra và thử lại.");
      const value = decode((await response.json()).context, id, version);
      if (active.current === controller && !controller.signal.aborted) setResult(value);
    } catch (failure) {
      if (active.current === controller) setError(controller.signal.aborted ? "Chưa nhận được kết quả trong thời hạn. Bản nháp vẫn được giữ."
        : failure instanceof Error ? failure.message : "Trợ giúp chưa sẵn sàng.");
    } finally {
      window.clearTimeout(timeout);
      if (active.current === controller) { active.current = null; setPending(false); }
    }
  }
  return <aside className="my-4 min-w-0 rounded-xl border border-blue-200 p-4 dark:border-blue-800" aria-label="Trợ giúp hồ sơ dùng chung">
    <h3 className="font-semibold">Trợ giúp hồ sơ</h3>
    <p className="my-2 text-sm">Đọc lại trạng thái và nguồn theo quyền của bạn. Nội dung chưa lưu trong biểu mẫu vẫn được giữ.</p>
    <button type="button" className="fluent-btn-primary" disabled={pending} onClick={() => void inspect()}>{pending ? "Đang đối chiếu…" : "Đối chiếu hồ sơ và nguồn"}</button>
    {pending && <p role="status" className="mt-2 text-sm">Đang đọc phiên bản {version}…</p>}
    {error && <p role="alert" className="mt-3 text-sm text-red-700 dark:text-red-300">{error} {expired && <a className="underline" href={sessionLoginHref()}>Đăng nhập lại</a>}</p>}
    {result && <div className="mt-4 space-y-3 text-sm">
      <p role="status">{result.status === "source_changed" ? "Nguồn đã thay đổi — cần đối chiếu phiên bản áp dụng" : result.status === "missing_source" ? "Chưa đủ nguồn" : "Đã đọc hồ sơ và nguồn"} · Phiên bản {result.resource.version}</p>
      <AssistantContent content={result.guidance} audience={result.resource.view} />
      <ul className="space-y-2">{result.evidence.map(e => <li key={`${e.source_id}:${e.version_id}`} className="break-words">
        {e.classification === "synthetic" ? "Nguồn mô phỏng" : "Bản chụp nguồn công khai"}: {e.locator}
        <span className="block break-all text-xs">Phiên bản {e.version_id} · SHA256 {e.sha256}</span>
      </li>)}</ul>
      <ul className="list-inside list-disc space-y-1">{result.limitations.map((s, i) => <li key={i}>{s}</li>)}</ul>
    </div>}
    {process.env.NEXT_PUBLIC_UNIFIED_WORKFLOW === "true" && <WorkflowDefinitionPanel id={id} version={version} kind={surface === "service" ? "service_request" : "certificate_request"} />}
    {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && <ResourceAssistant id={id} version={version} surface={surface} />}
  </aside>;
}
