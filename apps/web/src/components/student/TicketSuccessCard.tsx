"use client";

import React from "react";
import Link from "next/link";
import { CheckCircle2, AlertTriangle, ArrowRight, Clock } from "lucide-react";

interface TicketSuccessCardProps {
  ticketId?: string;
  ticketCode?: string;
  title?: string;
}

export function TicketSuccessCard({
  ticketCode = "TKT-2026-0142",
  title = "Giấy xác nhận sinh viên",
}: TicketSuccessCardProps) {
  return (
    <div className="p-4 rounded-2xl bg-emerald-500/10 dark:bg-emerald-950/30 backdrop-blur-md border border-emerald-500/30 text-xs space-y-3 transition-all shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-slate-900 dark:text-white text-xs sm:text-sm">
              Đã gửi yêu cầu vào hệ thống thành công!
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="font-mono font-bold text-emerald-700 dark:text-emerald-300">
                {ticketCode}
              </span>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                MỚI TIẾP NHẬN
              </span>
            </div>
          </div>
        </div>
      </div>

      <p className="text-slate-700 dark:text-slate-300 leading-relaxed text-[11px]">
        Yêu cầu cấp <strong>{title}</strong> của bạn đã được chuyển đến Cán bộ học vụ để kiểm tra điều kiện. Kết quả xử lý sẽ được cập nhật tự động tại mục &ldquo;Yêu cầu của tôi&rdquo;.
      </p>

      {/* Business rule disclaimer */}
      <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-800 dark:text-amber-300 flex items-start gap-2 text-[11px]">
        <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <div>
          <strong>Ghi chú nghiệp vụ:</strong> Văn bản chưa được ban hành tại bước này (đang chờ cán bộ thẩm định và ký số).
        </div>
      </div>

      <div className="flex items-center justify-between pt-1 border-t border-emerald-500/20 text-[11px]">
        <span className="text-slate-500 dark:text-slate-400 flex items-center gap-1">
          <Clock className="w-3.5 h-3.5" />
          <span>Thời gian xử lý cam kết (SLA): 24h – 48h</span>
        </span>

        <Link
          href="/my-requests"
          className="inline-flex items-center gap-1 font-semibold text-blue-600 dark:text-blue-400 hover:underline"
        >
          <span>Theo dõi tại Yêu cầu của tôi</span>
          <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  );
}
