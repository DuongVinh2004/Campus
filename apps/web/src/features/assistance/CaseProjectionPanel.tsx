"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { useEffect, useRef, useState } from "react";
import { ApiClient } from "../../lib/api/client";
import type { ResourceRef } from "../../lib/unified-ai-contracts";
interface Projection { resource: { version: number; status: string }; queue: string; source_state: string; handovers: Array<{ version: number; summary: { done: string[]; open: string[]; next_action: string; visibility: string } }> }
export function CaseProjectionPanel({ resource }: { resource: ResourceRef }) {
  const [value, setValue] = useState<Projection | null>(null);
  const [message, setMessage] = useState("");
  const context = `${resource.kind}:${resource.id}:${resource.expected_version}`;
  const current = useRef(context); current.current = context;
  const mounted = useRef(true);
  async function load() {
    const started = context;
    setValue(null);
    const result = await new ApiClient({ baseUrl: CAMPUS_API_BASE_URL }).post<Projection>("/v1/assistant/cases/projection:read", { resource });
    if (result.resource.version !== resource.expected_version) throw new Error("Hồ sơ đã đổi; tải lại trước khi tiếp tục");
    if (mounted.current && current.current === started) { setValue(result); setMessage(""); }
  }
  useEffect(() => {
    mounted.current = true; let cancelled = false;
    const refresh = () => { setValue(null); void load().catch(e => { if (!cancelled) setMessage(String(e)); }); };
    const visible = () => { if (document.visibilityState === "visible") refresh(); else setValue(null); };
    refresh(); window.addEventListener("focus", refresh); document.addEventListener("visibilitychange", visible);
    return () => { cancelled = true; mounted.current = false; window.removeEventListener("focus", refresh); document.removeEventListener("visibilitychange", visible); };
  }, [context]);
  return <section className="my-3 space-y-2 rounded border p-3" aria-label="Trạng thái chung theo quyền"><h3>Trạng thái hồ sơ hiện tại</h3>
    {value && <><p>v{value.resource.version} · {value.resource.status} · {value.queue} · nguồn {value.source_state}</p>{value.handovers.map(v => <div key={v.version}><p>Bàn giao v{v.version} · {v.summary.visibility}</p><p>Đã làm: {v.summary.done.join("; ")}</p><p>Còn mở: {v.summary.open.join("; ")}</p><p>Bước tiếp: {v.summary.next_action}</p></div>)}</>}
    <button type="button" onClick={() => void load().catch(e => setMessage(String(e)))}>Đối chiếu lại quyền, phiên bản và nguồn</button>{message && <p role="status">{message}</p>}
  </section>;
}
