"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, FileText, Loader2 } from "lucide-react";
import { useStore } from "@/lib/store";
import { useStudentWorkspace, type CertificateData } from "@/lib/student-workspace";
import { receiveMethodLabel } from "@/lib/student-assistant";
import { fieldClass, FlowHeader, primaryButton, secondaryButton, SubmissionSuccess, SummaryRow, surfaceClass } from "./StudentFlowUI";

export function CertificateFlow({ review = false }: { review?: boolean }) {
  const router = useRouter();
  const { currentUser, createTicket, dataConfig } = useStore();
  const { certificate, updateCertificate, setStep, recordSubmission, startNew, beginSubmission, endSubmission } = useStudentWorkspace();
  const [errors, setErrors] = useState<Partial<Record<keyof CertificateData, string>>>({});
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const submitLock = useRef(false);
  const data = certificate.data;

  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (hash) document.getElementById(hash)?.focus();
  }, []);

  if (!currentUser) return null;

  function edit(field: keyof CertificateData, value: string) {
    updateCertificate({ [field]: value });
    setErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError("");
  }

  function continueToReview(event: FormEvent) {
    event.preventDefault();
    const nextErrors: Partial<Record<keyof CertificateData, string>> = {};
    if (!data.purpose.trim()) nextErrors.purpose = "Nhập mục đích sử dụng giấy xác nhận.";
    if (!data.destinationOrg.trim()) nextErrors.destinationOrg = "Nhập tên cơ quan hoặc đơn vị nhận giấy.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      document.getElementById(nextErrors.purpose ? "certificate-purpose" : "certificate-destinationOrg")?.focus();
      return;
    }
    setStep("certificate", "review");
    router.push("/student/certificate/review");
  }

  async function submit() {
    if (submitLock.current || certificate.submission || certificate.step !== "review" || !data.purpose.trim() || !data.destinationOrg.trim()) return;
    if (!beginSubmission(certificate.id)) return;
    submitLock.current = true;
    setSubmitting(true);
    setSubmitError("");
    try {
      const ticket = await createTicket({
        type: "certificate", title: "Cấp giấy xác nhận sinh viên", certificateType: "Giấy xác nhận sinh viên", submissionKey: certificate.id,
        purpose: data.purpose.trim(), destinationOrg: data.destinationOrg.trim(), receiveMethod: data.receiveMethod, priority: "normal",
        priorityReason: "Sinh viên đã kiểm tra và xác nhận gửi yêu cầu cấp giấy.",
      });
      recordSubmission("certificate", ticket.id, ticket.code);
    } catch {
      setSubmitError("Chưa gửi được yêu cầu. Thông tin của bạn vẫn được giữ; hãy thử lại.");
    } finally {
      endSubmission(certificate.id);
      submitLock.current = false;
      setSubmitting(false);
    }
  }

  function editSummary(field: string) {
    setStep("certificate", "details");
    router.push(`/student/certificate#certificate-${field}`);
  }

  if (certificate.submission) return <SubmissionSuccess localOnly={dataConfig?.mode === "mock"} ticketId={certificate.submission.ticketId} ticketCode={certificate.submission.ticketCode} title={dataConfig?.mode === "mock" ? "Đã lưu hồ sơ" : "Đã gửi yêu cầu cấp giấy"}
    onNew={() => { startNew("certificate"); router.replace("/student/certificate"); }}>
    Cán bộ sẽ kiểm tra thông tin và xử lý yêu cầu. Bạn có thể theo dõi kết quả trong hồ sơ của mình.
  </SubmissionSuccess>;

  const valid = Boolean(data.purpose.trim() && data.destinationOrg.trim());
  return <div className="mx-auto max-w-[720px]">
    <FlowHeader title={review ? "Kiểm tra trước khi gửi" : "Xin giấy xác nhận sinh viên"} step={review ? "review" : "details"} />
    {review ? <div className={surfaceClass}>
      <p className="text-sm text-slate-500 dark:text-slate-400">Yêu cầu cấp giấy xác nhận sinh viên</p>
      <dl className="mt-2">
        <SummaryRow label="Sinh viên" editable={false}>{currentUser.name} · {currentUser.mssv || currentUser.id}</SummaryRow>
        <SummaryRow label="Mục đích" onEdit={() => editSummary("purpose")}>{data.purpose}</SummaryRow>
        <SummaryRow label="Cơ quan hoặc đơn vị nhận giấy" onEdit={() => editSummary("destinationOrg")}>{data.destinationOrg}</SummaryRow>
        <SummaryRow label="Cách nhận" onEdit={() => editSummary("receiveMethod")}>{receiveMethodLabel(data.receiveMethod)}</SummaryRow>
      </dl>
      <p className="mt-5 text-sm leading-relaxed text-slate-600 dark:text-slate-300">Sau khi bạn gửi, cán bộ sẽ tiếp nhận yêu cầu để kiểm tra. Giấy xác nhận được phát hành sau khi hồ sơ được duyệt.</p>
      {!valid && <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-400">Bạn cần điền mục đích và nơi nhận trước khi gửi.</p>}
      {valid && certificate.step !== "review" && <p role="status" className="mt-4 text-sm text-slate-600 dark:text-slate-300">Bản nháp vừa thay đổi. Hãy kiểm tra lại các thông tin trên.</p>}
      {submitError && <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-400">{submitError}</p>}
      <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link href="/student/certificate" aria-disabled={submitting} onClick={(event) => { if (submitting) event.preventDefault(); }} className={secondaryButton}>Quay lại</Link>
        {!valid ? <Link href="/student/certificate" className={primaryButton}>Điền thông tin còn thiếu</Link>
          : certificate.step !== "review" ? <button type="button" onClick={() => setStep("certificate", "review")} className={primaryButton}>Xác nhận thông tin mới</button>
          : <button type="button" onClick={() => void submit()} disabled={submitting} className={primaryButton}>{submitting ? <><Loader2 className="h-4 w-4 animate-spin" />Đang gửi…</> : "Gửi yêu cầu cấp giấy"}</button>}
      </div>
    </div> : <form onSubmit={continueToReview} noValidate className={surfaceClass}>
      <div className="mb-7 flex items-start gap-3 border-b border-slate-100 pb-5 dark:border-slate-800">
        <FileText className="mt-1 h-5 w-5 shrink-0 text-slate-500" />
        <div><p className="text-base font-medium">{currentUser.name}</p><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">MSSV {currentUser.mssv || currentUser.id} · Thông tin từ tài khoản</p></div>
      </div>
      <div className="space-y-6">
        <div>
          <label htmlFor="certificate-purpose" className="mb-2 block text-base font-medium">Mục đích sử dụng</label>
          <input id="certificate-purpose" name="purpose" value={data.purpose} onChange={(event) => edit("purpose", event.target.value)} maxLength={500} required
            aria-invalid={Boolean(errors.purpose)} aria-describedby={`certificate-purpose-hint${errors.purpose ? " certificate-purpose-error" : ""}`} placeholder="Ví dụ: Vay vốn sinh viên" className={fieldClass} />
          <p id="certificate-purpose-hint" className="mt-2 text-sm text-slate-500 dark:text-slate-400">Cho biết bạn sẽ dùng giấy xác nhận để làm gì.</p>
          {errors.purpose && <p id="certificate-purpose-error" className="mt-2 text-sm text-red-600 dark:text-red-400">{errors.purpose}</p>}
        </div>
        <div>
          <label htmlFor="certificate-destinationOrg" className="mb-2 block text-base font-medium">Cơ quan hoặc đơn vị nhận giấy</label>
          <input id="certificate-destinationOrg" name="destinationOrg" value={data.destinationOrg} onChange={(event) => edit("destinationOrg", event.target.value)} maxLength={500} required
            aria-invalid={Boolean(errors.destinationOrg)} aria-describedby={errors.destinationOrg ? "certificate-destinationOrg-error" : undefined} placeholder="Ví dụ: Ngân hàng Chính sách Xã hội, chi nhánh…" className={fieldClass} />
          {errors.destinationOrg && <p id="certificate-destinationOrg-error" className="mt-2 text-sm text-red-600 dark:text-red-400">{errors.destinationOrg}</p>}
        </div>
        <fieldset id="certificate-receiveMethod" tabIndex={-1}>
          <legend className="mb-3 text-base font-medium">Cách nhận giấy</legend>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {([{ value: "digital_pdf", title: "Bản điện tử (PDF)", hint: "Xem kết quả trong hồ sơ" }, { value: "paper_stamped", title: "Bản giấy", hint: "Nhận theo hướng dẫn của cán bộ" }] as const).map((method) =>
              <label key={method.value} className={`flex min-h-20 cursor-pointer items-start gap-3 rounded-xl border p-4 ${data.receiveMethod === method.value ? "border-slate-700 bg-slate-50 dark:border-slate-300 dark:bg-slate-800" : "border-slate-200 dark:border-slate-700"}`}>
                <input type="radio" name="receiveMethod" value={method.value} checked={data.receiveMethod === method.value} onChange={() => edit("receiveMethod", method.value)} className="mt-1 h-4 w-4 accent-slate-800 dark:accent-slate-200" />
                <span><span className="block text-base font-medium">{method.title}</span><span className="mt-1 block text-sm text-slate-500 dark:text-slate-400">{method.hint}</span></span>
              </label>)}
          </div>
        </fieldset>
      </div>
      <div className="mt-8 flex flex-col-reverse gap-3 border-t border-slate-100 pt-6 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
        <p className="text-sm text-slate-500 dark:text-slate-400">Bản nháp được lưu trữ tự động trên hệ thống.</p>
        <button type="submit" className={primaryButton}>Tiếp tục<ArrowRight className="h-4 w-4" /></button>
      </div>
    </form>}
  </div>;
}
