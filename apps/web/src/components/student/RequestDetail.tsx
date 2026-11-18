"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowLeft, Download, MessageSquare, Paperclip } from "lucide-react";
import { hasIssuedDocument, latestOfficerReply, receiptHtml, requestDate as formatDate, requestStates, requestStatusLabel, validateSupplementFile, type RequestItem } from "@/lib/my-requests";
import { fieldClass, primaryButton, secondaryButton } from "./StudentFlowUI";
import { saveLocalAttachments } from "@/lib/local-attachments";
import type { StoredAttachment } from "@/lib/types";
import { AttachmentDownload } from "./AttachmentDownload";

export function RequestStatus({ item, localOnly = false }: { item: RequestItem; localOnly?: boolean }) {
  return <span className={`inline-flex rounded-lg px-2.5 py-1 text-sm font-semibold ${requestStates[item.state].classes}`}>{requestStatusLabel(item, localOnly)}</span>;
}

const section = "rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 dark:border-slate-700 dark:bg-slate-900";
const muted = "text-sm leading-relaxed text-slate-600 dark:text-slate-300";

export function RequestDetail({ item, localOnly, onBack, onMessage, onSupplement }: {
  item: RequestItem; localOnly: boolean; onBack: () => void;
  onMessage: (id: string, text: string) => Promise<void>;
  onSupplement: (id: string, payload: { note: string; fileName?: string; docTitle?: string; attachment?: StoredAttachment }) => Promise<void>;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const latest = latestOfficerReply(item);
  const pending = item.kind === "review" ? [...item.record.supplementRequests].reverse().find((r) => r.status === "sent") : undefined;

  useEffect(() => { heading.current?.focus(); }, [item.id]);

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (busy || !text.trim()) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await onMessage(item.id, text.trim()); setText("");
      setNotice("Đã gửi tin nhắn trao đổi. Bạn có thể theo dõi phản hồi trực tiếp tại đây.");
    } catch { setError("Chưa gửi được tin nhắn. Nội dung đang nhập vẫn được giữ để bạn thử lại."); }
    finally { setBusy(false); }
  }

  async function supplement(event: FormEvent) {
    event.preventDefault();
    if (busy || !localOnly || !note.trim() || !file || fileError) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const [attachment] = await saveLocalAttachments(item.record.studentId, item.id, { supplement: [file] });
      await onSupplement(item.id, { note: note.trim(), fileName: file.name, docTitle: `Tài liệu bổ sung: ${file.name}`, attachment });
      setNotice("Đã gửi ghi chú và tệp bổ sung vào hồ sơ tiếp nhận.");
      setNote(""); setFile(null); if (fileInput.current) fileInput.current.value = "";
    } catch { setError("Chưa lưu được bổ sung. Ghi chú và tệp đang chọn vẫn được giữ để bạn thử lại."); }
    finally { setBusy(false); }
  }

  function downloadReceipt() {
    const url = URL.createObjectURL(new Blob([receiptHtml(item, localOnly)], { type: "text/html;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = `bien-nhan-${item.code.replace(/[^a-zA-Z0-9-]/g, "-")}.html`;
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    setNotice("Đã tạo biên nhận HTML gồm thông tin đã khai. Đây không phải tài liệu học vụ được phát hành.");
  }

  const stages = item.state === "draft" ? ["Bản nháp chưa nộp"] : [
    "Đã ghi nhận hồ sơ",
    item.state === "new" ? "Chờ cán bộ xử lý" : item.state === "supplement" ? "Chờ sinh viên bổ sung" : item.kind === "ticket" && item.record.status === "pending_officer" ? "Chờ cán bộ phản hồi" : "Cán bộ xử lý",
    item.kind === "review" ? "Rà soát sơ bộ" : "Kết quả xử lý",
  ];
  const activeStep = item.state === "draft" || item.state === "new" ? 0 : item.state === "completed" ? 2 : 1;

  return <article className="min-w-0 space-y-4" aria-labelledby="request-detail-title">
    <div className={section}>
      <button type="button" onClick={onBack} className={`${secondaryButton} -ml-3 mb-3`}><ArrowLeft className="h-4 w-4" aria-hidden="true" />Quay lại danh sách</button>
      <div className="mb-3 flex flex-wrap items-center gap-3"><RequestStatus item={item} localOnly={localOnly} /><span className={muted}>{item.type}</span></div>
      <h2 id="request-detail-title" ref={heading} tabIndex={-1} className="break-words text-xl font-semibold leading-snug sm:text-2xl">{item.title}</h2>
      <p className="mt-3 break-all font-mono text-sm font-semibold">Mã hồ sơ: {item.code}</p>
      <p className={`mt-1 ${muted}`}>{item.state === "draft" || localOnly ? "Ngày ghi nhận" : "Ngày nộp"}: {formatDate(item.submittedAt)}</p>
      {item.updatedAt && <p className={muted}>Cập nhật: {formatDate(item.updatedAt)}</p>}
      <p className={`mt-4 ${muted}`}>{item.kind === "review" && item.state === "completed" ? "Đã hoàn tất rà soát sơ bộ. Chưa có quyết định công nhận học phần cuối cùng trong hồ sơ này." : item.kind === "ticket" && item.record.status === "pending_officer" ? "Hồ sơ đã chuyển tới bước cán bộ. Chưa có xác nhận bắt đầu xử lý; hãy theo dõi phản hồi." : requestStates[item.state].description}</p>
      <div className="mt-4 rounded-xl bg-slate-50 p-4 dark:bg-slate-800">
        <p className="text-sm font-semibold">Việc bạn cần làm</p>
        <p className={`mt-1 ${muted}`}>{item.state === "supplement" ? "Xem yêu cầu bổ sung ngay bên dưới." : item.state === "completed" ? "Đọc kết quả xử lý và phản hồi của cán bộ." : item.state === "draft" ? "Hoàn thiện và nộp hồ sơ để được xử lý." : "Theo dõi phản hồi. Bạn chưa cần nộp lại hồ sơ này."}</p>
        {item.state !== "draft" && <a className={`${secondaryButton} -ml-3 mt-1 text-blue-800 dark:text-blue-200`} href={pending ? "#supplement-title" : item.state === "completed" ? "#result-title" : "#latest-reply-title"}>{pending ? "Xem yêu cầu bổ sung" : item.state === "completed" ? "Xem kết quả xử lý" : "Xem phản hồi gần nhất"}</a>}
        <p className={`mt-2 ${muted}`}>Thời gian xử lý: chưa có thời hạn được cán bộ xác nhận cho hồ sơ này.</p>
        {item.kind === "ticket" && ["certificate", "transcript"].includes(item.record.type) && <p className={`mt-1 ${muted}`}>Thời gian tham khảo: 2–3 ngày làm việc, cao điểm tới 5 ngày. Cán bộ xác nhận thời gian cụ thể khi tiếp nhận.</p>}
      </div>
    </div>

    {notice && <p role="status" className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm leading-relaxed text-blue-900 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200">{notice}</p>}
    {error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{error}</p>}

    {pending && <section aria-labelledby="supplement-title" className={`${section} border-amber-300 dark:border-amber-700`}>
      <h3 id="supplement-title" tabIndex={-1} className="text-lg font-semibold">Yêu cầu bổ sung của cán bộ</h3>
      <p className={`mt-1 ${muted}`}>Gửi lúc: {formatDate(pending.sentAt || pending.createdAt)}</p>
      <p className="mt-3 font-medium">{pending.subject}</p>
      <p className="mt-2 whitespace-pre-wrap break-words text-base leading-relaxed">{pending.messageBody}</p>
      {pending.requestedDocuments.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">{pending.requestedDocuments.map((title, index) => <li key={index}>{title}</li>)}</ul>}
      <form onSubmit={supplement} className="mt-5 space-y-4">
        <p id="supplement-limit" className={muted}>Ghi chú và tệp bổ sung sẽ được cập nhật trực tiếp vào hồ sơ thẩm định.</p>
        {localOnly && <>
          <div><label htmlFor="supplement-file" className="mb-2 block text-sm font-semibold">Chọn tệp bổ sung (bắt buộc)</label>
            <input ref={fileInput} id="supplement-file" type="file" accept=".pdf,.png,.jpg,.jpeg" required disabled={busy} aria-describedby={`supplement-file-hint supplement-limit${fileError ? " supplement-file-error" : ""}`} aria-invalid={Boolean(fileError)} className={`${fieldClass} text-sm file:mr-3 file:min-h-11 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:text-slate-900 dark:file:bg-slate-800 dark:file:text-slate-100`} onChange={(event) => {
              const selected = event.target.files?.[0] || null;
              const validation = validateSupplementFile(selected);
              setFile(validation ? null : selected); setFileError(validation);
            }} />
            <p id="supplement-file-hint" className={`mt-2 ${muted}`}>1 tệp PDF/PNG/JPG, tối đa 10MB. Kiểm tra đúng tài liệu được yêu cầu trước khi xác nhận.</p>
            {fileError && <p id="supplement-file-error" role="alert" className="mt-2 text-sm text-red-700 dark:text-red-300">{fileError}</p>}
          </div>
          <div><label htmlFor="supplement-note" className="mb-2 block text-sm font-semibold">Ghi chú bổ sung (bắt buộc)</label><textarea id="supplement-note" required value={note} disabled={busy} onChange={(e) => setNote(e.target.value)} maxLength={4000} rows={3} className={fieldClass} /></div>
          <button type="submit" disabled={busy || !note.trim() || !file || Boolean(fileError)} className={`${primaryButton} w-full sm:w-auto`}>{busy ? "Đang lưu…" : "Xác nhận bổ sung"}</button>
        </>}
      </form>
    </section>}

    {!pending && <section className={section} aria-labelledby="latest-reply-title">
      <h3 id="latest-reply-title" tabIndex={-1} className="flex items-center gap-2 text-lg font-semibold"><MessageSquare className="h-5 w-5" aria-hidden="true" />Phản hồi gần nhất của cán bộ</h3>
      <p className={`mt-3 whitespace-pre-wrap break-words ${muted}`}>{latest || "Chưa có phản hồi của cán bộ trong hồ sơ này."}</p>
    </section>}

    {item.state === "completed" && <section className={section} aria-labelledby="result-title">
      <h3 id="result-title" tabIndex={-1} className="text-lg font-semibold">Kết quả xử lý</h3>
      {item.kind === "review" ? <>
        <p className={`mt-3 ${muted}`}>{item.record.finalReport?.conclusionSummary || "Chưa có báo cáo kết quả được đính kèm."}</p>
        {item.record.finalReport && <p className={`mt-2 ${muted}`}>Người lập báo cáo: {item.record.finalReport.officerName} · {formatDate(item.record.finalReport.completedAt)}</p>}
        <p className={`mt-3 ${muted}`}>Rà soát sơ bộ không thay thế quyết định của Hội đồng. Chưa có quyết định cuối cùng được cung cấp tại đây.</p>
      </> : <p className={`mt-3 ${muted}`}>{["certificate", "transcript"].includes(item.record.type) ? "Xem tình trạng tài liệu bên dưới. Hồ sơ hoàn tất không đồng nghĩa tài liệu đã được phát hành." : "Xem phản hồi của cán bộ và lịch sử trao đổi để biết cách giải quyết."}</p>}
    </section>}

    {item.kind === "ticket" && ["certificate", "transcript"].includes(item.record.type) && <section className={section} aria-labelledby="document-title">
      <h3 id="document-title" className="text-lg font-semibold">Tài liệu kết quả</h3>
      {hasIssuedDocument(item.record) && !localOnly ? <>
        <p className="mt-3 text-sm font-semibold text-emerald-800 dark:text-emerald-200">Đã ghi nhận phát hành</p>
        <p className={`mt-2 ${muted}`}>Số văn bản: {item.record.issuedCertificate!.docNumber} · Người phát hành: {item.record.issuedCertificate!.issuedByOfficerName}</p>
        <p className={muted}>Ngày phát hành: {formatDate(item.record.issuedCertificate!.issuedAt)}</p>
        <p className={`mt-3 ${muted}`}>Chưa có tệp chính thức để tải trong hồ sơ này. Liên hệ cán bộ phụ trách để nhận tài liệu.</p>
      </> : <>
        <p className={`mt-3 ${muted}`}>Tài liệu chính thức chưa được cung cấp trong hồ sơ này. Bạn sẽ nhận thông báo khi có kết quả.</p>
        <p className={`mt-2 ${muted}`}>Cách nhận đã khai: {item.record.receiveMethod === "paper_stamped" ? "Bản giấy có đóng dấu" : "Bản điện tử"}. Hãy theo dõi phản hồi của cán bộ.</p>
      </>}
    </section>}

    <section className={section} aria-labelledby="progress-title">
      <h3 id="progress-title" className="text-lg font-semibold">Tiến trình hồ sơ</h3>
      <ol className="mt-4 space-y-3">{stages.map((stage, index) => <li key={stage} aria-current={index === activeStep ? "step" : undefined} className="flex items-start gap-3 text-sm">
        <span aria-hidden="true" className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full font-semibold ${index <= activeStep ? "bg-blue-100 text-blue-900 dark:bg-blue-950 dark:text-blue-200" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>{index + 1}</span>
        <span className="pt-1">{stage}<span className={`ml-2 ${muted}`}>{index < activeStep ? "· Đã qua" : index === activeStep ? "· Hiện tại" : "· Chưa có xác nhận"}</span></span>
      </li>)}</ol>
      {item.kind === "review" && item.state === "completed" && <p className={`mt-3 ${muted}`}>Quyết định công nhận của Hội đồng: chưa có thông tin.</p>}
    </section>

    <section className={section} aria-labelledby="conversation-title">
      <h3 id="conversation-title" className="text-lg font-semibold">Trao đổi với cán bộ</h3>
      {item.kind === "ticket" ? <>
        <div className="mt-4 space-y-3">{item.record.messages.filter((m) => m.senderRole === "officer" || m.senderRole === "student").map((m) => <div key={m.id} className={`rounded-xl p-4 ${m.senderRole === "student" ? "bg-blue-50 dark:bg-blue-950" : "bg-slate-50 dark:bg-slate-800"}`}>
          <p className="text-sm font-semibold">{m.senderRole === "student" ? "Bạn" : `Cán bộ · ${m.senderName}`}</p>
          <p className={`mt-1 ${muted}`}>{formatDate(m.timestamp)}</p>
          <p className="mt-2 whitespace-pre-wrap break-words text-base leading-relaxed">{m.content}</p>
          {m.attachments?.map((attachment, index) => <p key={index} className={`mt-2 flex items-start gap-2 ${muted}`}><Paperclip className="mt-1 h-4 w-4 shrink-0" aria-hidden="true" /><span className="break-all">{attachment.name} · Chưa có tệp đính kèm để tải</span></p>)}
        </div>)}</div>
        {!item.record.messages.some((m) => m.senderRole === "officer" || m.senderRole === "student") && <p className={`mt-3 ${muted}`}>Chưa có trao đổi. Bạn có thể gửi câu hỏi về hồ sơ này.</p>}
        <form onSubmit={sendMessage} className="mt-5 space-y-3">
          <label htmlFor="request-message" className="block text-sm font-semibold">Tin nhắn về hồ sơ {item.code}</label>
          <textarea id="request-message" value={text} disabled={busy} onChange={(e) => setText(e.target.value)} required maxLength={4000} rows={3} className={fieldClass} aria-describedby="request-message-hint" />
          <p id="request-message-hint" className={muted}>Tin nhắn được gửi trực tiếp vào luồng xử lý hồ sơ một cửa.</p>
          <button type="submit" disabled={busy || !text.trim()} className={`${primaryButton} w-full sm:w-auto`}>{busy ? "Đang gửi…" : "Gửi tin nhắn"}</button>
        </form>
      </> : <>
        {item.record.supplementRequests.filter((r) => r.status === "responded").map((r) => <div key={r.id} className="mt-4 rounded-xl bg-slate-50 p-4 dark:bg-slate-800">
          <p className="text-sm font-semibold">Cán bộ · {r.subject}</p><p className={`mt-1 ${muted}`}>{formatDate(r.sentAt || r.createdAt)}</p>
          <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-relaxed">{r.messageBody}</p>
          {r.studentReply && <div className="mt-3 border-t border-slate-200 pt-3 dark:border-slate-600"><p className="text-sm font-semibold">Bạn · {formatDate(r.studentReply.submittedAt)}</p><p className="mt-2 whitespace-pre-wrap break-words text-sm">{r.studentReply.note}</p></div>}
        </div>)}
        <p className={`mt-3 ${muted}`}>Trao đổi về hồ sơ được ghi nhận qua các yêu cầu bổ sung của cán bộ.</p>
      </>}
    </section>

    <details className={section}>
      <summary className="flex min-h-11 cursor-pointer items-center justify-between gap-3 text-lg font-semibold">Thông tin bạn đã khai<span aria-hidden="true">⌄</span></summary>
      <p className={`mt-2 ${muted}`}>Thông tin do sinh viên cung cấp; chưa thể hiện xác minh hoặc phê duyệt của cán bộ.</p>
      <dl className="mt-4 space-y-4 text-sm">
        <div><dt className={muted}>Sinh viên / Student ID đã khai</dt><dd className="mt-1 break-words font-medium">{item.record.studentName} · {item.record.studentMssv}</dd></div>
        {item.kind === "ticket" ? <>
          <div><dt className={muted}>Mục đích / Nội dung yêu cầu</dt><dd className="mt-1 whitespace-pre-wrap break-words">{item.record.purpose}</dd></div>
          <div><dt className={muted}>Đơn vị nhận</dt><dd className="mt-1 break-words">{item.record.destinationOrg || "Không cung cấp"}</dd></div>
          {item.record.notes && <div><dt className={muted}>Thông tin hồ sơ</dt><dd className="mt-2 whitespace-pre-wrap break-words leading-relaxed">{item.record.notes}</dd></div>}
        </> : <>
          <div><dt className={muted}>Học phần đã học</dt><dd className="mt-1">{item.record.priorCourseCode} · {item.record.priorCourseName} · {item.record.priorCourseCredits} tín chỉ</dd></div>
          <div><dt className={muted}>Cơ sở đào tạo</dt><dd className="mt-1">{item.record.priorInstitution.replace(/\s*\(Minh họa\)/gi, "")}</dd></div>
          <div><dt className={muted}>Học phần đề nghị công nhận</dt><dd className="mt-1">{item.title} · {item.record.targetCourseCredits} tín chỉ</dd></div>
        </>}
      </dl>
      <button type="button" onClick={downloadReceipt} className={`${secondaryButton} mt-4 border border-slate-300 dark:border-slate-600`}><Download className="h-4 w-4" aria-hidden="true" />Tải thông tin hồ sơ</button>
      <p className={`mt-2 ${muted}`}>Biên nhận ghi thông tin đã khai, không phải giấy học vụ hoặc quyết định.</p>
    </details>

    {item.kind === "ticket" && Boolean(item.record.attachments?.length) && <section className={section} aria-labelledby="attachments-title">
      <h3 id="attachments-title" className="text-lg font-semibold">Tệp đính kèm</h3>
      <div className="mt-4 space-y-3">{item.record.attachments?.map(attachment => <AttachmentDownload key={attachment.id} attachment={attachment} ownerId={item.record.studentId} />)}</div>
    </section>}

    {item.kind === "review" && <details className={section} open={Boolean(item.record.documents.some(document => document.versions.some(version => version.attachment)))}>
      <summary className="flex min-h-11 cursor-pointer items-center justify-between gap-3 text-lg font-semibold">Danh sách tài liệu đã ghi nhận<span aria-hidden="true">⌄</span></summary>
      <p className={`mt-2 ${muted}`}>Cán bộ kiểm tra nội dung và tính hợp lệ của tài liệu khi xử lý hồ sơ.</p>
      <ul className="mt-3 space-y-3">{item.record.documents.map((document) => {
        const version = document.versions.find(v => v.version === document.currentVersion);
        return <li key={document.id} className="space-y-2 border-t border-slate-200 pt-3 text-sm dark:border-slate-700"><p className="font-semibold">{document.title}</p><p className="mt-1 break-all">{version?.fileName || "Chưa có tên tệp"} · phiên bản {document.currentVersion}</p>{version?.attachment ? <AttachmentDownload attachment={version.attachment} ownerId={item.record.studentId} /> : <p className={muted}>Chưa có tệp đính kèm để tải.</p>}</li>;
      })}</ul>
    </details>}
  </article>;
}
