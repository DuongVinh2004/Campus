"use client";

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
const message = (error: unknown) => error instanceof Error ? error.message : "Chưa thực hiện được thao tác phiếu ra lớp.";

function submissionTime(value: string, zoneId?: string) {
  return zoneId
    ? new Intl.DateTimeFormat("vi-VN", { timeZone: zoneId, dateStyle: "short", timeStyle: "short" }).format(new Date(value))
    : new Intl.DateTimeFormat("vi-VN", { timeZone: "UTC", dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function Receipt({ value, zoneId }: { value: LearningExitSubmission; zoneId?: string }) {
  return <section className={styles.exitReceipt} aria-label="Biên nhận bài nộp">
    <h4>Biên nhận bài nộp</h4>
    <p>Mã {value.receipt_id} · Lần {value.revision}</p>
    <time dateTime={value.submitted_at}>{submissionTime(value.submitted_at, zoneId)} ({zoneId ?? "UTC"})</time>
    <p className={styles.exitAnswer}>{value.answer}</p>
    {(value.history?.length ?? 0) > 1 && <details><summary>Lịch sử bài nộp của bạn</summary>
      <ul className={styles.list}>{value.history?.filter(item => item.revision !== value.revision).map(item => <li key={item.receipt_id}>
        <p>Lần {item.revision} · Mã {item.receipt_id}</p>
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
      setError(message(caught));
    }
  }, [actorId, clearScope, path, staff,currentReadScope]);

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    working.current = false; setBusy(false);
    setAttempt(current=>current?{...current,canRetry:false}:current);
    if(attempt)setNotice("Hãy kiểm tra lại biên nhận của lần gửi trước trước khi thử lại.");
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
    if (!signal || signal.aborted || working.current) {if(propagate)throw new Error('Chưa thể thực hiện; bản đang soạn vẫn được giữ.');return;}
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
        if(!propagate||denied(caught))setError(message(caught));
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
      if (signal.aborted) {if(propagate)throw new Error('Đã rời phiếu; bản đang soạn vẫn được giữ.');return;}
      setEditing(undefined); setExtension(undefined);setEditingOpen(false);setExtensionOpen(false);
      await readCurrent(signal);
      if (!signal.aborted) { setNotice("Đã cập nhật phiếu ra lớp."); onChange(); }
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
        setNotice(`Đã nhận bài lần ${saved.revision}.`);
      } catch (caught) {
        if (signal.aborted) return;
        if (uncertain(caught)) {
          setAttempt({ ...current, canRetry: false });
          setNotice("Chưa xác định máy chủ đã nhận bài. Hãy kiểm tra biên nhận trước khi thử lại.");
          return;
        }
        setAttempt(undefined);
        if (conflict(caught)) {
          await readCurrent(signal);
          if (!signal.aborted) {
            setNeedsChoice(true);
            setNotice("Bài nộp đã đổi trên thiết bị khác. Bản đang soạn vẫn còn trong tab này.");
          }
          return;
        }
        if (caught instanceof LearningApiError && caught.code === "TICKET_NOT_OPEN") {
          await readCurrent(signal);
          if (!signal.aborted) setNotice("Máy chủ chưa nhận lần gửi này. Bản đang soạn vẫn còn trong tab này.");
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
        setNotice(sameAnswer(saved) ? `Đã tìm thấy biên nhận lần ${saved.revision}.` : "Đã tìm thấy biên nhận trong lịch sử. Bài nộp hiện tại là một bản mới hơn.");
      } else if ((saved?.revision ?? 0) !== current.revision) {
        setAttempt(undefined); setNeedsChoice(observed.ticket.state === "OPEN");
        setNotice("Máy chủ có bản nộp khác. Bản đang soạn vẫn còn trong tab này.");
      } else if (observed.ticket.state === "OPEN") {
        setAttempt({ ...current, canRetry: true });
        setNotice("Chưa có biên nhận mới. Bạn có thể thử lại đúng lần gửi vừa rồi.");
      } else {
        setAttempt(undefined); setNeedsChoice(false);
        setNotice("Không có biên nhận cho lần gửi này và phiếu hiện không nhận bài. Bản đang soạn vẫn còn trong tab này.");
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
    if(!signal||signal.aborted||working.current)throw new Error('Chưa thể lưu bản rà bài; nháp vẫn được giữ.');
    working.current=true;++readGeneration.current;setBusy(true);setError('');setNotice('');
    try{
      await gateway.write(`${path}/review`,payload,'PUT',key,actorHeader(actorId),signal);
      if(signal.aborted)throw new Error('Đã rời phiếu; kiểm tra lại bản rà bài đã lưu trước khi thử lại.');
      const observed=await readCurrent(signal);
      if(!observed||signal.aborted)throw new Error('Chưa đọc lại được bản rà bài; nháp và khóa thử lại vẫn được giữ.');
      setNotice('Đã lưu bản rà bài riêng.');
    }finally{if(lifetime.current?.signal===signal){working.current=false;setBusy(false);}}
  }

  function publishReview() {
    void work(async signal => {
      await confirmWrite(`${path}/review`, { operation: "PUBLISH", revision: review?.revision ?? 0 },
        "exit-review-save", "Công bố lời giải chung của phiếu", "PUT");
      if (signal.aborted) return;
      await readCurrent(signal);
      if (!signal.aborted) setNotice("Đã công bố lời giải chung.");
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

  if(owner.enabled&&!owner.scope)return <p role="status">Đang kiểm tra tài khoản trước khi mở nháp phiếu…</p>;
  return <section className={`${styles.panel} ${styles.stack} ${styles.exitDetail}`} aria-labelledby={labelId}>
    <div className={styles.row}><h3 id={labelId} tabIndex={-1} ref={heading}>Phiếu ra lớp</h3>
      <button type="button" onClick={onClose}>Quay lại danh sách phiếu</button></div>
    {error && <p role="alert">{error}</p>}
    {visible&&notice && <p role="status">{notice}</p>}
    {!scopedTicket && !error && <p role="status">Đang tải phiếu…</p>}
    {scopedTicket && <ExitTicketStatus ticket={scopedTicket} />}
    {visible && <>
      <p className={styles.exitAnswer}>{visible.question}</p>
      <ExitTicketTimes ticket={visible} />
      <button type="button" onClick={() => onOpen(visible.version_id, visible.page_no)}>Mở trang nguồn {visible.page_no}</button>
      {linked && <section className={styles.stack} aria-label="Chỉ dẫn đọc gắn với phiếu">
        <h4>Chỉ dẫn đọc · Lần {linked.revision}</h4>
        <p>{linked.purpose}</p>
        {linked.page_ranges.map(range => <button key={`${range.start}:${range.end}`} type="button"
          onClick={() => onOpen(visible.version_id, range.start)}>
          Đọc trang {range.start === range.end ? range.start : `${range.start}–${range.end}`}
        </button>)}
        {currentInstruction && <a href={`#learning-instruction-${linked.id}`} onClick={() => document.getElementById(`learning-instruction-${linked.id}`)?.focus()}>
          Đến chỉ dẫn đọc trong buổi
        </a>}
      </section>}
    </>}
    {!staff && scopedTicket&&receipt && <Receipt value={receipt} zoneId={visible?.zone_id} />}
    {!staff && visible?.state === "CLOSED" && receipt === null && <p>Chưa nộp bài.</p>}
    {(editable || holdDraft) && <form className={styles.stack} onSubmit={event => {
      event.preventDefault();
      if (canSubmit) send({ answer: clean, revision: answerRevision ?? receipt?.revision ?? 0, key: crypto.randomUUID(), canRetry: false });
    }}>
      <label>Câu trả lời riêng<textarea rows={5} value={answer} readOnly={!editable || !!attempt || needsChoice} disabled={busy}
        aria-describedby={`${answerDescription} ${answerCounter}`} onChange={event => {
          if (draftAnswer === undefined) setAnswerRevision(receipt?.revision ?? 0);
          setDraftAnswer(event.target.value);
        }} /></label>
      <p id={answerDescription}>Chỉ bạn và giảng viên đang được phân công có thể xem bài nộp. Hãy trả lời bằng lời của bạn.</p>
      <p id={answerCounter} aria-live="polite">{answerLength}/{answerLimit} ký tự</p>
      {editable && <button disabled={!canSubmit}>{receipt ? "Nộp bản sửa" : "Nộp câu trả lời"}</button>}
    </form>}
    {visible&&!staff&&attempt && <div className={styles.row}>
      <button type="button" disabled={busy} onClick={() => checkAttempt(attempt)}>Kiểm tra biên nhận</button>
      {attempt.canRetry && editable && <button type="button" disabled={busy} onClick={() => send(attempt)}>Thử lại lần gửi</button>}
    </div>}
    {needsChoice && editable && <div className={styles.row}>
      <button type="button" onClick={() => { setDraftAnswer(undefined); setAnswerRevision(undefined); setNeedsChoice(false); setNotice(""); }}>Dùng bản đã nộp</button>
      <button type="button" onClick={() => { setAnswerRevision(receipt?.revision ?? 0); setNeedsChoice(false); setNotice(""); }}>Giữ bản đang soạn</button>
    </div>}
    {staff && canManage && visible?.state === "DRAFT" && <>
      {editing !== undefined&&editingOpen ? <ExitTicketEditForm key={`${currentReadScope}:edit`} actorId={actorId} materials={materials} instructions={instructions} draft={editing}
        source={readerSource} busy={busy} onSave={(payload,key)=>change(payload,undefined,true,key)} onCancel={() => setEditingOpen(false)} />
        : <div className={styles.row}>
          <button type="button" disabled={busy} onClick={() => {setEditing(current=>current??visible);setEditingOpen(true);}}>Sửa bản nháp</button>
          <button type="button" disabled={busy} onClick={() => change({ operation: "PUBLISH", revision: visible.revision }, "Công bố phiếu ra lớp")}>Xem trước công bố</button>
        </div>}
    </>}
    {staff && canManage && visible && (visible.state === "SCHEDULED" || visible.state === "OPEN") && (
      extension&&extensionOpen ? <LearningMetadataForm key={`${currentReadScope}:extension`} actorId={actorId} draftId={`exit-extension:${ticketId}`} className={styles.stack} disabled={busy}
        initialValues={{closes:JSON.stringify(extension.wall)}} basis={{revision:extension.revision,zoneId:visible.zone_id,minimumCloseUtc:visible.closes.utc}}
        fieldLabels={{closes:'Giờ đóng mới'}} renderValue={(_name,value)=>{const wall:LearningExitWallInput=JSON.parse(value);return wall.local.replace('T',' ')+(wall.offset_minutes!==undefined?` · UTC ${wall.offset_minutes/60>=0?'+':''}${wall.offset_minutes/60}`:'');}}
        toPayload={({values,basis})=>{
          const wall:LearningExitWallInput=JSON.parse(values.closes),instant=exitWallInstant(wall,String(basis.zoneId));
          if(!instant||Date.parse(instant)<=Math.max(Date.parse(visible.closes.utc),Date.parse(String(basis.minimumCloseUtc))))throw new Error('Giờ đóng mới phải sau hạn hiện tại.');
          return {operation:'EXTEND',revision:basis.revision,closes:exitWallPayload(wall,String(basis.zoneId))};
        }} onSave={payload=>change(payload,'Gia hạn phiếu ra lớp',true)}
        onRead={async signal=>{
          const current=await gateway.request<LearningExitTicket>(path,{signal,headers:actorHeader(actorId)});
          if(current.state!=='OPEN'&&current.state!=='SCHEDULED')throw new Error('Phiếu không còn được gia hạn. Nháp vẫn được giữ.');
          return {values:{closes:JSON.stringify({local:current.closes.local,offset_minutes:current.closes.offset_minutes})},basis:{revision:current.revision,zoneId:current.zone_id,minimumCloseUtc:current.closes.utc}};
        }}>{(values,update,basis)=>{
          const wall:LearningExitWallInput=JSON.parse(values.closes),proposedClose=exitWallInstant(wall,String(basis.zoneId));
          const canExtend=!!proposedClose&&Date.parse(proposedClose)>Math.max(Date.parse(visible.closes.utc),Date.parse(String(basis.minimumCloseUtc)));
          return <>
        <ExitWallField label="Giờ đóng mới" zoneId={String(basis.zoneId)} value={wall} onChange={value=>update('closes',JSON.stringify(value))} />
        {proposedClose && !canExtend && <p role="alert">Giờ đóng mới phải sau hạn hiện tại.</p>}
        <div className={styles.row}><button disabled={busy || !canExtend}>Xem trước gia hạn</button>
          <button type="button" disabled={busy} onClick={() => setExtensionOpen(false)}>Quay lại</button></div>
        </>;}}</LearningMetadataForm> : <button type="button" disabled={busy} onClick={() => {setExtension(current=>current??{
        wall: { local: visible.closes.local, offset_minutes: visible.closes.offset_minutes }, revision: visible.revision,
      });setExtensionOpen(true);}}>Gia hạn nhận bài</button>
    )}
    {staff && canManage && visible && visible.state !== "CANCELLED" && !(visible.state==='DRAFT'&&editing&&editingOpen) && !(['SCHEDULED','OPEN'].includes(visible.state)&&extension&&extensionOpen) &&
      <button type="button" disabled={busy} onClick={() => change({ operation: "CANCEL", revision: visible.revision }, "Hủy phiếu ra lớp")}>Xem trước hủy phiếu</button>}
    {visible?.state === "CLOSED" && staff && reviewReadable && <section className={styles.stack} aria-label="Rà bài ra lớp">
      <h4>Rà bài ra lớp</h4>
      <button type="button" disabled={busy} onClick={loadSubmissions}>{submissions ? "Tải lại bài nộp" : "Xem bài nộp"}</button>
      {submissions?.length === 0 && <p>Chưa có bài nộp.</p>}
      {!!submissions?.length && <ul className={styles.list}>{submissions.map(item => <li key={item.id}>
        <p>{item.student_name ?? item.student_id} · Lần {item.revision}</p><p className={styles.exitAnswer}>{item.answer}</p>
      </li>)}</ul>}
      {canManage && (reviewDraft ? <LearningMetadataForm key={`${currentReadScope}:review`} actorId={actorId} draftId={`exit-review:${ticketId}`} className={styles.stack} disabled={busy}
        initialValues={{topics:review?.topics??reviewDraft.topics,next_plan:review?.next_plan??reviewDraft.next_plan,explanation:review?.explanation??reviewDraft.explanation}} basis={{revision:review?.revision??reviewDraft.revision}}
        fieldLabels={{topics:'Chủ đề lỗi thường gặp',next_plan:'Kế hoạch buổi sau',explanation:'Lời giải chung'}}
        toPayload={({values,basis})=>({operation:'SAVE_DRAFT',...values,revision:basis.revision})} onSave={saveReview}
        onRead={async signal=>{
          const current=await gateway.request<LearningExitTicket>(path,{signal,headers:actorHeader(actorId)});
          if(current.state!=='CLOSED')throw new Error('Phiếu không còn ở trạng thái được rà bài. Nháp vẫn được giữ.');
          const {review:latest}=await gateway.request<{review:LearningExitReview|null}>(`${path}/review`,{signal,headers:actorHeader(actorId)});
          if(!latest)throw new Error('Chưa có bản rà bài trên máy chủ để đối chiếu. Nháp vẫn được giữ.');
          return {values:{topics:latest.topics??'',next_plan:latest.next_plan??'',explanation:latest.explanation??''},basis:{revision:latest.revision}};
        }}>{(values,change)=><>
        <label>Chủ đề lỗi thường gặp<textarea rows={4} maxLength={reviewLimit} value={values.topics}
          onChange={event => change('topics',event.target.value)} /></label>
        <label>Kế hoạch buổi sau<textarea rows={4} maxLength={reviewLimit} value={values.next_plan}
          onChange={event => change('next_plan',event.target.value)} /></label>
        <label>Lời giải chung<textarea rows={4} maxLength={reviewLimit} value={values.explanation}
          onChange={event => change('explanation',event.target.value)} /></label>
        <p>Chỉ nội dung lời giải chung được đưa vào bản xem trước công bố.</p>
        <div className={styles.row}><button disabled={busy}>Lưu bản rà bài</button>
          <button type="button" disabled={busy} onClick={() => setReviewDraft(undefined)}>Quay lại</button></div>
        </>}</LearningMetadataForm> : <>
        {review?.topics && <p className={styles.exitAnswer}>Chủ đề lỗi · {review.topics}</p>}
        {review?.next_plan && <p className={styles.exitAnswer}>Kế hoạch buổi sau · {review.next_plan}</p>}
        {review?.explanation && <p className={styles.exitAnswer}>Lời giải nháp · {review.explanation}</p>}
        <button type="button" disabled={busy} onClick={() => setReviewDraft({ revision: review?.revision ?? 0, topics: review?.topics ?? "",
          next_plan: review?.next_plan ?? "", explanation: review?.explanation ?? "" })}>Soạn bản rà bài</button>
      </>)}
      {canManage&&!!review?.explanation?.trim()&&review.explanation!==review.published?.explanation&&<>
        {reviewDraft&&<p>Bản xem trước công bố chỉ lấy lời giải đã lưu; phần đang soạn chưa được công bố.</p>}
        <button type="button" disabled={busy} onClick={publishReview}>Xem trước công bố lời giải</button>
      </>}
    </section>}
    {visible?.state === "CLOSED" && review?.published && <section className={styles.stack} aria-label="Lời giải chung">
      <h4>Lời giải chung</h4><p className={styles.exitAnswer}>{review.published.explanation}</p>
    </section>}
    <button type="button" disabled={busy} onClick={() => void work(async signal => { await readCurrent(signal); })}>Tải lại phiếu</button>
  </section>;
}
