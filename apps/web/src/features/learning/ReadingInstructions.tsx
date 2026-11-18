"use client";
import { useEffect,useMemo,useRef,useState } from "react";
import { LearningGateway,type LearningExitTicket,type LearningMaterial } from "../../lib/data/api/learning-gateway";
import styles from "./learning.module.css";
import { useActorRouteState,useTabDraftOwner } from "../chat/route-drafts";
import {LearningMetadataForm} from './LearningMetadataForm';
type PageRange={start:number;end:number};
type InstructionRevision = {
  version_id: string; page_ranges: PageRange[]; purpose: string;
  timing: "BEFORE" | "DURING" | "AFTER"; questions: string[]; revision: number;
};
export type ReadingInstruction = InstructionRevision & { id: string; status?: string; seen_at?: string | null; history?: InstructionRevision[] };
const when = { BEFORE: "Trước buổi", DURING: "Trong buổi", AFTER: "Sau buổi" };
const pageLabel = ({ start, end }: PageRange) => start === end ? `${start}` : `${start}–${end}`;
const instructionValues=(row:ReadingInstruction)=>({version_id:row.version_id,ranges:row.page_ranges.map(pageLabel).join(', ').replaceAll('–','-'),purpose:row.purpose,timing:row.timing,questions:row.questions.join('\n')});
export function parseReadingRanges(text:string):PageRange[]{
  const ranges=text.split(",").map(part=>part.trim()).filter(Boolean).map(part=>{if(!/^\d+(?:\s*-\s*\d+)?$/.test(part))throw new Error("Nhập trang dạng 1-3, 5.");const [start,end]=part.split("-").map(Number);if(start<1||(end!==undefined&&end<start))throw new Error("Khoảng trang không hợp lệ.");return {start,end:end??start};});
  if(!ranges.length||ranges.length>30)throw new Error("Chọn từ 1 đến 30 khoảng trang.");return ranges;
}
export function ReadingInstructions({sessionId,materials,canManage,onOpen,actorId,onRows,exitTickets,onExitTicket}:{
  sessionId:string;materials:LearningMaterial[];canManage:boolean;onOpen:(versionId:string,page:number)=>void;
  actorId?:string;onRows?:(actorId:string,sessionId:string,rows:ReadingInstruction[])=>void;
  exitTickets?:LearningExitTicket[];onExitTicket?:(ticketId:string)=>void;
}){
  const api=useMemo(()=>new LearningGateway(undefined,actorId),[actorId]);
  const owner=useTabDraftOwner();
  const key=JSON.stringify(["reading-instructions",actorId,sessionId]);
  const readScope=JSON.stringify([owner.scope,key]);
  const [itemsScope,setItemsScope]=useState<string>();
  const [editor,setEditor]=useActorRouteState<{editing:ReadingInstruction|null;drafts:Record<string,Record<string,string>>;revision:number}>(owner.scope,key,()=>({editing:null,drafts:{},revision:0}));
  const editing=editor.editing,formKey=editing?.id||"new";
  const setEditing=(editing:ReadingInstruction|null)=>setEditor(current=>({...current,editing}));
  const [items,setItems]=useState<ReadingInstruction[]>([]),[error,setError]=useState("");
  const [busy,setBusy]=useActorRouteState(owner.scope,key+":busy",false);
  const [readRevision,setReadRevision]=useActorRouteState(owner.scope,key+":reads",0);
  const scope=useRef<AbortController | null>(null);
  const reload=async(signal=scope.current?.signal)=>{
    if (signal?.aborted) return;
    const rows=await api.list<ReadingInstruction>(`/sessions/${sessionId}/reading-instructions`,signal,actorId ? { "X-Campus-Reader-Actor": actorId } : undefined);
    if(!signal?.aborted){setItems(rows);setItemsScope(readScope);if(actorId)onRows?.(actorId,sessionId,rows);}
  };
  const lastScope=useRef(`${actorId||""}:${sessionId}`);
  useEffect(()=>{const controller=new AbortController();scope.current=controller;setItemsScope(undefined);const key=`${actorId||""}:${sessionId}`;if(lastScope.current!==key){setItems([]);if(!owner.enabled)setEditor({editing:null,drafts:{},revision:0});lastScope.current=key;}setError("");void reload(controller.signal).catch(e=>{if(!controller.signal.aborted){setItemsScope(undefined);setError(e instanceof Error?e.message:"Chưa đọc được chỉ dẫn.");}});return()=>controller.abort();},[actorId,sessionId,onRows,readRevision,readScope]);
  async function markSeen(item: ReadingInstruction) {
    setBusy(true);
    setError("");
    try {
      await api.write(`/reading-instructions/${item.id}/seen`, { revision: item.revision }, "PUT");
      await reload();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Chưa ghi nhận được chỉ dẫn đã xem.");
    } finally {
      setBusy(false);
    }
  }
  if(owner.enabled&&!owner.scope)return <p role="status">Đang kiểm tra tài khoản trước khi mở nháp chỉ dẫn…</p>;
  const visibleItems=itemsScope===readScope?items:[];
  const currentRow=visibleItems.find(item=>item.id===editing?.id)??editing;
  return <section className={styles.stack} aria-label="Chỉ dẫn đọc theo buổi"><h3>Đọc trước trong và sau buổi học</h3>{error&&<p role="alert">{error}</p>}
    {itemsScope!==readScope&&!error&&<p role="status">Đang đọc chỉ dẫn…</p>}
    {itemsScope===readScope&&!visibleItems.length && <p className={styles.muted}>Chưa có chỉ dẫn đọc.</p>}
    <ul className={styles.list}>{visibleItems.map(item => <li id={`learning-instruction-${item.id}`} tabIndex={-1} key={item.id} className={styles.material}>
      <strong>{when[item.timing]}</strong>
      <p>{item.purpose}</p>
      {item.questions?.length > 0 && <ul>{item.questions.map((question, index) => <li key={index}>{question}</li>)}</ul>}
      <div className={styles.row}>
        {item.page_ranges.map((range, index) => (
          <button key={index} onClick={() => onOpen(item.version_id, range.start)}>Mở trang {pageLabel(range)}</button>
        ))}
        {canManage ? <button disabled={busy} onClick={() => setEditing(item)}>Sửa chỉ dẫn</button>
          : item.seen_at ? <span>Đã đánh dấu xem</span>
          : <button disabled={busy} onClick={() => void markSeen(item)}>Đánh dấu đã xem</button>}
      </div>
      {onExitTicket && exitTickets?.map(ticket => ticket.state !== "SOURCE_UNAVAILABLE" && ticket.state !== "DRAFT" &&
        ticket.instruction?.id === item.id && <button key={ticket.id} type="button" onClick={() => onExitTicket(ticket.id)}>
          Mở phiếu ra lớp · Chỉ dẫn lần {ticket.instruction.revision}
        </button>)}
      {canManage && !!item.history?.length && <details>
        <summary>Lịch sử chỉnh sửa chỉ dẫn</summary>
        <ul>{item.history.map(revision => <li key={revision.revision}>
          <strong>Lần {revision.revision} · {when[revision.timing]} · Trang {revision.page_ranges.map(pageLabel).join(", ")}</strong>
          <p>{revision.purpose}</p>
          {revision.questions?.length > 0 && <ul>{revision.questions.map((question, index) => <li key={index}>{question}</li>)}</ul>}
        </li>)}</ul>
      </details>}
    </li>)}</ul>
    {canManage && <details open={!!editing || undefined}>
      <summary>{editing ? "Chỉnh sửa chỉ dẫn" : "Thêm chỉ dẫn đọc"}</summary>
      <LearningMetadataForm key={`${owner.scope??key}:${formKey}`} actorId={actorId??''} draftId={`reading-instruction:${sessionId}:${formKey}`} className={styles.stack} disabled={busy}
        initialValues={currentRow?instructionValues(currentRow):{version_id:'',ranges:'',purpose:'',timing:'BEFORE',questions:''}} basis={{revision:currentRow?.revision}}
        fieldLabels={{version_id:'Tài liệu',ranges:'Trang cần đọc',purpose:'Mục đích',timing:'Thời điểm',questions:'Câu hỏi tự kiểm tra mỗi dòng một câu'}}
        valueLabels={{timing:when,version_id:Object.fromEntries(materials.flatMap(material=>material.versions.map(version=>[version.id,`${material.title} · Phiên bản ${version.version_no}`])))}}
        toPayload={({values,basis})=>({version_id:values.version_id,page_ranges:parseReadingRanges(values.ranges),purpose:values.purpose.trim(),timing:values.timing,questions:values.questions.split('\n').map(value=>value.trim()).filter(Boolean),...(editing?{revision:basis.revision}:{})})}
        onSave={async(payload,requestKey)=>{
          const requestScope=scope.current;setBusy(true);setError('');
          try{await api.write(editing?`/reading-instructions/${editing.id}`:`/sessions/${sessionId}/reading-instructions`,payload,editing?'PATCH':'POST',requestKey);await reload(requestScope?.signal);}
          finally{setBusy(false);if(requestScope?.signal.aborted)setReadRevision(value=>value+1);}
        }}
        onRead={editing?async signal=>{
          const rows=await api.list<ReadingInstruction>(`/sessions/${sessionId}/reading-instructions`,signal,actorId?{'X-Campus-Reader-Actor':actorId}:undefined);
          const row=rows.find(item=>item.id===editing.id);
          if(!row||row.status==='SOURCE_UNAVAILABLE')throw new Error('Không còn đọc được chỉ dẫn để đối chiếu. Nháp vẫn được giữ.');
          return {values:instructionValues(row),basis:{revision:row.revision}};
        }:undefined}>
        {(values,change)=><>
        <div className={styles.form}>
        <label>Tài liệu<select aria-label="Tài liệu" name="version_id" value={values.version_id} onChange={event=>change('version_id',event.target.value)} required>
          <option value="">Chọn bản đã công bố</option>
          {materials.flatMap(material => material.versions.filter(version => version.publication_state === "PUBLISHED")
            .map(version => <option key={version.id} value={version.id}>{material.title} · Phiên bản {version.version_no}</option>))}
        </select></label>
        <label>Trang cần đọc<input name="ranges" required placeholder="1-3, 5" value={values.ranges} onChange={event=>change('ranges',event.target.value)} /></label>
        <label>Thời điểm<select aria-label="Thời điểm" name="timing" value={values.timing} onChange={event=>change('timing',event.target.value)}>
          {Object.entries(when).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        </div>
        <label>Mục đích<textarea aria-label="Mục đích" name="purpose" rows={4} required value={values.purpose} onChange={event=>change('purpose',event.target.value)} /></label>
        <label>Câu hỏi tự kiểm tra mỗi dòng một câu<textarea aria-label="Câu hỏi tự kiểm tra mỗi dòng một câu" name="questions" rows={4} value={values.questions} onChange={event=>change('questions',event.target.value)} /></label>
        <div className={styles.row}>
        <button disabled={busy}>Lưu chỉ dẫn</button>
        {editing && <button type="button" onClick={() => setEditing(null)}>Hủy chỉnh sửa</button>}
        </div>
        </>}
      </LearningMetadataForm>
    </details>}
  </section>;
}
