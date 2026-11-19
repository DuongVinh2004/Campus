"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2 } from "lucide-react";
import { useStore } from "@/lib/store";
import { useStudentWorkspace, type ComplaintData } from "@/lib/student-workspace";
import { fieldClass, FlowHeader, primaryButton, secondaryButton, SubmissionSuccess, SummaryRow, surfaceClass } from "./StudentFlowUI";

export function ComplaintFlow({ review = false }: { review?: boolean }) {
  const router = useRouter();
  const { currentUser, createTicket, dataConfig } = useStore();
  const { complaint, updateComplaint, setStep, recordSubmission, startNew, beginSubmission, endSubmission } = useStudentWorkspace();
  const [errors, setErrors] = useState<Partial<Record<keyof ComplaintData, string>>>({});
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const submitLock = useRef(false);
  const data = complaint.data;

  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (hash) document.getElementById(hash)?.focus();
  }, []);

  if (!currentUser) return null;

  function edit(field: keyof ComplaintData, value: string) {
    updateComplaint({ [field]: value });
    setErrors((current) => ({ ...current, [field]: undefined }));
  }

  function continueToReview(event: FormEvent) {
    event.preventDefault();
    const nextErrors: Partial<Record<keyof ComplaintData, string>> = {};
    if (!data.course.trim()) nextErrors.course = "Nhập tên môn học và mã học phần nếu có.";
    if (!data.description.trim()) nextErrors.description = "Mô tả điểm hoặc thông tin bạn cần cán bộ kiểm tra.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      document.getElementById(nextErrors.course ? "complaint-course" : "complaint-description")?.focus();
      return;
    }
    setStep("complaint", "review");
    router.push("/student/complaint/review");
  }

  async function submit() {
    if (submitLock.current || complaint.submission || complaint.step !== "review" || !data.course.trim() || !data.description.trim()) return;
    if (!beginSubmission(complaint.id)) return;
    submitLock.current = true;
    setSubmitting(true);
    setSubmitError("");
    const notes = [`Môn học: ${data.course.trim()}`, `Loại điểm: ${data.assessment}`, `Nội dung cần kiểm tra: ${data.description.trim()}`,
      `Mong muốn: ${data.requestedOutcome.trim() || "Không cung cấp"}`, `Minh chứng: ${data.evidence.trim() || "Không cung cấp"}`].join("\n\n");
    try {
      const ticket = await createTicket({
        type: "complaint", title: `Khiếu nại điểm thi · ${data.course.trim()}`, certificateType: "Khiếu nại điểm thi", submissionKey: complaint.id,
        purpose: data.description.trim(), notes, destinationOrg: "Phòng Đào tạo & Khảo thí", priority: "high", isL4: true,
        l4TriggerReason: "Sinh viên đã xác nhận gửi khiếu nại điểm thi để cán bộ xem xét.",
        priorityReason: "Khiếu nại điểm thi cần cán bộ xác minh và phản hồi.",
      });
      recordSubmission("complaint", ticket.id, ticket.code);
    } catch {
      setSubmitError("Chưa gửi được khiếu nại. Nội dung của bạn vẫn được giữ; hãy thử lại.");
    } finally {
      endSubmission(complaint.id);
      submitLock.current = false;
      setSubmitting(false);
    }
  }

  function editSummary(field: string) {
    setStep("complaint", "details");
    router.push(`/student/complaint#complaint-${field}`);
  }

  if (complaint.submission) return <SubmissionSuccess localOnly={dataConfig?.mode === "mock"} ticketId={complaint.submission.ticketId} ticketCode={complaint.submission.ticketCode} title={dataConfig?.mode === "mock" ? "Đã lưu hồ sơ" : "Đã gửi khiếu nại cho cán bộ"}
    onNew={() => { startNew("complaint"); router.replace("/student/complaint"); }}>
    Cán bộ sẽ kiểm tra nội dung bạn cung cấp và phản hồi trong hồ sơ. Bạn có thể trao đổi thêm tại đó.
  </SubmissionSuccess>;

  const valid = Boolean(data.course.trim() && data.description.trim());
  return <div className="mx-auto max-w-[720px]">
    <FlowHeader title={review ? "Kiểm tra khiếu nại trước khi gửi" : "Gửi khiếu nại điểm thi"} step={review ? "review" : "details"} />
    {review ? <div className={surfaceClass}>
      <dl>
        <SummaryRow label="Sinh viên" editable={false}>{currentUser.name} · {currentUser.mssv || currentUser.id}</SummaryRow>
        <SummaryRow label="Môn học" onEdit={() => editSummary("course")}>{data.course}</SummaryRow>
        <SummaryRow label="Loại điểm" onEdit={() => editSummary("assessment")}>{data.assessment}</SummaryRow>
        <SummaryRow label="Nội dung cần kiểm tra" onEdit={() => editSummary("description")}>{data.description}</SummaryRow>
        <SummaryRow label="Mong muốn của bạn" onEdit={() => editSummary("requestedOutcome")}>{data.requestedOutcome}</SummaryRow>
        <SummaryRow label="Mô tả minh chứng" onEdit={() => editSummary("evidence")}>{data.evidence}</SummaryRow>
      </dl>
      <p className="mt-5 text-sm text-slate-600 dark:text-slate-300">Nội dung này sẽ được gửi để cán bộ xác minh và xem xét.</p>
      {!valid && <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-400">Hãy điền môn học và nội dung cần kiểm tra trước khi gửi.</p>}
      {submitError && <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-400">{submitError}</p>}
      <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link href="/student/complaint" aria-disabled={submitting} onClick={(event) => { if (submitting) event.preventDefault(); }} className={secondaryButton}>Quay lại</Link>
        {!valid ? <Link href="/student/complaint" className={primaryButton}>Điền thông tin còn thiếu</Link>
          : complaint.step !== "review" ? <button type="button" onClick={() => setStep("complaint", "review")} className={primaryButton}>Xác nhận thông tin mới</button>
          : <button type="button" onClick={() => void submit()} disabled={submitting} className={primaryButton}>{submitting ? <><Loader2 className="h-4 w-4 animate-spin" />Đang gửi…</> : "Gửi khiếu nại cho cán bộ"}</button>}
      </div>
    </div> : <form onSubmit={continueToReview} noValidate className={surfaceClass}>
      <p className="mb-6 text-sm leading-relaxed text-slate-600 dark:text-slate-300">Mô tả điểm cần kiểm tra để cán bộ có thể xem xét yêu cầu của bạn.</p>
      <div className="space-y-6">
        <div>
          <label htmlFor="complaint-course" className="mb-2 block text-base font-medium">Môn học</label>
          <input id="complaint-course" name="course" value={data.course} onChange={(event) => edit("course", event.target.value)} maxLength={200} required placeholder="Ví dụ: Cấu trúc dữ liệu (IT3011)" aria-invalid={Boolean(errors.course)} aria-describedby={errors.course ? "complaint-course-error" : undefined} className={fieldClass} />
          {errors.course && <p id="complaint-course-error" className="mt-2 text-sm text-red-600 dark:text-red-400">{errors.course}</p>}
        </div>
        <div>
          <label htmlFor="complaint-assessment" className="mb-2 block text-base font-medium">Loại điểm cần kiểm tra</label>
          <select id="complaint-assessment" name="assessment" value={data.assessment} onChange={(event) => edit("assessment", event.target.value)} className={fieldClass}>
            <option>Điểm thi cuối kỳ</option><option>Điểm giữa kỳ</option><option>Điểm tổng kết học phần</option><option>Loại điểm khác</option>
          </select>
        </div>
        <div>
          <label htmlFor="complaint-description" className="mb-2 block text-base font-medium">Nội dung cần kiểm tra</label>
          <textarea id="complaint-description" name="description" value={data.description} onChange={(event) => edit("description", event.target.value)} maxLength={4000} required rows={4} placeholder="Nêu điểm đang hiển thị và thông tin bạn cho rằng có sai lệch…" aria-invalid={Boolean(errors.description)} aria-describedby={errors.description ? "complaint-description-error" : undefined} className={fieldClass} />
          {errors.description && <p id="complaint-description-error" className="mt-2 text-sm text-red-600 dark:text-red-400">{errors.description}</p>}
        </div>
        <div>
          <label htmlFor="complaint-requestedOutcome" className="mb-2 block text-base font-medium">Mong muốn của bạn <span className="font-normal text-slate-500 dark:text-slate-400">(không bắt buộc)</span></label>
          <textarea id="complaint-requestedOutcome" name="requestedOutcome" value={data.requestedOutcome} onChange={(event) => edit("requestedOutcome", event.target.value)} maxLength={2000} rows={2} placeholder="Ví dụ: Đề nghị kiểm tra lại điểm trên cổng sinh viên" className={fieldClass} />
        </div>
        <div>
          <label htmlFor="complaint-evidence" className="mb-2 block text-base font-medium">Mô tả minh chứng <span className="font-normal text-slate-500 dark:text-slate-400">(không bắt buộc)</span></label>
          <textarea id="complaint-evidence" name="evidence" value={data.evidence} onChange={(event) => edit("evidence", event.target.value)} maxLength={2000} rows={2} placeholder="Nêu biên bản, bài thi hoặc trao đổi bạn có…" aria-describedby="complaint-evidence-hint" className={fieldClass} />
          <p id="complaint-evidence-hint" className="mt-2 text-sm text-slate-500 dark:text-slate-400">Bạn có thể trao đổi thêm với cán bộ trong hồ sơ sau khi gửi.</p>
        </div>
      </div>
      <div className="mt-8 flex flex-col-reverse gap-3 border-t border-slate-100 pt-6 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
        <p className="text-sm text-slate-500 dark:text-slate-400">Bản nháp được lưu trữ tự động trên hệ thống.</p>
        <button type="submit" className={primaryButton}>Tiếp tục<ArrowRight className="h-4 w-4" /></button>
      </div>
    </form>}
  </div>;
}
