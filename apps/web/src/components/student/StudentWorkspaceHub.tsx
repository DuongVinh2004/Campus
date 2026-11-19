"use client";

import React from "react";
import Link from "next/link";
import {
  FileText,
  CheckCircle2,
  Clock,
  Sparkles,
  ShieldCheck,
  ChevronRight,
  Plus,
} from "lucide-react";
import { useStore } from "@/lib/store";

interface StudentWorkspaceHubProps {
  onOpenGate1: () => void;
  onSelectPreset: (reason: string, method?: "digital_pdf" | "paper_stamped") => void;
}

export function StudentWorkspaceHub({
  onOpenGate1,
  onSelectPreset,
}: StudentWorkspaceHubProps) {
  const { currentUser, tickets } = useStore();

  if (!currentUser) return null;

  const studentTickets = tickets.filter((t) => t.studentId === currentUser.id);

  return (
    <div className="flex flex-col h-full min-h-0 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-sm overflow-hidden text-xs">
      {/* Panel Top Header */}
      <div className="shrink-0 p-4 bg-white/40 dark:bg-slate-900/40 backdrop-blur-md border-b border-slate-200/60 dark:border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-blue-600/10 dark:bg-blue-500/20 text-blue-600 dark:text-blue-400 flex items-center justify-center border border-blue-200/60 dark:border-blue-800/60 font-bold">
            <FileText className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-slate-900 dark:text-white text-xs sm:text-sm">
              Bàn làm việc sinh viên
            </h3>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Kê khai trực tuyến và theo dõi hồ sơ 24/7
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold bg-emerald-50/80 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200/70 dark:border-emerald-800">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span role="status" aria-live="polite">Sẵn sàng</span>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain p-4 space-y-4">
        {/* Card 1: Fast Service Launcher */}
        <div className="p-4 rounded-2xl bg-slate-50/80 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-none space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-900 dark:text-white text-xs">
                Tạo yêu cầu cấp giấy
              </span>
              <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-semibold border border-slate-200 dark:border-slate-700">
                Mã biểu mẫu: BM-03
              </span>
            </div>
            <span className="text-[10px] text-slate-500 dark:text-slate-400">Giấy xác nhận sinh viên</span>
          </div>

          <p className="text-[11px] leading-relaxed text-slate-600 dark:text-slate-400">
            Điền thông tin và gửi yêu cầu cấp Giấy xác nhận sinh viên. Trợ lý AI có thể hỗ trợ đối chiếu dữ liệu học vụ.
          </p>

          <button
            type="button"
            onClick={onOpenGate1}
            className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold flex items-center justify-center gap-2 shadow-md shadow-blue-500/20 transition-all text-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Bắt đầu điền biểu mẫu</span>
          </button>

          <div className="space-y-1.5 pt-1 border-t border-slate-100 dark:border-slate-800/80">
            <span className="text-[10px] font-semibold text-slate-500 dark:text-slate-400 block">
              Chọn nhanh loại yêu cầu
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-1.5">
              <button
                type="button"
                onClick={() =>
                  onSelectPreset("Nộp Ngân hàng Chính sách Xã hội Chi nhánh Q. Thủ Đức (Học kỳ 2)")
                }
                className="p-2 text-left rounded-xl bg-white/60 dark:bg-slate-800/60 hover:bg-white/90 dark:hover:bg-slate-700/80 border border-slate-200/60 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-all text-[11px] backdrop-blur-xs"
              >
                <div className="font-semibold leading-snug min-h-[2rem]">Vay vốn ngân hàng</div>
                <div className="text-[10px] text-slate-400">Học kỳ 2 / 2026</div>
              </button>

              <button
                type="button"
                onClick={() =>
                  onSelectPreset(
                    "Nộp Ban Chỉ huy Quân sự địa phương xin tạm hoãn gọi nhập ngũ năm 2026"
                  )
                }
                className="p-2 text-left rounded-xl bg-white/60 dark:bg-slate-800/60 hover:bg-white/90 dark:hover:bg-slate-700/80 border border-slate-200/60 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-all text-[11px] backdrop-blur-xs"
              >
                <div className="font-semibold leading-snug min-h-[2rem]">Tạm hoãn nghĩa vụ quân sự</div>
                <div className="text-[10px] text-slate-400">Năm 2026</div>
              </button>

              <button
                type="button"
                onClick={() =>
                  onSelectPreset("Nộp Đơn vị tiếp nhận Thực tập tốt nghiệp doanh nghiệp (Học kỳ 2)")
                }
                className="p-2 text-left rounded-xl bg-white/60 dark:bg-slate-800/60 hover:bg-white/90 dark:hover:bg-slate-700/80 border border-slate-200/60 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-all text-[11px] backdrop-blur-xs"
              >
                <div className="font-semibold leading-snug min-h-[2rem]">Thực tập tốt nghiệp</div>
                <div className="text-[10px] text-slate-400">Kỳ tốt nghiệp</div>
              </button>
            </div>
          </div>

          <div className="p-2 rounded-xl bg-blue-50/70 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/40 flex items-start gap-2 text-[10px] text-blue-700 dark:text-blue-300">
            <Sparkles className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
            <span>
              <strong>Trợ lý có thể cập nhật biểu mẫu:</strong> Bạn có thể nhờ đổi mục đích hoặc phương thức nhận.
            </span>
          </div>
        </div>

        {/* Card 2: Tracked Tickets (As in Stitch Screenshot) */}
        <div className="space-y-2 pt-1">
          <div className="flex items-center justify-between text-xs px-1">
            <span className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
              <span>Yêu cầu đang theo dõi</span>
              <span className="px-1.5 py-0.5 rounded-full bg-slate-200 dark:bg-slate-700 font-mono text-[10px]">
                {studentTickets.length}
              </span>
            </span>
            <Link
              href="/my-requests"
              className="inline-flex min-h-[44px] items-center gap-0.5 px-2 rounded-lg text-[11px] text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/30 hover:underline"
            >
              <span>Xem tất cả yêu cầu</span>
              <ChevronRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="space-y-2">
            {studentTickets.map((t) => (
              <div
                key={t.id}
                className="p-3 rounded-2xl bg-white/70 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-700 shadow-none space-y-1.5 hover:border-blue-300 dark:hover:border-blue-700 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-slate-800 dark:text-slate-200 text-xs">
                    #{t.code}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                      t.status === "open"
                        ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                        : t.status === "pending_officer"
                        ? "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700"
                        : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20"
                    }`}
                  >
                    {t.status === "open"
                      ? "Mới tiếp nhận"
                      : t.status === "pending_officer"
                      ? "Đang chờ xử lý"
                      : "Đã hoàn tất"}
                  </span>
                </div>

                <div className="font-medium text-slate-900 dark:text-white text-xs min-h-[2rem] line-clamp-2">
                  {t.title}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[10px] text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-100 dark:border-slate-800/80">
                  <span>Cán bộ phụ trách: {t.assignedOfficerName || "Phòng Đào tạo"}</span>
                  <span className="font-mono text-amber-600 dark:text-amber-400 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    <span>Thời gian còn lại: {t.slaRemaining || t.slaDeadline}</span>
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Card 3: Academic Qualifications & Tuition */}
        <div className="p-3 rounded-2xl bg-slate-50/80 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-none space-y-2">
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              <span>Học phí Học kỳ II: Đã quyết toán</span>
            </div>
            <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
              0 VNĐ nợ
            </span>
          </div>

          <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-slate-100 dark:border-slate-800 text-slate-500 dark:text-slate-400">
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-blue-500 shrink-0" />
              <span>Tư cách học thuật: Bình thường</span>
            </span>
            <span>Tín chỉ: {currentUser.credits || "114 / 138 TC"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
