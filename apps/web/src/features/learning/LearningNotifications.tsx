"use client";
import { RefreshCw } from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";
import { useEffect,useMemo,useRef,useState } from "react";
import { LearningGateway } from "../../lib/data/api/learning-gateway";
import styles from "./learning.module.css";
type EventType = "MATERIAL_PUBLISHED" | "QUESTION_CREATED" | "QUESTION_REPLIED" | "QUESTION_SCOPE_CHANGED" | "REPLY_ENDORSED" | "PAGE_EXPLANATION_PUBLISHED" | "EXIT_TICKET_UPDATED" | "MATERIAL_QUARANTINED";
const descriptions:Record<EventType,string> = {
  MATERIAL_PUBLISHED:"Có phiên bản bài giảng được công bố",
  QUESTION_CREATED:"Có câu hỏi về bài giảng",
  QUESTION_REPLIED:"Câu hỏi của bạn có phản hồi",
  QUESTION_SCOPE_CHANGED:"Phạm vi một câu hỏi đã thay đổi",
  REPLY_ENDORSED:"Giảng viên đã xác nhận câu trả lời của bạn",
  PAGE_EXPLANATION_PUBLISHED:"Có lời giải chung cho buổi học",
  EXIT_TICKET_UPDATED:"Có cập nhật phiếu ra lớp",
  MATERIAL_QUARANTINED:"Một tệp bài giảng đã bị cách ly vì không vượt qua kiểm tra an toàn",
};
export interface LearningUpdate {id:string;title:string;version_id:string;material_id:string;offering_id?:string;session_id?:string|null;read_at:string|null;created_at:string;revision:number;event_type?:EventType;question_id?:string;page_no?:number;exit_ticket_id?:string}
export function LearningNotifications({onOpen,actorId}:{onOpen:(update:LearningUpdate)=>void;actorId?:string}){
  const api=useMemo(()=>new LearningGateway(undefined,actorId),[actorId]);
  const [items,setItems]=useState<LearningUpdate[]>([]),[error,setError]=useState("");
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false);
  const mounted=useRef(false),opening=useRef(false),request=useRef<AbortController|null>(null);
  async function reload(){
    if(!mounted.current)return;
    request.current?.abort();
    const controller=new AbortController();request.current=controller;setLoading(true);
    try{
      const rows=await api.list<LearningUpdate>("/me/notifications",controller.signal);
      if(mounted.current&&request.current===controller&&!controller.signal.aborted){setItems(rows);setError("");}
    }catch(e){
      if(mounted.current&&request.current===controller&&!controller.signal.aborted)setError(e instanceof Error?e.message:"Chưa tải lại được thông báo.");
    }finally{
      if(mounted.current&&request.current===controller)setLoading(false);
    }
  }
  useEffect(()=>{
    mounted.current=true;void reload();
    const interval=setInterval(()=>void reload(),30000);
    return()=>{mounted.current=false;request.current?.abort();request.current=null;clearInterval(interval);};
  },[api]);
  async function open(update:LearningUpdate){
    if(opening.current)return;
    opening.current=true;setBusy(true);setError("");
    try{
      if(!update.read_at)await api.write(`/me/notifications/${update.id}`,{read_at:new Date().toISOString(),revision:update.revision},"PATCH");
      if(!mounted.current)return;
      await reload();
      if(mounted.current)onOpen(update);
    }catch(e){
      if(mounted.current)setError(e instanceof Error?e.message:"Chưa mở được thông báo.");
    }finally{
      opening.current=false;if(mounted.current)setBusy(false);
    }
  }
  return <details className={styles.panel} aria-busy={loading||busy}><summary>Cập nhật học liệu · {loading?"Đang tải…":`${items.filter(item=>!item.read_at).length} chưa xem`}</summary>{error&&<p role="alert">{error}</p>}<IconButton label="Tải lại thông báo" disabled={busy} onClick={()=>void reload()} icon={<RefreshCw size={17} />} />{loading&&<p role="status">Đang tải thông báo…</p>}{!loading&&!error&&!items.length&&<p>Chưa có cập nhật học liệu được phép xem.</p>}<ul className={styles.list}>{items.map(item=><li key={item.id} className={styles.material}><strong>{item.title}</strong><p>{descriptions[item.event_type||"MATERIAL_PUBLISHED"]}{item.page_no && item.event_type !== "PAGE_EXPLANATION_PUBLISHED" && item.event_type !== "EXIT_TICKET_UPDATED" && ` · Trang ${item.page_no}`} · {new Date(item.created_at).toLocaleString("vi-VN")}</p><button disabled={busy} onClick={()=>void open(item)}>{item.event_type === "EXIT_TICKET_UPDATED" ? "Mở phiếu ra lớp" : item.event_type === "PAGE_EXPLANATION_PUBLISHED" ? "Mở nguồn lời giải chung" : item.question_id?"Mở trang câu hỏi":"Mở bản được công bố"}</button>{item.read_at&&<span> · Đã xem</span>}</li>)}</ul></details>;
}
