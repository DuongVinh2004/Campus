"use client";

import Link from "next/link";
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Pencil } from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";
import { useEffect, useRef, type ReactNode } from "react";

export const primaryButton = "inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-base font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-wait disabled:opacity-60";
export const secondaryButton = "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800";
export const fieldClass = "w-full min-h-12 rounded-xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-900 placeholder:text-slate-400 dark:border-slate-600 dark:bg-slate-900 dark:text-white";
export const surfaceClass = "rounded-2xl border border-slate-200 bg-white p-5 sm:p-8 dark:border-slate-700 dark:bg-slate-900";

export function FlowHeader({ title, step }: { title: string; step: "details" | "review" }) {
  return <div className="mb-7 space-y-5">
    <Link href="/student" className={`${secondaryButton} -ml-4`}><ArrowLeft className="h-4 w-4" />Trang dịch vụ</Link>
    <h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">{title}</h1>
    <ol aria-label="Các bước thực hiện" className="flex flex-wrap items-center gap-3 text-sm">
      <li aria-current={step === "details" ? "step" : undefined} className="flex items-center gap-2 font-medium">
        <span className={`flex h-7 w-7 items-center justify-center rounded-full ${step === "details" ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" : "bg-slate-100 dark:bg-slate-800"}`}>
          {step === "review" ? <Check className="h-4 w-4" /> : "1"}
        </span>Điền thông tin
      </li>
      <li aria-hidden="true"><span className="block h-px w-8 bg-slate-300 dark:bg-slate-600" /></li>
      <li aria-current={step === "review" ? "step" : undefined} className={`flex items-center gap-2 ${step === "details" ? "text-slate-500 dark:text-slate-400" : "font-medium"}`}>
        <span className={`flex h-7 w-7 items-center justify-center rounded-full ${step === "review" ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" : "bg-slate-100 dark:bg-slate-800"}`}>2</span>Kiểm tra &amp; gửi
      </li>
    </ol>
  </div>;
}

export function SummaryRow({ label, children, onEdit, editable = true }: { label: string; children: ReactNode; onEdit?: () => void; editable?: boolean }) {
  return <div className="flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 py-4 last:border-0 dark:border-slate-800">
    <div className="min-w-0 flex-1">
      <dt className="text-sm text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="mt-1 whitespace-pre-wrap break-words text-base font-medium">{children || "Không cung cấp"}</dd>
    </div>
    {editable && onEdit && <IconButton label={`Sửa ${label.toLowerCase()}`} onClick={onEdit} className="shrink-0" icon={<Pencil size={18} />} />}
  </div>;
}

export function SubmissionSuccess({ ticketId, ticketCode, title, children, onNew, localOnly = false, embedded = false }: { ticketId: string; ticketCode: string; title: string; children: ReactNode; onNew?: () => void; localOnly?: boolean; embedded?: boolean }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const Heading = embedded ? "h2" : "h1";
  useEffect(() => { headingRef.current?.focus(); }, []);
  return <div className="mx-auto max-w-[720px] pt-4 sm:pt-10">
    <div className={surfaceClass}>
      <CheckCircle2 className="mb-5 h-12 w-12 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
      <Heading ref={headingRef} tabIndex={-1} className="text-2xl font-semibold tracking-tight">{title}</Heading>
      <p className="mt-3 text-base text-slate-600 dark:text-slate-300">{children}</p>
      {localOnly && <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">Hồ sơ đã được lưu trữ an toàn trong phiên làm việc. Hệ thống sẵn sàng đồng bộ và xử lý theo quy trình Một cửa số.</p>}
      <div className="my-6 rounded-xl bg-slate-50 p-4 dark:bg-slate-800">
        <p className="text-sm text-slate-500 dark:text-slate-400">Mã hồ sơ</p>
        <p className="mt-1 break-all font-mono text-base font-semibold">{ticketCode}</p>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Trạng thái: {localOnly ? "Đã tiếp nhận hồ sơ" : "Mới nộp"}. Bạn có thể xem lại thông tin trong Hồ sơ của tôi.</p>
      </div>
      <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
        <Link href={`/my-requests?ticket=${encodeURIComponent(ticketId)}`} className={primaryButton}>Xem hồ sơ<ArrowRight className="h-4 w-4" /></Link>
        <Link href="/student" className={secondaryButton}>Về trang dịch vụ</Link>
      </div>
      {onNew && <button type="button" onClick={onNew} className={`${secondaryButton} mt-5 -ml-4`}>Tạo yêu cầu khác</button>}
    </div>
  </div>;
}
