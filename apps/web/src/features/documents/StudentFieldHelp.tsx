"use client";
import { useState } from "react";
import { useOptionalUnifiedAssistant } from "@/lib/unified-assistant-runtime";
import type { SurfaceContext } from "@/lib/assistant-state-service";
import type { ResourceRef } from "@/lib/unified-ai-contracts";
import { ApiClientError } from "@/lib/api/client";

export function formErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiClientError)) return {};
  return Object.fromEntries((error.problem.errors || []).map(e => [e.pointer.replace(/^\/(body\/)?form\//, "").split("/")[0], e.detail]));
}
export function MissingFields({ errors }: { errors: Record<string, string> }) {
  if (!Object.keys(errors).length) return null;
  return <div role="alert" className="my-3 rounded-lg border border-red-400 p-3"><p>Máy chủ yêu cầu kiểm tra các trường sau. Nội dung đang soạn được giữ.</p><ul>{Object.entries(errors).map(([field, detail]) => <li key={field}><a href={`#student-field-${field}`}>{field}: {detail}</a></li>)}</ul></div>;
}
export function StudentFieldHelp({ field, resource, hint, error }: { field: NonNullable<SurfaceContext["field"]>; resource?: ResourceRef; hint: string; error?: string }) {
  const runtime = useOptionalUnifiedAssistant();
  const [text, setText] = useState(""), [busy, setBusy] = useState(false);
  async function inspect() {
    if (!runtime || !resource) return; setBusy(true);
    try { await runtime.guard(); const value = await runtime.service.resolveSurface({ surface: resource.kind === "certificate_request" ? "certificate" : "service", resource, field }); await runtime.guard(); setText(value.field_guidance || "Đọc hướng dẫn nguồn của hồ sơ."); }
    catch (e) { setText(e instanceof Error ? e.message : "Chưa đối chiếu được trường này."); }
    finally { setBusy(false); }
  }
  return <div id={`student-help-${field}`} className="my-1 text-xs"><p>{hint}</p>{error && <p role="alert">{error}</p>}
    {resource && runtime?.capabilities?.resource_context && <button className="min-h-11 underline" type="button" disabled={busy} onClick={() => void inspect()}>Trợ giúp trường đã lưu</button>}{text && <p role="status">{text}</p>}
  </div>;
}
export async function readTextAttachment(file: File, count: number) {
  if (!file.name.toLowerCase().endsWith(".txt") || /[\\/:\u0000]/.test(file.name) || file.name.length > 120 || file.size > 16000 || file.size === 0 || count >= 3) throw new Error("Tối đa 3 tệp .txt UTF-8, 16 KB/tệp, tên không chứa đường dẫn.");
  const content = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
  if (!content.trim() || content.includes("\u0000") || new TextEncoder().encode(content).length > 16000) throw new Error("Nội dung tệp không hợp lệ.");
  return { name: file.name, content };
}
