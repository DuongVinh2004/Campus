"use client";

import { LearningApiError, type LearningUploadAttempt, type LearningVersion } from "../../lib/data/api/learning-gateway";
import {useActorRouteState,useTabDraftOwner} from "../chat/route-drafts";
import {useRef} from 'react';
import styles from './learning.module.css';

export type UploadDraft={title:string;file?:File;targetId?:string;creating?:boolean;createKey:string;attempt:LearningUploadAttempt;controller?:AbortController;history?:LearningUploadAttempt[]};
const fileSize=(bytes:number)=>bytes>=1048576?`${(bytes/1048576).toFixed(1).replace('.',',')} MB`:bytes>=1024?`${Math.round(bytes/1024)} KB`:`${bytes} byte`;
const fresh=():UploadDraft=>({title:'',createKey:crypto.randomUUID(),attempt:{intentKey:crypto.randomUUID(),contentKey:crypto.randomUUID(),completeKey:crypto.randomUUID()}});

export function LearningUploadForm({actorId,draftId,existing,accept,pptxEnabled,maxBytes,disabled,onUpload,onAccepted,onCancelIntent}:{
  actorId:string;draftId:string;existing:boolean;accept:string;pptxEnabled:boolean;maxBytes:number;disabled:boolean;
  onUpload:(draft:UploadDraft,file:File,signal:AbortSignal,onIntent:(id:string)=>void)=>Promise<LearningVersion>;
  onAccepted:(version:LearningVersion)=>void;
  onCancelIntent:(id:string)=>Promise<{state:string}>;
}){
  const owner=useTabDraftOwner(),scope=JSON.stringify(['learning-upload',actorId,draftId]);
  const [draft,setDraft,readDraft]=useActorRouteState<UploadDraft|undefined>(owner.scope,scope+':draft',undefined);
  const [busy,setBusy,readBusy]=useActorRouteState(owner.scope,scope+':busy',false);
  const [error,setError]=useActorRouteState(owner.scope,scope+':error','');
  const [restart,setRestart]=useActorRouteState(owner.scope,scope+':restart',false);
  const fileInput=useRef<HTMLInputElement>(null);
  const inputKey=JSON.stringify([owner.scope,scope]),activeInputScope=useRef(inputKey);activeInputScope.current=inputKey;
  const locked=busy||disabled||!!draft?.creating||!!draft?.attempt.started;
  if(owner.enabled&&!owner.scope)return <p role="status">Đang kiểm tra tài khoản trước khi chọn tệp…</p>;
  return <form className={styles.stack} onSubmit={event=>{
    event.preventDefault();if(readBusy()||disabled)return;
    const submitted=readDraft(),selected=submitted?.file;
    if(!submitted||!selected||!selected.size||!(pptxEnabled?/\.(pdf|pptx)$/i:/\.pdf$/i).test(selected.name)){setError('Chọn tệp học liệu hợp lệ, không rỗng.');return;}
    if(selected.size>maxBytes){setError('Tệp vượt giới hạn dung lượng cho phép.');return;}
    const submittedInputKey=inputKey,controller=new AbortController();submitted.controller=controller;
    setBusy(true);setError('');setRestart(false);
    void Promise.resolve().then(()=>onUpload(submitted,selected,controller.signal,()=>setDraft(current=>current?{...current}:current)))
      .then(version=>{
        const picker=fileInput.current;if(activeInputScope.current===submittedInputKey&&picker&&picker.files?.[0]===selected)picker.value='';
        setDraft(current=>current?.file===submitted.file&&current?.attempt===submitted.attempt?undefined:current);onAccepted(version);
      })
      .catch(caught=>{
        setError(caught instanceof Error?caught.message:'Chưa xác định kết quả tải. Hãy kiểm tra và thử tiếp.');
        if(caught instanceof LearningApiError&&(['UPLOAD_ABORTED','UPLOAD_EXPIRED'].includes(caught.code)||[413,415,422].includes(caught.status)))setRestart(true);
      }).finally(()=>{submitted.controller=undefined;setBusy(false);});
  }}>
    <fieldset className={styles.form} style={{minWidth:0}} disabled={locked}>
      {!existing&&<label>Tiêu đề bài giảng<input name="title" required maxLength={200} disabled={!!draft?.targetId} value={draft?.title??''} onChange={event=>{const title=event.target.value;setDraft(current=>({...current??fresh(),title}));}}/></label>}
      <label>{pptxEnabled?'File PDF hoặc PPTX':'File PDF'}<input key={inputKey} ref={fileInput} type="file" name="file" accept={accept} required={!draft?.file} onChange={event=>{
        const file=event.target.files?.[0];if(file)setDraft(current=>({...current??fresh(),file}));
      }}/></label>
    </fieldset>
    {draft?.file&&<p>Tệp đang giữ trong tab: {draft.file.name} · {fileSize(draft.file.size)}{maxBytes>0?` (tối đa ${fileSize(maxBytes)})`:''}.</p>}
    {error&&<p role="alert">{error}</p>}
    <div className={styles.row}><button disabled={busy||disabled||restart}>{draft?.attempt.started||draft?.creating?'Kiểm tra và tiếp tục tải':existing?'Tải phiên bản':'Tải và lưu nháp'}</button>
      {busy&&<button type="button" onClick={()=>{
        draft?.controller?.abort();const id=draft?.attempt.intentId;
        if(id)void onCancelIntent(id).then(result=>{if(['ABORTED','EXPIRED'].includes(result.state))setRestart(true);}).catch(caught=>setError(caught instanceof Error?caught.message:'Chưa xác định kết quả hủy.'));
      }}>Hủy tải tệp</button>}
      {restart&&!busy&&<button type="button" onClick={()=>{
        setDraft(current=>current?{...fresh(),title:current.title,file:current.file,targetId:current.targetId,history:[...current.history??[],current.attempt]}:current);setRestart(false);setError('');
      }}>Bắt đầu lượt tải mới</button>}
    </div>
  </form>;
}
