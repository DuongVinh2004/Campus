"use client";

import { useT } from "../../lib/i18n";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BookOpen } from "lucide-react";
import { AppShell, type Role } from "../../components/AppShell";
import { AccessibleDialog } from "../../components/shared/AccessibleDialog";
import { LearningGateway, LearningApiError, type LearningCapabilities, type LearningExitTicket, type LearningMaterial, type LearningOcrAnchor, type LearningOffering, type LearningPreview, type LearningReaderMetadata, type LearningSession, type LearningVersionChangeSet } from "../../lib/data/api/learning-gateway";
import { LearningPdfReader, type ReaderState, type ReaderSelection, type ReaderAnnotation } from "./reader/LearningPdfReader";
import { LearningDiscussion } from "./LearningDiscussion";
import { ReadingInstructions, type ReadingInstruction } from "./ReadingInstructions";
import { LearningPresentation,type PresentationPosition } from "./LearningPresentation";
import { LearningNotifications,type LearningUpdate } from "./LearningNotifications";
import { LearningExplanation } from "./LearningExplanation";
import { SessionPageFeedback, StudentPageFeedback } from "./PageFeedback";
import { PageExplanations, explanationLabels } from "./PageExplanations";
import { IdeaCards, IdeaShareSummary } from "./IdeaCards";
import type { LearningIdeaSource as IdeaSource } from "../../lib/data/api/learning-gateway";
import { ChangeDetails, VersionChangeBanner, VersionChangeEditor, olderPublishedVersions } from "./VersionChanges";
import { ExitTicketDetail } from "./ExitTicketDetail";
import { ExitTicketPreviewDetails, SessionExitTickets } from "./ExitTickets";
import { SessionPracticeSets } from "./PracticeSets";
import { AccessibleText, OcrReleasePreview } from "./AccessibleText";
import { CAMPUS_TIMEZONE, classDateTime, classDateTimeToUtc, classTimeZone } from "./learning-time";
import styles from "./learning.module.css";
import { LearningSessionNotice, PreservedActivity, useLearningSession } from "./learning-session";
import { LearningMetadataForm } from "./LearningMetadataForm";
import {LearningUploadForm,type UploadDraft} from './LearningUploadForm';
import type {LearningVersion} from '../../lib/data/api/learning-gateway';

type Catalog = { id: string; name?: string; code?: string; title?: string; display_name?: string; subject_id?: string; user_id?: string; role?: string; status?: string; revision?: number };
type Bookmark = { id: string; page_no: number; label: string };
type ReaderSync = {
  actorId: string;
  revision: number;
  pending?: ReaderState;
  saving?: Promise<boolean>;
  timer?: ReturnType<typeof setTimeout>;
  conflict?: boolean;
};
type ReaderLink = Pick<LearningUpdate,"version_id"|"offering_id"|"session_id"|"page_no"> & {anchor_id?:string};
type PendingReaderLink = ReaderLink & {sourceSessionId?: string; citation?: ReaderSelection};
type SessionRows<T> = { actorId: string; sessionId: string; rows: T[] };
type PreviewAction = {
  preview: LearningPreview; versionId: string; action: "publish" | "retract" | "cancel-publication";
  scheduledAt?: string; replacementId?: string;
  context:{offeringTitle?:string;sessionTitle?:string;materialTitle?:string;versionNo?:number;timeZone:string};
};
type ManagementAction = { action:string;title: string; path: string; payload: Record<string, unknown>; method: string; preview: LearningPreview; actorId?: string; context: {offering?:string;session?:string}; resolve: (value: unknown) => void; reject: (reason: Error) => void };
const formValue = (form: HTMLFormElement, key: string) => String(new FormData(form).get(key) ?? "").trim();
const errorText = (error: unknown) => error instanceof Error ? error.message : "Chưa hoàn thành thao tác học liệu.";
const label = (value: Catalog) => value.name || value.title || value.display_name || value.code || value.id;
const fieldLabels: Record<string,string> = {closes_at:"Giờ chốt",scheduled_at:"Giờ công bố",name:"Tên",code:"Mã môn",start_date:"Ngày bắt đầu",end_date:"Ngày kết thúc",timezone:"Múi giờ",section_code:"Mã lớp",title:"Tiêu đề",term_id:"Học kỳ",course_id:"Môn học",actor_subject_id:"Tài khoản",role:"Vai trò",status:"Trạng thái",visibility:"Hiển thị",description:"Mô tả",starts_at:"Thời gian",session_ids:"Thứ tự buổi học"};
const stateLabel=(value:string)=>({CONVERTING:"Đang kiểm tra và chuyển PowerPoint",QUEUED:"Chờ kiểm tra",VALIDATING:"Đang kiểm tra",SCANNING:"Đang quét tệp",EXTRACTING:"Đang chuẩn bị trang",READY:"Sẵn sàng",FAILED:"Xử lý thất bại",REJECTED:"Tệp không được chấp nhận",DRAFT:"Bản nháp",SCHEDULED:"Đã hẹn công bố",PUBLISHED:"Đã công bố",RETRACTED:"Đã thu hồi",QUARANTINED:"Đã cách ly"} as Record<string,string>)[value]||"Đang cập nhật";
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function readLink(search:string):ReaderLink|null {
  const params=new URLSearchParams(search),version=params.get("version_id"),page=params.get("page_no"),anchor=params.get("anchor_id");
  if(!version||!uuid.test(version)||(page!==null&&(!/^[1-9][0-9]{0,2}$/.test(page)||Number(page)>500))||(anchor!==null&&(!page||!uuid.test(anchor))))return null;
  const session = params.get("session_id");
  return {version_id:version,page_no:page?Number(page):undefined,anchor_id:anchor||undefined,session_id:session && uuid.test(session) ? session : undefined};
}
function linkPath(destination:ReaderLink) {
  const query=new URLSearchParams({version_id:destination.version_id});
  if(destination.page_no)query.set("page_no",String(destination.page_no));
  if(destination.anchor_id)query.set("anchor_id",destination.anchor_id);
  if(destination.session_id)query.set("session_id",destination.session_id);
  return `/learning?${query.toString()}`;
}

export function LearningWorkspace() {
  const t = useT();
  const [capabilities, setCapabilities] = useState<LearningCapabilities | null>(null);
  const [initializationAttempt, setInitializationAttempt] = useState(0);
  const pptxEnabled = capabilities?.pptx_available === true;
  const uploadAccept = pptxEnabled ? 'application/pdf,.pdf,application/vnd.openxmlformats-officedocument.presentationml.presentation,.pptx' : 'application/pdf,.pdf';
  const [role, setRole] = useState<Role>("guest");
  const [actorId,setActorId]=useState("");
  const [actorRoles,setActorRoles]=useState<string[]>([]);
  const gateway = useMemo(() => new LearningGateway(undefined, actorId || undefined), [actorId]);
  const session = useLearningSession(actorId, actorRoles);
  const [admin, setAdmin] = useState(false);
  const [offerings, setOfferings] = useState<LearningOffering[]>([]);
  const [offeringId, setOfferingId] = useState("");
  const [sessions, setSessions] = useState<LearningSession[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [materials, setMaterials] = useState<LearningMaterial[]>([]);
  const [linkCandidates,setLinkCandidates]=useState<LearningMaterial[]>([]);
  const [reader, setReader] = useState<LearningReaderMetadata | null>(null);
  const [readerSessionId, setReaderSessionId] = useState<string>();
  const [ideaDraftRequest, setIdeaDraftRequest] = useState<{ sequence: number; selection: ReaderSelection }>();
  const [ideaCitation, setIdeaCitation] = useState<ReaderSelection>();
  const [readerState, setReaderState] = useState<ReaderState | undefined>();
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [syncIssues, setSyncIssues] = useState<Record<string, "conflict" | "retry">>({});
  const [readerGeneration, setReaderGeneration] = useState(0);
  const [ocrNavigation, setOcrNavigation] = useState<{ generation: number; sequence: number; page: number }>();
  const readerEpoch = useRef(0);
  const revalidateInterrupted = useRef(false);
  const [selection,setSelection]=useState<ReaderSelection|null>(null);
  const [annotations,setAnnotations]=useState<ReaderAnnotation[]>([]);
  const [presentation,setPresentation]=useState<PresentationPosition|null>(null);
  const [readerPage,setReaderPage]=useState(1);
  const [anchorId,setAnchorId]=useState<string|undefined>();
  const [loginTarget,setLoginTarget]=useState("/learning");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pendingUpload, setPendingUpload] = useState<{ id: string; versionNo: number; sessionId: string } | null>(null);
  const [preview, setPreview] = useState<PreviewAction | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [management, setManagement] = useState<ManagementAction | null>(null);
  const [managementConfirmed, setManagementConfirmed] = useState(false);
  const [managementSubmitting, setManagementSubmitting] = useState(false);
  const [catalogs, setCatalogs] = useState<{ terms: Catalog[]; courses: Catalog[]; actors: Catalog[]; members: Catalog[] }>({ terms: [], courses: [], actors: [], members: [] });
  const [catalogScope,setCatalogScope]=useState<string>();
  const catalogRequest=useRef<AbortController|null>(null);
  const [revisionTick, setRevisionTick] = useState(0);
  const [exitRevision, setExitRevision] = useState(0);
  const [instructionRows, setInstructionRows] = useState<SessionRows<ReadingInstruction>>();
  const [exitRows, setExitRows] = useState<SessionRows<LearningExitTicket>>();
  const [exitSelection, setExitSelection] = useState<{ actorId: string; sessionId: string; id: string }>();
  const readerSync = useRef(new Map<string, ReaderSync>());
  const pendingNavigation=useRef<PendingReaderLink|null>(null);
  const pendingExitSession = useRef<{ offeringId: string; sessionId: string } | null>(null);
  const exitFocusOrigin = useRef<HTMLElement | null>(null);
  const currentWorkspace=useRef({actorId,offeringId,sessionId});
  currentWorkspace.current={actorId,offeringId,sessionId};
  const managementLifetime=useRef(true);
  const managementRequests=useRef(new Set<AbortController>());
  const currentManagement=useRef(management);
  const confirmingManagement=useRef(false);
  const publicationGeneration=useRef(0),publicationPending=useRef(false);
  const currentPublication=useRef(preview);currentPublication.current=preview;
  currentManagement.current=management;
  useEffect(()=>{
    managementLifetime.current=true;
    return()=>{
      managementLifetime.current=false;
      publicationGeneration.current++;publicationPending.current=false;
      for(const controller of managementRequests.current)controller.abort();
      catalogRequest.current?.abort();
      if(!confirmingManagement.current)currentManagement.current?.reject(new Error(t("lwx.1")));
    };
  },[]);
  const readerId = reader?.version_id || reader?.id;
  const syncIssue = readerId ? syncIssues[readerId] : undefined;
  const offering = offerings.find(item => item.id === offeringId);
  const activeMembers=catalogScope===JSON.stringify([actorId,offeringId])?catalogs.members:[];
  const timeZone = classTimeZone(offering?.timezone);
  const activeSession = sessions.find(item => item.id === sessionId);
  const manageable = !!offering?.capabilities.manage && offering.status === "ACTIVE";
  const exitEnabled = !!offering?.capabilities.exit_tickets;
  const exitStaff = offering?.member_role === "INSTRUCTOR" || !!offering?.capabilities.manage;
  const instructions = instructionRows?.actorId === actorId && instructionRows.sessionId === sessionId ? instructionRows.rows : [];
  const exitTickets = exitRows?.actorId === actorId && exitRows.sessionId === sessionId ? exitRows.rows : [];
  const exitTicketId = exitEnabled && exitSelection?.actorId === actorId && exitSelection.sessionId === sessionId ? exitSelection.id : undefined;
  const exitReaderSource = readerId && readerSessionId === sessionId ? { versionId: readerId, page: readerPage } : undefined;
  const acceptInstructionRows = useCallback((actorId: string, sessionId: string, rows: ReadingInstruction[]) => {
    setInstructionRows({ actorId, sessionId, rows });
  }, []);
  const acceptExitRows = useCallback((actorId: string, sessionId: string, rows: LearningExitTicket[]) => {
    setExitRows({ actorId, sessionId, rows });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const destination=readLink(window.location.search);
        if(destination)setLoginTarget(linkPath(destination));
        const ideaShare = new URLSearchParams(window.location.search).get("idea_share");
        if (!destination && ideaShare && uuid.test(ideaShare)) setLoginTarget(`/learning?idea_share=${ideaShare}`);
        const response = await fetch("/v1/users/me", { credentials: "include", cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error(response.status === 401 ? t("lwx.2") : t("lwx.3"));
        const actor = await response.json(); const isAdmin = actor.roles?.includes("SYSTEM_ADMIN") === true;
        const gateway = new LearningGateway(undefined, actor.user_id || actor.subject_id || undefined);
        const caps = await gateway.capabilities(controller.signal);
        if (controller.signal.aborted) return;
        setAdmin(isAdmin); setCapabilities(caps);setActorId(actor.user_id||actor.subject_id||"");
        setActorRoles(actor.roles ?? []);
        setRole(isAdmin ? "admin" : actor.roles?.includes("LECTURER") ? "lecturer" as Role : "student");
        if (caps.enabled === false || caps.available === false) return;
        const rows = await gateway.offerings(isAdmin, controller.signal);
        let first=rows[0]?.id||"";
        if(destination) {
          try {
            const metadata=await gateway.reader(destination.version_id,controller.signal);
            if(!rows.some(item=>item.id===metadata.offering_id&&item.capabilities.read))throw new Error(t("lwx.4"));
            if(destination.page_no&&destination.page_no>metadata.page_count)throw new Error(t("lwx.5"));
            const contexts = caps.session_contexts === true ? await gateway.sessionContexts(destination.version_id, controller.signal) : [];
            const sourceSessionId = contexts.find(context => context.id === destination.session_id)?.id
              ?? (contexts.length === 1 ? contexts[0].id : undefined);
            if(!controller.signal.aborted)pendingNavigation.current={
              ...destination, offering_id:metadata.offering_id, session_id:sourceSessionId, sourceSessionId,
            };
            first=metadata.offering_id;
          } catch(caught) {
            if(!controller.signal.aborted)setError(caught instanceof LearningApiError&&caught.status===404?t("lwx.6"):errorText(caught));
          }
        } else if(new URLSearchParams(window.location.search).has("version_id")) {
          setError(t("lwx.7"));
        }
        if (!controller.signal.aborted) { setOfferings(rows); setOfferingId(first); }
      } catch (caught) { if (!controller.signal.aborted) setError(errorText(caught)); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    })();
    return () => controller.abort();
  }, [initializationAttempt]);

  useEffect(() => {
    const controller = new AbortController(); setSessions([]); setSessionId(""); setMaterials([]); setReader(null);
    if (offeringId && offering?.capabilities.read) void gateway.sessions(offeringId, controller.signal).then(rows => {
      if (!controller.signal.aborted) {
        setSessions(rows);
        const destination=pendingNavigation.current;
        const exit = pendingExitSession.current;
        const exitLinked = exit?.offeringId === offeringId ? rows.find(row => row.id === exit.sessionId) : undefined;
        if (exit?.offeringId === offeringId) pendingExitSession.current = null;
        const linked=destination?.offering_id===offeringId&&rows.find(row=>row.id===destination?.session_id);
        const next=exitLinked?.id ?? (linked ? linked.id : rows[0]?.id||"");
        setSessionId(next);
        if(destination?.offering_id===offeringId) {
          if(next) pendingNavigation.current={...destination,session_id:next};
          else {pendingNavigation.current=null;void run(()=>openVersion(destination.version_id,destination.page_no,destination.anchor_id,destination.sourceSessionId,destination.citation));}
        }
      }
    }).catch(caught => { if (!controller.signal.aborted) setError(errorText(caught)); });
    return () => controller.abort();
  }, [offeringId, offering?.capabilities.read, revisionTick]);

  useEffect(() => {
    const controller = new AbortController(); setMaterials([]); setReader(null);
    if (sessionId) void gateway.materials(sessionId, controller.signal).then(rows => {
      if (!controller.signal.aborted) {setMaterials(rows);const destination=pendingNavigation.current;if(destination&&(!destination.session_id||destination.session_id===sessionId)){pendingNavigation.current=null;void run(()=>openVersion(destination.version_id,destination.page_no,destination.anchor_id,destination.sourceSessionId,destination.citation));}}
    }).catch(caught => { if (!controller.signal.aborted) setError(errorText(caught)); });
    return () => controller.abort();
  }, [sessionId]);
  useEffect(()=>{
    if(!sessionId||!materials.some(item=>item.versions?.some(version=>!["READY","FAILED","REJECTED"].includes(version.processing_state)))) return;
    const controller=new AbortController();const interval=setInterval(()=>{void gateway.materials(sessionId,controller.signal).then(rows=>{if(!controller.signal.aborted)setMaterials(rows);}).catch(caught=>{if(!controller.signal.aborted)setError(errorText(caught));});},3000);
    return()=>{controller.abort();clearInterval(interval);};
  },[sessionId,materials]);

  useEffect(() => {
    if (!pendingUpload) return;
    if (pendingUpload.sessionId !== sessionId) { setPendingUpload(null); return; }
    const version = materials.flatMap(item => item.versions ?? []).find(item => item.id === pendingUpload.id);
    if (!version || !["READY", "FAILED", "REJECTED"].includes(version.processing_state)) return;
    setNotice(version.processing_state === "READY"
      ? `Phiên bản ${pendingUpload.versionNo} đã sẵn sàng. Hãy xem trước trước khi công bố.`
      : version.processing_state === "REJECTED"
        ? `Phiên bản ${pendingUpload.versionNo} không được chấp nhận. Xem chi tiết trong lịch sử phiên bản.`
        : `Chưa xử lý được phiên bản ${pendingUpload.versionNo}. Xem chi tiết trong lịch sử phiên bản.`);
    setPendingUpload(null);
  }, [materials, pendingUpload, sessionId]);

  const refreshCatalogs = useCallback(async () => {
    if (!admin||!session.canAccess.current||!managementLifetime.current||currentWorkspace.current.actorId!==actorId||currentWorkspace.current.offeringId!==offeringId) return;
    catalogRequest.current?.abort();const controller=new AbortController();catalogRequest.current=controller;setCatalogScope(undefined);
    try{
    const [terms, courses, actors, members] = await Promise.all([
      gateway.list<Catalog>("/terms",controller.signal), gateway.list<Catalog>("/courses",controller.signal),
      gateway.list<Catalog>("/admin/eligible-actors",controller.signal),
      offeringId ? gateway.list<Catalog>(`/offerings/${offeringId}/members`,controller.signal) : Promise.resolve([]),
    ]);
    if(!controller.signal.aborted&&currentWorkspace.current.actorId===actorId&&currentWorkspace.current.offeringId===offeringId){setCatalogs({ terms, courses, actors, members });setCatalogScope(JSON.stringify([actorId,offeringId]));}
    }catch(caught){if(!controller.signal.aborted)throw caught;}
  }, [admin, actorId,offeringId,gateway]);
  useEffect(()=>{
    if(admin&&session.state==='ready')void refreshCatalogs().catch(caught=>setError(errorText(caught)));
    return()=>catalogRequest.current?.abort();
  },[admin,refreshCatalogs,session.state]);

  async function run(work: () => Promise<void>) {
    if (!session.canAccess.current) return;
    setBusy(true); setError(""); setNotice(""); setPendingUpload(null);
    try { await work(); } catch (caught) { setError(errorText(caught)); } finally { setBusy(false); }
  }
  async function openUpdate(update:LearningUpdate){
    await flushReaderState();
    if (update.event_type === "EXIT_TICKET_UPDATED" && update.exit_ticket_id && update.session_id) {
      if (update.offering_id && update.offering_id !== offeringId) {
        const rows = await gateway.offerings(admin);
        if (!rows.some(row => row.id === update.offering_id && row.capabilities.exit_tickets)) throw new Error(t("lwx.8"));
        pendingExitSession.current = { offeringId: update.offering_id, sessionId: update.session_id };
        setOfferings(rows); setOfferingId(update.offering_id);
      } else {
        if (!exitEnabled || !sessions.some(row => row.id === update.session_id)) throw new Error(t("lwx.8"));
        setSessionId(update.session_id);
      }
      selectExitTicket(update.exit_ticket_id, update.session_id);
      return;
    }
    const sourceSessionId = update.event_type === "PAGE_EXPLANATION_PUBLISHED" ? update.session_id ?? undefined : undefined;
    if(update.offering_id&&update.offering_id!==offeringId){setOfferings(await gateway.offerings(admin));pendingNavigation.current={...update,sourceSessionId};setOfferingId(update.offering_id);return;}
    if(update.session_id&&update.session_id!==sessionId&&sessions.some(item=>item.id===update.session_id)){pendingNavigation.current={...update,sourceSessionId};setSessionId(update.session_id);return;}
    await openVersion(update.version_id,update.page_no,undefined,sourceSessionId);
  }
  function selectExitTicket(id: string, sourceSessionId = sessionId) {
    exitFocusOrigin.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setExitSelection({ actorId, sessionId: sourceSessionId, id });
    requestAnimationFrame(() => document.getElementById(`learning-exit-ticket-${id}`)?.focus());
  }
  function closeExitTicket() {
    setExitSelection(undefined);
    const origin = exitFocusOrigin.current;
    if (origin?.isConnected) origin.focus();
    else document.getElementById("learning-exit-tickets-heading")?.focus();
  }
  function openExitSource(versionId: string, page: number) {
    void run(async () => {
      await openVersion(versionId, page, undefined, sessionId);
      requestAnimationFrame(() => document.getElementById("learning-reader")?.focus());
    });
  }
  async function reviewedWrite<T>(path: string, payload: Record<string, unknown>, action: string, title: string, method = "POST"): Promise<T> {
    if(currentManagement.current||managementRequests.current.size||currentPublication.current||publicationPending.current)throw new Error(t("lwx.9"));
    if(!session.canAccess.current)throw new Error(t("lwx.10"));
    const target = path.split("/").filter(part=>/^[0-9a-f]{8}-[0-9a-f-]{27}$/.test(part)).at(-1);
    const requestedActor = action.startsWith("exit-") || action.startsWith("ocr-") ? actorId : undefined;
    const body = { action, target_id: target, payload };
    const context=target&&!action.startsWith('idea-')?{offering:offering?.title,session:path.startsWith('/sessions/')||action.startsWith('exit-')||action==='page-explanation-update'?activeSession?.title:undefined}:{};
    const controller=new AbortController();managementRequests.current.add(controller);
    let preview:LearningPreview;
    try{
      preview=await gateway.write<LearningPreview>("/action-previews",body,"POST",undefined,
        requestedActor?{"X-Campus-Reader-Actor":requestedActor}:{},controller.signal);
      if(controller.signal.aborted||!managementLifetime.current)throw new Error(t("lwx.1"));
    }finally{managementRequests.current.delete(controller);}
    setManagementConfirmed(false);
    return new Promise<T>((resolve, reject) => {const next={ action,title, path, payload, method, preview, actorId: requestedActor,context, resolve:(value:unknown)=>resolve(value as T),reject };currentManagement.current=next;setManagement(next);});
  }
  function cancelManagement() { management?.reject(new Error(t("lwx.11"))); currentManagement.current=null;setManagement(null); }
  async function confirmManagement() {
    if (!management || !managementConfirmed || confirmingManagement.current || !session.canAccess.current) return;
    confirmingManagement.current=true;setManagementSubmitting(true);
    try {
      const body = { ...management.payload, preview_id: management.preview.preview_id, confirmation_token: management.preview.confirmation_token };
      const key = `learning-action:${management.preview.preview_id}`;
      const result = management.actorId
        ? await gateway.write(management.path, body, management.method, key, { "X-Campus-Reader-Actor": management.actorId })
        : await gateway.write(management.path, body, management.method, key);
      management.resolve(result); currentManagement.current=null;setManagement(null);
    } catch (caught) { management.reject(caught instanceof Error ? caught : new Error(errorText(caught))); currentManagement.current=null;setManagement(null); }
    finally { confirmingManagement.current=false;setManagementSubmitting(false); }
  }
  async function reloadMaterials() { if (sessionId) setMaterials(await gateway.materials(sessionId)); }
  async function openVersion(versionId: string, pageNo?: number, noteId?:string, sourceSessionId?:string, citation?: ReaderSelection) {
    await flushReaderState();
    const metadata = await gateway.reader(versionId);
    if(pageNo&&pageNo>metadata.page_count)throw new Error(t("lwx.5"));
    const [saved, marks] = await Promise.all([
      gateway.request<{ revision?: number; state?: ReaderState } & Partial<ReaderState>>(
        `/me/reader-state/${versionId}`, { headers: { "X-Campus-Reader-Actor": actorId } },
      ),
      gateway.list<Bookmark>(`/me/bookmarks?version_id=${versionId}`),
    ]);
    const sync = readerSync.current.get(versionId) ?? { actorId, revision: saved.revision ?? 0 };
    if (!sync.pending) sync.revision = saved.revision ?? 0;
    readerSync.current.set(versionId, sync);
    const initial = sync.pending ?? (saved.state || (saved.page_no ? saved : undefined)) as ReaderState | undefined;
    setReaderSessionId(sourceSessionId);
    setIdeaCitation(citation);
    setReaderState(pageNo?{...initial,page_no:pageNo,offset_x:0,offset_y:0} as ReaderState:initial);
    setBookmarks(marks); if(readerId!==versionId)setAnnotations([]); setSelection(null);setAnchorId(noteId);setPresentation(null);setReaderPage(pageNo||initial?.page_no||1); setReaderGeneration(++readerEpoch.current); setReader(metadata);
  }
  function beginIdea(selection: ReaderSelection) {
    setIdeaDraftRequest(previous => ({ sequence: (previous?.sequence ?? 0) + 1, selection }));
  }
  function openOcrSource(page: number, anchor?: LearningOcrAnchor, focus = true) {
    if (!readerId || !reader || !Number.isInteger(page) || page < 1 || page > reader.page_count) return;
    setOcrNavigation(previous => ({ generation: readerGeneration, sequence: (previous?.sequence ?? 0) + 1, page }));
    setIdeaCitation(anchor ? { version_id: readerId, page_no: page, anchor: { kind: "REGION", rects: [anchor] } } : undefined);
    if (focus) requestAnimationFrame(() => document.getElementById("learning-reader")?.focus());
  }
  async function openIdeaSource(source: IdeaSource) {
    const citation = source.kind === "REGION" ? { version_id: source.version_id, page_no: source.page_no,
      anchor: { kind: "REGION" as const, rects: source.rects } } : undefined;
    if (source.offering_id !== offeringId) {
      await flushReaderState();
      const available = await gateway.offerings(admin);
      if (!available.some(item => item.id === source.offering_id && item.capabilities.read)) throw new Error(t("lwx.12"));
      pendingNavigation.current = { version_id: source.version_id, offering_id: source.offering_id, page_no: source.page_no, citation };
      setOfferings(available); setOfferingId(source.offering_id);
      return;
    }
    await openVersion(source.version_id, source.page_no, undefined, undefined, citation);
    requestAnimationFrame(() => document.getElementById("learning-reader")?.focus());
  }
  function setSyncIssue(id: string, issue?: "conflict" | "retry") {
    setSyncIssues(previous => {
      if (previous[id] === issue) return previous;
      const next = { ...previous };
      if (issue) next[id] = issue;
      else delete next[id];
      return next;
    });
  }
  async function flushReaderState(id = readerId) {
    if (!session.canAccess.current) return;
    const sync = id && readerSync.current.get(id);
    if (!id || !sync) return;
    clearTimeout(sync.timer);
    sync.timer = undefined;
    while (sync.saving) {
      if (!(await sync.saving)) return;
    }
    if (!sync.pending || sync.conflict) return;
    const snapshot = sync.pending;
    const save = (async () => {
      try {
        const saved = await gateway.write<{ revision: number }>(
          `/me/reader-state/${id}`, { ...snapshot, revision: sync.revision }, "PUT", undefined,
          { "X-Campus-Reader-Actor": sync.actorId },
        );
        sync.revision = saved.revision;
        if (sync.pending === snapshot) sync.pending = undefined;
        setSyncIssue(id);
        return true;
      } catch (caught) {
        sync.conflict = caught instanceof LearningApiError && caught.status === 409;
        setSyncIssue(id, sync.conflict ? "conflict" : "retry");
        return false;
      }
    })();
    sync.saving = save;
    try { await save; }
    finally { if (sync.saving === save) sync.saving = undefined; }
  }
  function saveReaderState(state: ReaderState) {
    const sync = readerId ? readerSync.current.get(readerId) : undefined;
    if (!readerId || !sync || readerGeneration !== readerEpoch.current) return;
    sync.pending = state;
    if (!sync.timer && !sync.conflict) {
      sync.timer = setTimeout(() => { void flushReaderState(readerId); }, 5000);
    }
  }
  async function saveBookmark(page: number, label?: string) {
    if (!readerId) return;
    try {
      await gateway.write("/me/bookmarks", { version_id: readerId, page_no: page, label: label?.trim() || `Trang ${page}` });
      const marks = await gateway.list<Bookmark>(`/me/bookmarks?version_id=${readerId}`);
      if (readerEpoch.current !== readerGeneration) return;
      setBookmarks(marks);
      setNotice(t("lwx.13"));
    } catch (caught) {
      setError(errorText(caught));
      throw caught;
    }
  }
  async function resolveReaderConflict(useLocal: boolean) {
    const sync = readerId ? readerSync.current.get(readerId) : undefined;
    if (!readerId || !sync?.conflict) return;
    const saved = await gateway.request<ReaderState & {revision:number}>(
      `/me/reader-state/${readerId}`, { headers: { "X-Campus-Reader-Actor": sync.actorId } },
    );
    sync.revision = saved.revision;
    sync.conflict = false;
    if (useLocal) {
      await flushReaderState(readerId);
      if (sync.pending) return;
    } else {
      sync.pending = undefined;
      setReaderState(saved);
      setReaderPage(saved.page_no);
      setReaderGeneration(++readerEpoch.current);
    }
    setSyncIssue(readerId);
    setNotice(t("lwx.14"));
  }
  useEffect(() => {
    const reconnect = () => {
      for (const id of readerSync.current.keys()) void flushReaderState(id);
    };
    window.addEventListener("online", reconnect);
    return () => {
      window.removeEventListener("online", reconnect);
      for (const sync of readerSync.current.values()) clearTimeout(sync.timer);
    };
  }, []);
  useEffect(() => {
    if (!readerId || session.state !== "ready") return;
    const controller = new AbortController();
    let inflight = false;
    const revalidate = () => { inflight = true; void gateway.reader(readerId, controller.signal).then(metadata=>{
      if(!controller.signal.aborted)setReader(current=>(current?.version_id||current?.id)===readerId?metadata:current);
    }).catch(caught => {
      if (controller.signal.aborted)return;
      if(caught instanceof LearningApiError&&caught.status===401){ void session.check(); return; }
      if(caught instanceof LearningApiError&&[403,404].includes(caught.status)){
        setReader(null);setError(caught.status===404?t("lwx.15"):errorText(caught));
      }
    }).finally(() => { inflight = false; }); };
    // A focus also re-checks the account, which briefly leaves the "ready" state and tears this effect down.
    // Without this retry the check that was cut off would be lost and a newer or retracted version unseen.
    if (revalidateInterrupted.current) { revalidateInterrupted.current = false; revalidate(); }
    const visibility = () => { if (document.visibilityState === "visible") revalidate(); else void flushReaderState(); };
    window.addEventListener("focus", revalidate); document.addEventListener("visibilitychange", visibility);
    const interval = setInterval(revalidate, 30000);
    return () => { if (inflight) revalidateInterrupted.current = true; controller.abort(); clearInterval(interval); window.removeEventListener("focus", revalidate); document.removeEventListener("visibilitychange", visibility); };
  }, [readerId, session.state, session.check]);
  useEffect(()=>{
    if(!anchorId||!readerId)return;
    const note=annotations.find(item=>item.id===anchorId&&item.version_id===readerId&&item.page_no===readerPage);
    if(note)setSelection({version_id:readerId,page_no:note.page_no,anchor:note.anchor});
  },[anchorId,annotations,readerId,readerPage]);

  async function publishPreview(versionId: string, action: "publish" | "retract" | "cancel-publication", scheduledAt?: string, replacementId?: string) {
    if(currentManagement.current||managementRequests.current.size)throw new Error(t("lwx.9"));
    if(!session.canAccess.current)throw new Error(t("lwx.10"));
    const generation=++publicationGeneration.current;publicationPending.current=true;
    const material=materials.find(item=>item.versions.some(version=>version.id===versionId));
    const version=material?.versions.find(item=>item.id===versionId);
    const context={offeringTitle:offering?.title,sessionTitle:activeSession?.title,materialTitle:material?.title,versionNo:version?.version_no,timeZone};
    setConfirmed(false);
    try{
    let changeRevision: number | undefined;
    if (action === "publish") {
      const material = materials.find(item => item.versions.some(version => version.id === versionId));
      const version = material?.versions.find(item => item.id === versionId);
      if (material && version?.capabilities?.version_changes && olderPublishedVersions(material, version).length) {
        const { change_set: change } = await gateway.request<{ change_set: LearningVersionChangeSet | null }>(
          `/versions/${versionId}/change-set`, { headers: { "X-Campus-Reader-Actor": actorId } });
        if (!change?.base_available) throw new Error("Hãy lưu mô tả thay đổi và chọn phạm vi trước khi công bố.");
        changeRevision = change.revision;
      }
    }
    if(generation!==publicationGeneration.current||!managementLifetime.current)throw new Error("Yêu cầu xem trước đã đổi; bản đang soạn vẫn được giữ.");
    const result = await gateway.preview(versionId, action, scheduledAt, replacementId, changeRevision);
    if(generation!==publicationGeneration.current||!managementLifetime.current)throw new Error("Yêu cầu xem trước đã đổi; bản đang soạn vẫn được giữ.");
    const next={ preview: result, versionId, action, scheduledAt, replacementId,context };currentPublication.current=next;setPreview(next);
    }finally{if(generation===publicationGeneration.current)publicationPending.current=false;}
  }
  async function reorderSession(id: string, direction: number) {
    const ids = sessions.map(item=>item.id); const index=ids.indexOf(id); const next=index+direction;
    if(index<0 || next<0 || next>=ids.length) return;
    [ids[index],ids[next]]=[ids[next],ids[index]];
    await reviewedWrite(`/offerings/${offeringId}/session-order`,{session_ids:ids},"order_sessions","Đổi thứ tự buổi học","PUT");
    setSessions(await gateway.sessions(offeringId));
  }
  async function reorderMaterial(id:string,direction:number) {
    const ids=materials.map(item=>item.id),index=ids.indexOf(id),next=index+direction;
    if(index<0||next<0||next>=ids.length)return;
    [ids[index],ids[next]]=[ids[next],ids[index]];
    await reviewedWrite(`/sessions/${sessionId}/material-links`,{material_ids:ids},"material_links","Sắp xếp học liệu trong buổi","PUT");await reloadMaterials();
  }
  async function applyPublication() {
    if (!preview || !confirmed) return;
    if (Date.parse(preview.preview.expires_at) <= Date.now()) throw new Error(t("lwx.16"));
    await gateway.write(`/versions/${preview.versionId}/${preview.action}`, {
      preview_id: preview.preview.preview_id, confirmation_token: preview.preview.confirmation_token,
      ...(preview.scheduledAt ? { scheduled_at: preview.scheduledAt } : {}),
      ...(preview.replacementId ? { replacement_version_id: preview.replacementId } : {}),
      ...(preview.preview.change_set ? { change_set_revision: preview.preview.change_set.revision } : {}),
    }, "POST", `learning-publication:${preview.preview.preview_id}`);
    setPreview(null); await reloadMaterials(); setNotice(t("lwx.17"));
  }
  async function upload(draft:UploadDraft,file:File,signal:AbortSignal,onIntent:(id:string)=>void,materialId?:string) {
    if(!session.canAccess.current)throw new Error(t("lwx.10"));
    let targetId=materialId??draft.targetId;
    if(!targetId){
      draft.creating=true;
      const created=await gateway.write<LearningMaterial>(`/offerings/${offeringId}/materials`,{title:draft.title.trim(),description:"",session_id:sessionId},"POST",draft.createKey,{},signal);
      targetId=created.id;draft.targetId=targetId;
    }
    const version=await gateway.upload(targetId,file,signal,onIntent,draft.attempt);
    if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.offeringId===offeringId&&currentWorkspace.current.sessionId===sessionId){
      const rows=await gateway.materials(sessionId);
      if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.offeringId===offeringId&&currentWorkspace.current.sessionId===sessionId)setMaterials(rows);
    }
    return version;
  }
  function acceptedUpload(version:LearningVersion){
    if(currentWorkspace.current.actorId!==actorId||currentWorkspace.current.offeringId!==offeringId||currentWorkspace.current.sessionId!==sessionId)return;
    setNotice(`Đã nhận phiên bản ${version.version_no}. Hệ thống đang kiểm tra tệp; trạng thái sẽ tự cập nhật. Chỉ công bố sau khi xem trước bản sẵn sàng.`);
    setPendingUpload({id:version.version_id||version.id,versionNo:version.version_no,sessionId});
  }

  const pdfReader = reader && <LearningPdfReader key={`${reader.version_id || reader.id}:${readerGeneration}`}
    version={{...reader,version_id:reader.version_id||reader.id,download_allowed:reader.capabilities.download,download_path:`/v1/learning/versions/${reader.version_id||reader.id}/download`}}
    initialState={readerState} onStateChange={saveReaderState} onPageChange={setReaderPage} presentation={presentation}
    bookmarks={bookmarks} annotations={annotations} citation={ideaCitation}
    navigation={ocrNavigation?.generation === readerGeneration ? ocrNavigation : undefined} focusedAnnotationId={anchorId}
    onSelection={value=>{setAnchorId(undefined);setSelection(value);}} onIdeaSelection={reader.capabilities.idea_cards ? beginIdea : undefined}
    onAnnotationClick={note=>{setAnchorId(note.id);setSelection({version_id:reader.version_id||reader.id,page_no:note.page_no,anchor:note.anchor});}}
    onBookmark={saveBookmark}/>;

  return <><LearningSessionNotice state={session.state} onCheck={() => void session.check()} />
    <PreservedActivity mode={session.state === "ready" ? "visible" : "hidden"}>
    <AppShell activeNav="learning" userRole={role}><div className={styles.workspace}>
    <header className={styles.heading}><div><h1>{t("lwx.18")}</h1><p className={styles.muted}>{t("lwx.19")}</p></div><button disabled={busy || loading} onClick={() => {
      if (!capabilities || capabilities.enabled === false || capabilities.available === false) {
        setError(""); setLoading(true); setInitializationAttempt(value => value + 1); return;
      }
      void run(async () => { setOfferings(await gateway.offerings(admin)); if (sessionId) await reloadMaterials(); setNotice(t("lwx.20")); });
    }}>{t("lwx.21")}</button></header>
    {error && <div role="alert" className={`${styles.alert} ${styles.error}`}>{error} {role==="guest"&&<Link href={`/login?redirect=${encodeURIComponent(loginTarget)}`}>{t("lwx.22")}</Link>}</div>}
    {notice && <p role="status" className={styles.alert}>{notice}</p>}
    {busy&&<p role="status">{t("lwx.23")}</p>}
    {loading ? <p role="status">{t("lwx.24")}</p> : capabilities && (capabilities.enabled === false || capabilities.available === false) ? <p>{t("lwx.25")}</p> : <>
      <section className={styles.panel} aria-label={t("lwx.26")}>
        <div className={styles.offeringControl}>
          <label className={styles.offeringLabelField}>
            <span className={styles.offeringLabel}>{t("lwx.27")}</span>
            <div className={styles.selectWrapper}>
              <select
                aria-label={t("lwx.27")}
                disabled={!offerings.length}
                className={styles.offeringSelect}
                value={offeringId}
                onChange={event => {
                  const id = event.target.value;
                  void run(async () => {
                    await flushReaderState();
                    setOfferingId(id);
                  });
                }}
              >
                <option value="">{t("lwx.28")}</option>
                {offerings.map(item => (
                  <option key={item.id} value={item.id}>
                    {item.title || item.section_code} · {item.status === "ARCHIVED" ? t("lwx.29") : t("lwx.30")}
                  </option>
                ))}
              </select>
            </div>
          </label>
        </div>
        {!offerings.length && (
          <div className={styles.offeringEmpty}>
            <div className={styles.emptyIconCircle} aria-hidden="true">
              <BookOpen className={styles.emptyIcon} size={22} />
            </div>
            <div className={styles.emptyContent}>
              <p className={styles.emptyTitle}>{t("lwx.31")}</p>
              <p className={styles.emptyDesc}>{t("lwx.32")}</p>
            </div>
          </div>
        )}
      </section>
      <LearningNotifications actorId={actorId} onOpen={update=>void run(()=>openUpdate(update))}/>
      {admin && <details className={styles.panel} onToggle={event => { if (event.currentTarget.open) void run(refreshCatalogs); }}><summary>Quản trị học kỳ, môn học và thành viên</summary><div className={styles.stack}>
        <LearningMetadataForm actorId={actorId} draftId="admin:new-term" className={styles.form} disabled={busy}
          initialValues={{name:"",start_date:"",end_date:""}} basis={{timezone:CAMPUS_TIMEZONE}}
          toPayload={({values,basis})=>({name:values.name.trim(),start_date:values.start_date,end_date:values.end_date,timezone:basis.timezone})}
          onSave={async payload=>{await reviewedWrite("/terms",payload,"create_term","Tạo học kỳ");await refreshCatalogs();if(currentWorkspace.current.actorId===actorId)setNotice("Đã tạo học kỳ.");}}>
          {(values,change)=><><label>Tên học kỳ<input name="name" required value={values.name} onChange={event=>change("name",event.target.value)}/></label><label>Ngày bắt đầu<input name="start_date" type="date" required value={values.start_date} onChange={event=>change("start_date",event.target.value)}/></label><label>Ngày kết thúc<input name="end_date" type="date" required value={values.end_date} onChange={event=>change("end_date",event.target.value)}/></label><button>Tạo học kỳ</button></>}
        </LearningMetadataForm>
        <LearningMetadataForm actorId={actorId} draftId="admin:new-course" className={styles.form} disabled={busy} initialValues={{code:"",name:""}}
          toPayload={({values})=>({code:values.code.trim(),name:values.name.trim()})}
          onSave={async payload=>{await reviewedWrite("/courses",payload,"create_course","Tạo môn học");await refreshCatalogs();if(currentWorkspace.current.actorId===actorId)setNotice("Đã tạo môn học.");}}>
          {(values,change)=><><label>Mã môn<input name="code" required value={values.code} onChange={event=>change("code",event.target.value)}/></label><label>Tên môn<input name="name" required value={values.name} onChange={event=>change("name",event.target.value)}/></label><button>Tạo môn học</button></>}
        </LearningMetadataForm>
        <LearningMetadataForm actorId={actorId} draftId="admin:new-offering" className={styles.form} disabled={busy} initialValues={{term_id:"",course_id:"",section_code:"",title:""}}
          toPayload={({values})=>({term_id:values.term_id,course_id:values.course_id,section_code:values.section_code.trim(),title:values.title.trim()})}
          onSave={async payload=>{
            const created=await reviewedWrite<LearningOffering>("/offerings",payload,"create_offering","Tạo lớp học phần");
            if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.offeringId===offeringId){const rows=await gateway.offerings(true);if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.offeringId===offeringId){setOfferings(rows);setOfferingId(created.id);setNotice("Đã tạo lớp học phần.");}}
          }}>
          {(values,change)=><><label>Học kỳ<select aria-label="Học kỳ" name="term_id" required value={values.term_id} onChange={event=>change("term_id",event.target.value)}><option value="">Chọn học kỳ</option>{catalogs.terms.map(item=><option key={item.id} value={item.id}>{label(item)}</option>)}</select></label><label>Môn học<select aria-label="Môn học" name="course_id" required value={values.course_id} onChange={event=>change("course_id",event.target.value)}><option value="">Chọn môn</option>{catalogs.courses.map(item=><option key={item.id} value={item.id}>{label(item)}</option>)}</select></label><label>Mã lớp<input name="section_code" required value={values.section_code} onChange={event=>change("section_code",event.target.value)}/></label><label>Tên lớp<input name="title" required value={values.title} onChange={event=>change("title",event.target.value)}/></label><button>Tạo lớp</button></>}
        </LearningMetadataForm>
        {offeringId && <LearningMetadataForm actorId={actorId} draftId={`admin:member:${offeringId}`} className={styles.form} disabled={busy} initialValues={{actor_subject_id:"",role:"STUDENT"}}
          toPayload={({values})=>({actor_subject_id:values.actor_subject_id,role:values.role})}
          onSave={async payload=>{
            await reviewedWrite(`/offerings/${offeringId}/members`,payload,"add_member","Phân công thành viên lớp");await refreshCatalogs();
            if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.offeringId===offeringId){const rows=await gateway.offerings(true);if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.offeringId===offeringId){setOfferings(rows);setNotice("Đã phân công thành viên.");}}
          }}>
          {(values,change)=><><label>Tài khoản<select aria-label="Tài khoản" name="actor_subject_id" required value={values.actor_subject_id} onChange={event=>change("actor_subject_id",event.target.value)}><option value="">Chọn tài khoản</option>{catalogs.actors.map(item=><option key={item.id || item.subject_id || item.user_id} value={item.subject_id || item.user_id || item.id}>{label(item)}</option>)}</select></label><label>Vai trò trong lớp<select aria-label="Vai trò trong lớp" name="role" value={values.role} onChange={event=>change("role",event.target.value)}><option value="STUDENT">Sinh viên</option><option value="INSTRUCTOR">Giảng viên</option></select></label><button>Thêm thành viên</button></>}
        </LearningMetadataForm>}
        {activeMembers.length > 0 && <ul>{activeMembers.map(item=><li key={item.id} className={styles.row}><span>{label(item)} · {item.role === "INSTRUCTOR" ? "Giảng viên" : "Sinh viên"} · {item.status === "INACTIVE" ? "Ngưng phân công" : "Đang tham gia"}</span><button disabled={busy} onClick={()=>void run(async()=>{await reviewedWrite(`/offerings/${offeringId}/members/${item.id}`,{status:item.status === "INACTIVE" ? "ACTIVE" : "INACTIVE",revision:item.revision},"update_member",item.status === "INACTIVE" ? "Khôi phục phân công" : "Ngưng quyền truy cập lớp","PATCH");await refreshCatalogs();})}>{item.status === "INACTIVE" ? "Khôi phục" : "Ngưng phân công"}</button></li>)}</ul>}
        {offeringId && offering?.status === "ACTIVE" && <button disabled={busy} onClick={()=>void run(async()=>{await reviewedWrite(`/offerings/${offeringId}/archive`,{revision:(offering as LearningOffering & {revision:number}).revision},"archive_offering","Lưu trữ lớp học phần");setOfferings(await gateway.offerings(true));})}>Lưu trữ lớp học phần</button>}
      </div></details>}
      {offering && <div className={styles.columns}><aside className={`${styles.panel} ${styles.stack}`}><h2>{t("lwx.33")}</h2>{offering.status === "ARCHIVED" && <p>{t("lwx.34")}</p>}
        {!offering.capabilities.read ? <p>{t("lwx.35")}</p> : !sessions.length ? <p>{t("lwx.36")}</p> : <nav aria-label={t("lwx.37")} className={styles.sessions}>{sessions.map(item=><button key={item.id} aria-pressed={item.id===sessionId} onClick={()=>void run(async()=>{await flushReaderState();setSessionId(item.id);})}>{item.sequence_no}. {item.title}</button>)}</nav>}
        {manageable && <LearningMetadataForm actorId={actorId} draftId={`new-session:${offeringId}`} className={styles.stack} disabled={busy}
          initialValues={{title:""}} basis={{sequence_no:Math.max(0,...sessions.map(item=>item.sequence_no))+1}}
          toPayload={({values,basis})=>({title:values.title.trim(),description:"",sequence_no:basis.sequence_no,starts_at:null})}
          onSave={async(payload,key)=>{
            if(!session.canAccess.current)throw new Error(t("lwx.10"));
            const created=await gateway.write<LearningSession>(`/offerings/${offeringId}/sessions`,payload,"POST",key);
            if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.offeringId===offeringId){
              const rows=await gateway.sessions(offeringId);
              if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.offeringId===offeringId){setSessions(rows);setSessionId(created.id);}
            }
          }}>{(values,change)=><><label>Tên buổi mới<input name="title" required maxLength={200} value={values.title} onChange={event=>change("title",event.target.value)}/></label><button className={styles.primary}>Thêm buổi</button></>}</LearningMetadataForm>}
      </aside><section className={`${styles.panel} ${styles.stack}`} aria-label={t("lwx.38")}><div className={styles.row}><h2>{activeSession?.title || t("lwx.39")}</h2><span>{materials.length} tài liệu</span></div>
        {manageable && <p id="learning-class-timezone" className={styles.muted}>Múi giờ của lớp {timeZone}</p>}
        {manageable && activeSession && <details><summary>Chỉnh sửa buổi học</summary>
          <LearningMetadataForm actorId={actorId} draftId={`session:${activeSession.id}`} className={styles.form} disabled={busy}
            initialValues={{title:activeSession.title,description:activeSession.description??"",starts_at:activeSession.starts_at?classDateTime(activeSession.starts_at,timeZone):""}}
            basis={{revision:activeSession.revision,timeZone}}
            fieldLabels={{title:'Tiêu đề buổi',description:'Mô tả buổi',starts_at:'Thời gian dự kiến'}}
            onRead={async signal=>{
              const rows=await gateway.sessions(offeringId,signal);
              if(signal.aborted||!session.canAccess.current||currentWorkspace.current.actorId!==actorId||currentWorkspace.current.offeringId!==offeringId||currentWorkspace.current.sessionId!==activeSession.id)throw new Error('Phạm vi buổi học đã thay đổi. Nháp vẫn được giữ.');
              const latest=rows.find(row=>row.id===activeSession.id);
              if(!latest)throw new Error('Không còn quyền đọc buổi học để đối chiếu. Nháp vẫn được giữ.');
              return {values:{title:latest.title,description:latest.description??'',starts_at:latest.starts_at?classDateTime(latest.starts_at,timeZone):''},basis:{revision:latest.revision,timeZone}};
            }}
            toPayload={({values,basis})=>({title:values.title.trim(),description:values.description.trim(),starts_at:values.starts_at?classDateTimeToUtc(values.starts_at,String(basis.timeZone)):null,revision:basis.revision})}
            onSave={async payload=>{
              await reviewedWrite(`/sessions/${activeSession.id}`,payload,"update_session","Cập nhật buổi học","PATCH");
              if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.offeringId===offeringId){
                const rows=await gateway.sessions(offeringId);
                if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.offeringId===offeringId)setSessions(rows);
              }
            }}>{(values,change)=><>
            <label>Tiêu đề buổi<input name="title" value={values.title} onChange={event=>change("title",event.target.value)} required/></label><label>Mô tả buổi<textarea name="description" value={values.description} onChange={event=>change("description",event.target.value)}/></label><label>Thời gian dự kiến<input type="datetime-local" name="starts_at" aria-describedby="learning-class-timezone" value={values.starts_at} onChange={event=>change("starts_at",event.target.value)}/></label><button>Xem trước cập nhật</button>
          </>}</LearningMetadataForm><div className={styles.actions}><button disabled={busy||sessions[0]?.id===sessionId} onClick={()=>void run(()=>reorderSession(sessionId,-1))}>Đưa buổi lên</button><button disabled={busy||sessions.at(-1)?.id===sessionId} onClick={()=>void run(()=>reorderSession(sessionId,1))}>Đưa buổi xuống</button></div>
        </details>}
        {manageable&&sessionId&&<details onToggle={event=>{if(event.currentTarget.open)void run(async()=>{const lists=await Promise.all(sessions.map(item=>gateway.materials(item.id)));const unique=new Map(lists.flat().map(item=>[item.id,item]));setLinkCandidates([...unique.values()].filter(item=>!materials.some(current=>current.id===item.id)));});}}><summary>Dùng lại bài giảng của buổi khác</summary><form className={styles.form} onSubmit={event=>{event.preventDefault();const id=formValue(event.currentTarget,"material_id");void run(async()=>{await reviewedWrite(`/sessions/${sessionId}/material-links`,{material_ids:[...materials.map(item=>item.id),id]},"material_links","Liên kết bài giảng vào buổi này","PUT");await reloadMaterials();});}}><label>Tài liệu trong cùng lớp<select aria-label="Tài liệu trong cùng lớp" name="material_id" required><option value="">Chọn tài liệu</option>{linkCandidates.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</select></label><button disabled={busy||!linkCandidates.length}>Thêm liên kết</button></form></details>}
        {sessionId && !materials.length && <p>{t("lwx.40")}</p>}
        <ul className={styles.list}>{materials.map(item=><li key={item.id} className={styles.material}><h3>{item.title}</h3>{item.description && <p>{item.description}</p>}<p className={`${styles.badge} ${item.visibility === "HIDDEN" || !item.current_published_version_id ? styles.badgeMuted : styles.badgeLive}`}>{item.visibility === "HIDDEN" ? "Đang ẩn" : item.current_published_version_id ? "Đã công bố" : "Chưa công bố"}</p>
          {item.current_published_version_id && <button className={styles.primary} disabled={busy} onClick={()=>void run(()=>openVersion(item.current_published_version_id!,undefined,undefined,sessionId))}>{t("lwx.41")}</button>}
          <details><summary>{t("lwx.42")}</summary>{item.versions?.length ? item.versions.map(version=><div className={styles.version} key={version.id}>
            <span>Phiên bản {version.version_no} · {stateLabel(version.processing_state)} · {stateLabel(version.publication_state)}</span>
            {version.source_media_type==='application/vnd.openxmlformats-officedocument.presentationml.presentation'&&<span>{t("lwx.44")}</span>}
            {['FAILED','REJECTED'].includes(version.processing_state)&&<p role="alert">{version.error_detail||t("lwx.45")}</p>}
            {version.publication_state==="QUARANTINED"&&<p role="alert">Tệp này bị cách ly vì không vượt qua kiểm tra an toàn nên đã được ẩn khỏi sinh viên và không thể mở hay công bố. Hãy kiểm tra tệp rồi tải lên một bản mới.</p>}
            {version.processing_state === "READY" && version.publication_state!=="QUARANTINED" && <button disabled={busy} onClick={()=>void run(()=>openVersion(version.id,undefined,undefined,sessionId))}>{version.publication_state === "PUBLISHED" ? "Mở" : "Xem trước"}</button>}
            {manageable && version.processing_state === "READY" && version.publication_state!=="QUARANTINED" && <><button disabled={busy} onClick={()=>void run(()=>publishPreview(version.id,version.publication_state === "PUBLISHED" ? "retract" : "publish"))}>{version.publication_state === "PUBLISHED" ? "Thu hồi" : "Công bố"}</button>
              {version.publication_state !== "PUBLISHED" && <LearningMetadataForm actorId={actorId} draftId={`publication-schedule:${version.id}`} className={styles.form} disabled={busy} clearOnSuccess={false}
                initialValues={{scheduled_at:""}} basis={{timeZone}} toPayload={({values,basis})=>({scheduled_at:classDateTimeToUtc(values.scheduled_at,String(basis.timeZone))})}
                onSave={payload=>publishPreview(version.id,"publish",String(payload.scheduled_at))}>
                {(values,change)=><><label>Hẹn giờ công bố<input name="scheduled_at" type="datetime-local" aria-describedby="learning-class-timezone" required value={values.scheduled_at} onChange={event=>change("scheduled_at",event.target.value)}/></label><button>Xem trước lịch</button></>}
              </LearningMetadataForm>}
              {version.publication_state === "SCHEDULED" && <button disabled={busy} onClick={()=>void run(()=>publishPreview(version.id,"cancel-publication"))}>Hủy lịch công bố</button>}
              {version.schedule_error === "CHANGE_SET_STALE" && <p role="status">Lịch đã dừng do mô tả hoặc bản trước thay đổi. Hãy xem trước lại.</p>}
              {version.capabilities?.version_changes && version.publication_state !== "RETRACTED" && <VersionChangeEditor
                key={`${actorId}:${version.id}`} actorId={actorId} version={version} material={item}
                onSave={(payload, key) => version.publication_state === "PUBLISHED"
                  ? reviewedWrite<LearningVersionChangeSet>(`/versions/${version.id}/change-set`, payload,
                    "version-change-save", `Đính chính mô tả của bản ${version.version_no}`, "PUT")
                  : gateway.write<LearningVersionChangeSet>(`/versions/${version.id}/change-set`, payload, "PUT",
                    key, { "X-Campus-Reader-Actor": actorId })}
              />}
            </>}
          </div>) : <p>{t("lwx.43")}</p>}</details>
          {manageable && <details><summary>Chỉnh sửa thông tin học liệu</summary><LearningMetadataForm actorId={actorId} draftId={`material:${item.id}`} className={styles.form} disabled={busy}
            initialValues={{title:item.title,description:item.description??"",visibility:item.visibility}} basis={{revision:item.revision}}
            fieldLabels={{title:'Tiêu đề',description:'Mô tả',visibility:'Hiển thị'}}
            valueLabels={{visibility:{VISIBLE:'Hiển thị trong lớp',HIDDEN:'Ẩn với sinh viên'}}}
            onRead={async signal=>{
              const rows=await gateway.materials(sessionId,signal);
              if(signal.aborted||!session.canAccess.current||currentWorkspace.current.actorId!==actorId||currentWorkspace.current.sessionId!==sessionId)throw new Error('Phạm vi học liệu đã thay đổi. Nháp vẫn được giữ.');
              const latest=rows.find(row=>row.id===item.id);
              if(!latest)throw new Error('Không còn quyền đọc học liệu để đối chiếu. Nháp vẫn được giữ.');
              return {values:{title:latest.title,description:latest.description??'',visibility:latest.visibility},basis:{revision:latest.revision}};
            }}
            toPayload={({values,basis})=>({...values,title:values.title.trim(),description:values.description.trim(),revision:basis.revision})}
            onSave={async payload=>{
              await reviewedWrite(`/materials/${item.id}`,payload,"hide_material","Cập nhật thông tin và quyền xem bài","PATCH");
              if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.sessionId===sessionId){
                const rows=await gateway.materials(sessionId);
                if(currentWorkspace.current.actorId===actorId&&currentWorkspace.current.sessionId===sessionId)setMaterials(rows);
              }
            }}>{(values,change)=><><label>Tiêu đề<input name="title" value={values.title} onChange={event=>change("title",event.target.value)} required/></label><label>Mô tả<textarea name="description" value={values.description} onChange={event=>change("description",event.target.value)}/></label><label>Hiển thị<select aria-label="Hiển thị" name="visibility" value={values.visibility} onChange={event=>change("visibility",event.target.value)}><option value="VISIBLE">Hiển thị trong lớp</option><option value="HIDDEN">Ẩn với sinh viên</option></select></label><button>Xem trước thay đổi</button></>}</LearningMetadataForm></details>}
          {manageable&&<div className={styles.actions}><button disabled={busy||materials[0]?.id===item.id} onClick={()=>void run(()=>reorderMaterial(item.id,-1))}>Đưa bài lên</button><button disabled={busy||materials.at(-1)?.id===item.id} onClick={()=>void run(()=>reorderMaterial(item.id,1))}>Đưa bài xuống</button></div>}
          {manageable && <details><summary>{t("lwx.55")}</summary><LearningUploadForm actorId={actorId} draftId={`version-upload:${item.id}`} existing accept={uploadAccept} pptxEnabled={pptxEnabled} disabled={busy}
            maxBytes={capabilities?.max_file_bytes||capabilities?.limits?.max_file_bytes||50*1024*1024} onUpload={(draft,file,signal,onIntent)=>upload(draft,file,signal,onIntent,item.id)} onAccepted={acceptedUpload}
            onCancelIntent={id=>gateway.write(`/upload-intents/${id}/abort`,{})}/></details>}
        </li>)}</ul>
        {manageable && sessionId && <details><summary>{pptxEnabled?'Thêm bài giảng PDF hoặc PowerPoint':'Thêm bài giảng PDF'}</summary><LearningUploadForm actorId={actorId} draftId={`new-upload:${offeringId}:${sessionId}`} existing={false} accept={uploadAccept} pptxEnabled={pptxEnabled} disabled={busy}
          maxBytes={capabilities?.max_file_bytes||capabilities?.limits?.max_file_bytes||50*1024*1024} onUpload={upload} onAccepted={acceptedUpload}
          onCancelIntent={id=>gateway.write(`/upload-intents/${id}/abort`,{})}/><p className={styles.muted}>{pptxEnabled?'PDF hoặc PPTX':'PDF'} tối đa {Math.round((capabilities?.max_file_bytes || capabilities?.limits?.max_file_bytes || 50*1024*1024)/1024/1024)} MiB. {pptxEnabled&&'PowerPoint được chuyển thành PDF để đọc; bản gốc được giữ riêng. '}Sau khi kiểm tra, hãy xem trước và công bố.</p></details>}
        {sessionId&&<ReadingInstructions key={`instruction:${actorId}:${sessionId}`} sessionId={sessionId} materials={materials} canManage={manageable}
          actorId={actorId || undefined} onRows={exitEnabled ? acceptInstructionRows : undefined}
          exitTickets={exitEnabled ? exitTickets : undefined} onExitTicket={exitEnabled ? selectExitTicket : undefined}
          onOpen={(id,page)=>void run(()=>openVersion(id,page,undefined,sessionId))}/>}
        {activeSession && actorId && exitEnabled && <SessionExitTickets key={`exit:${actorId}:${sessionId}`} actorId={actorId}
          sessionId={sessionId} materials={materials} instructions={instructions} zoneId={offering?.timezone || CAMPUS_TIMEZONE}
          canManage={manageable} source={exitReaderSource} refresh={exitRevision} onRows={acceptExitRows} onSelect={selectExitTicket} />}
        {activeSession && actorId && offering?.capabilities.practice && <SessionPracticeSets key={`practice:${actorId}:${sessionId}`} actorId={actorId}
          sessionId={sessionId} materials={materials} canManage={manageable} />}
        {activeSession && offering?.capabilities.page_feedback && <SessionPageFeedback
          key={`feedback:${actorId}:${activeSession.id}`} actorId={actorId} sessionId={activeSession.id}
          startsAt={activeSession.starts_at} timeZone={timeZone} canOpen={manageable}
          onConfigure={closesAt => reviewedWrite(`/sessions/${activeSession.id}/page-feedback-window`,
            { closes_at: closesAt }, "feedback-window-open",
            `Mở báo vướng cho ${activeSession.title} đến ${classDateTime(closesAt, timeZone).replace("T", " ")} (${timeZone})`, "PUT")}
          onOpen={(versionId, page) => void run(() => openVersion(versionId, page, undefined, activeSession.id))}
        />}
        {activeSession && offering?.capabilities.page_explanations && actorId && <PageExplanations
          key={`explanations:${actorId}:${activeSession.id}`} actorId={actorId} sessionId={activeSession.id} materials={materials} canManage={manageable}
          readerSource={readerId && readerSessionId === activeSession.id ? { versionId: readerId, page: readerPage } : undefined}
          onPublish={draft => reviewedWrite(`/page-explanations/${draft.id}`, { revision: draft.revision, publish: true },
            "page-explanation-update", `Công bố lời giải chung cho ${activeSession.title}`, "PATCH")}
          onOpen={(versionId, page) => void run(() => openVersion(versionId, page, undefined, activeSession.id))}
        />}
      </section></div>}
      {(reader || exitTicketId) && <div className={reader && exitTicketId ? styles.exitReaderColumns : undefined}>
      {reader && <section id="learning-reader" tabIndex={-1} className={styles.reader} aria-label={t("lwx.46")}>
        <div className={styles.row}><h2>{reader.title}</h2><span>Phiên bản {reader.version_no}</span><button onClick={()=>void run(async()=>{await flushReaderState();setReader(null);})}>{t("lwx.47")}</button></div>
        {readerId && reader.capabilities.page_feedback && actorId && <StudentPageFeedback
          key={`${actorId}:${readerId}:${readerGeneration}`} actorId={actorId} versionId={readerId}
          versionNumber={reader.version_no} pageNo={readerPage} sourceSessionId={readerSessionId} timeZone={timeZone}
        />}
        {readerId && reader.capabilities.version_changes && reader.publication_state === "PUBLISHED" && actorId && <VersionChangeBanner
          key={`${actorId}:${readerId}:${readerGeneration}`} actorId={actorId} versionId={readerId}
          onOpen={(versionId, page) => void run(() => openVersion(versionId, page, undefined, readerSessionId))}
        />}
        {exitEnabled && exitReaderSource && exitTickets.map(ticket => ticket.state !== "SOURCE_UNAVAILABLE"
          && ticket.state !== "DRAFT" && ticket.version_id === readerId && ticket.page_no === readerPage
          && <button type="button" key={ticket.id} onClick={() => selectExitTicket(ticket.id)}>Mở phiếu ra lớp · {ticket.question}</button>)}
        <button disabled={busy} onClick={()=>void run(async()=>{
          const note=annotations.find(item=>item.id===anchorId&&item.version_id===readerId&&item.page_no===readerPage);
          const url=new URL(linkPath({version_id:readerId!,page_no:readerPage,anchor_id:note?.id,session_id:readerSessionId}),window.location.origin);
          await navigator.clipboard.writeText(url.href);setNotice(t("lwx.48"));
        })}>{t("lwx.49")}</button>
        {reader.publication_state==="PUBLISHED"&&reader.current_published_version_id&&reader.current_published_version_id!==readerId&&
          <div className={styles.alert}><p role="status">{t("lwx.50")}</p><button disabled={busy} onClick={()=>void run(()=>openVersion(reader.current_published_version_id!,undefined,undefined,readerSessionId))}>Mở bản hiện hành</button></div>}
        {syncIssue === "conflict" && <div role="alert" className={styles.alert}><p>{t("lwx.51")}</p><button disabled={busy} onClick={()=>void run(()=>resolveReaderConflict(false))}>Dùng vị trí đã đồng bộ</button><button disabled={busy} onClick={()=>void run(()=>resolveReaderConflict(true))}>Giữ vị trí trên thiết bị này</button></div>}
        {syncIssue === "retry" && <div role="status" className={styles.alert}>{t("lwx.52")}<button disabled={busy} onClick={() => void flushReaderState()}>{t("lwx.53")}</button></div>}
        <LearningPresentation key={`${reader.offering_id||offeringId}:${reader.version_id||reader.id}`} offeringId={reader.offering_id||offeringId} versionId={reader.version_id||reader.id} actorId={actorId} canManage={reader.capabilities.manage} pageNo={readerPage} onPresentation={setPresentation}/>
        {readerId && reader.capabilities.idea_cards && <button type="button"
          onClick={() => beginIdea({ version_id: readerId, page_no: readerPage, anchor: { kind: "PAGE" } })}>{t("lwx.54")}</button>}
        {actorId && readerId && (reader.capabilities.accessible_text || reader.capabilities.manage_accessible_text)
          ? <AccessibleText key={`ocr:${actorId}:${readerId}`} actorId={actorId} versionId={readerId} pageCount={reader.page_count} sourcePage={readerPage}
            canRead={!!reader.capabilities.accessible_text} canManage={!!reader.capabilities.manage_accessible_text}
            published={reader.publication_state === "PUBLISHED"} onSource={openOcrSource} confirmWrite={reviewedWrite}>
              {pdfReader}
            </AccessibleText>
          : pdfReader}
        <LearningDiscussion key={reader.version_id||reader.id} versionId={reader.version_id||reader.id} renditionId={reader.rendition_id} selection={selection} canManage={reader.capabilities.manage} canShareNotes={reader.publication_state === "PUBLISHED"} actorId={actorId} onSource={page=>void run(async()=>{await openVersion(reader.version_id||reader.id,page,undefined,readerSessionId);document.getElementById("learning-reader")?.focus();})} onAnnotationsChange={setAnnotations}/>
        <LearningExplanation actorId={actorId} versionId={reader.version_id||reader.id} selection={selection} available={reader.capabilities.explain===true} onSource={(id,page)=>void run(()=>openVersion(id,page))}/>
      </section>}
      {exitTicketId && <ExitTicketDetail key={`${actorId}:${exitTicketId}`} actorId={actorId} ticketId={exitTicketId}
        staff={exitStaff} canManage={manageable} materials={materials} instructions={instructions}
        zoneId={offering?.timezone || CAMPUS_TIMEZONE} readerSource={exitReaderSource}
        onClose={closeExitTicket} onOpen={openExitSource} onChange={() => setExitRevision(current => current + 1)}
        confirmWrite={reviewedWrite} />}
      </div>}
      {actorId && capabilities?.idea_cards === true && <IdeaCards
        key={`ideas:${actorId}`} actorId={actorId} canCreate={role === "student" || offering?.member_role === "STUDENT"} sourceRequest={ideaDraftRequest}
        onOpen={source => void run(() => openIdeaSource(source))}
        onShare={(cardId, revision, recipientIds) => reviewedWrite(`/me/idea-cards/${cardId}/shares`,
          { revision, recipient_ids: recipientIds }, "idea-share-create", "Chia sẻ phiếu ý tưởng")}
      />}
    </>}
    <AccessibleDialog open={!!preview} onClose={()=>setPreview(null)} preventClose={busy} labelledBy="learning-publication-title" className={styles.dialog}>
      <h2 id="learning-publication-title">{t("lwx.57")} {preview?.action === "retract" ? "thu hồi" : preview?.action === "cancel-publication" ? "hủy lịch công bố" : "công bố"} học liệu</h2>
      <p>Lớp {preview?.context.offeringTitle}. Buổi {preview?.context.sessionTitle}.</p>
      <p>{preview?.context.materialTitle} · Phiên bản {preview?.context.versionNo}.</p>
      <p>{preview?.action === "retract" ? "Sinh viên sẽ không mở được phiên bản này qua cả liên kết cũ sau khi thu hồi."
        : preview?.action === "cancel-publication" ? "Phiên bản sẽ trở về bản nháp và lịch công bố được hủy."
        : preview?.scheduledAt ? `Tài liệu sẽ được công bố lúc ${new Date(preview.scheduledAt).toLocaleString("vi-VN", {timeZone:preview.context.timeZone})} (${preview.context.timeZone}).`
        : "Sinh viên của lớp sẽ được mở phiên bản này ngay sau khi công bố."}</p>
      {preview?.preview.change_set && <ChangeDetails change={preview.preview.change_set} />}
      {preview?.action === "retract" && preview.preview.retraction?.is_current && <label>
        Bản hiện hành sau khi thu hồi
        <select value={preview.replacementId ?? ""} disabled={busy} onChange={event => {
          const replacement = event.target.value || undefined;
          void run(() => publishPreview(preview.versionId, "retract", undefined, replacement));
        }}>
          <option value="">Tạm thời chưa có bản hiện hành</option>
          {preview.preview.retraction.candidates.map(candidate => (
            <option key={candidate.id} value={candidate.id}>Phiên bản {candidate.version_no} đã công bố</option>
          ))}
        </select>
      </label>}
      <label><span><input type="checkbox" checked={confirmed} disabled={busy} onChange={event=>setConfirmed(event.target.checked)}/> Tôi đã kiểm tra lớp, tài liệu và tác động của thao tác.</span></label>
      <div className={styles.row}><button disabled={busy} onClick={()=>setPreview(null)}>{t("lwx.56")}</button><button disabled={busy||!confirmed} onClick={()=>void run(applyPublication)}>{t("lwx.57")}</button></div>
    </AccessibleDialog>
    <AccessibleDialog open={!!management} onClose={cancelManagement} preventClose={managementSubmitting} labelledBy="learning-management-title" className={styles.dialog}>
      <h2 id="learning-management-title">{management?.title}</h2>{management?.context.offering && <p>Lớp của thao tác: {management.context.offering}.{management.context.session&&` Buổi: ${management.context.session}.`}</p>}
      {management?.preview.page_explanation ? <div>
        <p>{t(explanationLabels[management.preview.page_explanation.category])} · Trang {management.preview.page_explanation.page_no}</p>
        <p style={{ whiteSpace: "pre-wrap" }}>{management.preview.page_explanation.body}</p>
        <p>Lời giải này sẽ hiển thị cho thành viên còn quyền đọc tài liệu trong buổi.</p>
      </div> : management?.preview.change_set ? <ChangeDetails change={management.preview.change_set} />
      : management?.preview.exit_ticket ? <ExitTicketPreviewDetails preview={management.preview.exit_ticket} />
      : management?.preview.exit_review ? <div>
        <p>Lời giải sẽ hiển thị cho thành viên còn quyền đọc phiếu.</p>
        <p className={styles.exitAnswer}>{management.preview.exit_review.explanation}</p>
      </div> : management?.preview.idea_share ? <IdeaShareSummary value={management.preview.idea_share} />
      : management?.preview.ocr_release ? <OcrReleasePreview value={management.preview.ocr_release} /> : <>
        <dl>{Object.entries(management?.payload || {}).filter(([key])=>key!=="revision").map(([key,value])=><div key={key}><dt>{fieldLabels[key] || "Thông tin"}</dt><dd>{catalogs.terms.concat(catalogs.courses,catalogs.actors).find(item=>[item.id,item.subject_id,item.user_id].includes(String(value))) ? label(catalogs.terms.concat(catalogs.courses,catalogs.actors).find(item=>[item.id,item.subject_id,item.user_id].includes(String(value)))!) : (typeof value==="string"&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}.*Z$/.test(value)?`${classDateTime(value,timeZone).replace("T"," ")} (${timeZone})`:String(value ?? "Không đặt"))}</dd></div>)}</dl>
        <p>{({
          create_term:'Bản ghi mới chưa được tạo. Kiểm tra thông tin trước khi xác nhận.',
          create_course:'Bản ghi mới chưa được tạo. Kiểm tra thông tin trước khi xác nhận.',
          create_offering:'Bản ghi mới chưa được tạo. Kiểm tra thông tin trước khi xác nhận.',
          update_session:'Cập nhật tiêu đề, mô tả hoặc thời gian buổi học theo thông tin đã xem trước.',
          order_sessions:'Cập nhật thứ tự buổi học trong lớp. Nội dung và lịch sử buổi học được giữ lại.',
          material_links:'Cập nhật danh sách hoặc thứ tự bài giảng được liên kết với buổi học này.',
          add_member:'Phân công tài khoản đã chọn vào lớp theo vai trò đã xem trước.',
          update_member:'Thay đổi trạng thái phân công có thể thay đổi quyền truy cập lớp của thành viên này.',
          archive_offering:'Lưu trữ lớp học phần có thể làm thay đổi quyền truy cập lớp. Nội dung và lịch sử được giữ lại.',
          hide_material:'Cập nhật thông tin và trạng thái hiển thị bài giảng. Ẩn bài có thể làm sinh viên không mở được tài liệu.',
        } as Record<string,string>)[management?.action??'']??'Kiểm tra nội dung, phạm vi và tác động của thao tác trước khi xác nhận.'}</p>
      </>}
      <label><span><input type="checkbox" checked={managementConfirmed} onChange={event=>setManagementConfirmed(event.target.checked)}/> Tôi đã kiểm tra thông tin và tác động.</span></label>
      <div className={styles.row}><button disabled={managementSubmitting} onClick={cancelManagement}>{t("lwx.56")}</button><button disabled={managementSubmitting||!managementConfirmed} onClick={()=>void confirmManagement()}>Xác nhận thay đổi</button></div>
    </AccessibleDialog>
  </div></AppShell></PreservedActivity></>;
}
