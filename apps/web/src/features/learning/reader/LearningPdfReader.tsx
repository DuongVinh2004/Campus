"use client";

import { useT } from "@/lib/i18n";
import React, { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy, RenderTask, TouchManager } from "pdfjs-dist";
import type { PDFViewer, PDFLinkService, PDFFindController, EventBus } from "pdfjs-dist/web/pdf_viewer.mjs";
import "pdfjs-dist/web/pdf_viewer.css";
import { PanelLeft, LayoutGrid, ListTree, Bookmark, BookmarkPlus, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, Minus, Plus, MoveHorizontal, Scan, RotateCw, Maximize, Minimize, Search, Download, BoxSelect, StickyNote, Rows3, Columns2, File as FileIcon, X } from "lucide-react";
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

function IconButton({ label, children, pressed, ...rest }: { label: string; children: React.ReactNode; pressed?: boolean } & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "aria-label" | "title">) {
  return <button type="button" className="lpr-btn" aria-label={label} title={label} aria-pressed={pressed} {...rest}>{children}</button>;
}

function PageThumbnail({ doc, pageNo, selected, onSelect }: { doc: PDFDocumentProxy; pageNo: number; selected: boolean; onSelect: () => void }) {
  const t = useT();
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
  return <button ref={button} type="button" className="learning-reader-thumbnail" aria-label={t("pdfx.61", { p: pageNo })} aria-current={selected ? "page" : undefined} onClick={onSelect}><canvas ref={canvas} aria-hidden="true" /><span>Trang {pageNo}</span></button>;
}

export function LearningPdfReader({ version, initialState, bookmarks = [], onStateChange, onBookmark, annotations = [], citation, navigation, focusedAnnotationId, onSelection, onIdeaSelection, onAnnotationClick, presentation, onPageChange, accessAllowed=true, onAccessDenied, className = "" }: LearningPdfReaderProps) {
  const t = useT();
  const shell = useRef<HTMLElement>(null), container = useRef<HTMLDivElement>(null), pages = useRef<HTMLDivElement>(null);
  const runtime = useRef<ReaderRuntime | null>(null);
  const callbacks = useRef({ onStateChange, onBookmark }); callbacks.current = { onStateChange, onBookmark };
  const annotationCallback = useRef(onAnnotationClick); annotationCallback.current = onAnnotationClick;
  const presentationCallbacks=useRef({onPageChange,onAccessDenied});presentationCallbacks.current={onPageChange,onAccessDenied};
  const followingRef=useRef(false),personalPosition=useRef<ReaderState|null>(null),lastPresentationSequence=useRef(-1);
  const followedPresentation=useRef<string|undefined>(undefined);
  const seed = useRef(initialState); seed.current = initialState;
  const [status, setStatus] = useState(t("pdfx.1")), [error, setError] = useState("");
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
  const [searchOpen, setSearchOpen] = useState(false);
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
    setReady(false); setDoc(null); setError(""); setStatus(t("pdfx.1")); setOutline([]); setSelection(null);followingRef.current=false;setFollowing(false);personalPosition.current=null;
    const host = container.current, pageHost = pages.current;
    if(!accessAllowed){setError(t("pdfx.2"));setStatus("");pageHost.replaceChildren();return;}
    const emit = () => {
      const rt = runtime.current; if (!rt || disposed || followingRef.current) return;
      const state=readPosition(rt,host);
      void Promise.resolve(callbacks.current.onStateChange?.(state)).catch(() => setStatus(t("pdfx.3")));
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
        link.title = t("pdfx.62", { h: destination.host });
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
        setReady(false); setDoc(null); setError(t("pdfx.4"));
        void task?.destroy();
        },
      });
      if (disposed) { range.abort(); return; }
      task = pdfjs.getDocument({ url: source, range, withCredentials: true, enableXfa: false, disableStream: true, disableAutoFetch: true, rangeChunkSize: 262144 });
      task.onPassword = () => { setError(t("pdfx.5")); void task?.destroy(); };
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
      bus.on("updatefindmatchescount", ({ matchesCount }: { matchesCount: { current: number; total: number } }) => { if (!disposed) setMatches(t("pdfx.63", { a: matchesCount.current, b: matchesCount.total })); });
      bus.on("updatefindcontrolstate", ({ state }: { state: number }) => { if (!disposed && state === 1) setMatches(t("pdfx.6")); });
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
    })().catch(() => { if (!disposed) { setError(t("pdfx.7")); setStatus(""); } });
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
        mark.title=annotation.body??t("pdfx.8");mark.setAttribute('aria-label',t("pdfx.64", { p: annotation.page_no, q: (annotation.body??annotation.anchor.text_quote?.exact??t("pdfx.13")).slice(0,120) }));
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
      setStatus(t("pdfx.9"));
    } finally {
      setBookmarkSaving(false);
    }
  }

  const downloadHref = (version.download_allowed ?? version.capabilities?.download) ? (version.download_path ?? version.content_path.replace(/\/content$/, "/download")) : null;
  const openSidebar = (tab: "pages" | "outline" | "bookmarks") => setSidebar(sidebar === tab ? null : tab);
  const viewModes: { id: ReaderState["scroll_mode"]; label: string; icon: React.ReactNode }[] = [
    { id: "vertical", label: t("pdfx.16"), icon: <Rows3 size={17} aria-hidden="true" /> },
    { id: "horizontal", label: t("pdfx.17"), icon: <Columns2 size={17} aria-hidden="true" /> },
    { id: "page", label: t("pdfx.18"), icon: <FileIcon size={17} aria-hidden="true" /> },
  ];

  return <section ref={shell} className={`learning-pdf-reader ${focused ? "learning-reader-focused" : ""} ${className}`} aria-label={t("pdfx.65", { v: version.title })}>
    <div className="lpr-bar" role="toolbar" aria-label={t("pdfx.10")}>
      <div className="lpr-group">
        <IconButton label={t("pdfx.51")} pressed={sidebar !== null} onClick={() => setSidebar(sidebar ? null : "pages")}><PanelLeft size={18} aria-hidden="true" /></IconButton>
      </div>
      <div className="lpr-title"><strong>{version.title}</strong><span>{count > 0 ? `${count} trang` : "PDF"}</span></div>
      <div className="lpr-group">
        <IconButton label={t("pdfx.35")} pressed={searchOpen} onClick={() => setSearchOpen(value => !value)}><Search size={18} aria-hidden="true" /></IconButton>
        {onBookmark && <IconButton label={t("pdfx.31")} disabled={!ready || bookmarkSaving} onClick={() => void bookmark()}><BookmarkPlus size={18} aria-hidden="true" /></IconButton>}
        {onSelection && <>
          <span className="lpr-divider" aria-hidden="true" />
          <IconButton label={t("pdfx.32")} pressed={regionMode} disabled={!ready} onClick={() => { setRegionMode(v => !v); setSelection(null); }}><BoxSelect size={18} aria-hidden="true" /></IconButton>
          <IconButton label={t("pdfx.33")} disabled={!ready} onClick={() => onSelection({ version_id: version.version_id, page_no: current, anchor: { kind: "PAGE" } })}><StickyNote size={18} aria-hidden="true" /></IconButton>
        </>}
        <span className="lpr-divider" aria-hidden="true" />
        {downloadHref && <a className="lpr-btn" href={downloadHref} download aria-label={t("pdfx.34")} title={t("pdfx.34")}><Download size={18} aria-hidden="true" /></a>}
        <IconButton label={focused ? t("pdfx.29") : t("pdfx.30")} pressed={focused} onClick={() => void fullscreen()}>{focused ? <Minimize size={18} aria-hidden="true" /> : <Maximize size={18} aria-hidden="true" />}</IconButton>
      </div>
    </div>
    <div className="lpr-viewbar">
      <div className="lpr-group">
        <IconButton label={t("pdfx.19")} disabled={!ready || current <= 1} onClick={() => go(current - 1)}><ChevronLeft size={18} aria-hidden="true" /></IconButton>
        <input className="lpr-page-input" aria-label={t("pdfx.21")} type="number" min={1} max={count || 1} value={current} disabled={!ready} onChange={e => { if (e.target.value) go(Number(e.target.value)); }} />
        <span className="lpr-count">/ {count || "—"}</span>
        <IconButton label={t("pdfx.20")} disabled={!ready || current >= count} onClick={() => go(current + 1)}><ChevronRight size={18} aria-hidden="true" /></IconButton>
      </div>
      <span className="lpr-divider" aria-hidden="true" />
      <div className="lpr-group">
        <IconButton label={t("pdfx.22")} disabled={!ready} onClick={() => zoom(scale - 0.25)}><Minus size={17} aria-hidden="true" /></IconButton>
        <output className="lpr-zoom" aria-label={t("pdfx.23")}>{Math.round(scale * 100)}%</output>
        <IconButton label={t("pdfx.24")} disabled={!ready} onClick={() => zoom(scale + 0.25)}><Plus size={17} aria-hidden="true" /></IconButton>
        <IconButton label={t("pdfx.25")} disabled={!ready} onClick={() => zoom("page-width")}><MoveHorizontal size={17} aria-hidden="true" /></IconButton>
        <IconButton label={t("pdfx.26")} disabled={!ready} onClick={() => zoom("page-fit")}><Scan size={17} aria-hidden="true" /></IconButton>
      </div>
      <span className="lpr-divider" aria-hidden="true" />
      <div className="lpr-group" role="group" aria-label={t("pdfx.15")}>
        {viewModes.map(item => <IconButton key={item.id} label={item.label} pressed={mode === item.id} disabled={!ready} onClick={() => changeMode(item.id)}>{item.icon}</IconButton>)}
        <IconButton label="Xoay" disabled={!ready} onClick={() => { if (runtime.current) runtime.current.viewer.pagesRotation = (runtime.current.viewer.pagesRotation + 90) % 360; }}><RotateCw size={17} aria-hidden="true" /></IconButton>
      </div>
    </div>
    {searchOpen && <form className="lpr-search" role="search" onSubmit={e => { e.preventDefault(); search(); }}>
      <Search size={16} aria-hidden="true" />
      <input aria-label={t("pdfx.35")} placeholder={t("pdfx.35")} value={query} onChange={e => setQuery(e.target.value)} autoFocus />
      <span role="status" className="lpr-matches">{matches}</span>
      <IconButton label={t("pdfx.37")} disabled={!ready || !query.trim()} onClick={() => search(true)}><ChevronUp size={17} aria-hidden="true" /></IconButton>
      <IconButton label={t("pdfx.36")} type="submit" disabled={!ready || !query.trim()}><ChevronDown size={17} aria-hidden="true" /></IconButton>
    </form>}
    {version.has_text_layer === false && <p className="learning-reader-notice">{t("pdfx.38")}</p>}
    {status && <p className="learning-reader-notice" role="status">{status}</p>}
    {rangePaused && <div className="learning-reader-notice" role="status">
      <p>{t("pdfx.39")}</p>
      <button type="button" onClick={() => retryRange.current?.()}>{t("pdfx.40")}</button>
    </div>}
    {error && <div role="alert" className="learning-reader-notice"><p>{error}</p><button type="button" onClick={() => setRetry(v => v + 1)}>{t("pdfx.41")}</button></div>}
    {regionMode && <p role="status" className="learning-reader-notice">{t("pdfx.42")}</p>}
    {selection && <div className="learning-reader-selection" role="status"><span>{t("pdfx.70", { p: selection.page_no })}: {selection.anchor.text_quote?.exact.slice(0, 120) ?? t("pdfx.43")}</span><button type="button" onClick={() => { onSelection?.(selection); setSelection(null); }}>{t("pdfx.44")}</button>{onIdeaSelection && <button type="button" onClick={() => { onIdeaSelection(selection); setSelection(null); }}>{t("pdfx.45")}</button>}<button type="button" onClick={() => setSelection(null)}>{t("pdfx.46")}</button></div>}
    {presentation && presentation.active !== false && <div className="learning-reader-selection"><span>{presentation.version_id !== version.version_id ? t("pdfx.47") : following ? t("pdfx.66", { p: presentation.page_no }) : t("pdfx.67", { p: presentation.page_no })}</span><button type="button" disabled={!ready || presentation.version_id !== version.version_id} onClick={following ? stopFollowing : startFollowing}>{following ? t("pdfx.48") : personalPosition.current ? t("pdfx.49") : t("pdfx.50")}</button></div>}
    <div className="learning-reader-body">
      {sidebar && <aside className="learning-reader-sidebar" aria-label={t("pdfx.51")}>
        <div className="lpr-side-tabs">
          <IconButton label={t("pdfx.11")} pressed={sidebar === "pages"} onClick={() => openSidebar("pages")}><LayoutGrid size={17} aria-hidden="true" /></IconButton>
          <IconButton label={t("pdfx.12")} pressed={sidebar === "outline"} onClick={() => openSidebar("outline")}><ListTree size={17} aria-hidden="true" /></IconButton>
          <IconButton label={t("pdfx.13")} pressed={sidebar === "bookmarks"} onClick={() => openSidebar("bookmarks")}><Bookmark size={17} aria-hidden="true" /></IconButton>
          <span className="lpr-spacer" />
          <IconButton label={t("pdfx.52")} onClick={() => setSidebar(null)}><X size={17} aria-hidden="true" /></IconButton>
        </div>
        <div className="lpr-side-list">
          {sidebar === "pages" && doc && Array.from({ length: count }, (_, i) => <PageThumbnail key={i} doc={doc} pageNo={i + 1} selected={current === i + 1} onSelect={() => go(i + 1)} />)}
          {sidebar === "outline" && (outline.length ? outline.map((entry, i) => <button type="button" className="lpr-side-item" key={i} style={{ paddingInlineStart: `${10 + entry.depth * 14}px` }} onClick={() => { if (entry.dest) void runtime.current?.links.goToDestination(entry.dest); }}>{entry.title}</button>) : <p className="lpr-side-empty">{t("pdfx.53")}</p>)}
          {sidebar === "bookmarks" && <>
            {bookmarks.length ? bookmarks.map(mark => <button type="button" className="lpr-side-item" key={mark.id} onClick={() => go(mark.page_no)}><Bookmark size={14} aria-hidden="true" /> {mark.label || t("pdfx.69", { p: mark.page_no })}</button>) : <p className="lpr-side-empty">{t("pdfx.54")}</p>}
            {onBookmark && <form className="learning-reader-bookmark-form" onSubmit={event => { event.preventDefault(); void bookmark(bookmarkLabel); }}>
              <label>{t("pdfx.55")}<input maxLength={500} value={bookmarkLabel} onChange={event => setBookmarkLabel(event.target.value)} /></label>
              <button type="submit" disabled={!ready || bookmarkSaving}>{t("pdfx.56")}</button>
            </form>}
          </>}
        </div>
      </aside>}
      <div ref={container} className={`learning-reader-viewport ${regionMode ? "learning-reader-region-mode" : ""}`} data-testid="learning-pdf-viewport" onMouseUp={captureTextSelection} onKeyUp={captureTextSelection} onPointerDown={regionStart} onPointerUp={regionEnd} onPointerCancel={() => { drag.current = null; }}><div ref={pages} className="pdfViewer" /></div>
    </div>
    <AccessibleDialog open={externalUrl !== null} onClose={() => setExternalUrl(null)} labelledBy="learning-external-link-title" className={styles.dialog}>
      <h3 id="learning-external-link-title">{t("pdfx.57")}</h3>
      <p>{t("pdfx.58")}</p>
      <p style={{ overflowWrap: "anywhere" }}>{externalUrl}</p>
      <div className={styles.row}>
        <button type="button" onClick={() => setExternalUrl(null)}>{t("pdfx.59")}</button>
        {externalUrl && <a href={externalUrl} target="_blank" rel="noopener noreferrer" onClick={() => setExternalUrl(null)}>{t("pdfx.60")}</a>}
      </div>
    </AccessibleDialog>
  </section>;
}

export default LearningPdfReader;
