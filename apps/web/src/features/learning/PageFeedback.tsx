"use client";

import { useT, type MessageKey } from "@/lib/i18n";
import { useEffect, useId, useRef, useState } from "react";
import { AccessibleDialog } from "../../components/shared/AccessibleDialog";
import { LearningApiError, LearningGateway, type LearningSessionContext } from "../../lib/data/api/learning-gateway";
import { classDateTime, classDateTimeToUtc } from "./learning-time";
import styles from "./learning.module.css";
import { useActorRouteState, useTabDraftOwner } from "../chat/route-drafts";

const gateway = new LearningGateway();
const reasons = {
  HARD_TO_UNDERSTAND: "pfx.1",
  NEED_EXAMPLE: "pfx.2",
  POSSIBLE_ERROR: "pfx.3",
} as const;
type Reason = keyof typeof reasons;
type Feedback = { id: string; session_id: string; category: Reason; status: "ACTIVE" | "WITHDRAWN"; revision: number };
type Window = { closes_at: string };
type Summary = {
  state: "NOT_OPENED" | "WAITING" | "AVAILABLE" | "UNAVAILABLE";
  closes_at: string | null;
  pages: { version_id: string; page_no: number; band: "5-9" | "10-19" | "20+" }[];
};
type Attempt = { key: string; path: string; method: "PUT" | "PATCH"; body: Record<string, unknown>; revision: number };
type PageDraft = { selected: string; reason: Reason; revision: number; pending?: Attempt };

function errorMessage(error: unknown, t: (key: MessageKey) => string) {
  if (error instanceof LearningApiError) {
    switch (error.code) {
      case "FEEDBACK_WINDOW_UNAVAILABLE": return t("pfx.4");
      case "FEEDBACK_WINDOW_CLOSED": return t("pfx.5");
      case "FEEDBACK_SESSION_FIXED": return t("pfx.6");
      case "NETWORK_ERROR": return t("pfx.7");
    }
  }
  return error instanceof Error ? error.message : t("pfx.8");
}

function displayCutoff(value: string, timeZone: string) {
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(value));
}

export function StudentPageFeedback({ actorId, versionId, versionNumber, pageNo, sourceSessionId, timeZone }: {
  actorId: string; versionId: string; versionNumber: number; pageNo: number; sourceSessionId?: string; timeZone: string;
}) {
  const t = useT();
  const title = useId();
  const pageDescription = useId();
  const status = useRef<HTMLParagraphElement>(null);
  const owner = useTabDraftOwner();
  const scope = JSON.stringify(["page-feedback",actorId,versionId]);
  const [target, setTarget] = useActorRouteState<number|undefined>(owner.scope,scope+":target",undefined);
  const [drafts,setDrafts] = useActorRouteState<Record<number,PageDraft>>(owner.scope,scope+":drafts",{});
  const draft = target === undefined ? undefined : drafts[target];
  const selected = draft?.selected ?? "";
  const reason = draft?.reason ?? "HARD_TO_UNDERSTAND";
  const pending = draft?.pending;
  const readScope = JSON.stringify([owner.scope,scope,target]);
  const [loadedScope,setLoadedScope] = useState<string>();
  const [contexts, setContexts] = useState<LearningSessionContext[]>([]);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [window, setWindow] = useState<Window | null>();
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const active = useRef<AbortController | null>(null);
  const isOpen = target !== undefined;
  const contextReady = loadedScope === readScope;
  function updateDraft(page: number, patch: Partial<PageDraft>) {
    setDrafts(current=>({...current,[page]:{...(current[page]??{selected:"",reason:"HARD_TO_UNDERSTAND",revision:0}),...patch}}));
  }
  const path = (page: number) => `/versions/${versionId}/pages/${page}/me/feedback`;
  const current = (page: number, signal: AbortSignal) => gateway.request<{ feedback: Feedback | null }>(path(page), {
    signal, headers: { "X-Campus-Reader-Actor": actorId },
  });
  useEffect(() => {
    const controller = new AbortController();
    active.current = controller; setBusy(false);setLoadedScope(undefined);
    setContexts([]);setFeedback(null);setMessage("");setError("");
    if (target !== undefined && (!owner.enabled || owner.scope)) {
      setLoading(true);void loadContext(target, controller);
    }
    return () => controller.abort();
  }, [actorId, versionId, target, readScope, owner.enabled, owner.scope]);
  useEffect(() => {
    setWindow(undefined);
    if (target === undefined || !selected) return;
    const controller = new AbortController();
    void gateway.request<{ window: Window | null }>(`/sessions/${selected}/page-feedback-window`, {
      signal: controller.signal, headers: { "X-Campus-Reader-Actor": actorId },
    }).then(result => { if (!controller.signal.aborted) setWindow(result.window); })
      .catch(caught => { if (!controller.signal.aborted) setError(errorMessage(caught, t)); });
    return () => controller.abort();
  }, [actorId, selected, target,readScope]);

  async function open() {
    setTarget(pageNo);
  }

  async function loadContext(page: number, controller: AbortController) {
    try {
      const [links, own] = await Promise.all([
        gateway.sessionContexts(versionId, controller.signal, actorId), current(page, controller.signal),
      ]);
      if (controller.signal.aborted) return;
      setContexts(links); setFeedback(own.feedback);
      setDrafts(current=>current[page]?current:{...current,[page]:{
        reason:own.feedback?.category ?? "HARD_TO_UNDERSTAND",revision:own.feedback?.revision ?? 0,
        selected:own.feedback?.session_id ?? links.find(link=>link.id===sourceSessionId)?.id ?? (links.length===1?links[0].id:"")}});
      setLoadedScope(readScope);
    } catch (caught) {
      if (!controller.signal.aborted) setError(errorMessage(caught, t));
    } finally {
      if (!controller.signal.aborted && active.current === controller) {
        setLoading(false);
      }
    }
  }

  function close() {
    active.current?.abort();
    setTarget(undefined);
  }

  async function save(attempt: Attempt, checkFirst: boolean) {
    const controller = active.current;
    if (!controller || controller.signal.aborted || target === undefined || busy || !contextReady) return;
    // The initiating button can become disabled or disappear while the request runs.
    status.current?.focus();
    setBusy(true); setError(""); setMessage("");
    updateDraft(target,{pending:attempt});
    try {
      if (checkFirst) {
        const result = await current(target, controller.signal);
        if (controller.signal.aborted) return;
        if ((result.feedback?.revision ?? 0) !== attempt.revision) {
          setFeedback(result.feedback);updateDraft(target,{pending:undefined,revision:result.feedback?.revision??0,
            ...(result.feedback?{selected:result.feedback.session_id,reason:result.feedback.category}:{})});
          setMessage(t("pfx.9"));
          return;
        }
      }
      const result = await gateway.write<Feedback>(attempt.path, attempt.body, attempt.method, attempt.key,
        { "X-Campus-Reader-Actor": actorId }, controller.signal);
      if (controller.signal.aborted) return;
      setFeedback(result);updateDraft(target,{pending:undefined,selected:result.session_id,reason:result.category,revision:result.revision});
      setMessage(result.status === "WITHDRAWN" ? t("pfx.10") : t("pfx.11"));
    } catch (caught) {
      if (controller.signal.aborted) return;
      if (checkFirst || (caught instanceof LearningApiError && (caught.status === 0 || caught.status >= 500 || caught.status === 401 || caught.code === "REVISION_CONFLICT"))) updateDraft(target,{pending:attempt});
      else updateDraft(target,{pending:undefined});
      if(caught instanceof LearningApiError && [401,403,404].includes(caught.status))setLoadedScope(undefined);
      setError(errorMessage(caught, t));
    } finally {
      if (active.current === controller) setBusy(false);
    }
  }

  const linked = contextReady ? contexts.find(context => context.id === selected) : undefined;
  const hasActiveFeedback = feedback?.status === "ACTIVE";
  let statusMessage = message;
  if (busy) statusMessage = t("pfx.12");
  else if (loading || (!contextReady && !error) || (!error && linked && window === undefined)) statusMessage = t("pfx.13");
  else if (!message && !error) {
    if (!contexts.length && !feedback) statusMessage = t("pfx.14");
    else if (linked && window === null) statusMessage = t("pfx.4");
  }
  if(owner.enabled&&!owner.scope)return <p role="status">{t("pfx.15")}</p>;
  return <>
    <button type="button" aria-haspopup="dialog" onClick={event => {
      event.currentTarget.focus({ preventScroll: true });
      void open();
    }}>{t("pfx.16")}</button>
    <AccessibleDialog open={isOpen} labelledBy={title} describedBy={pageDescription} className={styles.dialog}
      preventClose={busy} onClose={close}>
      <h2 id={title} tabIndex={0}>{t("pfx.16")}</h2>
      <p id={pageDescription}>Phiên bản {versionNumber} · Trang {target}</p>
      <p>{t("pfx.17")}</p>
      {contextReady && !loading && feedback && <p>{linked?.title ?? t("pfx.18")} · {hasActiveFeedback ? t(reasons[feedback.category]) : t("pfx.19")}</p>}
      {contextReady && !loading && !feedback && contexts.length > 1 && <label>{t("pfx.20")}
        <select value={selected} onChange={event => target!==undefined&&updateDraft(target,{selected:event.target.value})} disabled={busy || !!pending}>
          <option value="">{t("pfx.21")}</option>
          {contexts.map(context => <option key={context.id} value={context.id}>{context.title}</option>)}
        </select>
      </label>}
      {contextReady && !loading && !feedback && contexts.length === 1 && <p>{contexts[0].title}</p>}
      {contextReady && window && <p>Giờ chốt {displayCutoff(window.closes_at, timeZone)} ({timeZone}). Các thay đổi sau giờ này chỉ cập nhật phản hồi riêng.</p>}
      {linked && <fieldset disabled={busy || !!pending}>
        <legend>{t("pfx.22")}</legend>
        {(Object.keys(reasons) as Reason[]).map(value => <label key={value}>
          <input type="radio" name={title} value={value} checked={reason === value} onChange={() => target!==undefined&&updateDraft(target,{reason:value})} /> {t(reasons[value])}
        </label>)}
      </fieldset>}
      <div>
        <p ref={status} role="status" tabIndex={busy ? 0 : -1} aria-label={t("pfx.23")}>{statusMessage}</p>
        <p role="alert">{error}</p>
      </div>
      <div className={styles.row}>
        {target !== undefined && linked && <button type="button" disabled={busy || loading || !!pending || !window}
          onClick={() => void save({ path: path(target), method: "PUT", key: crypto.randomUUID(),
            body: { category: reason, session_id: selected, revision: draft?.revision ?? 0 }, revision: draft?.revision ?? 0 }, false)}>
          {hasActiveFeedback ? t("pfx.24") : t("pfx.25")}
        </button>}
        {contextReady && hasActiveFeedback && <button type="button" disabled={busy || !!pending}
          onClick={() => void save({ path: `/me/page-feedback/${feedback.id}`, method: "PATCH", key: crypto.randomUUID(),
            body: { revision: feedback.revision }, revision: feedback.revision }, false)}>{t("pfx.26")}</button>}
        {contextReady && pending && <button type="button" disabled={busy} onClick={() => void save(pending, true)}>{t("pfx.27")}</button>}
        <button type="button" disabled={busy} onClick={close}>{t("pfx.28")}</button>
      </div>
    </AccessibleDialog>
  </>;
}

export function SessionPageFeedback({ actorId, sessionId, startsAt, timeZone, canOpen, onConfigure, onOpen }: {
  actorId: string; sessionId: string; startsAt: string | null; timeZone: string; canOpen: boolean;
  onConfigure: (closesAt: string) => Promise<unknown>; onOpen: (versionId: string, page: number) => void;
}) {
  const t = useT();
  const owner=useTabDraftOwner();
  const scope=JSON.stringify(["session-page-feedback",actorId,sessionId]);
  const readScope=JSON.stringify([owner.scope,scope]);
  const [loadedScope,setLoadedScope]=useState<string>();
  const [summaryRow, setSummary] = useState<Summary>();
  const summary=loadedScope===readScope?summaryRow:undefined;
  const [reload, setReload] = useActorRouteState(owner.scope,scope+":reload",0);
  const [saving, setSaving] = useActorRouteState(owner.scope,scope+":saving",false);
  const [cutoff,setCutoff]=useActorRouteState<string|undefined>(owner.scope,scope+":cutoff",undefined);
  const [error, setError] = useActorRouteState(owner.scope,scope+":error","");
  useEffect(() => {
    const controller = new AbortController();
    setError("");setLoadedScope(undefined);
    if(owner.enabled&&!owner.scope)return ()=>controller.abort();
    void gateway.request<Summary>(`/sessions/${sessionId}/page-feedback-summary`, {
      signal: controller.signal, headers: { "X-Campus-Reader-Actor": actorId },
    }).then(result => { if (!controller.signal.aborted) {setSummary(result);setLoadedScope(readScope);} })
      .catch(caught => { if (!controller.signal.aborted) setError(errorMessage(caught, t)); });
    return () => controller.abort();
  }, [actorId, sessionId, reload,readScope,owner.enabled,owner.scope]);
  const suggested = startsAt ? new Date(new Date(startsAt).getTime() + 48 * 60 * 60 * 1000) : null;
  if(owner.enabled&&!owner.scope)return <p role="status">{t("pfx.29")}</p>;
  return <section aria-label={t("pfx.30")}>
    <h3>{t("pfx.30")}</h3>
    {summary?.state === "NOT_OPENED" && canOpen && <form className={styles.form} onSubmit={event => {
      event.preventDefault();
      const value = String(new FormData(event.currentTarget).get("closes_at") ?? "");
      if(saving)return;setSaving(true); setError("");
      void Promise.resolve().then(() => onConfigure(classDateTimeToUtc(value, timeZone)))
        .then(() => setReload(current=>current+1)).catch(caught => setError(errorMessage(caught, t))).finally(() => setSaving(false));
    }}>
      <label>Giờ chốt ({timeZone}) <input name="closes_at" type="datetime-local" required
        disabled={saving} value={cutoff??(suggested && suggested.getTime() > Date.now() ? classDateTime(suggested.getTime(), timeZone) : "")}
        onChange={event=>setCutoff(event.target.value)} /></label>
      <button disabled={saving}>{t("pfx.31")}</button>
    </form>}
    {summary?.closes_at && <p>Giờ chốt {displayCutoff(summary.closes_at, timeZone)} ({timeZone}).</p>}
    {summary?.state === "WAITING" && <p role="status">{t("pfx.32")}</p>}
    {summary?.state === "UNAVAILABLE" && <p role="status">{t("pfx.33")}</p>}
    {summary?.state === "AVAILABLE" && (summary.pages.length ? <ul>
      {summary.pages.map(({ version_id, page_no, band }) => <li key={`${version_id}:${page_no}`}>
        <button type="button" onClick={() => onOpen(version_id, page_no)}>Mở trang {page_no}</button> · {band} lượt báo
      </li>)}
    </ul> : <p>{t("pfx.34")}</p>)}
    {error && <p role="alert">{error}</p>}
    {summary?.state !== "NOT_OPENED" && <button type="button" onClick={() => setReload(reload + 1)}>{t("pfx.35")}</button>}
  </section>;
}
