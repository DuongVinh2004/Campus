"use client";
import { useEffect,useMemo,useRef,useState,type FormEvent } from "react";
import { LearningGateway } from "../../lib/data/api/learning-gateway";
import type { ReaderSelection } from "./reader/LearningPdfReader";
import styles from "./learning.module.css";
import { useActorRouteState, useTabDraftOwner } from "../chat/route-drafts";
type Citation={version_id:string;material_id:string;offering_id:string;page_no:number;quote:string;source_sha256:string};
type Explanation={answer:string;questions:string[];citations:Citation[];scope:string};
export function LearningExplanation({versionId,selection,available,onSource,actorId}:{versionId:string;selection:ReaderSelection|null;available:boolean;onSource:(versionId:string,pageNo:number)=>void;actorId?:string}){
  const api=useMemo(()=>new LearningGateway(undefined,actorId),[actorId]);
  const owner=useTabDraftOwner();
  const initialQuestion="Giải thích nội dung được chọn và gợi ý câu hỏi để tôi tự kiểm tra.";
  const [question,setQuestion]=useActorRouteState(owner.scope,JSON.stringify(["learning-explanation",actorId,versionId]),initialQuestion);
  const [result,setResult]=useState<Explanation|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const generation=useRef(0);
  useEffect(()=>{generation.current++;setResult(null);setError("");setBusy(false);},[actorId,versionId,selection]);
  useEffect(()=>{if(!owner.enabled||!owner.scope)setQuestion(initialQuestion);},[actorId,versionId]);
  async function explain(event:FormEvent<HTMLFormElement>){event.preventDefault();if(!available||!selection||selection.version_id!==versionId)return;const requestGeneration=generation.current;setBusy(true);setError("");setResult(null);try{const question=String(new FormData(event.currentTarget).get("question")||"").trim();const value=await api.write<Explanation>(`/versions/${versionId}/explain`,{page_no:selection.page_no,question,quote:selection.anchor.text_quote?.exact?.slice(0,2000)||""});if(typeof value.answer!=="string"||!Array.isArray(value.citations)||value.citations.some(citation=>citation.version_id!==versionId||citation.page_no!==selection.page_no))throw new Error("Chưa xác minh được nguồn của câu trả lời.");if(generation.current===requestGeneration)setResult(value);}catch(e){if(generation.current===requestGeneration)setError(e instanceof Error?e.message:"Chưa giải thích được nội dung.");}finally{if(generation.current===requestGeneration)setBusy(false);}}
  return <section className={`${styles.panel} ${styles.stack}`} aria-label="Giải thích nội dung được chọn"><h3>Giải thích và tự kiểm tra</h3>
    {!available?<p>Hỗ trợ AI chưa sẵn sàng trong môi trường này. Bạn vẫn có thể đọc, ghi chú và hỏi giảng viên.</p>:<><p>{selection?`Giải thích trong phạm vi trang ${selection.page_no} của phiên bản đang đọc.`:"Chọn đoạn văn hoặc trang trong trình đọc trước khi đặt câu hỏi."}</p><form className={styles.form} onSubmit={explain}><label>Bạn cần hiểu điều gì<textarea name="question" required maxLength={2000} value={question} onChange={event=>setQuestion(event.target.value)}/></label><button disabled={busy||!selection}>Giải thích nội dung</button></form></>}
    {busy&&<p role="status">Đang đối chiếu trang nguồn và chuẩn bị giải thích…</p>}{error&&<p role="alert">{error}</p>}
    {result&&<><p style={{whiteSpace:"pre-wrap"}}>{result.answer}</p>{result.questions?.length>0&&<><h4>Câu hỏi tự kiểm tra</h4><ul>{result.questions.map((question,index)=><li key={index}>{question}</li>)}</ul></>}<h4>Nguồn trong bài giảng</h4><ul>{result.citations.map((citation,index)=><li key={index}><button onClick={()=>onSource(citation.version_id,citation.page_no)}>Mở trang {citation.page_no} của phiên bản này</button><blockquote>{citation.quote}</blockquote></li>)}</ul></>}
  </section>;
}
