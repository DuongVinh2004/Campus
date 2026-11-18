"use client";
import { useCallback,useEffect,useMemo,useRef,useState } from "react";
import { LearningGateway } from "../../lib/data/api/learning-gateway";
import styles from "./learning.module.css";
type Session={id:string;offering_id:string;version_id:string;host_id:string;page_no:number;sequence:number;status:"ACTIVE"|"ENDED";revision:number};
export type PresentationPosition={presentation_id:string;version_id:string;page_no:number;sequence:number;active:boolean};
export function LearningPresentation({offeringId,versionId,actorId,canManage,pageNo,onPresentation}:{offeringId:string;versionId:string;actorId:string;canManage:boolean;pageNo:number;onPresentation:(position:PresentationPosition|null)=>void}){
  const api=useMemo(()=>new LearningGateway(undefined,actorId),[actorId]);
  const [sessions,setSessions]=useState<Session[]>([]),[current,setCurrent]=useState<Session|null>(null),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const currentRef=useRef(current);currentRef.current=current;
  const sending=useRef(false),latestPage=useRef(pageNo);latestPage.current=pageNo;
  const discovery=useRef<AbortController|null>(null);
  const reload=useCallback(async()=>{
    discovery.current?.abort();
    const controller=new AbortController();
    discovery.current=controller;
    try{
      const rows=await api.list<Session>(`/offerings/${offeringId}/presentations`,controller.signal);
      if(!controller.signal.aborted)setSessions(rows.filter(row=>row.version_id===versionId&&row.status==="ACTIVE"));
    }catch(e){
      if(!controller.signal.aborted)setError(e instanceof Error?e.message:"Chưa tải được phiên trình bày.");
    }
  },[api,offeringId,versionId]);
  useEffect(()=>{
    const refresh=()=>{if(document.visibilityState==="visible")void reload();};
    void reload();
    const interval=setInterval(refresh,10000);
    window.addEventListener("focus",refresh);
    document.addEventListener("visibilitychange",refresh);
    return()=>{
      discovery.current?.abort();clearInterval(interval);
      window.removeEventListener("focus",refresh);document.removeEventListener("visibilitychange",refresh);
      onPresentation(null);
    };
  },[reload,onPresentation]);
  useEffect(()=>{onPresentation(current?{presentation_id:current.id,version_id:current.version_id,page_no:current.page_no,sequence:current.sequence,active:current.status==="ACTIVE"}:null);},[current,onPresentation]);
  useEffect(()=>{
    if (!current) return;
    const id = current.id;
    let active = true;
    let ended = current.status === "ENDED";
    const controller = new AbortController();
    const stream = !ended && typeof EventSource !== "undefined"
      ? new EventSource(`/v1/learning/presentations/${id}/events`, { withCredentials: true })
      : null;
    const update = (value: Session) => {
      if (!active || ended || value.id !== id || value.sequence < (currentRef.current?.sequence ?? 0)) return;
      ended = value.status === "ENDED";
      currentRef.current = value;
      setCurrent(value);
      if (ended) stream?.close();
    };
    const disconnect = (message: string) => {
      if (!active || ended || currentRef.current?.status === "ENDED") return;
      active = false;
      controller.abort();
      stream?.close();
      currentRef.current = null;
      setCurrent(null);
      setError(message);
    };
    const offline = () => disconnect("Mất kết nối phiên trình bày. Bạn đang tự đọc. Hãy chọn theo dõi lại khi kết nối trở lại.");
    stream?.addEventListener("position", event => {
      try { update(JSON.parse((event as MessageEvent).data)); }
      catch { setError("Dữ liệu đồng bộ trang chưa hợp lệ."); }
    });
    stream?.addEventListener("unavailable", () => disconnect("Phiên trình bày không còn được phép truy cập."));
    stream?.addEventListener("error", offline);
    window.addEventListener("offline", offline);
    const poll = setInterval(() => {
      if (active && !ended) void api.request<Session>(`/presentations/${id}`, { signal: controller.signal })
        .then(update).catch(offline);
    }, 5000);
    return () => {
      active = false;
      controller.abort();
      stream?.close();
      clearInterval(poll);
      window.removeEventListener("offline", offline);
    };
  },[current?.id]);
  useEffect(()=>{
    const timer=setTimeout(()=>{if(sending.current)return;sending.current=true;
      void (async () => {
        try {
          for (let attempt = 0; attempt < 20; attempt++) {
            const session = currentRef.current, desired = latestPage.current;
            if (!session || session.host_id !== actorId || session.status !== "ACTIVE" || session.page_no === desired) return;
            const updated = await api.write<Session>(`/presentations/${session.id}/position`, {page_no:desired,sequence:session.sequence});
            const selected = currentRef.current;
            if (selected?.id !== updated.id || selected.sequence > updated.sequence) return;
            currentRef.current = updated;
            setCurrent(updated);
          }
        } catch (error) {
          if (currentRef.current) setError(error instanceof Error ? error.message : "Chưa đồng bộ được trang giảng.");
        } finally {
          sending.current = false;
        }
      })();
    },150);return()=>clearTimeout(timer);
  },[pageNo,actorId]);
  async function start(){setBusy(true);setError("");try{const session=await api.write<Session>(`/offerings/${offeringId}/presentations`,{version_id:versionId});setCurrent(session);setSessions(previous=>[session,...previous.filter(item=>item.id!==session.id)]);}catch(e){setError(e instanceof Error?e.message:"Chưa bắt đầu được phiên.");}finally{setBusy(false);}}
  async function end(){if(!current)return;setBusy(true);try{const ended=await api.write<Session>(`/presentations/${current.id}/end`,{});currentRef.current=ended;setCurrent(ended);setSessions(previous=>previous.filter(item=>item.id!==current.id));}catch(e){setError(e instanceof Error?e.message:"Chưa kết thúc được phiên.");}finally{setBusy(false);}}
  return <section className={`${styles.panel} ${styles.stack}`} aria-label="Theo dõi trang giảng viên"><h3>Trang giảng viên đang trình bày</h3>{error&&<p role="alert">{error}</p>}<div className={styles.row}>
    {canManage&&<button disabled={busy} onClick={()=>void start()}>Bắt đầu trình bày tài liệu này</button>}
    <button onClick={()=>{setError("");void reload();}}>Tải lại phiên trình bày</button>
    {sessions.map((session,index)=><button key={session.id} aria-pressed={session.id===current?.id} onClick={()=>{setError("");setCurrent(session);}}>Chọn phiên trình bày {index+1} · trang {session.page_no}</button>)}
    {current&&<><p>{current.status==="ACTIVE"?`Đang trình bày trang ${current.page_no}. Chọn Theo giảng viên trong trình đọc để theo dõi.`:"Phiên trình bày đã kết thúc."}</p>{current.host_id===actorId&&current.status==="ACTIVE"&&<button disabled={busy} onClick={()=>void end()}>Kết thúc trình bày</button>}<button onClick={()=>setCurrent(null)}>Rời phiên trình bày</button></>}
    {!sessions.length&&!current&&<p>Chưa có phiên trình bày tài liệu này.</p>}
  </div></section>;
}
