"use client";

import { useT, type MessageKey } from "@/lib/i18n";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import {
  LearningGateway,
  type LearningExitDraft,
  type LearningExitTicket,
  type LearningExitWallInput,
  type LearningExitWallTime,
  type LearningMaterial,
  type LearningPreview,
  type LearningVisibleExitTicket,
} from "../../lib/data/api/learning-gateway";
import { classDateTimeCandidates, utcOffsetLabel } from "./learning-time";
import type { ReadingInstruction } from "./ReadingInstructions";
import styles from "./learning.module.css";
import { useActorRouteState,useTabDraftOwner } from "../chat/route-drafts";

const gateway = new LearningGateway();
const emptyTime: LearningExitWallInput = { local: "" };
const labels: Record<LearningExitTicket["state"], MessageKey> = {
  DRAFT: "etx.1",
  SCHEDULED: "etx.2",
  OPEN: "etx.3",
  CLOSED: "etx.4",
  CANCELLED: "etx.5",
  SOURCE_UNAVAILABLE: "etx.6",
};

export function ExitTicketTimes({ ticket }: { ticket: LearningVisibleExitTicket }) {
  const t = useT();
  const wall = (value: LearningExitWallTime) => <time dateTime={value.utc}>
    {value.local.replace("T", " ")} ({utcOffsetLabel(value.offset_minutes)})
  </time>;
  return <dl className={styles.exitTimes}>
    <div><dt>{t("etx.7")}</dt><dd>{ticket.zone_id}</dd></div>
    <div><dt>{t("etx.8")}</dt><dd>{wall(ticket.opens)}</dd></div>
    <div><dt>{t("etx.9")}</dt><dd>{wall(ticket.closes)}</dd></div>
  </dl>;
}

export function ExitTicketPreviewDetails({ preview }: { preview: NonNullable<LearningPreview["exit_ticket"]> }) {
  const t = useT();
  return <div className={styles.stack}>
    <p>{t("etx.34", { s: t(labels[preview.state]) })}</p>
    {preview.state !== "SOURCE_UNAVAILABLE" && <>
      <p>{t("etx.35", { p: preview.page_no })} · {preview.question}</p>
      <ExitTicketTimes ticket={preview} />
    </>}
    <p>{t("etx.36", { a: preview.students, b: preview.submissions })}</p>
  </div>;
}

function timeCandidates(local: string, zoneId: string) {
  try { return classDateTimeCandidates(local, zoneId); }
  catch { return []; }
}

export function exitWallInstant(value: LearningExitWallInput, zoneId: string) {
  const candidates = timeCandidates(value.local, zoneId);
  return (candidates.length === 1 ? candidates[0] : candidates.find(candidate => candidate.offsetMinutes === value.offset_minutes))?.utc;
}

export function exitWallPayload(value: LearningExitWallInput, zoneId: string): LearningExitWallInput {
  return timeCandidates(value.local, zoneId).length > 1 ? value : { local: value.local };
}

export function ExitWallField({ label, zoneId, value, onChange }: {
  label: string; zoneId: string; value: LearningExitWallInput; onChange: (value: LearningExitWallInput) => void;
}) {
  const t = useT();
  const errorId = useId();
  const candidates = timeCandidates(value.local, zoneId);
  const invalid = !!value.local && candidates.length === 0;
  return <div className={styles.stack}>
    <label>{label} ({zoneId})
      <input type="datetime-local" required step={60} value={value.local}
        aria-invalid={invalid || undefined} aria-describedby={invalid ? errorId : undefined}
        onChange={event => onChange({ local: event.target.value })} />
    </label>
    {invalid && <p id={errorId} role="alert">{t("etx.10")}</p>}
    {candidates.length > 1 && <label>{t("etx.37", { l: label.toLowerCase() })}
      <select required value={value.offset_minutes ?? ""} onChange={event => onChange({
        local: value.local, ...(event.target.value ? { offset_minutes: Number(event.target.value) } : {}),
      })}>
        <option value="">{t("etx.11")}</option>
        {candidates.map(candidate => <option key={candidate.utc} value={candidate.offsetMinutes}>
          {utcOffsetLabel(candidate.offsetMinutes)}
        </option>)}
      </select>
    </label>}
  </div>;
}

export type ExitFormValues={versionId:string;page:number;question:string;opens:LearningExitWallInput;closes:LearningExitWallInput;instruction:string};
export type ExitPinnedInstruction={versionId:string;instruction:NonNullable<LearningVisibleExitTicket['instruction']>};
export function initialExitFormValues(draft?:LearningVisibleExitTicket,source?:{versionId:string;page:number}):ExitFormValues{return {
  versionId:draft?.version_id??source?.versionId??'',page:draft?.page_no??source?.page??1,question:draft?.question??'',
  opens:draft?.opens?{local:draft.opens.local,offset_minutes:draft.opens.offset_minutes}:emptyTime,
  closes:draft?.closes?{local:draft.closes.local,offset_minutes:draft.closes.offset_minutes}:emptyTime,
  instruction:draft?.instruction?`${draft.instruction.id}:${draft.instruction.revision}`:''};}
export function exitDraftState(values:ExitFormValues,materials:LearningMaterial[],instructions:ReadingInstruction[],zoneId:string,draft?:LearningVisibleExitTicket,pins:ExitPinnedInstruction[]=[]){
  const {versionId,page,question,opens,closes,instruction}=values;
  const versions=materials.filter(material=>material.visibility==='VISIBLE').flatMap(material=>material.versions.filter(version=>version.publication_state==='PUBLISHED'&&version.processing_state==='READY').map(version=>({...version,title:material.title})));
  const activeVersion=versions.find(version=>version.id===versionId);
  const options=instructions.filter(item=>item.version_id===versionId&&item.status!=='ARCHIVED').map(item=>({value:`${item.id}:${item.revision}`,title:item.purpose,id:item.id,revision:item.revision}));
  const pinned=[...pins,...(draft?.instruction?[{versionId:draft.version_id,instruction:draft.instruction}]:[])];
  for(const entry of pinned){const item=entry.instruction,value=`${item.id}:${item.revision}`;if(entry.versionId===versionId&&!options.some(option=>option.value===value))options.push({value,title:item.purpose,id:item.id,revision:item.revision});}
  const bound=options.find(item=>item.value===instruction),openUtc=exitWallInstant(opens,zoneId),closeUtc=exitWallInstant(closes,zoneId);
  const reversed=!!openUtc&&!!closeUtc&&closeUtc<=openUtc;
  const valid=!!activeVersion&&Number.isInteger(page)&&page>=1&&page<=activeVersion.page_count&&!!question.trim()&&!!openUtc&&!!closeUtc&&!reversed&&(!instruction||!!bound);
  return {versions,activeVersion,options,bound,reversed,valid};
}
export function exitDraftPayload(values:ExitFormValues,materials:LearningMaterial[],instructions:ReadingInstruction[],zoneId:string,draft?:LearningVisibleExitTicket,pins:ExitPinnedInstruction[]=[]):LearningExitDraft{
  const {valid,bound,reversed}=exitDraftState(values,materials,instructions,zoneId,draft,pins);
  if(!valid)throw new Error(reversed?'Giờ đóng phải sau giờ mở.':'Kiểm tra nguồn, trang, chỉ dẫn đọc và lịch nhận bài. Nháp vẫn được giữ.');
  return {version_id:values.versionId,page_no:values.page,question:values.question.trim(),opens:exitWallPayload(values.opens,zoneId),closes:exitWallPayload(values.closes,zoneId),instruction:bound?{id:bound.id,revision:bound.revision}:null};
}
export function ExitTicketDraftForm({ materials, instructions, zoneId, source, draft, busy, onSave, onCancel,draftScope,controlledValues,onValuesChange,embedded=false,pinnedInstructions=[] }: {
  materials: LearningMaterial[]; instructions: ReadingInstruction[]; zoneId: string;
  source?: { versionId: string; page: number }; draft?: LearningVisibleExitTicket; busy: boolean;
  onSave: (draft: LearningExitDraft) => void; onCancel: () => void;
  draftScope?:string;
  controlledValues?:ExitFormValues;onValuesChange?:(patch:Partial<ExitFormValues>)=>void;embedded?:boolean;pinnedInstructions?:ExitPinnedInstruction[];
}) {
  const t = useT();
  const owner=useTabDraftOwner();
  const [retainedValues,setValues]=useActorRouteState<ExitFormValues>(draftScope?owner.scope:null,JSON.stringify(["exit-ticket-form",draftScope]),()=>initialExitFormValues(draft,source));
  const values=controlledValues??retainedValues;
  const {versionId,page,question,opens,closes,instruction}=values;
  const update=(patch:Partial<ExitFormValues>)=>onValuesChange?onValuesChange(patch):setValues(current=>({...current,...patch}));
  const setPage=(page:number)=>update({page});
  const setQuestion=(question:string)=>update({question});
  const setOpens=(opens:LearningExitWallInput)=>update({opens});
  const setCloses=(closes:LearningExitWallInput)=>update({closes});
  const setInstruction=(instruction:string)=>update({instruction});
  const {versions,activeVersion,options,bound,reversed,valid}=exitDraftState(values,materials,instructions,zoneId,draft,pinnedInstructions);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!valid || busy) return;
    onSave(exitDraftPayload(values,materials,instructions,zoneId,draft,pinnedInstructions));
  }
  const fields=<>
    <label>{t("etx.13")}<select required value={versionId} onChange={event => {
      update({versionId:event.target.value,page:1,instruction:''});
    }}>
      <option value="">{t("etx.14")}</option>
      {versions.map(version => <option value={version.id} key={version.id}>{version.title} · {t("etx.38", { v: version.version_no })}</option>)}
    </select></label>
    <label>{t("etx.15")}<input type="number" min={1} max={activeVersion?.page_count ?? 1} required value={page}
      onChange={event => setPage(Number(event.target.value))} /></label>
    {source && versions.some(version => version.id === source.versionId) && <button type="button" onClick={() => {
      update({versionId:source.versionId,page:source.page,...(versionId!==source.versionId?{instruction:''}:{})});
    }}>{t("etx.16")}</button>}
    <label>{t("etx.17")}<textarea required maxLength={1000} rows={3} value={question}
      onChange={event => setQuestion(event.target.value)} /></label>
    <ExitWallField label={t("etx.18")} zoneId={zoneId} value={opens} onChange={setOpens} />
    <ExitWallField label={t("etx.19")} zoneId={zoneId} value={closes} onChange={setCloses} />
    {reversed && <p role="alert">{t("etx.12")}</p>}
    <label>{t("etx.20")}<select value={instruction} onChange={event => setInstruction(event.target.value)}>
      <option value="">{t("etx.21")}</option>
      {options.map(option => <option key={option.value} value={option.value}>{option.title} · {t("etx.39", { r: option.revision })}</option>)}
    </select></label>
    {instruction&&!bound&&<p role="alert">{t("etx.22")}</p>}
    <div className={styles.row}><button disabled={busy || !valid}>{t("etx.23")}</button>
      <button type="button" disabled={busy} onClick={onCancel}>{t("etx.24")}</button></div>
  </>;
  return embedded?<div className={styles.stack}>{fields}</div>:<form onSubmit={submit} className={styles.stack}><fieldset disabled={busy} className={styles.stack}>{fields}</fieldset></form>;
}

export function SessionExitTickets({ actorId, sessionId, materials, instructions, zoneId, canManage, source, refresh, onRows, onSelect }: {
  actorId: string; sessionId: string; materials: LearningMaterial[]; instructions: ReadingInstruction[]; zoneId: string;
  canManage: boolean; source?: { versionId: string; page: number }; refresh: number;
  onRows: (actorId: string, sessionId: string, tickets: LearningExitTicket[]) => void; onSelect: (id: string) => void;
}) {
  const t = useT();
  const [rows, setRows] = useState<LearningExitTicket[] | null>(null);
  const owner=useTabDraftOwner();
  const draftKey=JSON.stringify(["session-exit-draft",actorId,sessionId]);
  const readScope=JSON.stringify([owner.scope,actorId,sessionId]);
  const [rowsScope,setRowsScope]=useState<string>();
  const scopedRows=rowsScope===readScope?rows:null;
  const [creating,setCreating]=useActorRouteState(owner.scope,draftKey+":creating",false);
  const [busy,setBusy]=useActorRouteState(owner.scope,draftKey+":busy",false);
  const [error,setError]=useActorRouteState(owner.scope,draftKey+":error","");
  const [formRevision,setFormRevision]=useActorRouteState(owner.scope,draftKey+":form",0);
  const [readRevision,setReadRevision]=useActorRouteState(owner.scope,draftKey+":reads",0);
  const [readError, setReadError] = useState("");
  const alive = useRef(false);
  const listGeneration = useRef(0);
  const [attempts,setAttempts]=useActorRouteState<Record<string,string>>(owner.scope,draftKey+":attempts",()=>({}));
  const currentScope=useRef("");currentScope.current=JSON.stringify([owner.scope,actorId,sessionId]);
  const path = `/sessions/${sessionId}/exit-tickets`;

  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    setRowsScope(undefined);setReadError('');
    const load = () => {
      const generation = ++listGeneration.current;
      void gateway.list<LearningExitTicket>(path, controller.signal, { "X-Campus-Reader-Actor": actorId }).then(tickets => {
        if (controller.signal.aborted || generation !== listGeneration.current) return;
        setReadError(""); setRows(tickets);setRowsScope(readScope);onRows(actorId, sessionId, tickets);
      }).catch(caught => {
        if (controller.signal.aborted || generation !== listGeneration.current) return;
        setReadError(caught instanceof Error ? caught.message : t("etx.25"));
        setRows([]);setRowsScope(readScope);onRows(actorId, sessionId, []);
      });
    };
    load();
    window.addEventListener("focus", load);
    const timer = window.setInterval(load, 30000);
    return () => { controller.abort(); window.removeEventListener("focus", load); window.clearInterval(timer); };
  }, [actorId, onRows, path, refresh, sessionId,readRevision,readScope]);

  async function create(draft: LearningExitDraft) {
    if(busy)return;
    const operationScope=currentScope.current;
    setBusy(true); setError("");
    const payload = JSON.stringify(draft);
    const requestKey=attempts[payload]??crypto.randomUUID();
    setAttempts(current=>({...current,[payload]:requestKey}));
    try {
      const ticket = await gateway.write<LearningExitTicket>(path, draft, "POST", requestKey, { "X-Campus-Reader-Actor": actorId });
      setAttempts(current=>{if(current[payload]!==requestKey)return current;const {[payload]:saved,...remaining}=current;return remaining;});
      setCreating(false);setFormRevision(value=>value+1);
      if (!alive.current||currentScope.current!==operationScope){setReadRevision(value=>value+1);return;}
      ++listGeneration.current;
      const next = [ticket, ...(scopedRows ?? []).filter(item => item.id !== ticket.id)];
      setRows(next);setRowsScope(readScope);onRows(actorId, sessionId, next); onSelect(ticket.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("etx.26"));
    } finally {
      setBusy(false);
    }
  }

  if(owner.enabled&&!owner.scope)return <p role="status">{t("etx.27")}</p>;
  return <section className={styles.stack} aria-label={t("etx.28")}>
    <h3 id="learning-exit-tickets-heading" tabIndex={-1}>{t("etx.29")}</h3>
    {readError && <p role="alert">{readError}</p>}
    {scopedRows === null && <p role="status">{t("etx.30")}</p>}
    {!readError && scopedRows?.length === 0 && <p>{t("etx.31")}</p>}
    {scopedRows && scopedRows.length > 0 && <ul className={styles.list}>{scopedRows.map(ticket => <li key={ticket.id} className={styles.material}>
      <p>{t(labels[ticket.state])}{ticket.state !== "SOURCE_UNAVAILABLE" && ` · ${t("etx.35", { p: ticket.page_no })}`}</p>
      <button type="button" onClick={() => onSelect(ticket.id)}>
        {ticket.state === "SOURCE_UNAVAILABLE" ? t("etx.32") : ticket.question}
      </button>
    </li>)}</ul>}
    {canManage && !creating && <button type="button" onClick={() => setCreating(true)}>{t("etx.33")}</button>}
    {canManage && creating && <ExitTicketDraftForm materials={materials} instructions={instructions} zoneId={zoneId}
      source={source} busy={busy} draftScope={JSON.stringify([actorId,sessionId,formRevision])} onSave={draft => void create(draft)} onCancel={() => setCreating(false)} />}
    {error && <p role="alert">{error}</p>}
  </section>;
}

export function ExitTicketStatus({ ticket }: { ticket: LearningExitTicket }) {
  const t = useT();
  return <p role="status">{t(labels[ticket.state])}</p>;
}

