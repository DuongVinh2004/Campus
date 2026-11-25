"use client";
import { RefreshCw } from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";

import { useT, type MessageKey } from "@/lib/i18n";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  LearningApiError,
  LearningGateway,
  type LearningExitDraft,
  type LearningExitReceipt,
  type LearningExitReview,
  type LearningExitStaffSubmission,
  type LearningExitSubmission,
  type LearningExitTicket,
  type LearningExitWallInput,
  type LearningMaterial,
  type LearningVisibleExitTicket,
} from "../../lib/data/api/learning-gateway";
import { ExitTicketDraftForm, ExitTicketStatus, ExitTicketTimes, ExitWallField, exitWallInstant, exitWallPayload } from "./ExitTickets";
import type { ReadingInstruction } from "./ReadingInstructions";
import styles from "./learning.module.css";
import { useActorRouteState,useTabDraftOwner } from "../chat/route-drafts";
import {LearningMetadataForm} from './LearningMetadataForm';
import {ExitTicketEditForm} from './ExitTicketEditForm';

const gateway = new LearningGateway();
const answerLimit = 1000;
const reviewLimit = 3000;
type ConfirmWrite = (path: string, payload: Record<string, unknown>, action: string, title: string, method: string) => Promise<unknown>;
type Attempt = { answer: string; revision: number; key: string; canRetry: boolean };
type ReviewDraft = { revision: number; topics: string; next_plan: string; explanation: string };

const actorHeader = (actorId: string) => ({ "X-Campus-Reader-Actor": actorId });
const denied = (error: unknown) => error instanceof LearningApiError && [401, 403, 404].includes(error.status);
const conflict = (error: unknown) => error instanceof LearningApiError && error.code === "REVISION_CONFLICT";
const uncertain = (error: unknown) => error instanceof LearningApiError && (error.status === 0 || error.status >= 500);
const message = (error: unknown, t: (key: MessageKey) => string) => error instanceof Error ? error.message : t("etdx.1");

function submissionTime(value: string, zoneId?: string) {
  return zoneId
    ? new Intl.DateTimeFormat("vi-VN", { timeZone: zoneId, dateStyle: "short", timeStyle: "short" }).format(new Date(value))
    : new Intl.DateTimeFormat("vi-VN", { timeZone: "UTC", dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function Receipt({ value, zoneId }: { value: LearningExitSubmission; zoneId?: string }) {
  const t = useT();
  return <section className={styles.exitReceipt} aria-label={t("etdx.2")}>
    <h4>{t("etdx.2")}</h4>
    <p>{t("etdx.62", { id: value.receipt_id, r: value.revision })}</p>
    <time dateTime={value.submitted_at}>{submissionTime(value.submitted_at, zoneId)} ({zoneId ?? "UTC"})</time>
    <p className={styles.exitAnswer}>{value.answer}</p>
    {(value.history?.length ?? 0) > 1 && <details><summary>{t("etdx.3")}</summary>
      <ul className={styles.list}>{value.history?.filter(item => item.revision !== value.revision).map(item => <li key={item.receipt_id}>
        <p>{t("etdx.63", { id: item.receipt_id, r: item.revision })}</p>
        <time dateTime={item.submitted_at}>{submissionTime(item.submitted_at, zoneId)} ({zoneId ?? "UTC"})</time>
        <p className={styles.exitAnswer}>{item.answer}</p>
      </li>)}</ul>
    </details>}
  </section>;
}

export function ExitTicketDetail({ actorId, ticketId, staff, canManage, materials, instructions, zoneId, readerSource,
  onClose, onOpen, onChange, confirmWrite }: {
  actorId: string; ticketId: string; staff: boolean; canManage: boolean;
  materials: LearningMaterial[]; instructions: ReadingInstruction[]; zoneId: string; readerSource?: { versionId: string; page: number };
  onClose: () => void; onOpen: (versionId: string, page: number) => void; onChange: () => void; confirmWrite: ConfirmWrite;
}) {
  const t = useT();
  const labelId = `learning-exit-ticket-${ticketId}`;
  const answerDescription = useId();
  const answerCounter = useId();
  const heading = useRef<HTMLHeadingElement | null>(null);
  const lifetime = useRef<AbortController | null>(null);
  const readGeneration = useRef(0);
  const working = useRef(false);
  const owner=useTabDraftOwner();
  const draftScope=JSON.stringify(["exit-ticket-detail",actorId,ticketId,staff]);
  const currentReadScope=JSON.stringify([owner.scope,actorId,ticketId,staff]);
  const [loadedScope,setLoadedScope]=useState<string>();
  const [mutationKeys,setMutationKeys]=useActorRouteState<Record<string,string>>(owner.scope,draftScope+":keys",()=>({}));
  const [ticket, setTicket] = useState<LearningExitTicket | null>(null);
  const [receipt, setReceipt] = useState<LearningExitSubmission | null | undefined>(undefined);
  const [review, setReview] = useState<LearningExitReview | null>(null);
  const [submissions, setSubmissions] = useState<LearningExitStaffSubmission[] | null>(null);
  const [draftAnswer,setDraftAnswer]=useActorRouteState<string|undefined>(owner.scope,draftScope+":answer",undefined);
  const [answerRevision,setAnswerRevision]=useActorRouteState<number|undefined>(owner.scope,draftScope+":answer-revision",undefined);
  const [attempt,setAttempt]=useActorRouteState<Attempt|undefined>(owner.scope,draftScope+":attempt",undefined);
  const [needsChoice,setNeedsChoice]=useActorRouteState(owner.scope,draftScope+":choice",false);
  const [editing,setEditing]=useActorRouteState<LearningVisibleExitTicket|undefined>(owner.scope,draftScope+":editing",undefined);
  const [editingOpen,setEditingOpen]=useActorRouteState(owner.scope,draftScope+':editing-open',true);
  const [extension,setExtension]=useActorRouteState<{wall:LearningExitWallInput;revision:number}|undefined>(owner.scope,draftScope+":extension",undefined);
  const [extensionOpen,setExtensionOpen]=useActorRouteState(owner.scope,draftScope+':extension-open',true);
  const [reviewDraft,setReviewDraft]=useActorRouteState<ReviewDraft|undefined>(owner.scope,draftScope+":review",undefined);
  const [reviewReadable,setReviewReadable]=useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const path = `/exit-tickets/${ticketId}`;

  const clearScope = useCallback(() => {
    setTicket(null); setReceipt(undefined); setReview(null); setSubmissions(null);setReviewReadable(false);setLoadedScope(undefined);
  }, []);

  const readCurrent = useCallback(async (signal: AbortSignal) => {
    const generation = ++readGeneration.current;
    const current = () => !signal.aborted && generation === readGeneration.current;
    const init = { signal, headers: actorHeader(actorId) };
    try {
      let next = await gateway.request<LearningExitTicket>(path, init);
      if (!current()) return;
      setTicket(next);
      if (next.state !== "CLOSED") { setReview(null); setSubmissions(null);setReviewReadable(false); }
      const own = !staff ? await gateway.request<{ submission: LearningExitSubmission | null }>(`${path}/me/submission`, init) : undefined;
      if (!current()) return;
      if (own) setReceipt(own.submission);
      if (next.state === "CLOSED") {
        try {
          const reviewed = await gateway.request<{ review: LearningExitReview | null }>(`${path}/review`, init);
          if (current()) {setReview(reviewed.review);setReviewReadable(true);}
        } catch (caught) {
          if (!denied(caught)) throw caught;
          if (!current()) return;
          setReview(null); setSubmissions(null);setReviewReadable(false);
          // The source can be withdrawn between reads while the owner's receipt stays available.
          next = await gateway.request<LearningExitTicket>(path, init);
          if (current()) setTicket(next);
        }
      }
      if (!current()) return;
      setLoadedScope(currentReadScope);
      return { ticket: next, receipt: own?.submission };
    } catch (caught) {
      if (!current()) return;
      if (denied(caught)) clearScope();
      setError(message(caught, t));
    }
  }, [actorId, clearScope, path, staff,currentReadScope]);

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    working.current = false; setBusy(false);
    setAttempt(current=>current?{...current,canRetry:false}:current);
    if(attempt)setNotice(t("etdx.4"));
    heading.current?.focus();
    const refresh = () => { if (!working.current) void readCurrent(controller.signal); };
    refresh();
    window.addEventListener("focus", refresh);
    const poll = window.setInterval(refresh, 15000);
    return () => { controller.abort(); window.removeEventListener("focus", refresh); window.clearInterval(poll); };
  }, [readCurrent]);

  const boundaryTicket=loadedScope===currentReadScope?ticket:null;
  const nextBoundary = boundaryTicket?.state === "OPEN" ? boundaryTicket.closes.utc : boundaryTicket?.state === "SCHEDULED" ? boundaryTicket.opens.utc : undefined;
  useEffect(() => {
    const signal = lifetime.current?.signal;
    if (!signal || !nextBoundary) return;
    const untilBoundary = Date.parse(nextBoundary) - Date.now();
    if (untilBoundary < 0 || untilBoundary > 2147482647) return;
    const timer = window.setTimeout(() => { if (!working.current) void readCurrent(signal); }, untilBoundary + 100);
    return () => window.clearTimeout(timer);
  }, [nextBoundary, readCurrent]);

  async function work(operation: (signal: AbortSignal) => Promise<void>,propagate=false) {
    const signal = lifetime.current?.signal;
    if (!signal || signal.aborted || working.current) {if(propagate)throw new Error(t("etdx.5"));return;}
    working.current = true;
    ++readGeneration.current;
    setBusy(true); setError(""); setNotice("");
    try { await operation(signal); }
    catch (caught) {
      if (!signal.aborted) {
        if (denied(caught)) {
          if (caught instanceof LearningApiError && caught.status === 401) clearScope();
          else await readCurrent(signal);
        }
        if (signal.aborted) {if(propagate)throw caught;return;}
        if(!propagate||denied(caught))setError(message(caught, t));
      }
      if(propagate)throw caught;
    } finally {
      if (lifetime.current?.signal === signal) {
        working.current = false; setBusy(false);
      }
    }
  }

  function change(payload: Record<string, unknown>, title?: string,propagate=false,privateKey?:string) {
    return work(async signal => {
      if (title) await confirmWrite(path, payload, "exit-ticket-update", title, "PATCH");
      else await writePrivate(path, payload, "PATCH", signal,privateKey);
      if (signal.aborted) {if(propagate)throw new Error(t("etdx.6"));return;}
      setEditing(undefined); setExtension(undefined);setEditingOpen(false);setExtensionOpen(false);
      await readCurrent(signal);
      if (!signal.aborted) { setNotice(t("etdx.7")); onChange(); }
    },propagate);
  }

  function writePrivate(destination: string, payload: Record<string, unknown>, method: string, signal: AbortSignal,suppliedKey?:string) {
    const stamp = JSON.stringify([destination,method,payload]);
    const key=mutationKeys[stamp]??suppliedKey??crypto.randomUUID();
    setMutationKeys(current=>({...current,[stamp]:key}));
    return gateway.write(destination, payload, method, key, actorHeader(actorId), signal)
      .then(value => {
        if (signal.aborted) throw new DOMException("Cancelled", "AbortError");
        setMutationKeys(current=>{if(current[stamp]!==key)return current;const {[stamp]:saved,...remaining}=current;return remaining;});return value;
      });
  }

  function send(current: Attempt) {
    setAttempt({ ...current, canRetry: false });
    void work(async signal => {
      try {
        const saved = await gateway.write<LearningExitReceipt>(`${path}/me/submission`,
          { answer: current.answer, revision: current.revision }, "PUT", current.key, actorHeader(actorId), signal);
        if (signal.aborted) return;
        setReceipt(previous => ({ ...saved, history: [...(previous?.history ?? (previous ? [previous] : []))
          .filter(item => item.revision !== saved.revision), saved] }));
        setDraftAnswer(undefined); setAnswerRevision(undefined); setAttempt(undefined); setNeedsChoice(false);
        setNotice(t("etdx.64", { r: saved.revision }));
      } catch (caught) {
        if (signal.aborted) return;
        if (uncertain(caught)) {
          setAttempt({ ...current, canRetry: false });
          setNotice(t("etdx.8"));
          return;
        }
        setAttempt(undefined);
        if (conflict(caught)) {
          await readCurrent(signal);
          if (!signal.aborted) {
            setNeedsChoice(true);
            setNotice(t("etdx.9"));
          }
          return;
        }
        if (caught instanceof LearningApiError && caught.code === "TICKET_NOT_OPEN") {
          await readCurrent(signal);
          if (!signal.aborted) setNotice(t("etdx.10"));
          return;
        }
        throw caught;
      }
    });
  }

  function checkAttempt(current: Attempt) {
    void work(async signal => {
      const observed = await readCurrent(signal);
      if (!observed || signal.aborted) return;
      const saved = observed.receipt;
      const sameAnswer = (item: LearningExitReceipt) => item.revision === current.revision + 1 && item.answer === current.answer;
      if (saved && (sameAnswer(saved) || saved.history?.some(sameAnswer))) {
        setAttempt(undefined); setNeedsChoice(false); setDraftAnswer(undefined); setAnswerRevision(undefined);
        setNotice(sameAnswer(saved) ? t("etdx.65", { r: saved.revision }) : t("etdx.11"));
      } else if ((saved?.revision ?? 0) !== current.revision) {
        setAttempt(undefined); setNeedsChoice(observed.ticket.state === "OPEN");
        setNotice(t("etdx.12"));
      } else if (observed.ticket.state === "OPEN") {
        setAttempt({ ...current, canRetry: true });
        setNotice(t("etdx.13"));
      } else {
        setAttempt(undefined); setNeedsChoice(false);
        setNotice(t("etdx.14"));
      }
    });
  }

  function loadSubmissions() {
    void work(async signal => {
      setSubmissions(null);
      const rows = await gateway.list<LearningExitStaffSubmission>(`${path}/submissions`, signal, actorHeader(actorId));
      if (!signal.aborted) setSubmissions(rows);
    });
  }

  async function saveReview(payload:Record<string,unknown>,key:string) {
    const signal=lifetime.current?.signal;
    if(!signal||signal.aborted||working.current)throw new Error(t("etdx.15"));
    working.current=true;++readGeneration.current;setBusy(true);setError('');setNotice('');
    try{
      await gateway.write(`${path}/review`,payload,'PUT',key,actorHeader(actorId),signal);
      if(signal.aborted)throw new Error(t("etdx.16"));
      const observed=await readCurrent(signal);
      if(!observed||signal.aborted)throw new Error(t("etdx.17"));
      setNotice(t("etdx.18"));
    }finally{if(lifetime.current?.signal===signal){working.current=false;setBusy(false);}}
  }

  function publishReview() {
    void work(async signal => {
      await confirmWrite(`${path}/review`, { operation: "PUBLISH", revision: review?.revision ?? 0 },
        "exit-review-save", t("etdx.19"), "PUT");
      if (signal.aborted) return;
      await readCurrent(signal);
      if (!signal.aborted) setNotice(t("etdx.20"));
    });
  }

  const answer = draftAnswer ?? receipt?.answer ?? "";
  const scopedTicket=loadedScope===currentReadScope?ticket:null;
  const visible = scopedTicket && scopedTicket.state !== "SOURCE_UNAVAILABLE" ? scopedTicket : null;
  const editable = !!visible && visible.state === "OPEN" && !staff && receipt !== undefined;
  const holdDraft = !!visible && !editable && draftAnswer !== undefined && !staff;
  const linked = visible?.instruction;
  const currentInstruction = linked && instructions.some(instruction => instruction.id === linked.id && instruction.revision === linked.revision);
  const clean = answer.trim();
  const answerLength = Array.from(answer).length;
  const canSubmit = editable && !busy && !attempt && !needsChoice && !!clean && answerLength <= answerLimit
    && (!receipt || clean !== receipt.answer);

  if(owner.enabled&&!owner.scope)return <p role="status">{t("etdx.21")}</p>;
  return <section className={`${styles.panel} ${styles.stack} ${styles.exitDetail}`} aria-labelledby={labelId}>
    <div className={styles.row}><h3 id={labelId} tabIndex={-1} ref={heading}>{t("etdx.22")}</h3>
      <button type="button" onClick={onClose}>{t("etdx.23")}</button></div>
    {error && <p role="alert">{error}</p>}
    {visible&&notice && <p role="status">{notice}</p>}
    {!scopedTicket && !error && <p role="status">{t("etdx.24")}</p>}
    {scopedTicket && <ExitTicketStatus ticket={scopedTicket} />}
    {visible && <>
      <p className={styles.exitAnswer}>{visible.question}</p>
      <ExitTicketTimes ticket={visible} />
      <button type="button" onClick={() => onOpen(visible.version_id, visible.page_no)}>{t("etdx.66", { p: visible.page_no })}</button>
      {linked && <section className={styles.stack} aria-label={t("etdx.25")}>
        <h4>{t("etdx.67", { r: linked.revision })}</h4>
        <p>{linked.purpose}</p>
        {linked.page_ranges.map(range => <button key={`${range.start}:${range.end}`} type="button"
          onClick={() => onOpen(visible.version_id, range.start)}>
          {t("etdx.68", { r: range.start === range.end ? range.start : `${range.start}–${range.end}` })}
        </button>)}
        {currentInstruction && <a href={`#learning-instruction-${linked.id}`} onClick={() => document.getElementById(`learning-instruction-${linked.id}`)?.focus()}>
          {t("etdx.69")}
        </a>}
      </section>}
    </>}
    {!staff && scopedTicket&&receipt && <Receipt value={receipt} zoneId={visible?.zone_id} />}
    {!staff && visible?.state === "CLOSED" && receipt === null && <p>{t("etdx.26")}</p>}
    {(editable || holdDraft) && <form className={styles.stack} onSubmit={event => {
      event.preventDefault();
      if (canSubmit) send({ answer: clean, revision: answerRevision ?? receipt?.revision ?? 0, key: crypto.randomUUID(), canRetry: false });
    }}>
      <label>{t("etdx.27")}<textarea rows={5} value={answer} readOnly={!editable || !!attempt || needsChoice} disabled={busy}
        aria-describedby={`${answerDescription} ${answerCounter}`} onChange={event => {
          if (draftAnswer === undefined) setAnswerRevision(receipt?.revision ?? 0);
          setDraftAnswer(event.target.value);
        }} /></label>
      <p id={answerDescription}>{t("etdx.28")}</p>
      <p id={answerCounter} aria-live="polite">{t("etdx.70", { a: answerLength, b: answerLimit })}</p>
      {editable && <button disabled={!canSubmit}>{receipt ? t("etdx.29") : t("etdx.30")}</button>}
    </form>}
    {visible&&!staff&&attempt && <div className={styles.row}>
      <button type="button" disabled={busy} onClick={() => checkAttempt(attempt)}>{t("etdx.31")}</button>
      {attempt.canRetry && editable && <button type="button" disabled={busy} onClick={() => send(attempt)}>{t("etdx.32")}</button>}
    </div>}
    {needsChoice && editable && <div className={styles.row}>
      <button type="button" onClick={() => { setDraftAnswer(undefined); setAnswerRevision(undefined); setNeedsChoice(false); setNotice(""); }}>{t("etdx.33")}</button>
      <button type="button" onClick={() => { setAnswerRevision(receipt?.revision ?? 0); setNeedsChoice(false); setNotice(""); }}>{t("etdx.34")}</button>
    </div>}
    {staff && canManage && visible?.state === "DRAFT" && <>
      {editing !== undefined&&editingOpen ? <ExitTicketEditForm key={`${currentReadScope}:edit`} actorId={actorId} materials={materials} instructions={instructions} draft={editing}
        source={readerSource} busy={busy} onSave={(payload,key)=>change(payload,undefined,true,key)} onCancel={() => setEditingOpen(false)} />
        : <div className={styles.row}>
          <button type="button" disabled={busy} onClick={() => {setEditing(current=>current??visible);setEditingOpen(true);}}>{t("etdx.35")}</button>
          <button type="button" disabled={busy} onClick={() => change({ operation: "PUBLISH", revision: visible.revision }, t("etdx.36"))}>{t("etdx.37")}</button>
        </div>}
    </>}
    {staff && canManage && visible && (visible.state === "SCHEDULED" || visible.state === "OPEN") && (
      extension&&extensionOpen ? <LearningMetadataForm key={`${currentReadScope}:extension`} actorId={actorId} draftId={`exit-extension:${ticketId}`} className={styles.stack} disabled={busy}
        initialValues={{closes:JSON.stringify(extension.wall)}} basis={{revision:extension.revision,zoneId:visible.zone_id,minimumCloseUtc:visible.closes.utc}}
        fieldLabels={{closes:t("etdx.38")}} renderValue={(_name,value)=>{const wall:LearningExitWallInput=JSON.parse(value);return wall.local.replace('T',' ')+(wall.offset_minutes!==undefined?` · UTC ${wall.offset_minutes/60>=0?'+':''}${wall.offset_minutes/60}`:'');}}
        toPayload={({values,basis})=>{
          const wall:LearningExitWallInput=JSON.parse(values.closes),instant=exitWallInstant(wall,String(basis.zoneId));
          if(!instant||Date.parse(instant)<=Math.max(Date.parse(visible.closes.utc),Date.parse(String(basis.minimumCloseUtc))))throw new Error(t("etdx.39"));
          return {operation:'EXTEND',revision:basis.revision,closes:exitWallPayload(wall,String(basis.zoneId))};
        }} onSave={payload=>change(payload,t("etdx.40"),true)}
        onRead={async signal=>{
          const current=await gateway.request<LearningExitTicket>(path,{signal,headers:actorHeader(actorId)});
          if(current.state!=='OPEN'&&current.state!=='SCHEDULED')throw new Error(t("etdx.41"));
          return {values:{closes:JSON.stringify({local:current.closes.local,offset_minutes:current.closes.offset_minutes})},basis:{revision:current.revision,zoneId:current.zone_id,minimumCloseUtc:current.closes.utc}};
        }}>{(values,update,basis)=>{
          const wall:LearningExitWallInput=JSON.parse(values.closes),proposedClose=exitWallInstant(wall,String(basis.zoneId));
          const canExtend=!!proposedClose&&Date.parse(proposedClose)>Math.max(Date.parse(visible.closes.utc),Date.parse(String(basis.minimumCloseUtc)));
          return <>
        <ExitWallField label={t("etdx.38")} zoneId={String(basis.zoneId)} value={wall} onChange={value=>update('closes',JSON.stringify(value))} />
        {proposedClose && !canExtend && <p role="alert">{t("etdx.39")}</p>}
        <div className={styles.row}><button disabled={busy || !canExtend}>{t("etdx.42")}</button>
          <button type="button" disabled={busy} onClick={() => setExtensionOpen(false)}>{t("etdx.43")}</button></div>
        </>;}}</LearningMetadataForm> : <button type="button" disabled={busy} onClick={() => {setExtension(current=>current??{
        wall: { local: visible.closes.local, offset_minutes: visible.closes.offset_minutes }, revision: visible.revision,
      });setExtensionOpen(true);}}>{t("etdx.44")}</button>
    )}
    {staff && canManage && visible && visible.state !== "CANCELLED" && !(visible.state==='DRAFT'&&editing&&editingOpen) && !(['SCHEDULED','OPEN'].includes(visible.state)&&extension&&extensionOpen) &&
      <button type="button" disabled={busy} onClick={() => change({ operation: "CANCEL", revision: visible.revision }, t("etdx.45"))}>{t("etdx.46")}</button>}
    {visible?.state === "CLOSED" && staff && reviewReadable && <section className={styles.stack} aria-label={t("etdx.47")}>
      <h4>{t("etdx.47")}</h4>
      <button type="button" disabled={busy} onClick={loadSubmissions}>{submissions ? t("etdx.48") : t("etdx.49")}</button>
      {submissions?.length === 0 && <p>{t("etdx.50")}</p>}
      {!!submissions?.length && <ul className={styles.list}>{submissions.map(item => <li key={item.id}>
        <p>{item.student_name ?? item.student_id} · {t("etdx.71", { r: item.revision })}</p><p className={styles.exitAnswer}>{item.answer}</p>
      </li>)}</ul>}
      {canManage && (reviewDraft ? <LearningMetadataForm key={`${currentReadScope}:review`} actorId={actorId} draftId={`exit-review:${ticketId}`} className={styles.stack} disabled={busy}
        initialValues={{topics:review?.topics??reviewDraft.topics,next_plan:review?.next_plan??reviewDraft.next_plan,explanation:review?.explanation??reviewDraft.explanation}} basis={{revision:review?.revision??reviewDraft.revision}}
        fieldLabels={{topics:t("etdx.51"),next_plan:t("etdx.52"),explanation:t("etdx.53")}}
        toPayload={({values,basis})=>({operation:'SAVE_DRAFT',...values,revision:basis.revision})} onSave={saveReview}
        onRead={async signal=>{
          const current=await gateway.request<LearningExitTicket>(path,{signal,headers:actorHeader(actorId)});
          if(current.state!=='CLOSED')throw new Error(t("etdx.54"));
          const {review:latest}=await gateway.request<{review:LearningExitReview|null}>(`${path}/review`,{signal,headers:actorHeader(actorId)});
          if(!latest)throw new Error(t("etdx.55"));
          return {values:{topics:latest.topics??'',next_plan:latest.next_plan??'',explanation:latest.explanation??''},basis:{revision:latest.revision}};
        }}>{(values,change)=><>
        <label>{t("etdx.51")}<textarea rows={4} maxLength={reviewLimit} value={values.topics}
          onChange={event => change('topics',event.target.value)} /></label>
        <label>{t("etdx.52")}<textarea rows={4} maxLength={reviewLimit} value={values.next_plan}
          onChange={event => change('next_plan',event.target.value)} /></label>
        <label>{t("etdx.53")}<textarea rows={4} maxLength={reviewLimit} value={values.explanation}
          onChange={event => change('explanation',event.target.value)} /></label>
        <p>{t("etdx.56")}</p>
        <div className={styles.row}><button disabled={busy}>{t("etdx.57")}</button>
          <button type="button" disabled={busy} onClick={() => setReviewDraft(undefined)}>{t("etdx.43")}</button></div>
        </>}</LearningMetadataForm> : <>
        {review?.topics && <p className={styles.exitAnswer}>{t("etdx.72", { v: review.topics })}</p>}
        {review?.next_plan && <p className={styles.exitAnswer}>{t("etdx.73", { v: review.next_plan })}</p>}
        {review?.explanation && <p className={styles.exitAnswer}>{t("etdx.74", { v: review.explanation })}</p>}
        <button type="button" disabled={busy} onClick={() => setReviewDraft({ revision: review?.revision ?? 0, topics: review?.topics ?? "",
          next_plan: review?.next_plan ?? "", explanation: review?.explanation ?? "" })}>{t("etdx.58")}</button>
      </>)}
      {canManage&&!!review?.explanation?.trim()&&review.explanation!==review.published?.explanation&&<>
        {reviewDraft&&<p>{t("etdx.59")}</p>}
        <button type="button" disabled={busy} onClick={publishReview}>{t("etdx.60")}</button>
      </>}
    </section>}
    {visible?.state === "CLOSED" && review?.published && <section className={styles.stack} aria-label={t("etdx.53")}>
      <h4>{t("etdx.53")}</h4><p className={styles.exitAnswer}>{review.published.explanation}</p>
    </section>}
    <IconButton label={t("etdx.61")} disabled={busy} onClick={() => void work(async signal => { await readCurrent(signal); })} icon={<RefreshCw size={17} />} />
  </section>;
}
