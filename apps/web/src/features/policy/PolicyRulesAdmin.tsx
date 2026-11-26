"use client";

import React, { useCallback, useEffect, useState } from "react";
import { policyRulesApi, type DraftView, type Preview, type Review, type RuleList, type RuleView, type RuleStatus } from "../../lib/policy-rules-api";

const STATUS: Record<RuleStatus, string> = { PUBLISHED: "Đang áp dụng", STALE: "Cần rà lại (nguồn đã đổi)", RETIRED: "Đã ngừng" };
const VERDICT: Record<Review["verdict"], string> = { approved: "Duyệt", rejected: "Từ chối", needs_source: "Cần thêm nguồn" };

function message(error: unknown): string {
  return error instanceof Error && error.message ? error.message : "Không thực hiện được. Hãy thử lại.";
}

function issueText(issue: unknown): string {
  return typeof issue === "string" ? issue : JSON.stringify(issue);
}

/** Confirm step shared by publish and retire: the change is shown first, nothing happens until the button is pressed. */
function ConfirmChange({ preview, onDone, onCancel }: { preview: Preview; onDone: () => void; onCancel: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const change = preview.change;
  return (
    <div role="dialog" aria-label="Xác nhận thay đổi luật" className="space-y-2">
      <p><strong>{change.retire ? "Ngừng áp dụng" : "Công bố"}</strong> luật <code>{String(change.rule_id)}</code>, phiên bản {String(change.version)}
        {change.supersedes_version ? ` (thay phiên bản ${String(change.supersedes_version)})` : ""}.</p>
      {typeof change.vectors === "number" && <p>{change.vectors} ca kiểm tự sinh đã chạy đúng.</p>}
      <p><small>Bản xem trước hết hạn lúc {new Date(preview.expires_at).toLocaleString("vi-VN")}.</small></p>
      {error && <p role="alert">{error}</p>}
      <button type="button" disabled={busy} onClick={async () => {
        setBusy(true); setError(null);
        try { await policyRulesApi.confirm(preview); onDone(); } catch (e) { setError(message(e)); } finally { setBusy(false); }
      }}>Xác nhận</button>
      <button type="button" onClick={onCancel}>Hủy</button>
    </div>
  );
}

function DraftPanel({ draftId, onChanged }: { draftId: string; onChanged: () => void }) {
  const [draft, setDraft] = useState<DraftView | null>(null);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [verdict, setVerdict] = useState<Review["verdict"]>("approved");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { const value = await policyRulesApi.draft(draftId); setDraft(value); setText(JSON.stringify(value.body, null, 2)); setError(null); }
    catch (e) { setError(message(e)); }
  }, [draftId]);
  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<unknown>, done: string) {
    setError(null); setStatus(null);
    try { await action(); setStatus(done); await load(); onChanged(); } catch (e) { setError(message(e)); }
  }

  if (!draft) return error ? <p role="alert">{error}</p> : <p role="status">Đang tải bản nháp…</p>;
  return (
    <section aria-label={`Bản nháp ${draft.rule_id}`} className="space-y-3">
      <h3>Bản nháp: {draft.rule_id}</h3>
      <p>{draft.origin === "MODEL_CANDIDATE" ? "Do AI soạn từ quy chế" : "Do cán bộ soạn"} · cập nhật {new Date(draft.updated_at).toLocaleString("vi-VN")}</p>
      {draft.issues.length > 0
        ? <div role="status"><p>Còn {draft.issues.length} lỗi phải sửa trước khi duyệt:</p><ul>{draft.issues.map((issue, i) => <li key={i}>{issueText(issue)}</li>)}</ul></div>
        : <p role="status">Kiểm cấu trúc và nguyên văn: đạt · {draft.vector_count} ca kiểm tự sinh{draft.mismatches.length ? ` · ${draft.mismatches.length} ca lệch` : " · không ca nào lệch"}.</p>}
      <label>Nội dung luật (JSON)
        <textarea value={text} rows={14} spellCheck={false} onChange={(e) => setText(e.target.value)} />
      </label>
      <button type="button" onClick={() => {
        let body: Record<string, unknown>;
        try { body = JSON.parse(text); } catch { setError("Nội dung không phải JSON hợp lệ."); return; }
        void run(() => policyRulesApi.updateDraft(draft.id, body, draft.row_version), "Đã lưu bản nháp.");
      }}>Lưu bản nháp</button>
      <button type="button" onClick={() => void run(() => policyRulesApi.validate(draft.id), "Đã kiểm lại.")}>Kiểm lại</button>
      <h4>Duyệt</h4>
      {draft.reviews.length === 0 ? <p>Chưa có lượt duyệt.</p> : (
        <ul>{draft.reviews.map((r, i) => <li key={i}>{VERDICT[r.verdict]} — {r.note} <small>({new Date(r.at).toLocaleString("vi-VN")})</small></li>)}</ul>
      )}
      <fieldset>
        <legend>Phán quyết của người duyệt</legend>
        {(Object.keys(VERDICT) as Review["verdict"][]).map((v) => (
          <label key={v}><input type="radio" name={`verdict-${draft.id}`} checked={verdict === v} onChange={() => setVerdict(v)} /> {VERDICT[v]}</label>
        ))}
        <label>Ghi chú (ít nhất 8 ký tự)<input value={note} onChange={(e) => setNote(e.target.value)} /></label>
        <button type="button" disabled={note.trim().length < 8} onClick={() => void run(() => policyRulesApi.review(draft.id, verdict, note.trim()), "Đã ghi phán quyết.")}>Ghi phán quyết</button>
      </fieldset>
      <button type="button" onClick={async () => { setError(null); try { setPreview(await policyRulesApi.publishPreview(draft.id)); } catch (e) { setError(message(e)); } }}>
        Xem trước khi công bố
      </button>
      {preview && <ConfirmChange preview={preview} onCancel={() => setPreview(null)} onDone={() => { setPreview(null); setStatus("Đã công bố."); onChanged(); }} />}
      {status && <p role="status">{status}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

function RulePanel({ ruleId, onChanged }: { ruleId: string; onChanged: () => void }) {
  const [rule, setRule] = useState<RuleView | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { try { setRule(await policyRulesApi.rule(ruleId)); } catch (e) { setError(message(e)); } }, [ruleId]);
  useEffect(() => { void load(); }, [load]);
  if (!rule) return error ? <p role="alert">{error}</p> : <p role="status">Đang tải luật…</p>;
  const body = rule.current.body as { conclusion?: { label?: string }; sources?: { quote?: string; path?: string }[] };
  return (
    <section aria-label={`Luật ${rule.rule_id}`} className="space-y-2">
      <h3>{body.conclusion?.label ?? rule.rule_id}</h3>
      <p>Phiên bản {rule.current.version} · {STATUS[rule.current.status]}</p>
      {Array.isArray(body.sources) && body.sources.length > 0 && (
        <ul aria-label="Căn cứ nguyên văn">{body.sources.map((s, i) => <li key={i}><blockquote>{s.quote}</blockquote>{s.path && <small>{s.path}</small>}</li>)}</ul>
      )}
      <p>Các phiên bản: {rule.versions.map((v) => `${v.version} (${STATUS[v.status]})`).join(", ")}</p>
      {rule.current.status !== "RETIRED" && (
        <button type="button" onClick={async () => { setError(null); try { setPreview(await policyRulesApi.retirePreview(rule.rule_id)); } catch (e) { setError(message(e)); } }}>
          Xem trước khi ngừng áp dụng
        </button>
      )}
      {preview && <ConfirmChange preview={preview} onCancel={() => setPreview(null)} onDone={() => { setPreview(null); void load(); onChanged(); }} />}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

/** Rules authored from the regulation: what applies now, drafts waiting for review, and publish/retire with a confirm step. */
export function PolicyRulesAdmin() {
  const [list, setList] = useState<RuleList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<{ kind: "draft" | "rule"; id: string } | null>(null);
  const load = useCallback(async () => { try { setList(await policyRulesApi.list()); setError(null); } catch (e) { setError(message(e)); } }, []);
  useEffect(() => { void load(); }, [load]);
  if (error && !list) return <p role="alert">{error}</p>;
  if (!list) return <p role="status">Đang tải danh sách luật…</p>;
  return (
    <div className="space-y-6">
      {list.stale > 0 && <p role="status">{list.stale} luật cần rà lại vì đoạn quy chế được trích đã thay đổi.</p>}
      <section aria-label="Luật đang có">
        <h2>Luật</h2>
        {list.rules.length === 0 ? <p>Chưa có luật nào.</p> : (
          <table>
            <thead><tr><th scope="col">Kết luận</th><th scope="col">Chủ đề</th><th scope="col">Phiên bản</th><th scope="col">Trạng thái</th><th scope="col"><span className="sr-only">Mở</span></th></tr></thead>
            <tbody>{list.rules.map((r) => (
              <tr key={r.rule_id}><th scope="row">{r.label}</th><td>{r.topic}</td><td>{r.version}</td><td>{STATUS[r.status]}</td>
                <td><button type="button" onClick={() => setOpen({ kind: "rule", id: r.rule_id })}>Xem</button></td></tr>
            ))}</tbody>
          </table>
        )}
      </section>
      <section aria-label="Bản nháp chờ duyệt">
        <h2>Bản nháp</h2>
        {list.drafts.length === 0 ? <p>Không có bản nháp.</p> : (
          <ul>{list.drafts.map((d) => (
            <li key={d.id}>{d.rule_id} · {d.origin === "MODEL_CANDIDATE" ? "AI soạn" : "cán bộ soạn"} · {new Date(d.updated_at).toLocaleString("vi-VN")}
              <button type="button" onClick={() => setOpen({ kind: "draft", id: d.id })}>Mở</button></li>
          ))}</ul>
        )}
      </section>
      {open?.kind === "draft" && <DraftPanel key={open.id} draftId={open.id} onChanged={() => void load()} />}
      {open?.kind === "rule" && <RulePanel key={open.id} ruleId={open.id} onChanged={() => void load()} />}
    </div>
  );
}
