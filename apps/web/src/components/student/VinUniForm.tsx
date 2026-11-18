"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, ExternalLink, FileText, Loader2, MessageCircle } from "lucide-react";
import { useStore } from "@/lib/store";
import { useVinUniForms } from "@/lib/vinuni-workspace";
import { VINUNI_SOURCES, documentTypes, validateForm, visibleFields, type VinUniTask, type FormField } from "@/lib/vinuni-forms";
import { useAssistant } from "@/lib/assistant-context";
import { saveLocalAttachments, validateAttachment } from "@/lib/local-attachments";
import { fieldClass, primaryButton, secondaryButton, SubmissionSuccess, surfaceClass, SummaryRow } from "./StudentFlowUI";

interface FormProps { task: VinUniTask; review?: boolean; embedded?: boolean }
export function VinUniForm(props: FormProps) {
  const { state } = useVinUniForms();
  return <VinUniFormContent key={state[props.task].id} {...props} />;
}
function VinUniFormContent({ task, review: routeReview = false, embedded = false }: FormProps) {
  const router = useRouter();
  const { currentUser, createTicket, dataConfig } = useStore();
  const { state, store } = useVinUniForms();
  const draft = state[task];
  const review = routeReview || draft.stage === 2;
  const assistant = useAssistant();
  const prefix = useId();
  const container = useRef<HTMLDivElement>(null);
  const values = draft.values;
  const files = store.getFiles(task);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [fileErrors, setFileErrors] = useState<Record<string, string>>({});
  const submitting = state.pending.includes(draft.id);
  const [submitError, setSubmitError] = useState("");
  const submission = draft.submission;
  const heading = useRef<HTMLHeadingElement>(null);
  const base = `/student/${task}`;
  const isDocument = task === "certificate";
  const localOnly = dataConfig?.mode === "mock";
  const stepTitle = review ? "Kiểm tra thông tin trước khi xác nhận" : isDocument ? draft.stage === 0 ? "Bạn cần loại tài liệu nào?" : "Bạn muốn nhận tài liệu thế nào?" : draft.stage === 0 ? "Thông tin học phần cần xem xét" : "Căn cứ và tài liệu minh chứng";
  const steps = isDocument ? ["Tài liệu", "Cách nhận", "Kiểm tra"] : ["Học phần", "Minh chứng", "Kiểm tra"];
  const allErrors = validateForm(task, values, [0, 1], files);
  const valid = Object.keys(allErrors).length === 0;
  const checked = draft.checked === JSON.stringify(values);

  useEffect(() => { heading.current?.focus(); }, [review, draft.stage]);
  useEffect(() => {
    if (assistant.fieldTarget?.task !== task) return;
    const element = container.current?.querySelector<HTMLElement>(`[data-form-field="${assistant.fieldTarget.name}"]`);
    element?.focus(); element?.scrollIntoView({ block: "nearest" });
  }, [assistant.fieldTarget, task, draft.stage]);

  function goEdit(stage: number) { store.stage(task, stage); if (routeReview && !embedded) router.push(base); }
  function startNew() {
    assistant.openForm(task);
    if (store.startNew(task, /@(?:[\w-]+\.)*(?:huce|vinuni)\.edu\.vn$/i.test(currentUser?.email || "") ? currentUser!.email : currentUser?.email || "")) {
      assistant.openForm(task); if (routeReview && !embedded) router.push(base);
    }
  }

  function edit(name: string, value: string) {
    store.update(task, { [name]: value });
    setErrors((previous) => ({ ...previous, [name]: "" }));
    setSubmitError("");
  }
  function focusFirst(next: Record<string, string>) { requestAnimationFrame(() => container.current?.querySelector<HTMLElement>(`[data-form-field="${Object.keys(next)[0]}"]`)?.focus()); }
  function advance(event: FormEvent) {
    event.preventDefault();
    const next = { ...validateForm(task, values, [draft.stage], files), ...(draft.stage === 1 ? fileErrors : {}) };
    setErrors(next);
    if (Object.keys(next).length) { focusFirst(next); return; }
    if (draft.stage === 0) { store.stage(task, 1); return; }
    store.check(task); store.stage(task, 2); if (!embedded) router.push(`${base}/review`);
  }
  function formNotes() {
    const rows = [`Sinh viên: ${currentUser?.name}`, `Student ID: ${currentUser?.mssv || currentUser?.id}`];
    for (const stage of [0, 1]) for (const f of visibleFields(task, stage, values)) {
      const value = values[f.name] || "";
      rows.push(`${f.label}: ${f.type === "checkbox" ? value === "yes" ? "Có" : "Không" : f.options?.find(([id]) => id === value)?.[1] || value || "Không cung cấp"}`);
    }
    return rows.join("\n\n");
  }
  function submissionKey() {
    let hash = 2166136261;
    for (const character of `${draft.id}:${draft.checked}`) hash = Math.imul(hash ^ character.charCodeAt(0), 16777619);
    return `vinuni-${task}-${(hash >>> 0).toString(36)}`;
  }
  async function submit() {
    if (!valid || !checked || !currentUser) return;
    if (process.env.NEXT_PUBLIC_UNIFIED_AI === "true") {
      setSubmitError("Biểu mẫu này chưa có consumer gửi trong hệ thống hợp nhất. Nháp và tệp được giữ; mở Giấy xác nhận hoặc Phúc khảo & hỗ trợ để tạo hồ sơ trên máy chủ.");
      return;
    }
    const operation = store.beginSubmission(task);
    if (!operation) return;
    setSubmitError("");
    const documentLabel = documentTypes.find(([id]) => id === values.documentType)?.[1] || "Tài liệu học vụ";
    try {
      const attachments = Object.values(files).some(group => group.length)
        ? dataConfig?.mode === "mock"
          ? await saveLocalAttachments(currentUser.id, submissionKey(), files)
          : (() => { throw new Error("Chưa kết nối nơi tiếp nhận tệp. Hồ sơ vẫn được giữ để bạn gửi lại sau."); })()
        : [];
      const requestPayload = { schemaVersion: 1 as const, task, documentType: isDocument ? values.documentType : undefined,
        submittedFields: [0, 1].flatMap(stage => visibleFields(task, stage, values)).filter(field => field.type !== "file").map(field => ({ name: field.name, label: field.label, value: field.type === "checkbox" ? values[field.name] === "yes" ? "Có" : "Không" : field.options?.find(([id]) => id === values[field.name])?.[1] || values[field.name] || "Không cung cấp" })) };
      const ticket = await createTicket(isDocument ? {
        requestPayload,
        type: values.documentType === "TNR" ? "transcript" : "certificate", title: `${documentLabel} · ${values.copies} bản`, certificateType: documentLabel,
        submissionKey: submissionKey(), attachments, purpose: values.purpose?.trim() || `Yêu cầu ${documentLabel}`,
        destinationOrg: values.destinationOrg?.trim() || (values.recipient === "other" ? values.recipientEmail : "VinUni Registrar"),
        receiveMethod: values.receiveMethod === "paper_stamped" ? "paper_stamped" : "digital_pdf", notes: formNotes(), priority: "normal",
        priorityReason: "Sinh viên đã kiểm tra và gửi yêu cầu tài liệu trong Campus 24/7.",
      } : {
        type: "complaint", title: `Grade Appeal · ${values.courseCode} · ${values.course}`, certificateType: "Khiếu nại điểm tổng kết học phần",
        requestPayload,
        submissionKey: submissionKey(), attachments, purpose: values.description.trim(), destinationOrg: "Academic Quality Assurance",
        receiveMethod: "digital_pdf", notes: formNotes(), priority: "high", isL4: true,
        l4TriggerReason: "Sinh viên đã xác nhận gửi Grade Appeal để cán bộ xem xét.",
        priorityReason: "Khiếu nại điểm tổng kết học phần cần cán bộ xác minh và phản hồi.",
      });
      store.recordSubmission(task, operation, { ticketId: ticket.id, ticketCode: ticket.code });
    } catch (failure) {
      setSubmitError(failure instanceof Error && /tệp|thiết bị|trình duyệt/.test(failure.message) ? failure.message : "Chưa nộp được hồ sơ. Bản nháp và tệp đã chọn vẫn được giữ; hãy thử lại.");
    } finally { store.endSubmission(operation); }
  }
  function attachment(field: FormField, selected: File[]) {
    const invalid = selected.length > 5 || selected.some((f) => validateAttachment(f));
    if (invalid) {
      const message = "Chọn tối đa 5 tệp PDF/PNG/JPG, mỗi tệp không rỗng và tối đa 10MB. Tệp hợp lệ đã chọn trước đó vẫn được giữ.";
      setFileErrors((previous) => ({ ...previous, [field.name]: message }));
      setErrors((previous) => ({ ...previous, [field.name]: message })); return;
    }
    setFileErrors((previous) => { const next = { ...previous }; delete next[field.name]; return next; });
    store.attach(task, field.name, selected); setErrors((previous) => ({ ...previous, [field.name]: "" })); setSubmitError("");
  }
  function renderField(field: FormField) {
    const id = `${prefix}-${field.name}`;
    const error = errors[field.name];
    const props = { id, "data-form-field": field.name, disabled: submitting, "aria-invalid": Boolean(error), "aria-describedby": `${id}-hint${error ? ` ${id}-error` : ""}` };
    if (field.type === "select" && ["documentType", "receiveMethod", "delivery", "recipient"].includes(field.name)) return <fieldset key={field.name} className="sm:col-span-2" aria-describedby={`${id}-hint${error ? ` ${id}-error` : ""}`}>
      <legend className="text-sm font-semibold">{field.label}</legend>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">{field.options?.map(([value, label], index) => <label key={value} className={`flex min-h-16 cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors ${values[field.name] === value ? "border-blue-600 bg-blue-50 dark:border-blue-400 dark:bg-blue-950/40" : "border-slate-300 bg-white hover:border-slate-400 dark:border-slate-600 dark:bg-slate-900"}`}>
        <input {...props} id={`${id}-${value}`} data-form-field={index === 0 ? field.name : undefined} type="radio" name={id} value={value} checked={values[field.name] === value} onChange={() => edit(field.name, value)} className="mt-1 h-4 w-4 shrink-0 accent-blue-600" />
        <span className="text-sm font-medium leading-relaxed">{label}{field.name === "documentType" && <span className="mt-1 block text-xs font-normal text-slate-600 dark:text-slate-400">{documentTypes.find(([code]) => code === value)?.[2]}</span>}</span>
      </label>)}</div>
      <p id={`${id}-hint`} className="mt-2 text-xs text-slate-600 dark:text-slate-400">{field.hint || "Chọn một phương án phù hợp với yêu cầu của bạn."}</p>
      <button type="button" onClick={() => assistant.helpField(task, field.name, field.label, field.hint)} className="inline-flex min-h-11 items-center gap-1 text-xs font-medium text-blue-700 dark:text-blue-300"><MessageCircle className="h-4 w-4" />Giải thích lựa chọn</button>
      {error && <p id={`${id}-error`} role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>}
    </fieldset>;
    const wide = field.type === "textarea" || field.type === "file" || field.type === "checkbox" || ["documentType", "contactOutcome", "contactDates", "scope", "delivery", "recipient", "address"].includes(field.name);
    return <div key={field.name} className={`${wide ? "sm:col-span-2" : ""} ${field.type === "checkbox" ? "rounded-xl border border-slate-200 p-3 dark:border-slate-700" : ""}`}>
      {field.type === "checkbox" ? <label className="flex min-h-11 items-start gap-3" htmlFor={id}><input {...props} type="checkbox" checked={values[field.name] === "yes"} onChange={(event) => edit(field.name, event.target.checked ? "yes" : "")} className="mt-1 h-5 w-5 shrink-0 accent-blue-600" /><span className="text-sm font-medium leading-relaxed">{field.label}{field.required && " *"}</span></label>
        : <><div className="mb-2 flex items-center justify-between gap-2"><label htmlFor={id} className="block text-sm font-medium">{field.label}{!field.required && " (không bắt buộc)"}</label><button type="button" onClick={() => assistant.helpField(task, field.name, field.label, field.hint)} aria-label={`Giải thích trường ${field.label}`} className="inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center gap-1 rounded-lg px-2 text-xs font-medium text-blue-700 hover:bg-blue-50 dark:text-blue-300 dark:hover:bg-blue-950"><MessageCircle className="h-4 w-4" />Giải thích</button></div>
          {field.type === "select" ? <select {...props} value={values[field.name] || ""} onChange={(event) => edit(field.name, event.target.value)} className={fieldClass}>{field.options?.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
            : field.type === "textarea" ? <textarea {...props} value={values[field.name] || ""} onChange={(event) => edit(field.name, event.target.value)} maxLength={4000} rows={3} className={fieldClass} />
              : field.type === "file" ? <><input {...props} type="file" accept=".pdf,.png,.jpg,.jpeg" multiple onChange={(event) => attachment(field, Array.from(event.target.files || []))} className={`${fieldClass} text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-2 file:text-blue-700`} />
                {values[field.name] && <p className="mt-2 whitespace-pre-wrap break-all text-xs text-slate-500">{files[field.name]?.length ? "Đã chọn trong phiên này:" : "Tệp trong bản nháp — cần chọn lại:"}{"\n"}{values[field.name]}</p>}</>
                : <input {...props} type={field.type || "text"} value={values[field.name] || ""} onChange={(event) => edit(field.name, event.target.value)} min={field.type === "number" ? 1 : undefined} max={field.type === "number" ? 99 : undefined} maxLength={field.type === "number" || field.type === "date" ? undefined : 4000} className={fieldClass} />}
        </>}
      <p id={`${id}-hint`} className="mt-1.5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">{field.hint}</p>
      {field.type === "checkbox" && <button type="button" onClick={() => assistant.helpField(task, field.name, field.label, field.hint)} aria-label={`Hỏi trợ lý về ${field.label}`} className="inline-flex min-h-11 items-center text-xs font-medium text-blue-700 dark:text-blue-300">Hỏi về mục này</button>}
      {error && <p id={`${id}-error`} role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>}
    </div>;
  }

  if (submission) return <div><SubmissionSuccess embedded={embedded} localOnly={dataConfig?.mode === "mock"} title={dataConfig?.mode === "mock" ? "Đã lưu hồ sơ" : isDocument ? "Đã nộp yêu cầu tài liệu" : "Đã nộp khiếu nại điểm"} ticketId={submission.ticketId} ticketCode={submission.ticketCode}>
    Bạn đã nhận mã hồ sơ. Mở Hồ sơ của tôi để xem thông tin đã khai, trạng thái và phản hồi.
  </SubmissionSuccess><button type="button" onClick={startNew} className={`${secondaryButton} mt-4 border border-slate-300 dark:border-slate-600`}>Tạo yêu cầu mới</button></div>;

  return <div ref={container} className="mx-auto max-w-[800px]">
    {process.env.NEXT_PUBLIC_UNIFIED_AI === "true" && <aside className="mb-4 rounded-xl border p-3 text-sm"><p>Biểu mẫu cục bộ này chưa có consumer gửi hồ sơ trong bản hợp nhất. Nháp và tệp được giữ; OCR và xác thực giấy tờ chưa được kết nối.</p><Link className="underline" href={isDocument ? "/tickets" : "/services"}>Mở biểu mẫu có máy chủ để chuẩn bị và xác nhận</Link></aside>}
    {!embedded && <Link href="/student" className={`${secondaryButton} -ml-3 mb-3`}><ArrowLeft className="h-4 w-4" />Dịch vụ sinh viên</Link>}
    {embedded ? <h2 ref={heading} tabIndex={-1} className="sr-only">{stepTitle}</h2> : <h1 ref={heading} tabIndex={-1} className="text-2xl font-semibold tracking-tight">{review ? "Kiểm tra hồ sơ trước khi nộp" : isDocument ? "Yêu cầu cấp giấy tờ học vụ" : "Khiếu nại điểm học phần"}</h1>}
    <ol aria-label="Các bước nộp hồ sơ" className={`${embedded ? "mb-3" : "my-3"} grid max-w-md grid-cols-3 gap-2 text-xs`}>{steps.map((label, index) => {
      const current = review ? 2 : draft.stage;
      return <li key={label} aria-current={current === index ? "step" : undefined} className={`flex min-w-0 items-center gap-1.5 border-b-2 pb-2 ${current === index ? "border-blue-600 font-semibold text-blue-700 dark:border-blue-400 dark:text-blue-300" : index < current ? "border-blue-200 text-slate-700 dark:border-blue-800 dark:text-slate-300" : "border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-400"}`}><span aria-hidden="true" className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] ${current === index ? "bg-blue-600 text-white dark:bg-blue-500" : "bg-slate-200 dark:bg-slate-800"}`}>{index < current ? <Check className="h-3 w-3" /> : index + 1}</span><span className="truncate">{label}</span></li>;
    })}</ol>
    {state.issue && <p role="alert" className="mb-4 text-sm text-amber-700">{state.issue}</p>}
    {review ? <div className={surfaceClass}>
      <div className="flex items-center gap-2 text-base font-semibold"><FileText className="h-5 w-5 text-blue-600" />{isDocument ? documentTypes.find(([id]) => id === values.documentType)?.[1] : "Phúc khảo điểm học phần"}</div>
      <dl className="mt-3"><SummaryRow label="Sinh viên" editable={false}>{currentUser?.name} · {currentUser?.mssv || currentUser?.id}</SummaryRow>
        {[0, 1].map((stage) => <div key={stage}>{visibleFields(task, stage, values).map((field) => <SummaryRow key={field.name} label={field.label} onEdit={() => { goEdit(stage); assistant.focusField(field.name); }}>{field.type === "checkbox" ? values[field.name] === "yes" ? "Đã chọn" : "Không chọn" : field.options?.find(([id]) => id === values[field.name])?.[1] || values[field.name] || "Không cung cấp"}</SummaryRow>)}</div>)}
      </dl>
      {!valid && <div role="alert" className="mt-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200"><p className="font-semibold">Hồ sơ chưa đủ thông tin</p><ul className="mt-2 list-disc space-y-1 pl-5">{Object.entries(allErrors).map(([name, text]) => <li key={name}>{text}</li>)}</ul></div>}
      {valid && !checked && <p role="status" className="mt-4 text-sm text-amber-700">Bản nháp đã thay đổi. Kiểm tra lại trước khi nộp hồ sơ.</p>}
      <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm leading-relaxed dark:bg-slate-800"><p className="font-medium">{isDocument ? `Phí tham khảo: ${(Number(values.copies || 1) * 50000).toLocaleString("vi-VN")}đ (${values.copies || 1} bản)` : "Phí rà soát điểm tham khảo: 1.000.000đ/yêu cầu/học phần"}</p>
        <p className="mt-2 text-slate-600 dark:text-slate-300">{isDocument ? "Thời gian tham khảo 2–3 ngày làm việc; cao điểm tới 5 ngày. Cán bộ xác nhận phí, điều kiện và thời gian thực tế. Chuyển phát quốc tế có phí riêng." : "Theo quy trình đào tạo: nộp trong 5 ngày làm việc sau khi điểm chính thức công bố trên cổng đào tạo. Campus 24/7 ghi nhận hồ sơ và danh sách tệp minh chứng để cán bộ phụ trách xem xét."}</p>
        {!isDocument && <p className="mt-2 font-medium">Bộ phận Khảo thí & Đảm bảo chất lượng: khaothi@huce.edu.vn</p>}
      </div>
      {submitError && <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-400">{submitError}</p>}
      <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-between"><button type="button" disabled={submitting} onClick={() => goEdit(0)} className={secondaryButton}>Sửa thông tin</button>
        {!valid ? <button type="button" onClick={() => { const first = Object.keys(allErrors)[0]; goEdit(visibleFields(task, 0, values).some((f) => f.name === first) ? 0 : 1); }} className={primaryButton}>Bổ sung thông tin</button>
          : !checked ? <button type="button" onClick={() => store.check(task)} className={primaryButton}>Xác nhận thông tin mới</button> : <button type="button" onClick={() => void submit()} disabled={submitting} className={primaryButton}>{submitting ? <><Loader2 className="h-4 w-4 animate-spin" />{localOnly ? "Đang lưu…" : "Đang gửi…"}</> : localOnly ? "Lưu hồ sơ dự thảo" : isDocument ? "Gửi yêu cầu tiếp nhận" : "Gửi khiếu nại điểm"}</button>}
      </div>
      {!isDocument && <a href={VINUNI_SOURCES.appealForm} target="_blank" rel="noopener noreferrer" className={`${secondaryButton} mt-4 border border-slate-200 dark:border-slate-700`}><ExternalLink className="h-4 w-4" />Xem mẫu đơn phúc khảo tham chiếu</a>}
    </div> : <form noValidate onSubmit={advance} className={surfaceClass}>
      <div className="mb-4 flex items-center gap-3 border-b border-slate-100 pb-4 dark:border-slate-800"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"><Check className="h-4 w-4" /></span><div><p className="text-sm font-medium">{currentUser?.name} · {currentUser?.mssv || currentUser?.id}</p><p className="text-xs text-slate-600 dark:text-slate-400">Thông tin lấy từ tài khoản của bạn</p></div></div>
      {!isDocument && draft.stage === 0 && <p className="mb-5 text-sm leading-relaxed text-slate-600 dark:text-slate-300">Chỉ áp dụng điểm tổng kết học phần. Trao đổi với giảng viên qua email trước khi lập khiếu nại chính thức.</p>}
      {isDocument && values.documentType === "GRD" && draft.stage === 0 && <p className="mb-5 text-sm text-amber-700">Xác nhận tốt nghiệp chỉ được cấp sau khi Phòng Đào tạo xác nhận đủ điều kiện. Nếu chưa đủ, liên hệ về xác nhận tốt nghiệp dự kiến.</p>}
      <p className="mb-4 text-xs text-slate-600 dark:text-slate-400">Điền các mục bên dưới; mục tùy chọn có nhãn “không bắt buộc”.</p>
      <div className="grid grid-cols-1 gap-x-5 gap-y-3 sm:grid-cols-2">{visibleFields(task, draft.stage, values).sort((a, b) => Number(b.name === "documentType") - Number(a.name === "documentType")).map(renderField)}</div>
      <div className="sticky -bottom-4 z-10 -mx-5 -mb-5 mt-6 flex flex-col-reverse gap-3 rounded-b-2xl border-t border-slate-200 bg-white p-4 sm:-bottom-6 sm:-mx-8 sm:-mb-8 sm:flex-row sm:items-center sm:justify-between dark:border-slate-700 dark:bg-slate-900">{draft.stage === 1 ? <button type="button" onClick={() => { store.stage(task, 0); setErrors({}); }} className={secondaryButton}>Quay lại</button> : <p className="text-xs text-slate-600 dark:text-slate-400">Chưa gửi hồ sơ · bạn có thể sửa lại</p>}<button type="submit" className={primaryButton}>{draft.stage === 0 ? isDocument ? "Tiếp tục · Cách nhận" : "Tiếp tục · Minh chứng" : "Kiểm tra hồ sơ"}<ArrowRight className="h-4 w-4" /></button></div>
    </form>}
    <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-500"><a href={isDocument ? VINUNI_SOURCES.documents : VINUNI_SOURCES.appeal} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center gap-1 underline">Nguồn hướng dẫn học vụ<ExternalLink className="h-3 w-3" /></a><a href={VINUNI_SOURCES.fees} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center gap-1 underline">Biểu phí chính thức<ExternalLink className="h-3 w-3" /></a></div>
    <button type="button" disabled={submitting} onClick={startNew} className="inline-flex min-h-11 items-center text-xs font-medium text-blue-700 disabled:opacity-40 dark:text-blue-300">Tạo bản nháp khác · giữ bản hiện tại trong lịch sử</button>
  </div>;
}
