"use client";

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
const labels: Record<LearningExitTicket["state"], string> = {
  DRAFT: "Bản nháp",
  SCHEDULED: "Chưa mở",
  OPEN: "Đang nhận bài",
  CLOSED: "Đã đóng",
  CANCELLED: "Đã hủy",
  SOURCE_UNAVAILABLE: "Nguồn học liệu không còn khả dụng",
};

export function ExitTicketTimes({ ticket }: { ticket: LearningVisibleExitTicket }) {
  const wall = (value: LearningExitWallTime) => <time dateTime={value.utc}>
    {value.local.replace("T", " ")} ({utcOffsetLabel(value.offset_minutes)})
  </time>;
  return <dl className={styles.exitTimes}>
    <div><dt>Múi giờ lớp</dt><dd>{ticket.zone_id}</dd></div>
    <div><dt>Mở</dt><dd>{wall(ticket.opens)}</dd></div>
    <div><dt>Đóng</dt><dd>{wall(ticket.closes)}</dd></div>
  </dl>;
}

export function ExitTicketPreviewDetails({ preview }: { preview: NonNullable<LearningPreview["exit_ticket"]> }) {
  return <div className={styles.stack}>
    <p>Trạng thái sau xác nhận · {labels[preview.state]}</p>
    {preview.state !== "SOURCE_UNAVAILABLE" && <>
      <p>Trang {preview.page_no} · {preview.question}</p>
      <ExitTicketTimes ticket={preview} />
    </>}
    <p>Tại lúc xem trước, thao tác ảnh hưởng {preview.students} sinh viên và {preview.submissions} bài đã nộp.</p>
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
  const errorId = useId();
  const candidates = timeCandidates(value.local, zoneId);
  const invalid = !!value.local && candidates.length === 0;
  return <div className={styles.stack}>
    <label>{label} ({zoneId})
      <input type="datetime-local" required step={60} value={value.local}
        aria-invalid={invalid || undefined} aria-describedby={invalid ? errorId : undefined}
        onChange={event => onChange({ local: event.target.value })} />
    </label>
    {invalid && <p id={errorId} role="alert">Giờ này không tồn tại trong múi giờ của lớp.</p>}
    {candidates.length > 1 && <label>Độ lệch UTC cho {label.toLowerCase()}
      <select required value={value.offset_minutes ?? ""} onChange={event => onChange({
        local: value.local, ...(event.target.value ? { offset_minutes: Number(event.target.value) } : {}),
      })}>
        <option value="">Chọn độ lệch cho giờ bị lặp</option>
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
    <label>Phiên bản nguồn<select required value={versionId} onChange={event => {
      update({versionId:event.target.value,page:1,instruction:''});
    }}>
      <option value="">Chọn phiên bản đã công bố</option>
      {versions.map(version => <option value={version.id} key={version.id}>{version.title} · Bản {version.version_no}</option>)}
    </select></label>
    <label>Trang nguồn<input type="number" min={1} max={activeVersion?.page_count ?? 1} required value={page}
      onChange={event => setPage(Number(event.target.value))} /></label>
    {source && versions.some(version => version.id === source.versionId) && <button type="button" onClick={() => {
      update({versionId:source.versionId,page:source.page,...(versionId!==source.versionId?{instruction:''}:{})});
    }}>Dùng trang đang đọc</button>}
    <label>Câu hỏi vận dụng<textarea required maxLength={1000} rows={3} value={question}
      onChange={event => setQuestion(event.target.value)} /></label>
    <ExitWallField label="Giờ mở" zoneId={zoneId} value={opens} onChange={setOpens} />
    <ExitWallField label="Giờ đóng" zoneId={zoneId} value={closes} onChange={setCloses} />
    {reversed && <p role="alert">Giờ đóng phải sau giờ mở.</p>}
    <label>Chỉ dẫn đọc gắn kèm<select value={instruction} onChange={event => setInstruction(event.target.value)}>
      <option value="">Không gắn chỉ dẫn đọc</option>
      {options.map(option => <option key={option.value} value={option.value}>{option.title} · Lần {option.revision}</option>)}
    </select></label>
    {instruction&&!bound&&<p role="alert">Chỉ dẫn đọc không còn phù hợp với nguồn đã chọn. Hãy kiểm tra lại; nháp vẫn được giữ.</p>}
    <div className={styles.row}><button disabled={busy || !valid}>Lưu bản nháp</button>
      <button type="button" disabled={busy} onClick={onCancel}>Quay lại</button></div>
  </>;
  return embedded?<div className={styles.stack}>{fields}</div>:<form onSubmit={submit} className={styles.stack}><fieldset disabled={busy} className={styles.stack}>{fields}</fieldset></form>;
}

export function SessionExitTickets({ actorId, sessionId, materials, instructions, zoneId, canManage, source, refresh, onRows, onSelect }: {
  actorId: string; sessionId: string; materials: LearningMaterial[]; instructions: ReadingInstruction[]; zoneId: string;
  canManage: boolean; source?: { versionId: string; page: number }; refresh: number;
  onRows: (actorId: string, sessionId: string, tickets: LearningExitTicket[]) => void; onSelect: (id: string) => void;
}) {
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
        setReadError(caught instanceof Error ? caught.message : "Chưa tải được phiếu ra lớp.");
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
      setError(caught instanceof Error ? caught.message : "Chưa tạo được phiếu.");
    } finally {
      setBusy(false);
    }
  }

  if(owner.enabled&&!owner.scope)return <p role="status">Đang kiểm tra tài khoản trước khi mở nháp phiếu…</p>;
  return <section className={styles.stack} aria-label="Phiếu ra lớp theo buổi">
    <h3 id="learning-exit-tickets-heading" tabIndex={-1}>Phiếu ra lớp</h3>
    {readError && <p role="alert">{readError}</p>}
    {scopedRows === null && <p role="status">Đang tải phiếu ra lớp…</p>}
    {!readError && scopedRows?.length === 0 && <p>Buổi này chưa có phiếu ra lớp.</p>}
    {scopedRows && scopedRows.length > 0 && <ul className={styles.list}>{scopedRows.map(ticket => <li key={ticket.id} className={styles.material}>
      <p>{labels[ticket.state]}{ticket.state !== "SOURCE_UNAVAILABLE" && ` · Trang ${ticket.page_no}`}</p>
      <button type="button" onClick={() => onSelect(ticket.id)}>
        {ticket.state === "SOURCE_UNAVAILABLE" ? "Xem phiếu đã mất nguồn" : ticket.question}
      </button>
    </li>)}</ul>}
    {canManage && !creating && <button type="button" onClick={() => setCreating(true)}>Tạo phiếu ra lớp</button>}
    {canManage && creating && <ExitTicketDraftForm materials={materials} instructions={instructions} zoneId={zoneId}
      source={source} busy={busy} draftScope={JSON.stringify([actorId,sessionId,formRevision])} onSave={draft => void create(draft)} onCancel={() => setCreating(false)} />}
    {error && <p role="alert">{error}</p>}
  </section>;
}

export function ExitTicketStatus({ ticket }: { ticket: LearningExitTicket }) {
  return <p role="status">{labels[ticket.state]}</p>;
}

