"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { AccessibleDialog } from "../../components/shared/AccessibleDialog";
import { LearningGateway, type LearningPreview } from "../../lib/data/api/learning-gateway";
import type { ReaderAnchor, ReaderAnnotation, ReaderSelection } from "./reader/LearningPdfReader";
import styles from "./learning.module.css";
import { useActorRouteState, useTabDraftOwner } from "../chat/route-drafts";

type Note = ReaderAnnotation & { body: string; revision: number; status: string };
type Scope = "CLASS" | "PRIVATE_TO_INSTRUCTORS";
type Reply = { id: string; body: string; author_name: string; endorsed: boolean; visibility?: Scope };
type Question = { id: string; page_no: number; body: string; author_name: string; author_id: string; visibility: Scope; replies: Reply[]; revision: number };
type ScopeChange = { to: Scope; body: string; page_no: number; version_id: string; anchor: ReaderAnchor };
type SharingPreview = LearningPreview & { sharing: ScopeChange };
const message = (e: unknown) => e instanceof Error ? e.message : "Chưa lưu được trao đổi.";
type TextDraft = { text: string };
type NoteEditor = { active: Note | null; drafts: Record<string, TextDraft> };
type QuestionDraft = { text: string; visibility: Scope };
type PendingWrite = { fingerprint: string; key: string };
const emptyQuestion: QuestionDraft = { text: "", visibility: "PRIVATE_TO_INSTRUCTORS" };

export function LearningDiscussion({ versionId, renditionId, selection, canManage, actorId, canShareNotes, onSource, onAnnotationsChange }: {
  versionId: string; renditionId?: string | null; selection: ReaderSelection | null; canManage: boolean;
  actorId?: string;
  canShareNotes?: boolean;
  onSource?: (page: number) => void;
  onAnnotationsChange: (notes: ReaderAnnotation[]) => void;
}) {
  const api = useMemo(() => new LearningGateway(undefined, actorId), [actorId]);
  const owner = useTabDraftOwner();
  const draftKey = JSON.stringify(["learning-discussion", actorId, versionId, renditionId || null]);
  const [notes,setNotes]=useState<Note[]>([]),[questions,setQuestions]=useState<Question[]>([]);
  const [error,setError]=useActorRouteState(owner.scope,draftKey+":error","");
  const [notice,setNotice]=useActorRouteState(owner.scope,draftKey+":notice","");
  const [busy,setBusy]=useActorRouteState(owner.scope,draftKey+":busy",false);
  const [editor,setEditor]=useActorRouteState<NoteEditor>(owner.scope,draftKey+":notes",()=>({active:null,drafts:{}}));
  const editing = editor.active;
  const noteKey = editing?.id || "new";
  const setEditing = (note: Note | null) => setEditor(old => ({ ...old, active: note }));
  const [questionDraft,setQuestionDraft]=useActorRouteState<QuestionDraft>(owner.scope,draftKey+":question",emptyQuestion);
  const [replyDrafts,setReplyDrafts]=useActorRouteState<Record<string,TextDraft>>(owner.scope,draftKey+":replies",()=>({}));
  const [sharing,setSharing]=useActorRouteState<{id:string; revision:number; preview:SharingPreview; kind:"note"|"question"}|null>(owner.scope,draftKey+":sharing",null);
  const [confirmed,setConfirmed]=useActorRouteState(owner.scope,draftKey+":confirmed",false);
  const [readRevision,setReadRevision]=useActorRouteState(owner.scope,draftKey+":revision",0);
  const [writeKeys,setWriteKeys]=useActorRouteState<Record<string,PendingWrite>>(owner.scope,draftKey+":write-keys",()=>({}));
  const scopeKey=`${actorId || ""}:${versionId}`;
  const currentVersion=useRef(scopeKey);currentVersion.current=scopeKey;
  const mounted=useRef(true);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  async function load(signal?: AbortSignal) {
    const [items,threads]=await Promise.all([api.list<Note>(`/me/annotations?version_id=${versionId}`,signal),api.list<Question>(`/versions/${versionId}/questions`,signal)]);
    if(!signal?.aborted&&currentVersion.current===scopeKey) {setNotes(items);setQuestions(threads);onAnnotationsChange(items.filter(item=>item.status!=="ARCHIVED"));}
  }
  const lastScope = useRef(`${actorId || ""}:${versionId}`);
  async function writeDraft(path: string, payload: unknown, method = "POST") {
    const fingerprint = JSON.stringify([path, method, payload]);
    const previous = writeKeys[path];
    const pending = previous?.fingerprint === fingerprint ? previous : { fingerprint, key: crypto.randomUUID() };
    setWriteKeys(current => ({ ...current, [path]: pending }));
    const value = await api.write(path, payload, method, pending.key);
    setWriteKeys(current => { if (current[path] !== pending) return current; const { [path]: saved, ...remaining } = current; return remaining; });
    return value;
  }
  useEffect(()=>{const controller=new AbortController();const scope=`${actorId || ""}:${versionId}`;if(lastScope.current!==scope){setNotes([]);setQuestions([]);if(!owner.enabled||!owner.scope){setEditor({active:null,drafts:{}});setQuestionDraft(emptyQuestion);setReplyDrafts({});setSharing(null);setConfirmed(false);setError("");}lastScope.current=scope;}void load(controller.signal).catch(e=>{if(!controller.signal.aborted)setError(message(e));});return()=>controller.abort();},[actorId,versionId,readRevision]);
  async function run(work:()=>Promise<void>) {if(busy)return;setBusy(true);setError("");setNotice("");try{await work();if(mounted.current&&currentVersion.current===scopeKey)await load();}catch(e){setError(message(e));}finally{setBusy(false);if(!mounted.current||currentVersion.current!==scopeKey)setReadRevision(value=>value+1);}}
  function saveNote(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();const form=event.currentTarget;const body=String(new FormData(form).get("body")||"").trim();
    const submitted = editor.drafts[noteKey];
    if(!editing&&(!selection||selection.version_id!==versionId)){setError("Chọn đoạn văn, vùng hoặc trang bằng công cụ ghi chú trong trình đọc trước.");return;}
    void run(async()=>{if(editing)await writeDraft(`/me/annotations/${editing.id}`,{body,revision:editing.revision},"PATCH");else await writeDraft("/me/annotations",{version_id:versionId,...(renditionId?{rendition_id:renditionId}:{}),page_no:selection!.page_no,anchor:selection!.anchor,body});setEditor(current=>{if(current.drafts[noteKey]!==submitted)return current;const {[noteKey]:saved,...remaining}=current.drafts;return {active:current.active===editing?null:current.active,drafts:remaining};});setNotice("Đã lưu ghi chú riêng.");});
  }
  function ask(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();const form=event.currentTarget;const data=new FormData(form);
    if(!selection||selection.version_id!==versionId){setError("Chọn đoạn văn, vùng hoặc trang để gắn câu hỏi với đúng vị trí.");return;}
    const submitted=questionDraft;
    void run(async()=>{await writeDraft(`/versions/${versionId}/questions`,{...(renditionId?{rendition_id:renditionId}:{}),page_no:selection.page_no,anchor:selection.anchor,body:String(data.get("body")||"").trim(),visibility:String(data.get("visibility")||"PRIVATE_TO_INSTRUCTORS")});setQuestionDraft(current=>current===submitted?emptyQuestion:current);setNotice("Đã gửi câu hỏi theo phạm vi chia sẻ bạn chọn.");});
  }
  async function previewSharing(question:Question) {
    const visibility:Scope=question.visibility==="CLASS"?"PRIVATE_TO_INSTRUCTORS":"CLASS";
    const preview=await api.write<SharingPreview>("/action-previews",{action:"question-update",target_id:question.id,payload:{visibility,revision:question.revision}});
    if(currentVersion.current!==scopeKey)return;
    if(preview.sharing?.version_id!==versionId||preview.sharing.to!==visibility)throw new Error("Không thể xác minh nội dung xem trước.");
    setConfirmed(false);
    setSharing({id:question.id,revision:question.revision,preview,kind:"question"});
  }
  async function previewNoteSharing(note: Note) {
    const preview = await api.write<SharingPreview>("/action-previews", {
      action: "annotation-share", target_id: note.id, payload: { revision: note.revision },
    });
    if (currentVersion.current !== scopeKey) return;
    if (preview.sharing?.version_id !== versionId || preview.sharing.to !== "PRIVATE_TO_INSTRUCTORS") {
      throw new Error("Không thể xác minh nội dung xem trước.");
    }
    setConfirmed(false);
    setSharing({id:note.id,revision:note.revision,preview,kind:"note"});
  }
  async function applySharing() {
    if(!sharing||!confirmed)return;
    const {id,revision,preview,kind}=sharing;
    setSharing(null);
    setConfirmed(false);
    if (kind === "note") {
      await api.write(`/me/annotations/${id}/share`, {revision,preview_id:preview.preview_id,confirmation_token:preview.confirmation_token},
        "POST", `learning-note:${preview.preview_id}`);
      setNotice("Đã gửi một bản sao cho giảng viên. Ghi chú gốc vẫn là của riêng bạn.");
      return;
    }
    await api.write(`/questions/${id}`,{visibility:preview.sharing.to,revision,preview_id:preview.preview_id,confirmation_token:preview.confirmation_token},"PATCH",`learning-question:${preview.preview_id}`);
    setNotice(preview.sharing.to==="CLASS"?"Đã chia sẻ câu hỏi với lớp. Các phản hồi riêng vẫn được giữ riêng.":"Đã chuyển câu hỏi về phạm vi riêng với giảng viên.");
  }
  if (owner.enabled && !owner.scope) return <p role="status">Đang kiểm tra tài khoản trước khi mở nháp trao đổi…</p>;
  return <section className={`${styles.panel} ${styles.stack}`} aria-label="Ghi chú và hỏi đáp tài liệu">
    <div className={styles.row}><h2>Ghi chú và hỏi đáp</h2><button disabled={busy} onClick={()=>void run(async()=>{})}>Tải lại trao đổi</button></div>
    {error&&<p role="alert" className={`${styles.alert} ${styles.error}`}>{error}</p>}{notice&&<p role="status">{notice}</p>}
    <p>{selection?`Đang chọn nội dung ở trang ${selection.page_no}.` : "Dùng công cụ ghi chú trong trình đọc để chọn đoạn văn, vùng hoặc cả trang."}</p>
    <details open><summary>Ghi chú riêng của bạn</summary><p className={styles.muted}>Giảng viên và sinh viên khác không xem được ghi chú riêng này.</p>
      <form className={styles.form} key={editing?.id||"new-note"} onSubmit={saveNote}><label>{editing?"Sửa ghi chú":"Nội dung ghi chú"}<textarea name="body" value={editor.drafts[noteKey]?.text??editing?.body??""} onChange={event=>{const text=event.target.value;setEditor(current=>({...current,drafts:{...current.drafts,[noteKey]:{text}}}));}} required maxLength={8000}/></label><button disabled={busy||(!selection&&!editing)}>Lưu ghi chú riêng</button>{editing&&<button type="button" onClick={()=>setEditing(null)}>Hủy chỉnh sửa</button>}</form>
      {!notes.length&&<p>Chưa có ghi chú riêng ở phiên bản này.</p>}
      <ul className={styles.list}>{notes.filter(note=>note.status!=="ARCHIVED").map(note=><li key={note.id} className={styles.material}><strong>Trang {note.page_no}</strong><p style={{whiteSpace:"pre-wrap"}}>{note.body}</p><div className={styles.row}><button disabled={busy} onClick={()=>setEditing(note)}>Sửa ghi chú</button><button disabled={busy} onClick={()=>void run(async()=>{await api.write(`/me/annotations/${note.id}`,{status:"ARCHIVED",revision:note.revision},"PATCH");})}>Lưu trữ ghi chú</button>{canShareNotes && <button disabled={busy} onClick={()=>void run(()=>previewNoteSharing(note))}>Xem trước khi gửi ghi chú</button>}</div></li>)}</ul>
    </details>
    <details><summary>Đặt câu hỏi tại vị trí đang chọn</summary><form className={styles.form} onSubmit={ask}><label>Câu hỏi<textarea name="body" value={questionDraft.text} onChange={event=>{const text=event.target.value;setQuestionDraft(current=>({...current,text}));}} required maxLength={8000}/></label><label>Ai được xem<select aria-label="Ai được xem" name="visibility" value={questionDraft.visibility} onChange={event=>{const visibility=event.target.value as Scope;setQuestionDraft(current=>({...current,visibility}));}}><option value="PRIVATE_TO_INSTRUCTORS">Chỉ tôi và giảng viên của lớp</option><option value="CLASS">Cả lớp</option></select></label><button disabled={busy||!selection}>Gửi câu hỏi</button></form></details>
    {!questions.length&&<p>Chưa có câu hỏi được phép xem.</p>}
    <ul className={styles.list}>{questions.map(question=><li className={styles.material} key={question.id}>
      <h3>Trang {question.page_no} · {question.author_name||"Thành viên lớp"}</h3>
      <p className={styles.muted}>{question.visibility==="CLASS"?"Chia sẻ với lớp":"Riêng với giảng viên"}</p>
      <p style={{whiteSpace:"pre-wrap"}}>{question.body}</p>
      <div className={styles.row}>
        {onSource&&<button disabled={busy} onClick={()=>onSource(question.page_no)}>Mở trang {question.page_no} của câu hỏi</button>}
        {actorId&&actorId===question.author_id&&<button disabled={busy} onClick={()=>void run(()=>previewSharing(question))}>{question.visibility==="CLASS"?"Đổi sang câu hỏi riêng":"Xem trước khi chia sẻ với lớp"}</button>}
      </div>
      <ul>{question.replies?.map(reply=><li key={reply.id}>
        <strong>{reply.author_name||"Thành viên lớp"}</strong>
        {reply.visibility==="PRIVATE_TO_INSTRUCTORS"&&question.visibility==="CLASS"&&<span> · Phản hồi riêng</span>}
        {reply.endorsed&&<span> · Được giảng viên xác nhận</span>}
        <p style={{whiteSpace:"pre-wrap"}}>{reply.body}</p>
        {canManage&&!reply.endorsed&&<button disabled={busy} onClick={()=>void run(async()=>{await api.write(`/replies/${reply.id}/endorse`,{});})}>Xác nhận câu trả lời</button>}
      </li>)}</ul>
      <form className={styles.form} onSubmit={event=>{
        event.preventDefault();const form=event.currentTarget;const body=String(new FormData(form).get("body")||"").trim();
        const submitted=replyDrafts[question.id];
        void run(async()=>{await writeDraft(`/questions/${question.id}/replies`,{body,question_revision:question.revision});setReplyDrafts(current=>current[question.id]===submitted?{...current,[question.id]:{text:""}}:current);});
      }}>
        <label>Trả lời<textarea name="body" value={replyDrafts[question.id]?.text??""} onChange={event=>{const text=event.target.value;setReplyDrafts(current=>({...current,[question.id]:{text}}));}} required maxLength={5000}/></label>
        <p className={styles.muted}>{question.visibility==="CLASS"?"Cả lớp sẽ xem được câu trả lời.":"Chỉ người hỏi và giảng viên của lớp xem được câu trả lời."}</p>
        <button disabled={busy}>Gửi trả lời</button>
      </form>
    </li>)}</ul>
    <AccessibleDialog open={!!sharing} onClose={()=>setSharing(null)} preventClose={busy} labelledBy="learning-question-sharing-title" className={styles.dialog}>
      <h2 id="learning-question-sharing-title">{sharing?.kind === "note" ? "Gửi bản sao ghi chú cho giảng viên" : "Xác nhận phạm vi câu hỏi"}</h2>
      {sharing&&<>
        <p>Trang {sharing.preview.sharing.page_no} · {sharing.kind === "note" ? "Chỉ bạn và giảng viên hiện tại của lớp xem được bản sao trong mục hỏi đáp. Ghi chú gốc vẫn riêng tư." : sharing.preview.sharing.to==="CLASS"?"Thành viên của lớp có quyền mở bài sẽ thấy câu hỏi sau đây. Phản hồi riêng sẽ vẫn được giữ riêng.":"Chỉ bạn và giảng viên hiện tại của lớp sẽ xem được cuộc trao đổi."}</p>
        <blockquote style={{whiteSpace:"pre-wrap"}}>{sharing.preview.sharing.body}</blockquote>
        {sharing.preview.sharing.anchor.text_quote?.exact&&<p>Đoạn trong bài giảng: {sharing.preview.sharing.anchor.text_quote.exact}</p>}
        <label><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/> Tôi đã kiểm tra nội dung và người được xem.</label>
        <div className={styles.row}><button disabled={busy} onClick={()=>setSharing(null)}>Quay lại</button><button disabled={busy||!confirmed} onClick={()=>void run(applySharing)}>{sharing.kind === "note" ? "Xác nhận gửi bản sao" : "Xác nhận đổi phạm vi"}</button></div>
      </>}
    </AccessibleDialog>
  </section>;
}
