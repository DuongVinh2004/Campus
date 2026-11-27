"use client";

import { useT } from "@/lib/i18n";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ChevronRight, FileText } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { ApiClient, ApiClientError } from "@/lib/api/client";
import { assistantClientId } from "@/lib/assistant-state-service";
import { ServiceCatalog } from "./ServiceCatalog";
import { OPS_ENABLED, problemMessage, ticketsApi, type ServiceKind } from "@/lib/campus-ops-api";
import { SubmittedTickets } from "../tickets/SubmittedTickets";
import { chatDraftActorScope, useActorRouteState, useTabDraftOwner } from "../chat/route-drafts";

type Kind = "STUDENT_CERTIFICATE" | "GRADE_APPEAL" | "GENERAL_SUPPORT";
type Form = { kind: Kind; purpose: string; recipient: string; course: string; reason: string };
type Draft = { id: string; version: number; form: Form; status: "DRAFT"; sent_to_university: false; updated_at: string };
type Preview = { preview_id: string; confirmation_token: string; expires_at: string; payload: { id: string; form: Form } };
type Pending = { preview_id: string; confirmation_token: string; client_id: string; confirmed: true };
const titles: Record<Kind, string> = { STUDENT_CERTIFICATE: "Giấy xác nhận sinh viên đang học", GRADE_APPEAL: "Phúc khảo kết quả học tập", GENERAL_SUPPORT: "Hỗ trợ thủ tục học vụ" };
const blank = (kind: Kind): Form => ({ kind, purpose: "", recipient: "", course: "", reason: "" });
const endpoint = "/v1/student-preparations";
const SENT_KEY = "campus:sent-drafts";
function readSentDrafts(): Record<string, string> {
  try { const value = JSON.parse(window.localStorage.getItem(SENT_KEY) || "{}"); return value && typeof value === "object" ? value : {}; } catch { return {}; }
}
function writeSentDrafts(value: Record<string, string>) {
  try { window.localStorage.setItem(SENT_KEY, JSON.stringify(value)); } catch { /* private mode: the badge is session-only */ }
}

export function OperationalServiceWorkspace({ history = false }: { history?: boolean }) {
  const t = useT();
  return <AppShell activeNav={history ? "tickets" : "services"} userRole="guest"><ScopedServiceContent history={history} /></AppShell>;
}

function ScopedServiceContent({ history }: { history: boolean }) {
  const t = useT();
  const owner = useTabDraftOwner();
  if (owner.enabled && !owner.scope) return <p role="status">{t("osw.1")}</p>;
  return <ServiceContent key={owner.scope || "standalone"} history={history} ownerScope={owner.scope} />;
}

function ServiceContent({ history, ownerScope }: { history: boolean; ownerScope: string | null }) {
  const t = useT();
  type Actor = { user_id?: string; subject_id?: string; display_name: string; roles: string[] };
  const [actor, setActor] = useState<Actor | null>(null);
  const [rows, setRows] = useState<Draft[]>([]);
  const prefix = history ? "student-preparation:tickets:" : "student-preparation:services:";
  const [selected, setSelected] = useActorRouteState<Draft | null>(ownerScope, prefix + "selected", null);
  const [entries, setEntries] = useActorRouteState<Record<string, { selected: Draft | null; form: Form }>>(ownerScope, prefix + "entries", () => ({}));
  const [form, setForm] = useActorRouteState<Form>(ownerScope, prefix + "form", () => blank("GENERAL_SUPPORT"));
  const [editing, setEditing] = useActorRouteState(ownerScope, prefix + "editing", false);
  const [showHistory, setShowHistory] = useActorRouteState(ownerScope, prefix + "history", history);
  const [preview, setPreview] = useActorRouteState<Preview | null>(ownerScope, prefix + "preview", null);
  const [pending, setPending] = useActorRouteState<Pending | null>(ownerScope, prefix + "pending", null);
  const [reviewed, setReviewed] = useActorRouteState(ownerScope, prefix + "reviewed", false);
  const [uncertain, setUncertain] = useActorRouteState(ownerScope, prefix + "uncertain", false);
  const [error, setError] = useActorRouteState(ownerScope, prefix + "error", "");
  const [notice, setNotice] = useActorRouteState(ownerScope, prefix + "notice", "");
  const [working, setWorking] = useActorRouteState(ownerScope, prefix + "working", false);
  const [hasDraft, setHasDraft] = useActorRouteState(ownerScope, prefix + "has-draft", false);
  const [initializing, setInitializing] = useState(true);
  const busy = initializing || working;
  const [focusRequest, setFocusRequest] = useState(0);
  const [confirmSubmitId, setConfirmSubmitId] = useState<string | null>(null);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [submitResult, setSubmitResult] = useState<{ ok: boolean; message: string; ticketId?: string } | null>(null);
  const [ticketsRefresh, setTicketsRefresh] = useState(0);
  // A draft stays on file after it is sent (the server has no draft deletion), so remember which version went out.
  const [sent, setSent] = useState<Record<string, string>>({});
  useEffect(() => { setSent(readSentDrafts()); }, []);
  const formPanel = useRef<HTMLElement>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const student = actor?.roles.includes("STUDENT");
  const api = () => new ApiClient();

  useEffect(() => {
    if (editing) {
      formPanel.current?.scrollIntoView({ block: "start", behavior: "instant" });
      formPanel.current?.focus({ preventScroll: true });
    }
  }, [editing, selected?.id, focusRequest]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const user = await api().get<Actor>("/v1/users/me");
        if (!active) return;
        if (ownerScope && chatDraftActorScope(user) !== ownerScope) throw new Error("Tài khoản đã thay đổi; bản nháp riêng được giữ để đối chiếu.");
        if (!user.roles.includes("STUDENT")) { setActor(user); return; }
        const result = await api().get<{ items: Draft[] }>(endpoint);
        if (!active) return;
        const params = new URLSearchParams(window.location.search);
        const requestId = params.get("request");
        const kind = params.has("new") ? "STUDENT_CERTIFICATE" : params.get("kind");
        const requestedKind = !requestId && kind && Object.hasOwn(titles, kind) ? kind as Kind : null;
        const switchKind = requestedKind && (!hasDraft || form.kind !== requestedKind || selected !== null);
        const switchRecord = requestId && (!hasDraft || selected?.id !== requestId);
        const blocked = hasDraft && (switchKind || switchRecord) && (working || uncertain);
        let requested: Draft | null = null;
        if (switchRecord && !blocked) {
          requested = await api().get<Draft>(`${endpoint}/${encodeURIComponent(requestId!)}`);
          if (!active) return;
        }
        if (ownerScope) {
          const verified = await api().get<Actor>("/v1/users/me");
          if (!active) return;
          if (chatDraftActorScope(verified) !== ownerScope) throw new Error("Tài khoản đã thay đổi; bản nháp riêng được giữ để đối chiếu.");
        }
        setActor(user);
        setRows(result.items);
        if (blocked) { setError("Cần đọc lại kết quả lưu của bản nháp đang chờ trước khi chuyển sang hồ sơ khác."); return; }
        if (hasDraft && !requested && !switchKind) return;
        const retained = { ...entries, [selected?.id || "new:" + form.kind]: { selected, form } };
        if (requested) {
          const restored = retained[requested.id] || { selected: requested, form: requested.form };
          setEntries(retained); setSelected(restored.selected); setForm(restored.form);
          setEditing(true); setShowHistory(true); setHasDraft(true);
          setPreview(null); setPending(null); setReviewed(false);
        } else if (switchKind && requestedKind) {
          const restored = retained["new:" + requestedKind] || { selected: null, form: blank(requestedKind) };
          setEntries(retained); setSelected(restored.selected); setForm(restored.form);
          setEditing(true); setHasDraft(true); setPreview(null); setPending(null); setReviewed(false);
        }
      } catch (e) { if (active) setError(e instanceof Error ? e.message : "Chưa đọc được hồ sơ"); }
      finally { if (active) setInitializing(false); }
    })();
    return () => { active = false; };
  }, []);

  function activate(kind: Kind, row: Draft | null = null) {
    if (busy || uncertain) return;
    const retained = { ...entries, [selected?.id || "new:" + form.kind]: { selected, form } };
    const next = retained[row?.id || "new:" + kind] || { selected: row, form: row?.form || blank(kind) };
    setEntries(retained);
    setHasDraft(true);
    setSelected(next.selected); setForm(next.form); setEditing(true); setPreview(null); setPending(null); setReviewed(false); setError(""); setNotice("");
    setFocusRequest(value => value + 1);
    window.history.replaceState(window.history.state, "", row ? `${window.location.pathname}?request=${row.id}` : `${window.location.pathname}?kind=${kind}`);
  }
  function choose(kind: Kind) { activate(kind); }
  // Sends a saved draft to the internal one-stop workflow. The key is derived from the draft id and version, so a
  // retry (or a second click) of the same version replays the same ticket instead of creating a duplicate.
  async function submitDraft(row: Draft) {
    const lines = [
      row.form.purpose.trim() && `Mục đích: ${row.form.purpose.trim()}`,
      row.form.recipient.trim() && `Đơn vị nhận: ${row.form.recipient.trim()}`,
      row.form.course.trim() && `Học phần: ${row.form.course.trim()}`,
      row.form.reason.trim() && `Nội dung: ${row.form.reason.trim()}`,
    ].filter(Boolean) as string[];
    const summary = lines.join("\n");
    if (summary.length < 10) {
      setSubmitResult({ ok: false, message: "Nháp còn quá ngắn. Hãy mở nháp, bổ sung nội dung rồi lưu lại trước khi gửi." });
      setConfirmSubmitId(null);
      return;
    }
    setSubmittingId(row.id); setSubmitResult(null);
    try {
      const fields = Object.fromEntries(Object.entries({ purpose: row.form.purpose, recipient: row.form.recipient, course: row.form.course, reason: row.form.reason })
        .filter(([, value]) => value.trim()).map(([key, value]) => [key, value.trim()]));
      const ticket = await ticketsApi.submit({ service_kind: row.form.kind as ServiceKind, title: titles[row.form.kind], summary, fields }, `draft-${row.id}-v${row.version}`);
      setSubmitResult({ ok: true, message: `Đã gửi hồ sơ ${ticket.code} đến bộ phận Một cửa. Theo dõi tiến trình ở mục “Hồ sơ đã gửi” bên dưới.`, ticketId: ticket.id });
      setSent(current => { const next = { ...current, [`${row.id}-v${row.version}`]: ticket.code }; writeSentDrafts(next); return next; });
      setTicketsRefresh(value => value + 1);
      window.dispatchEvent(new Event("campus:notifications-changed"));
    } catch (e) {
      setSubmitResult({ ok: false, message: problemMessage(e, "Chưa gửi được hồ sơ. Nháp của bạn vẫn được giữ nguyên.") });
    } finally { setSubmittingId(null); setConfirmSubmitId(null); }
  }
  function edit(patch: Partial<Form>) { setHasDraft(true); setForm(current => ({ ...current, ...patch })); setPreview(null); setPending(null); setReviewed(false); setNotice(""); }
  async function prepare() {
    if (busy) return;
    setWorking(true); setError(""); setNotice("");
    try {
      const result = await api().post<Preview>(`${endpoint}/preview`, { form, document_id: selected?.id ?? null, expected_version: selected?.version ?? 0 });
      setPreview(result); setReviewed(false);
      setPending({ preview_id: result.preview_id, confirmation_token: result.confirmation_token, client_id: assistantClientId(), confirmed: true });
    } catch (e) { setError(e instanceof Error ? e.message : "Chưa xem trước được; nội dung được giữ"); }
    finally { setWorking(false); }
  }
  async function save() {
    if (!pending || !reviewed || busy) return;
    setWorking(true); setUncertain(true); setError("");
    try {
      const result = await api().post<{ effect: string; document: Draft; receipt_id: string }>(`${endpoint}/save`, pending);
      if (result.effect !== "draft_saved" || result.document.id !== preview?.payload.id || result.document.sent_to_university !== false) throw new Error("Chưa xác nhận được kết quả lưu");
      setSelected(result.document); setForm(result.document.form);
      setEntries(current => ({ ...current, [result.document.id]: { selected: result.document, form: result.document.form },
        ...(!selected ? { ["new:" + result.document.form.kind]: { selected: null, form: blank(result.document.form.kind) } } : {}) }));
      setRows(current => [result.document, ...current.filter(r => r.id !== result.document.id)]);
      setPreview(null); setPending(null); setUncertain(false); setShowHistory(true);
      setNotice(`Đã lưu nháp · Biên nhận ${result.receipt_id}. Chưa gửi đến trường.`);
      if (mounted.current) window.history.replaceState(window.history.state, "", `${window.location.pathname}?request=${result.document.id}`);
    } catch (e) {
      setUncertain(!(e instanceof ApiClientError && e.problem.status >= 400 && e.problem.status < 500));
      setError(e instanceof Error ? e.message : "Chưa rõ kết quả lưu; đọc lại bằng cùng mã lưu");
    } finally { setWorking(false); }
  }

  const visibleRows = selected && !rows.some(row => row.id === selected.id) ? [selected, ...rows] : rows;

  return <>
    <div className="campus-workflow space-y-5">
      <header className="campus-page-heading"><div data-eyebrow={t("osw.35")}><h1 className="text-2xl font-semibold">{history ? t("osw.33") : t("osw.34")}</h1><p className="mt-2 text-sm">{actor?.display_name ? `${actor.display_name} · ` : ""}{t("oswx.1")}</p></div></header>
      <p className="campus-panel text-sm" role="status">{t("oswx.2")}</p>
      {error && <p role="alert" className="rounded-xl border border-[var(--color-danger-subtle)] bg-[var(--surface-subtle)] p-3 text-xs text-[var(--color-danger)]">{error} {t("oswx.3")}</p>}
      {busy && <p role="status">{t("osw.2")}</p>}
      {notice && <p role="status" className="rounded-xl border border-[var(--color-success-subtle)] bg-[var(--surface-subtle)] p-3 text-xs text-[var(--color-success)]">{notice}</p>}
      {!actor && !busy && <Link href="/login" className="fluent-btn-primary">{t("osw.3")}</Link>}
      {actor && !student && <p>{t("osw.4")} <Link href="/knowledge/sources" className="underline">{t("osw.5")}</Link> {t("osw.6")} <Link href="/login" className="underline">{t("osw.7")}</Link> {t("osw.8")}</p>}
      {!editing && history && !!student && <Link href="/services" className="fluent-btn-primary w-fit">{t("osw.9")}</Link>}
      {!editing && !history && <ServiceCatalog preparationOnly authenticated={!!student} onChoose={choose} onCertificate={() => choose("STUDENT_CERTIFICATE")} onHistory={() => setShowHistory(true)} />}
      {student && showHistory && (
        <section className="campus-panel space-y-4">
          <h2 className="text-lg font-semibold">{t("osw.10")}</h2>
          {!visibleRows.length && !busy && (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[var(--border-color)] py-8 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--color-primary-light)] text-[var(--color-primary)]">
                <FileText className="h-5 w-5" aria-hidden="true" />
              </div>
              <p className="text-sm text-[var(--text-secondary)]">{t("osw.11")}</p>
            </div>
          )}
          <ul className="space-y-3">
            {visibleRows.map(row => (
              <li key={row.id}>
                <button
                  type="button"
                  disabled={busy || uncertain}
                  className="campus-record-option group flex min-h-[56px] w-full items-center justify-between gap-3 rounded-[12px] border border-[var(--border-color)] bg-[var(--surface-card)] p-3.5 text-left transition hover:bg-[var(--surface-subtle)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={() => activate(row.form.kind, row)}
                >
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <strong className="font-semibold">{titles[row.form.kind]}</strong>
                    <span className="block truncate text-sm text-[var(--text-secondary)]">
                      {(row.form.reason.trim() || row.form.purpose).replace(/\s+/g, " ").trim().slice(0, 80)}
                    </span>
                    <span className="flex flex-wrap items-center gap-2 text-xs text-[var(--text-secondary)]">
                      <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-[var(--color-primary-light)] px-2 py-0.5 font-medium text-[var(--color-primary)]">
                        <FileText className="h-3 w-3" aria-hidden="true" />
                        <span>{t("oswx.4", { v: row.version })}</span>
                      </span>
                      <span>{t("oswx.5")} · {new Date(row.updated_at).toLocaleString("vi-VN")}</span>
                    </span>
                  </div>
                  <ChevronRight className="h-5 w-5 shrink-0 text-[var(--text-secondary)] transition-colors group-hover:text-[var(--color-primary)]" aria-hidden="true" />
                </button>
                {OPS_ENABLED && (
                  <div className="mt-2 flex flex-wrap items-center justify-end gap-2">
                    {sent[`${row.id}-v${row.version}`] ? (
                      <span className="text-sm text-[var(--color-success)]" role="status" data-testid={`draft-sent-${row.id}`}>Đã gửi hồ sơ {sent[`${row.id}-v${row.version}`]}</span>
                    ) : confirmSubmitId === row.id ? (
                      <>
                        <span className="text-sm text-[var(--text-secondary)]" role="status">{t("osw.12")}</span>
                        <button type="button" className="fluent-btn-primary min-h-[44px]" data-testid={`draft-submit-confirm-${row.id}`} disabled={submittingId === row.id} onClick={() => void submitDraft(row)}>
                          {submittingId === row.id ? t("osw.28") : t("osw.29")}
                        </button>
                        <button type="button" className="fluent-btn-secondary min-h-[44px]" disabled={submittingId === row.id} onClick={() => setConfirmSubmitId(null)}>{t("osw.13")}</button>
                      </>
                    ) : (
                      <button type="button" className="fluent-btn-secondary min-h-[44px]" data-testid={`draft-submit-${row.id}`} disabled={busy || uncertain || !!submittingId}
                        onClick={() => { setSubmitResult(null); setConfirmSubmitId(row.id); }}>{t("osw.14")}</button>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
          {submitResult && <p role={submitResult.ok ? "status" : "alert"} className={"rounded-xl border p-3 text-sm " + (submitResult.ok ? "border-[var(--color-primary)] bg-[var(--color-primary-light)]" : "border-[var(--border-color)]")} data-testid="draft-submit-result">{submitResult.message}</p>}
        </section>
      )}
      {student && history && OPS_ENABLED && <SubmittedTickets initialId={submitResult?.ticketId ?? null} refreshToken={ticketsRefresh} />}
      {student && editing && <section ref={formPanel} tabIndex={-1} aria-label={t("osw.30")} className="campus-panel space-y-4">
        <button type="button" className="fluent-btn-secondary" disabled={busy || uncertain} onClick={() => { setEditing(false); setPreview(null); setPending(null); }}>{history ? t("osw.26") : t("osw.27")}</button>
        <h2 className="text-xl font-semibold">Chuẩn bị {titles[form.kind].toLocaleLowerCase("vi")}</h2>
        {selected && <p className="text-sm">{t("oswx.6", { id: selected.id, v: selected.version })}</p>}
        {form.kind === "GRADE_APPEAL" && <p>{t("osw.15")}</p>}
        {form.kind === "STUDENT_CERTIFICATE" && <p>{t("osw.16")}</p>}
        <fieldset disabled={busy || uncertain} className="space-y-4">
          {form.kind === "STUDENT_CERTIFICATE" && <><label className="block">{t("osw.17")}<input className="fluent-input mt-1 w-full" maxLength={2000} value={form.purpose} onChange={e => edit({ purpose: e.target.value })} /></label><label className="block">{t("osw.18")}<input className="fluent-input mt-1 w-full" maxLength={500} value={form.recipient} onChange={e => edit({ recipient: e.target.value })} /></label></>}
          {form.kind === "GRADE_APPEAL" && <label className="block">{t("osw.19")}<input className="fluent-input mt-1 w-full" maxLength={500} value={form.course} onChange={e => edit({ course: e.target.value })} /></label>}
          <label className="block">{t("osw.20")}<textarea className="fluent-input mt-1 w-full" rows={5} maxLength={6000} value={form.reason} onChange={e => edit({ reason: e.target.value })} /></label>
          <button type="button" className="fluent-btn-primary" disabled={!form.reason.trim()} onClick={() => void prepare()}>{t("osw.21")}</button>
        </fieldset>
        {preview && <section aria-label={t("osw.21")} className="space-y-3 rounded-xl border p-4"><h3 className="font-semibold">{t("osw.22")}</h3><p>{titles[preview.payload.form.kind]}</p>{preview.payload.form.purpose && <p>Mục đích: {preview.payload.form.purpose}</p>}{preview.payload.form.recipient && <p>Đơn vị nhận: {preview.payload.form.recipient}</p>}{preview.payload.form.course && <p>Học phần tự khai: {preview.payload.form.course}</p>}<p className="whitespace-pre-wrap">{preview.payload.form.reason}</p><p className="text-sm">{t("osw.23")}</p><label className="block"><input type="checkbox" checked={reviewed} disabled={busy || uncertain} onChange={e => setReviewed(e.target.checked)} /> {t("osw.24")}</label><button type="button" className="fluent-btn-primary" disabled={busy || !reviewed} onClick={() => void save()}>{uncertain ? t("osw.31") : t("osw.32")}</button></section>}
        <Link href="/chat" className="underline">{t("osw.25")}</Link>
      </section>}
    </div>
  </>;
}
