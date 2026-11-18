"use client";

import React, { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy, RenderTask, TouchManager } from "pdfjs-dist";
import type { PDFViewer, PDFLinkService, PDFFindController, EventBus } from "pdfjs-dist/web/pdf_viewer.mjs";
import "pdfjs-dist/web/pdf_viewer.css";
import "./learning-reader.css";
import { rectFromClient, rotateAnchorRect, type ReaderAnnotation, type ReaderSelection } from "./reader-anchors";
import { authenticatedPdfRange } from "./authenticated-range";
import { AccessibleDialog } from "../../../components/shared/AccessibleDialog";
import styles from "../learning.module.css";
export type { ReaderAnnotation, ReaderSelection, ReaderAnchor } from "./reader-anchors";

export interface ReaderState {
  page_no: number;
  offset_x: number;
  offset_y: number;
  scroll_mode: "vertical" | "horizontal" | "page";
  zoom_mode: "custom" | "page-width" | "page-fit";
  zoom_value: number;
  rotation: number;
}

export interface LearningReaderVersion {
  version_id: string;
  title: string;
  content_path: string;
  page_count?: number;
  has_text_layer?: boolean;
  download_allowed?: boolean;
  download_path?: string;
  capabilities?: { download?: boolean };
}

export interface LearningPdfReaderProps {
  version: LearningReaderVersion;
  initialState?: Partial<ReaderState> | null;
  bookmarks?: { id: string; page_no: number; label?: string }[];
  onStateChange?: (state: ReaderState) => void | Promise<void>;
  onBookmark?: (page: number, label?: string) => void | Promise<void>;
  annotations?: ReaderAnnotation[];
  citation?: ReaderSelection;
  navigation?: { sequence: number; page: number };
  focusedAnnotationId?: string;
  onSelection?: (selection: ReaderSelection) => void;
  onIdeaSelection?: (selection: ReaderSelection) => void;
  onAnnotationClick?: (annotation: ReaderAnnotation) => void;
  presentation?: { presentation_id?: string; version_id: string; page_no: number; sequence: number; active?: boolean } | null;
  onPageChange?: (page: number) => void;
  accessAllowed?: boolean;
  onAccessDenied?: () => void;
  className?: string;
}

type ReaderRuntime = { viewer: PDFViewer; links: PDFLinkService; find: PDFFindController; bus: EventBus; doc: PDFDocumentProxy };
type OutlineEntry = { title: string; dest: string | unknown[] | null; depth: number };
const scrollModes = { vertical: 0, horizontal: 1, page: 3 } as const;
const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value));

export function validatePdfSource(source: string, origin: string): string {
  const url=new URL(source,origin);
  if(url.origin!==origin||!["http:","https:"].includes(url.protocol)||url.username||url.password)throw new Error("PDF source must use the Campus origin");
  return url.href;
}

function readPosition(rt:ReaderRuntime,host:HTMLDivElement):ReaderState {
  const page=rt.viewer.getPageView(rt.viewer.currentPageNumber-1)?.div,value=rt.viewer.currentScaleValue;
  return {page_no:rt.viewer.currentPageNumber,offset_x:page?clamp((host.scrollLeft-page.offsetLeft)/Math.max(1,page.clientWidth),0,1):0,offset_y:page?clamp((host.scrollTop-page.offsetTop)/Math.max(1,page.clientHeight),0,1):0,
    scroll_mode:rt.viewer.scrollMode===1?"horizontal":rt.viewer.scrollMode===3?"page":"vertical",zoom_mode:value==="page-width"||value==="page-fit"?value:"custom",zoom_value:clamp(rt.viewer.currentScale,0.5,3),rotation:rt.viewer.pagesRotation};
}

export function normalizeReaderState(state: Partial<ReaderState> | null | undefined, pageCount: number): ReaderState {
  const finite = (value: number | undefined, fallback: number) => Number.isFinite(value) ? value! : fallback;
  return {
    page_no: Math.trunc(clamp(finite(state?.page_no, 1), 1, Math.max(1, pageCount))),
    offset_x: clamp(finite(state?.offset_x, 0), 0, 1), offset_y: clamp(finite(state?.offset_y, 0), 0, 1),
    scroll_mode: state?.scroll_mode && state.scroll_mode in scrollModes ? state.scroll_mode : "vertical",
    zoom_mode: ["page-width", "page-fit", "custom"].includes(state?.zoom_mode || "") ? state!.zoom_mode! : "page-width",
    zoom_value: clamp(finite(state?.zoom_value, 1), 0.5, 3),
    rotation: [0, 90, 180, 270].includes(state?.rotation ?? -1) ? state!.rotation! : 0,
  };
}

function PageThumbnail({ doc, pageNo, selected, onSelect }: { doc: PDFDocumentProxy; pageNo: number; selected: boolean; onSelect: () => void }) {
  const button = useRef<HTMLButtonElement>(null), canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!button.current) return;
    let disposed = false, task: RenderTask | undefined;
    const observer = new IntersectionObserver(async ([entry]) => {
      if (!entry.isIntersecting || disposed || !canvas.current) { task?.cancel(); return; }
      try {
        const page = await doc.getPage(pageNo);
        if (disposed || !canvas.current) return;
        const viewport = page.getViewport({ scale: 100 / page.getViewport({ scale: 1 }).width });
        canvas.current.width = Math.ceil(viewport.width); canvas.current.height = Math.ceil(viewport.height);
        task = page.render({ canvas: canvas.current, viewport }); await task.promise;
      } catch { /* Main viewer owns load failures. A thumbnail may be cancelled when hidden. */ }
    }, { rootMargin: "100px" });
    observer.observe(button.current);
    return () => { disposed = true; observer.disconnect(); task?.cancel(); };
  }, [doc, pageNo]);
  return <button ref={button} type="button" className="learning-reader-thumbnail" aria-label={`Đến trang ${pageNo}`} aria-current={selected ? "page" : undefined} onClick={onSelect}><canvas ref={canvas} aria-hidden="true" /><span>Trang {pageNo}</span></button>;
}

export function LearningPdfReader({ version, initialState, bookmarks = [], onStateChange, onBookmark, annotations = [], citation, navigation, focusedAnnotationId, onSelection, onIdeaSelection, onAnnotationClick, presentation, onPageChange, accessAllowed=true, onAccessDenied, className = "" }: LearningPdfReaderProps) {
  const shell = useRef<HTMLElement>(null), container = useRef<HTMLDivElement>(null), pages = useRef<HTMLDivElement>(null);
  const runtime = useRef<ReaderRuntime | null>(null);
  const callbacks = useRef({ onStateChange, onBookmark }); callbacks.current = { onStateChange, onBookmark };
  const annotationCallback = useRef(onAnnotationClick); annotationCallback.current = onAnnotationClick;
  const presentationCallbacks=useRef({onPageChange,onAccessDenied});presentationCallbacks.current={onPageChange,onAccessDenied};
  const followingRef=useRef(false),personalPosition=useRef<ReaderState|null>(null),lastPresentationSequence=useRef(-1);
  const followedPresentation=useRef<string|undefined>(undefined);
  const seed = useRef(initialState); seed.current = initialState;
  const [status, setStatus] = useState("Đang mở bài giảng…"), [error, setError] = useState("");
  const [rangePaused, setRangePaused] = useState(false);
  const [externalUrl, setExternalUrl] = useState<string | null>(null);
  const retryRange = useRef<(() => void) | null>(null);
  const [ready, setReady] = useState(false), [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [current, setCurrent] = useState(1), [count, setCount] = useState(version.page_count ?? 0);
  const [mode, setMode] = useState<ReaderState["scroll_mode"]>("vertical"), [scale, setScale] = useState(1);
  const [query, setQuery] = useState(""), [matches, setMatches] = useState("");
  const [sidebar, setSidebar] = useState<"pages" | "outline" | "bookmarks" | null>(null), [outline, setOutline] = useState<OutlineEntry[]>([]);
  const [bookmarkLabel, setBookmarkLabel] = useState("");
  const [bookmarkSaving, setBookmarkSaving] = useState(false);
  const [focused, setFocused] = useState(false), [retry, setRetry] = useState(0);
  const [regionMode, setRegionMode] = useState(false), [selection, setSelection] = useState<ReaderSelection | null>(null);
  const [paint, setPaint] = useState(0);
  const [following,setFollowing]=useState(false);
  const [toolsExpanded, setToolsExpanded] = useState(false);
  const drag = useRef<{page:HTMLElement; x:number; y:number; pointer:number} | null>(null);

  useEffect(() => {
    if (!container.current || !pages.current) return;
    let disposed = false, timer: ReturnType<typeof setTimeout> | undefined;
    const rangeController = new AbortController();
    let task: import("pdfjs-dist").PDFDocumentLoadingTask | undefined;
    let observer: ResizeObserver | undefined;
    let touchManager: TouchManager | undefined;
    let accessTimer:ReturnType<typeof setInterval>|undefined;
    retryRange.current = null;
    setRangePaused(false);
    setReady(false); setDoc(null); setError(""); setStatus("Đang mở bài giảng…"); setOutline([]); setSelection(null);followingRef.current=false;setFollowing(false);personalPosition.current=null;
    const host = container.current, pageHost = pages.current;
    if(!accessAllowed){setError("Bạn không còn quyền đọc bài giảng này.");setStatus("");pageHost.replaceChildren();return;}
    const emit = () => {
      const rt = runtime.current; if (!rt || disposed || followingRef.current) return;
      const state=readPosition(rt,host);
      void Promise.resolve(callbacks.current.onStateChange?.(state)).catch(() => setStatus("Vị trí đọc chưa được đồng bộ. Bạn vẫn có thể tiếp tục đọc."));
    };
    const schedule = () => { if (timer) clearTimeout(timer); timer = setTimeout(emit, 250); };
    void (async () => {
      // Import sequentially: viewer reads the PDF.js instance initialized by the core module.
      const pdfjs = await import("pdfjs-dist");
      const { EventBus, PDFViewer, PDFLinkService, PDFFindController } = await import("pdfjs-dist/web/pdf_viewer.mjs");
      if (disposed) return;
      pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
      const bus = new EventBus(), links = new PDFLinkService({ eventBus: bus });
      links.addLinkAttributes = (link, url) => {
        let destination: URL;
        try { destination = new URL(url); } catch { return; }
        if (!["http:", "https:"].includes(destination.protocol) || destination.username || destination.password) return;
        link.href = "#";
        link.title = `Liên kết ngoài tới ${destination.host}`;
        link.onclick = event => {
          event.preventDefault();
          if (document.fullscreenElement) void document.exitFullscreen().catch(() => {});
          setExternalUrl(destination.href);
        };
      };
      const find = new PDFFindController({ eventBus: bus, linkService: links });
      const viewer = new PDFViewer({ container: host, viewer: pageHost, eventBus: bus, linkService: links, findController: find,
        textLayerMode: 1, annotationMode: 1, maxCanvasPixels: 16 * 1024 * 1024, supportsPinchToZoom: true });
      links.setViewer(viewer);
      touchManager = new pdfjs.TouchManager({container:host,signal:rangeController.signal,
        isPinchingDisabled:()=>!runtime.current||Boolean(drag.current),
        onPinching:(origin:number[],previous:number,next:number,dx:number,dy:number)=>{
          if(previous<=0)return;
          const factor=clamp(viewer.currentScale*next/previous,0.5,3)/viewer.currentScale;
          viewer.updateScale({scaleFactor:factor,origin,pan:[dx,dy],drawingDelay:100});
        },
        onPanning:(dx:number,dy:number)=>host.scrollBy({left:-dx,top:-dy}),
      });
      const source=validatePdfSource(version.content_path,window.location.origin);
      const range = await authenticatedPdfRange(pdfjs, source, {
        signal: rangeController.signal,
        onPause: retryPending => {
          if (disposed) return;
          retryRange.current = retryPending;
          setRangePaused(retryPending !== null);
        },
        onError: () => {
        if (disposed) return;
        viewer.setDocument(null); links.setDocument(null); runtime.current = null;
        setReady(false); setDoc(null); setError("Chưa đọc được PDF hoặc quyền truy cập đã thay đổi. Hãy mở lại bài giảng.");
        void task?.destroy();
        },
      });
      if (disposed) { range.abort(); return; }
      task = pdfjs.getDocument({ url: source, range, withCredentials: true, enableXfa: false, disableStream: true, disableAutoFetch: true, rangeChunkSize: 262144 });
      task.onPassword = () => { setError("PDF có mật khẩu chưa được hỗ trợ. Hãy liên hệ giảng viên để nhận bản có thể đọc."); void task?.destroy(); };
      const pdf = await task.promise; if (disposed) { await task.destroy(); return; }
      runtime.current = { viewer, links, find, bus, doc: pdf }; setDoc(pdf); setCount(pdf.numPages);
      bus.on("pagesinit", () => {
        if (disposed) return;
        const saved = normalizeReaderState(seed.current, pdf.numPages);
        viewer.scrollMode = scrollModes[saved.scroll_mode]; viewer.pagesRotation = saved.rotation;
        viewer.currentScaleValue = saved.zoom_mode === "custom" ? String(saved.zoom_value) : saved.zoom_mode;
        viewer.currentPageNumber = saved.page_no; setMode(saved.scroll_mode); setCurrent(saved.page_no);
        requestAnimationFrame(() => {
          if (disposed) return;
          const page = viewer.getPageView(saved.page_no - 1)?.div;
          if (page) { host.scrollTop = page.offsetTop + saved.offset_y * page.clientHeight; host.scrollLeft = page.offsetLeft + saved.offset_x * page.clientWidth; }
          setReady(true); setStatus("");
        });
      });
      bus.on("pagechanging", ({ pageNumber }: { pageNumber: number }) => { if (!disposed) { setCurrent(pageNumber);presentationCallbacks.current.onPageChange?.(pageNumber); schedule(); } });
      bus.on("scalechanging", ({ scale: next }: { scale: number }) => { if (!disposed) { setScale(next); schedule(); } });
      bus.on("pagerendered", () => { if (!disposed) setPaint(v=>v+1); });
      bus.on("rotationchanging", () => { schedule(); if (!disposed) setPaint(v=>v+1); }); bus.on("scrollmodechanged", schedule); bus.on("updateviewarea", schedule);
      bus.on("updatefindmatchescount", ({ matchesCount }: { matchesCount: { current: number; total: number } }) => { if (!disposed) setMatches(`${matchesCount.current}/${matchesCount.total} kết quả`); });
      bus.on("updatefindcontrolstate", ({ state }: { state: number }) => { if (!disposed && state === 1) setMatches("Không tìm thấy văn bản"); });
      viewer.setDocument(pdf); links.setDocument(pdf);
      const verifyAccess=async()=>{
        if(disposed||!runtime.current)return;
        try{const response=await fetch(source,{method:"HEAD",credentials:"same-origin",cache:"no-store"});
          if(!disposed&&[401,403,404].includes(response.status)){if(accessTimer)clearInterval(accessTimer);viewer.setDocument(null);links.setDocument(null);runtime.current=null;setDoc(null);setReady(false);setSelection(null);setError("Bạn không còn quyền đọc bài giảng này. Hãy kiểm tra lại lớp học và phiên đăng nhập.");void task?.destroy();presentationCallbacks.current.onAccessDenied?.();}
        }catch{ /* A temporary network failure does not grant more access or claim a revoked session. */ }
      };
      accessTimer=setInterval(()=>void verifyAccess(),30000);host.addEventListener("learning-check-access",verifyAccess);
      window.addEventListener("focus",verifyAccess);
      const removeAccessCheck=()=>{host.removeEventListener("learning-check-access",verifyAccess);window.removeEventListener("focus",verifyAccess);};
      bus.on("pagesdestroy",removeAccessCheck);
      const tree = await pdf.getOutline();
      if (!disposed && tree) {
        const flattened: OutlineEntry[] = [];
        const flatten = (items: typeof tree, depth: number) => { for (const item of items) { if (flattened.length >= 500) return; flattened.push({ title: item.title, dest: item.dest, depth }); if (depth < 5 && item.items?.length) flatten(item.items, depth + 1); } };
        flatten(tree, 0); setOutline(flattened);
      }
      observer = new ResizeObserver(() => {
        // On narrow screens the text pane hides the PDF. Fitting a zero-size
        // viewport distorts page offsets and can move a source jump to another page.
        if (!host.clientWidth || !host.clientHeight) return;
        const scale = viewer.currentScaleValue;
        if (scale === "page-width" || scale === "page-fit") viewer.currentScaleValue = scale;
        viewer.update();
      });
      observer.observe(host);
    })().catch(() => { if (!disposed) { setError("Chưa mở được bài giảng. Kiểm tra kết nối và quyền truy cập rồi thử lại."); setStatus(""); } });
    const flush = () => emit();
    const reconnect = () => retryRange.current?.();
    host.addEventListener("scroll", schedule);
    window.addEventListener("pagehide", flush);
    window.addEventListener("online", reconnect);
    return () => { emit(); disposed = true; touchManager?.destroy(); rangeController.abort(); if (timer) clearTimeout(timer);if(accessTimer)clearInterval(accessTimer); observer?.disconnect(); host.removeEventListener("scroll", schedule); window.removeEventListener("pagehide", flush); window.removeEventListener("online", reconnect); runtime.current?.viewer.setDocument(null); runtime.current?.links.setDocument(null); runtime.current = null; void task?.destroy(); };
  }, [version.version_id, version.content_path, retry,accessAllowed]);

  const stopFollowing=()=>{
    const rt=runtime.current,saved=personalPosition.current;
    if(rt&&saved){rt.viewer.scrollMode=scrollModes[saved.scroll_mode];setMode(saved.scroll_mode);rt.viewer.pagesRotation=saved.rotation;rt.viewer.currentScaleValue=saved.zoom_mode==="custom"?String(saved.zoom_value):saved.zoom_mode;rt.viewer.currentPageNumber=saved.page_no;
      requestAnimationFrame(()=>{const page=rt.viewer.getPageView(saved.page_no-1)?.div,host=container.current;if(page&&host){host.scrollTop=page.offsetTop+saved.offset_y*page.clientHeight;host.scrollLeft=page.offsetLeft+saved.offset_x*page.clientWidth;}followingRef.current=false;});
    }else followingRef.current=false;
    setFollowing(false);
  };
  const startFollowing=()=>{
    if(!presentation||presentation.active===false||presentation.version_id!==version.version_id||!runtime.current||!container.current)return;
    personalPosition.current=readPosition(runtime.current,container.current);followingRef.current=true;setFollowing(true);lastPresentationSequence.current=-1;followedPresentation.current=presentation.presentation_id;
  };
  useEffect(()=>{
    if(!following)return;
    if(!presentation||presentation.active===false||presentation.presentation_id!==followedPresentation.current){stopFollowing();return;}
    if(presentation.version_id!==version.version_id)return;
    if(presentation.sequence<=lastPresentationSequence.current)return;
    const rt=runtime.current;if(!ready||!rt)return;
    lastPresentationSequence.current=presentation.sequence;rt.viewer.currentPageNumber=clamp(presentation.page_no,1,rt.doc.numPages);
  },[presentation,following,ready,version.version_id]);

  useEffect(() => {
    const rt = runtime.current;
    if (!navigation || !ready || !rt) return;
    if (followingRef.current) {
      followingRef.current = false;
      setFollowing(false);
    }
    rt.viewer.currentPageNumber = clamp(navigation.page, 1, rt.doc.numPages);
  }, [navigation, ready]);

  useEffect(() => {
    const rt=runtime.current, host=pages.current; if(!rt||!host)return;
    const created:HTMLElement[]=[];
    for(const annotation of annotations){
      if(annotation.version_id!==version.version_id)continue;
      const page=rt.viewer.getPageView(annotation.page_no-1)?.div;if(!page)continue;
      const rects=annotation.anchor.rects?.length?annotation.anchor.rects:[{x:0,y:0,width:1,height:0.025}];
      for(const [index,rect]of rects.entries()){
        const mapped=rotateAnchorRect(rect,rt.viewer.pagesRotation+(rt.viewer.getPageView(annotation.page_no-1)?.pdfPage?.rotate??0)),mark=document.createElement('button');
        mark.type='button';mark.className='learning-reader-annotation';mark.dataset.annotationId=annotation.id;
        if(annotation.id===focusedAnnotationId){mark.dataset.focused='true';mark.setAttribute('aria-pressed','true');}
        mark.style.left=`${mapped.x*100}%`;mark.style.top=`${mapped.y*100}%`;mark.style.width=`${mapped.width*100}%`;mark.style.height=`${mapped.height*100}%`;
        mark.title=annotation.body??'Ghi chú';mark.setAttribute('aria-label',`Ghi chú trang ${annotation.page_no}: ${(annotation.body??annotation.anchor.text_quote?.exact??'Đánh dấu').slice(0,120)}`);
        if(index>0){mark.setAttribute('aria-hidden','true');mark.tabIndex=-1;}
        mark.onclick=()=>annotationCallback.current?.(annotation);
        page.append(mark);created.push(mark);
      }
    }
    if (citation?.version_id === version.version_id && citation.anchor.kind === "REGION") {
      const pageView = rt.viewer.getPageView(citation.page_no - 1);
      for (const rect of citation.anchor.rects ?? []) {
        if (!pageView?.div) break;
        const mapped = rotateAnchorRect(rect, rt.viewer.pagesRotation + (pageView.pdfPage?.rotate ?? 0));
        const mark = document.createElement("span");
        mark.className = "learning-reader-citation";
        mark.setAttribute("aria-hidden", "true");
        Object.assign(mark.style, { left: `${mapped.x * 100}%`, top: `${mapped.y * 100}%`,
          width: `${mapped.width * 100}%`, height: `${mapped.height * 100}%` });
        pageView.div.append(mark);
        created.push(mark);
      }
    }
    return()=>created.forEach(mark=>mark.remove());
  },[annotations,citation,focusedAnnotationId,version.version_id,paint,ready]);

  const captureTextSelection=()=>{
    if(regionMode||!onSelection)return;
    const selected=window.getSelection();if(!selected||selected.isCollapsed||!selected.rangeCount)return;
    const range=selected.getRangeAt(0),element=(node:Node)=>node instanceof Element?node:node.parentElement;
    const page=element(range.startContainer)?.closest<HTMLElement>('.page'),end=element(range.endContainer)?.closest<HTMLElement>('.page');
    if(!page||page!==end||!container.current?.contains(page))return;
    const exact=selected.toString().trim().slice(0,1000);if(!exact)return;
    const pageBox=page.getBoundingClientRect(),rotation=(runtime.current?.viewer.pagesRotation??0)+(runtime.current?.viewer.getPageView(Number(page.dataset.pageNumber)-1)?.pdfPage?.rotate??0);
    const rects=Array.from(range.getClientRects()).filter(rect=>rect.width>0&&rect.height>0).map(rect=>rectFromClient(rect,pageBox,rotation)).filter(rect=>rect.width>0&&rect.height>0).slice(0,100);
    const before=range.cloneRange();before.selectNodeContents(page.querySelector('.textLayer')??page);before.setEnd(range.startContainer,range.startOffset);
    const after=range.cloneRange();after.selectNodeContents(page.querySelector('.textLayer')??page);after.setStart(range.endContainer,range.endOffset);
    setSelection({version_id:version.version_id,page_no:Number(page.dataset.pageNumber),anchor:{kind:'TEXT',rects,text_quote:{exact,prefix:before.toString().slice(-50),suffix:after.toString().slice(0,50)}}});
  };

  const regionStart=(event:React.PointerEvent<HTMLDivElement>)=>{
    if(!regionMode||!onSelection||event.button!==0)return;
    const page=(event.target as Element).closest<HTMLElement>('.page');if(!page)return;
    event.preventDefault();event.currentTarget.setPointerCapture(event.pointerId);
    drag.current={page,x:event.clientX,y:event.clientY,pointer:event.pointerId};
  };
  const regionEnd=(event:React.PointerEvent<HTMLDivElement>)=>{
    const start=drag.current;if(!start||start.pointer!==event.pointerId)return;drag.current=null;
    if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);
    const width=Math.abs(event.clientX-start.x),height=Math.abs(event.clientY-start.y);if(width<4||height<4)return;
    const rotation=(runtime.current?.viewer.pagesRotation??0)+(runtime.current?.viewer.getPageView(Number(start.page.dataset.pageNumber)-1)?.pdfPage?.rotate??0);
    const rect=rectFromClient({left:Math.min(start.x,event.clientX),top:Math.min(start.y,event.clientY),width,height},start.page.getBoundingClientRect(),rotation);
    setSelection({version_id:version.version_id,page_no:Number(start.page.dataset.pageNumber),anchor:{kind:'REGION',rects:[rect]}});setRegionMode(false);
  };

  const go = (page: number) => { if (runtime.current && Number.isInteger(page)) runtime.current.viewer.currentPageNumber = clamp(page, 1, count); };
  const zoom = (next: number | "page-width" | "page-fit") => { if (runtime.current) runtime.current.viewer.currentScaleValue = typeof next === "number" ? String(clamp(next, 0.5, 3)) : next; };
  const changeMode = (next: ReaderState["scroll_mode"]) => { setMode(next); if (runtime.current) runtime.current.viewer.scrollMode = scrollModes[next]; };
  const search = (previous = false) => { runtime.current?.bus.dispatch("find", { source: shell.current, type: "again", query, caseSensitive: false, entireWord: false, highlightAll: true, findPrevious: previous, matchDiacritics: false }); };
  const fullscreen = async () => { setFocused(v => !v); try { if (document.fullscreenElement) await document.exitFullscreen(); else await shell.current?.requestFullscreen?.(); } catch { /* Focus layout remains available when native fullscreen is denied. */ } };
  async function bookmark(label?: string) {
    setBookmarkSaving(true);
    try {
      await callbacks.current.onBookmark?.(current, label);
      if (label !== undefined) setBookmarkLabel("");
    } catch {
      setStatus("Chưa lưu được đánh dấu. Hãy thử lại.");
    } finally {
      setBookmarkSaving(false);
    }
  }

  return <section ref={shell} className={`learning-pdf-reader ${focused ? "learning-reader-focused" : ""} ${toolsExpanded ? "learning-reader-tools-expanded" : ""} ${className}`} aria-label={`Đọc ${version.title}`}>
    <div className="learning-reader-title"><strong>{version.title}</strong><span>{count > 0 ? `${count} trang` : "PDF"}</span></div>
    <div className="learning-reader-toolbar" role="toolbar" aria-label="Công cụ đọc PDF">
      <button type="button" onClick={() => setSidebar(sidebar === "pages" ? null : "pages")} aria-pressed={sidebar === "pages"}>Ảnh trang</button>
      <button type="button" onClick={() => setSidebar(sidebar === "outline" ? null : "outline")} aria-pressed={sidebar === "outline"}>Mục lục</button>
      <button type="button" onClick={() => setSidebar(sidebar === "bookmarks" ? null : "bookmarks")} aria-pressed={sidebar === "bookmarks"}>Đánh dấu</button>
      <label>Cách xem <select aria-label="Cách xem PDF" value={mode} disabled={!ready} onChange={e => changeMode(e.target.value as ReaderState["scroll_mode"])}><option value="vertical">Cuộn dọc</option><option value="horizontal">Cuộn ngang</option><option value="page">Từng trang</option></select></label>
      <button type="button" className="learning-reader-primary-control" aria-label="Trang trước" disabled={!ready || current <= 1} onClick={() => go(current - 1)}>‹</button>
      <label>Trang <input aria-label="Số trang" type="number" min={1} max={count || 1} value={current} disabled={!ready} onChange={e => { if (e.target.value) go(Number(e.target.value)); }} /></label><span>/ {count || "—"}</span>
      <button type="button" className="learning-reader-primary-control" aria-label="Trang sau" disabled={!ready || current >= count} onClick={() => go(current + 1)}>›</button>
      <button type="button" className="learning-reader-primary-control" aria-label="Thu nhỏ" disabled={!ready} onClick={() => zoom(scale - 0.25)}>−</button><output aria-label="Mức phóng">{Math.round(scale * 100)}%</output>
      <button type="button" className="learning-reader-primary-control" aria-label="Phóng to" disabled={!ready} onClick={() => zoom(scale + 0.25)}>+</button>
      <button type="button" className="learning-reader-primary-control" disabled={!ready} onClick={() => zoom("page-width")}>Vừa rộng</button><button type="button" disabled={!ready} onClick={() => zoom("page-fit")}>Vừa trang</button>
      <button type="button" className="learning-reader-tools-toggle learning-reader-primary-control" aria-expanded={toolsExpanded} onClick={() => setToolsExpanded(value => !value)}>{toolsExpanded ? "Thu gọn công cụ" : "Công cụ đọc"}</button>
      <button type="button" disabled={!ready} onClick={() => { if (runtime.current) runtime.current.viewer.pagesRotation = (runtime.current.viewer.pagesRotation + 90) % 360; }}>Xoay</button>
      <button type="button" onClick={() => void fullscreen()} aria-pressed={focused}>{focused ? "Thoát tập trung" : "Toàn màn hình"}</button>
      {onBookmark && <button type="button" disabled={!ready || bookmarkSaving} onClick={() => void bookmark()}>Đánh dấu trang này</button>}
      {onSelection && <><button type="button" disabled={!ready} aria-pressed={regionMode} onClick={()=>{setRegionMode(v=>!v);setSelection(null);}}>Chọn vùng ghi chú</button><button type="button" disabled={!ready} onClick={()=>onSelection({version_id:version.version_id,page_no:current,anchor:{kind:'PAGE'}})}>Ghi chú cả trang</button></>}
      {(version.download_allowed ?? version.capabilities?.download) && <a href={version.download_path ?? version.content_path.replace(/\/content$/, "/download")} download>Tải bản gốc</a>}
    </div>
    <form className="learning-reader-search" onSubmit={e => { e.preventDefault(); search(); }}><label>Tìm trong bài <input aria-label="Tìm trong bài" value={query} onChange={e => setQuery(e.target.value)} /></label><button type="submit" disabled={!ready || !query.trim()}>Tìm tiếp</button><button type="button" disabled={!ready || !query.trim()} onClick={() => search(true)}>Kết quả trước</button><span role="status">{matches}</span></form>
    {version.has_text_layer === false && <p className="learning-reader-notice">Tài liệu scan chưa có lớp chữ. Bạn vẫn xem được trang; tìm và chọn văn bản chưa khả dụng.</p>}
    {status && <p className="learning-reader-notice" role="status">{status}</p>}
    {rangePaused && <div className="learning-reader-notice" role="status">
      <p>Đang chờ kết nối để tải thêm trang. Bạn có thể tiếp tục xem phần đã tải.</p>
      <button type="button" onClick={() => retryRange.current?.()}>Thử tải phần còn thiếu</button>
    </div>}
    {error && <div role="alert" className="learning-reader-notice"><p>{error}</p><button type="button" onClick={() => setRetry(v => v + 1)}>Thử lại</button></div>}
    {regionMode&&<p role="status" className="learning-reader-notice">Kéo một vùng trên trang để gắn ghi chú. Bạn cũng có thể dùng nút Ghi chú cả trang.</p>}
    {selection&&<div className="learning-reader-selection" role="status"><span>Trang {selection.page_no}: {selection.anchor.text_quote?.exact.slice(0,120)??'Vùng đã chọn'}</span><button type="button" onClick={()=>{onSelection?.(selection);setSelection(null);}}>Ghi chú phần đã chọn</button>{onIdeaSelection && <button type="button" onClick={() => { onIdeaSelection(selection); setSelection(null); }}>Lưu vào phiếu ý tưởng</button>}<button type="button" onClick={()=>setSelection(null)}>Bỏ chọn</button></div>}
    {presentation&&presentation.active!==false&&<div className="learning-reader-selection"><span>{presentation.version_id!==version.version_id?"Giảng viên đang trình bày phiên bản khác. Hãy mở đúng phiên bản để theo dõi.":following?`Đang theo giảng viên ở trang ${presentation.page_no}`:`Giảng viên đang ở trang ${presentation.page_no}. Bạn đang tự đọc.`}</span><button type="button" disabled={!ready||presentation.version_id!==version.version_id} onClick={following?stopFollowing:startFollowing}>{following?"Tạm rời giảng viên":personalPosition.current?"Quay lại giảng viên":"Theo giảng viên"}</button></div>}
    <div className="learning-reader-body">
      {sidebar && <aside className="learning-reader-sidebar" aria-label="Điều hướng tài liệu"><button type="button" onClick={() => setSidebar(null)}>Đóng điều hướng</button>
        {sidebar === "pages" && doc && Array.from({ length: count }, (_, i) => <PageThumbnail key={i} doc={doc} pageNo={i + 1} selected={current === i + 1} onSelect={() => go(i + 1)} />)}
        {sidebar === "outline" && (outline.length ? outline.map((entry, i) => <button type="button" key={i} style={{ paddingInlineStart: `${8 + entry.depth * 12}px` }} onClick={() => { if (entry.dest) void runtime.current?.links.goToDestination(entry.dest); }}>{entry.title}</button>) : <p>PDF không có mục lục nội bộ.</p>)}
        {sidebar === "bookmarks" && <>
          {bookmarks.length ? bookmarks.map(mark => <button type="button" key={mark.id} onClick={() => go(mark.page_no)}>{mark.label || `Trang ${mark.page_no}`}</button>) : <p>Bạn chưa đánh dấu trang nào.</p>}
          {onBookmark && <form className="learning-reader-bookmark-form" onSubmit={event => { event.preventDefault(); void bookmark(bookmarkLabel); }}>
            <label>Nhãn đánh dấu<input maxLength={500} value={bookmarkLabel} onChange={event => setBookmarkLabel(event.target.value)} /></label>
            <button type="submit" disabled={!ready || bookmarkSaving}>Lưu đánh dấu</button>
          </form>}
        </>}
      </aside>}
      <div ref={container} className={`learning-reader-viewport ${regionMode?'learning-reader-region-mode':''}`} data-testid="learning-pdf-viewport" onMouseUp={captureTextSelection} onKeyUp={captureTextSelection} onPointerDown={regionStart} onPointerUp={regionEnd} onPointerCancel={()=>{drag.current=null;}}><div ref={pages} className="pdfViewer" /></div>
    </div>
    <AccessibleDialog open={externalUrl !== null} onClose={() => setExternalUrl(null)} labelledBy="learning-external-link-title" className={styles.dialog}>
      <h3 id="learning-external-link-title">Mở liên kết ngoài?</h3>
      <p>Liên kết trong tài liệu sẽ mở một trang web bên ngoài Campus 24/7.</p>
      <p style={{ overflowWrap: "anywhere" }}>{externalUrl}</p>
      <div className={styles.row}>
        <button type="button" onClick={() => setExternalUrl(null)}>Quay lại tài liệu</button>
        {externalUrl && <a href={externalUrl} target="_blank" rel="noopener noreferrer" onClick={() => setExternalUrl(null)}>Mở trang web</a>}
      </div>
    </AccessibleDialog>
  </section>;
}

export default LearningPdfReader;
