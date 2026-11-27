"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { FeatureGate } from "../../lib/features";
import { policyApi, POLICY_PREFILL_KEY, type PolicyMatch } from "../../lib/policy-api";
import { proceduresApi, type ProcedureText } from "../../lib/procedures-api";
import { EXTRACTED_KEY } from "../procedures/ProcedureRunner";

function PolicyCard({ text }: { text: string }) {
  const [match, setMatch] = useState<PolicyMatch | null>(null);
  useEffect(() => {
    let alive = true;
    policyApi.match(text).then(m => { if (alive) setMatch(m); }).catch(() => { if (alive) setMatch(null); });
    return () => { alive = false; };
  }, [text]);
  if (!match?.topic) return null;
  const remember = () => {
    try { window.sessionStorage.setItem(POLICY_PREFILL_KEY, JSON.stringify({ topic: match.topic, values: match.values })); } catch { /* optional */ }
  };
  return (
    <aside aria-label="Kiểm tra điều kiện" className="campus-card space-y-1">
      <strong>Kiểm tra điều kiện: {match.label}</strong>
      <p>Nhập số liệu của bạn để biết có đạt điều kiện theo quy chế hay không, kèm điều khoản làm căn cứ.</p>
      {match.evidence.length > 0 && <p><small>Đã lấy từ câu của bạn: {match.evidence.map(e => `“${e.snippet}”`).join(", ")} — hãy kiểm tra lại.</small></p>}
      <Link href="/policy/simulator" onClick={remember}>Mở trình kiểm tra</Link>
    </aside>
  );
}

function ProcedureCard({ text }: { text: string }) {
  const [found, setFound] = useState<ProcedureText | null>(null);
  const [title, setTitle] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    proceduresApi.fromText(text).then(r => {
      if (!alive) return;
      setFound(r);
      setTitle(r.suggestions.find(s => s.procedure_id === r.procedure_id)?.title ?? null);
    }).catch(() => { if (alive) setFound(null); });
    return () => { alive = false; };
  }, [text]);
  if (!found || !found.procedure_id) return null;

  const begin = async () => {
    setBusy(true); setError(null);
    try {
      const run = await proceduresApi.start(found.procedure_id as string);
      const extracted = Object.fromEntries(found.extracted.map(e => [e.field, e.value]));
      try { window.sessionStorage.setItem(EXTRACTED_KEY(run.id), JSON.stringify(extracted)); } catch { /* optional */ }
      window.location.assign(`/services/procedures?run=${encodeURIComponent(run.id)}`);
    } catch (e) { setError(e instanceof Error ? e.message : "Không bắt đầu được."); setBusy(false); }
  };
  return (
    <aside aria-label="Làm thủ tục cùng trợ lý" className="campus-card space-y-1">
      <strong>Làm thủ tục: {title ?? found.procedure_id}</strong>
      <p>Trợ lý giúp bạn điền thông tin và kiểm tra điều kiện. Hồ sơ chỉ được gửi khi bạn xem trước và bấm “Gửi hồ sơ”.</p>
      {error && <p role="alert">{error}</p>}
      <button type="button" onClick={() => void begin()} disabled={busy}>Bắt đầu cùng trợ lý</button>
    </aside>
  );
}

/** Cards shown under a student's own question when it looks like a policy check or a procedure. Each card sits behind its feature flag. */
export function ChatSuggestionCards({ text }: { text: string }) {
  const question = text.trim();
  if (question.length < 8 || question.length > 1000) return null;
  return (
    <div className="space-y-2 pl-9 pr-2">
      <FeatureGate feature="policy.simulator"><PolicyCard text={question} /></FeatureGate>
      <FeatureGate feature="agent.procedures"><ProcedureCard text={question} /></FeatureGate>
    </div>
  );
}
