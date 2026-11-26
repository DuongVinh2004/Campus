"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { policyApi, type PolicyField, type PolicyForm, type PolicyResult, type PolicyTopic, type ProofNode } from "../../lib/policy-api";

const OUTCOME_LABEL: Record<PolicyResult["outcome"], string> = {
  SATISFIED: "Đạt điều kiện", NOT_SATISFIED: "Chưa đạt điều kiện", UNDETERMINED: "Chưa đủ thông tin để kết luận",
};
const VALUE_MARK: Record<string, { mark: string; word: string }> = {
  T: { mark: "✓", word: "đúng" }, F: { mark: "✗", word: "sai" }, U: { mark: "?", word: "chưa biết" },
};
const REASON_TEXT: Record<string, string> = {
  MISSING_INPUT: "Còn thiếu thông tin ở bên dưới.", NO_APPLICABLE_RULE: "Chưa có quy định áp dụng cho trường hợp này.",
  RULE_CONFLICT: "Có hai quy định cho kết quả khác nhau; hãy hỏi phòng chức năng.", RULE_STALE: "Quy định đã đổi, đang chờ cập nhật; hãy hỏi phòng chức năng.",
  EXCEPTION_CONFLICT: "Có hai ngoại lệ mâu thuẫn; hãy hỏi phòng chức năng.", DEFER_TO_STAFF: "Trường hợp này cần cán bộ xem xét.",
};

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Không thực hiện được.";
}

function Proof({ node }: { node: ProofNode }) {
  const mark = VALUE_MARK[node.value];
  const isGroup = node.kind !== "pred";
  const label = isGroup
    ? node.kind === "all" ? "Cần đủ tất cả các điều kiện sau" : node.kind === "any" ? "Cần một trong các điều kiện sau" : "Điều kiện sau không được xảy ra"
    : node.text ?? "";
  return (
    <li role="treeitem" aria-expanded={isGroup ? true : undefined}>
      <span aria-hidden="true">{mark.mark} </span>
      <span>{label}</span>
      <span className="sr-only"> ({mark.word})</span>
      {node.source && (
        <details>
          <summary>Xem điều khoản: {node.source.path}</summary>
          <blockquote>{node.source.quote}</blockquote>
        </details>
      )}
      {node.children && node.children.length > 0 && (
        <ul role="group">{node.children.map(child => <Proof key={child.id} node={child} />)}</ul>
      )}
    </li>
  );
}

function FieldInput({ field, value, onChange }: { field: PolicyField; value: unknown; onChange: (v: unknown) => void }) {
  const id = `pf-${field.var}`;
  if (field.type === "boolean") {
    return (
      <label htmlFor={id}>
        <input id={id} type="checkbox" checked={value === true} onChange={e => onChange(e.target.checked)} /> {field.label}
      </label>
    );
  }
  if (field.type === "enum") {
    return (
      <label htmlFor={id}>{field.label}
        <select id={id} value={(value as string) ?? ""} onChange={e => onChange(e.target.value || undefined)}>
          <option value="">Chưa biết</option>
          {field.values.map(v => <option key={v} value={v}>{v}</option>)}
        </select>
      </label>
    );
  }
  const numeric = field.type === "number" || field.type === "integer";
  return (
    <label htmlFor={id}>{field.label}{field.unit ? ` (${field.unit})` : ""}
      <input id={id} type={numeric ? "number" : "text"} inputMode={numeric ? "decimal" : undefined} min={field.min ?? undefined} max={field.max ?? undefined}
        step={field.step ?? undefined} value={value === undefined ? "" : String(value)}
        onChange={e => onChange(e.target.value === "" ? undefined : numeric ? Number(e.target.value) : e.target.value)} />
      {field.source.path && <small> Nguồn: {field.source.path}</small>}
    </label>
  );
}

export function PolicySimulator() {
  const [topics, setTopics] = useState<PolicyTopic[] | null>(null);
  const [topic, setTopic] = useState<string | null>(null);
  const [form, setForm] = useState<PolicyForm | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<PolicyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [slider, setSlider] = useState<{ field: PolicyField; value: number } | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => { policyApi.topics().then(r => setTopics(r.topics)).catch(e => setError(message(e))); }, []);
  useEffect(() => () => { if (debounce.current) clearTimeout(debounce.current); }, []);

  const choose = useCallback((t: string) => {
    setTopic(t); setForm(null); setResult(null); setValues({}); setSlider(null); setError(null);
    policyApi.form(t).then(setForm).catch(e => setError(message(e)));
  }, []);

  const run = useCallback(async (inputs: Record<string, unknown>) => {
    if (!topic) return;
    setBusy(true); setError(null);
    try { setResult(await policyApi.evaluate(topic, inputs)); } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }, [topic]);

  const pickSlider = (field: PolicyField) => {
    const current = typeof values[field.var] === "number" ? (values[field.var] as number) : (field.min ?? 0);
    setSlider({ field, value: current });
  };
  const moveSlider = (next: number) => {
    if (!slider) return;
    setSlider({ ...slider, value: next });
    const inputs = { ...values, [slider.field.var]: next };
    setValues(inputs);
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => { void run(inputs); }, 300);
  };

  const numericFields = (form?.fields ?? []).filter(f => f.type === "number" || f.type === "integer");

  return (
    <div className="space-y-4">
      {error && <p role="alert">{error}</p>}
      {!topics && !error && <p role="status">Đang tải các chủ đề…</p>}
      {topics && topics.length === 0 && <p>Chưa có quy định nào được mã hóa để mô phỏng.</p>}
      {topics && topics.length > 0 && (
        <section aria-label="Chọn chủ đề">
          <ul className="space-y-2">
            {topics.map(t => (
              <li key={t.topic}>
                <button aria-pressed={topic === t.topic} onClick={() => choose(t.topic)}>
                  <strong>{t.label}</strong>{t.description ? <span> — {t.description}</span> : null}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {form && (
        <form className="campus-card space-y-3" onSubmit={e => { e.preventDefault(); void run(values); }} aria-label={`Biểu mẫu: ${form.conclusion}`}>
          <h2>{form.conclusion}</h2>
          <p>Nhập số liệu của bạn. Những ô để trống nghĩa là chưa biết; hệ thống sẽ không đoán thay bạn.</p>
          {form.fields.map(f => (
            <div key={f.var}><FieldInput field={f} value={values[f.var]} onChange={v => setValues(prev => {
              const next = { ...prev }; if (v === undefined) delete next[f.var]; else next[f.var] = v; return next; })} /></div>
          ))}
          <button type="submit" disabled={busy}>{busy ? "Đang kiểm tra…" : "Kiểm tra"}</button>
        </form>
      )}
      {result && (
        <section className="campus-card space-y-3" aria-live="polite" aria-label="Kết quả mô phỏng">
          <h2 data-testid="policy-outcome">{OUTCOME_LABEL[result.outcome]}</h2>
          {result.conclusion && <p>{result.conclusion.label}</p>}
          {result.reason && REASON_TEXT[result.reason] && result.outcome === "UNDETERMINED" && <p>{REASON_TEXT[result.reason]}</p>}
          {result.missing.length > 0 && (
            <p>Còn thiếu: {result.missing.map(m => form?.fields.find(f => f.var === m)?.label ?? m).join("; ")}.</p>
          )}
          {result.proof && <ul role="tree" aria-label="Chứng minh từng điều kiện"><Proof node={result.proof} /></ul>}
          {result.thresholds.length > 0 && (
            <div>
              <h3>Ngưỡng</h3>
              <ul>{result.thresholds.map(t => <li key={`${t.var}-${t.direction}`}>{t.text}</li>)}</ul>
            </div>
          )}
          {result.refer_to && (result.outcome === "UNDETERMINED") && <p>Bạn có thể hỏi phòng chức năng (Phòng Đào tạo) để được xác nhận.</p>}
          {numericFields.length > 0 && (
            <div>
              <h3>Nếu thay đổi</h3>
              <label>Chọn đại lượng
                <select value={slider?.field.var ?? ""} onChange={e => { const f = numericFields.find(x => x.var === e.target.value); if (f) pickSlider(f); else setSlider(null); }}>
                  <option value="">—</option>
                  {numericFields.map(f => <option key={f.var} value={f.var}>{f.label}</option>)}
                </select>
              </label>
              {slider && (
                <div>
                  <input type="range" aria-label={`Thanh trượt: ${slider.field.label}`} min={slider.field.min ?? 0} max={slider.field.max ?? 100}
                    step={slider.field.step ?? 1} value={slider.value} onChange={e => moveSlider(Number(e.target.value))} />
                  <input type="number" aria-label={`Giá trị: ${slider.field.label}`} min={slider.field.min ?? 0} max={slider.field.max ?? 100}
                    step={slider.field.step ?? 1} value={slider.value} onChange={e => moveSlider(Number(e.target.value))} />
                </div>
              )}
            </div>
          )}
          <p><em>Kết quả mô phỏng theo quy chế đã phát hành, không thay quyết định của nhà trường.</em></p>
        </section>
      )}
    </div>
  );
}
