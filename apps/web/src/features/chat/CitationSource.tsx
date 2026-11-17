"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import React, { useEffect, useRef, useState } from "react";
import { sessionLoginHref } from "./local-session";
import type { StreamCitation } from "./sse";

export interface CitationSourceBinding {
  conversationId: string;
  messageId: string;
  citation: StreamCitation["citation"];
}

interface SourceResult {
  issuer: string;
  effective_from: string;
  effective_until: string | null;
  content_text: string;
  applicability_note?: string;
}

const API_BASE_URL = CAMPUS_API_BASE_URL;
const UUID7 = /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export function CitationSource({ binding }: { binding: CitationSourceBinding }) {
  const [source, setSource] = useState<SourceResult | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error" | "expired" | "denied" | "success">("idle");
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => () => { controllerRef.current?.abort(); }, [binding]);

  async function open() {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const current = () => controllerRef.current === controller && !controller.signal.aborted;
    setSource(null); setState("loading");
    const timer = window.setTimeout(() => controller.abort(), 10000);
    try {
      const { conversationId, messageId, citation } = binding;
      if (![conversationId, messageId, citation.citation_id].every((id) => UUID7.test(id))) throw Error();
      const response = await fetch(`${API_BASE_URL}/v1/conversations/${conversationId}/messages/${messageId}/citations/${citation.citation_id}/source`, {
        credentials: "include", cache: "no-store", signal: controller.signal,
      });
      if (!current()) return;
      if (response.status === 401) { setState("expired"); return; }
      if ([403, 404].includes(response.status)) { setState("denied"); return; }
      if (!response.ok) throw Error();
      const result = await response.json();
      if (!current()) return;
      if (result.conversation_id !== conversationId || result.message_id !== messageId
          || result.representation !== "CITED_CHUNK" || !result.citation
          || Object.keys(citation).some((key) => key !== "locator" && result.citation[key] !== citation[key as keyof typeof citation])
          || Object.entries(citation.locator).some(([key, value]) => value != null && result.citation.locator?.[key] !== value)
          || typeof result.issuer !== "string" || !result.issuer.trim() || result.issuer.length > 300
          || typeof result.content_text !== "string" || !result.content_text.length || result.content_text.length > 20000
          || (result.applicability_note !== undefined && (typeof result.applicability_note !== "string" || result.applicability_note.length > 1000))
          || !citation.quote || !result.content_text.includes(citation.quote)
          || !/^[0-9a-f]{64}$/.test(result.content_sha256)
          || (citation.evidence_sha256 !== undefined && result.content_sha256 !== citation.evidence_sha256)
          || typeof result.effective_from !== "string" || !Number.isFinite(Date.parse(result.effective_from))
          || (result.effective_until !== null && (typeof result.effective_until !== "string" || !Number.isFinite(Date.parse(result.effective_until))))) throw Error();
      const bytes = new TextEncoder().encode(result.content_text);
      const digest = await window.crypto.subtle.digest("SHA-256", bytes);
      if (Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("") !== result.content_sha256) throw Error();
      if (current()) { setSource(result); setState("success"); }
    } catch {
      if (controllerRef.current === controller) { setSource(null); setState("error"); }
    } finally { window.clearTimeout(timer); }
  }

  return <div className="w-full min-w-0" style={{ overflowWrap: "anywhere" }}>
    <button type="button" onClick={() => void open()} disabled={state === "loading"}
      className="text-sm font-semibold text-blue-800 dark:text-blue-300 underline">
      {state === "loading" ? "Đang xác minh nguồn…" : "Mở đoạn nguồn gốc"}
    </button>
    {state === "expired" && <p role="alert">Phiên đăng nhập đã hết hạn. <a className="underline" href={sessionLoginHref(`/chat?conversation_id=${binding.conversationId}`)}>Đăng nhập lại</a>.</p>}
    {state === "denied" && <p role="alert">Nguồn không còn khả dụng hoặc bạn không có quyền truy cập. Hãy kiểm tra lại phiên đăng nhập.</p>}
    {state === "error" && <p role="alert">Chưa thể xác minh nguồn. Hãy thử mở lại.</p>}
    {source && <section aria-label="Đoạn nguồn gốc đã xác minh" className="mt-3 text-sm">
      {binding.citation.source_status === "SYNTHETIC" && <p className="font-semibold">Nguồn mô phỏng — không dùng làm quy định thực tế.</p>}
      <p>Cơ quan ban hành: {source.issuer}</p>
      {source.applicability_note && <p>{source.applicability_note}</p>}
      {!binding.citation.version_label.startsWith("public-") && <>
        <p>Phiên bản: {binding.citation.version_label}</p>
        {!source.applicability_note && <p>Hiệu lực từ: {new Date(source.effective_from).toLocaleString("vi-VN", { timeZone: "Asia/Bangkok" })}{source.effective_until ? ` đến ${new Date(source.effective_until).toLocaleString("vi-VN", { timeZone: "Asia/Bangkok" })}` : ""} (UTC+7)</p>}
      </>}
      <p>Vị trí: {binding.citation.locator.section_path || binding.citation.locator.paragraph_id || `Trang ${binding.citation.locator.page_start}`}</p>
      <p>Toàn bộ đoạn được trích dẫn:</p>
      <div className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded border p-3" data-testid="original-source-text">{source.content_text}</div>
    </section>}
  </div>;
}
