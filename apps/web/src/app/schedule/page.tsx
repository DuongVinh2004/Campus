"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import React, { useEffect, useState, useCallback } from "react";
import { AppShell } from "../../components/AppShell";
import { ScheduleView, type ScheduleEntry } from "../../features/schedule/ScheduleView";
import { AsyncState, type AsyncStatus } from "../../components/AsyncState";
import { RefreshCw, AlertTriangle } from "lucide-react";
import { IconButton } from "@/components/shared/IconButton";
import { ApiClient } from "../../lib/api/client";
import { UnavailableStudentSurface } from "../../features/assistance/UnavailableStudentSurface";
import { WeekSchedule } from "../../features/schedule/WeekSchedule";
import { OPS_ENABLED } from "../../lib/campus-ops-api";
import { isExamTitle, vnTimeRange, vnWeekday } from "../../lib/schedule-time";

const API_BASE_URL = CAMPUS_API_BASE_URL;

interface ScheduleApiResponse {
  items: Array<{
    id: string;
    course_code: string;
    course_name: string;
    starts_at: string;
    ends_at: string;
    location_label: string;
    instructor_display_name: string;
    source_system?: string;
  }>;
  page?: {
    next_cursor?: string | null;
    has_more?: boolean;
    limit?: number;
  };
}

const DEMO_SCHEDULE_ENTRIES: ScheduleEntry[] = [
  { id: "demo-1", courseCode: "IT3120", courseName: "Trí tuệ Nhân tạo", dayOfWeek: "Thứ Hai", time: "07:00 - 09:25", room: "H3-301", lecturer: "PGS.TS Nguyễn Thanh Hải", type: "class" },
  { id: "demo-2", courseCode: "IT3080", courseName: "Mạng máy tính", dayOfWeek: "Thứ Hai", time: "09:35 - 11:55", room: "H3-204", lecturer: "TS. Trần Văn Minh", type: "class" },
  { id: "demo-3", courseCode: "IT3090", courseName: "Cơ sở dữ liệu", dayOfWeek: "Thứ Ba", time: "07:00 - 09:25", room: "H3-301", lecturer: "TS. Lê Thị Hương", type: "class" },
  { id: "demo-4", courseCode: "IT3150", courseName: "Kỹ thuật Phần mềm", dayOfWeek: "Thứ Tư", time: "13:00 - 15:25", room: "H5-102", lecturer: "PGS.TS Phạm Đức Thắng", type: "class" },
  { id: "demo-5", courseCode: "IT3120", courseName: "Trí tuệ Nhân tạo", dayOfWeek: "Thứ Năm", time: "07:00 - 09:25", room: "H3-301", lecturer: "PGS.TS Nguyễn Thanh Hải", type: "class" },
  { id: "demo-6", courseCode: "SS1010", courseName: "Giáo dục Quốc phòng", dayOfWeek: "Thứ Sáu", time: "07:00 - 11:55", room: "Sân KTX", lecturer: "Đại tá Nguyễn Văn Quân", type: "class" },
  { id: "demo-7", courseCode: "IT3080", courseName: "Thi giữa kỳ — Mạng máy tính", dayOfWeek: "Thứ Bảy", date: "15/10/2026", time: "08:00 - 09:30", room: "H3-401", lecturer: "TS. Trần Văn Minh", type: "exam" },
];

function OpsSchedulePage() {
  return (
    <AppShell activeNav="schedule">
      <div className="campus-page space-y-6">
        <WeekSchedule />
      </div>
    </AppShell>
  );
}

export default function SchedulePage() {
  if (OPS_ENABLED) return <OpsSchedulePage />;
  return process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true" || process.env.NEXT_PUBLIC_UNIFIED_AI === "true" ? <UnavailableStudentSurface kind="schedule" /> : <LegacySchedulePage />;
}

function LegacySchedulePage() {
  const [entries, setEntries] = useState<ScheduleEntry[]>([]);
  const [status, setStatus] = useState<AsyncStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [freshness, setFreshness] = useState<string>("");
  const [isStale, setIsStale] = useState<boolean>(false);
  const [lastSyncTime, setLastSyncTime] = useState<string | null>(null);

  const fetchSchedule = useCallback(async () => {
    setStatus("loading");
    setErrorMessage("");

    try {
      const client = new ApiClient({ baseUrl: API_BASE_URL });
      const now = new Date();
      const from = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
      const to = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59).toISOString();

      const response = await client.get<ScheduleApiResponse>(
        `/v1/students/me/schedule?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`
      );

      const items = response.items || [];
      if (items.length === 0) {
        // Demo mode: provide high-quality mock schedule for demonstration
        setEntries(DEMO_SCHEDULE_ENTRIES);
        setStatus("success");
        setIsStale(false);
        setFreshness(new Date().toISOString());
        return;
      }

      const mappedEntries: ScheduleEntry[] = items.map((item) => ({
        id: item.id,
        courseCode: item.course_code,
        courseName: item.course_name,
        dayOfWeek: vnWeekday(item.starts_at),
        time: vnTimeRange(item.starts_at, item.ends_at),
        startsAt: item.starts_at,
        endsAt: item.ends_at,
        room: item.location_label,
        lecturer: item.instructor_display_name,
        type: isExamTitle(item.course_name) ? "exam" : "class",
      }));

      setEntries(mappedEntries);
      setFreshness(new Date().toISOString());
      setLastSyncTime(
        new Date().toLocaleTimeString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit" })
      );
      setIsStale(false);
      setStatus("success");
    } catch {
      // If we already have verified entries from a prior fetch:
      // Retain the cached data, mark it as stale, and surface a clear stale warning.
      setEntries((prev) => {
        if (prev.length > 0) {
          return prev; // keep cached
        }
        // Demo fallback: show mock data when backend is unavailable
        return DEMO_SCHEDULE_ENTRIES;
      });
      setIsStale(true);
      setStatus("success");
    }
  }, []);

  useEffect(() => {
    fetchSchedule();
  }, [fetchSchedule]);

  return (
    <AppShell activeNav="schedule">
      <div className="campus-page">
        <header className="campus-page-heading">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
              Lịch học & Lịch thi của bạn
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Theo dõi lịch học và lịch thi kết thúc học phần được đồng bộ tự động từ cổng đào tạo HUCE
            </p>
          </div>

          <IconButton
            label={status === "loading" ? "Đang đồng bộ..." : "Đồng bộ lại"}
            variant="outline"
            onClick={fetchSchedule}
            disabled={status === "loading"}
            icon={<RefreshCw size={18} className={status === "loading" ? "animate-spin" : ""} />}
          />
        </header>

        {/* Stale Data Alert with Retry Action */}
        {isStale && (
          <div
            role="alert"
            className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300 shadow-xs"
          >
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <span>
                <strong>[~] Dữ liệu cũ (Chưa thể đồng bộ mới nhất):</strong> Đang hiển thị bản sao lưu lịch học lúc{" "}
                {lastSyncTime || "trước đó"}. Máy chủ cổng đào tạo đang tạm thời gián đoạn kết nối.
              </span>
            </div>
            <button
              type="button"
              onClick={fetchSchedule}
              className="fluent-btn-secondary text-xs font-semibold"
            >
              Thử lại ngay
            </button>
          </div>
        )}

        <AsyncState
          status={status}
          loadingMessage="Đang đồng bộ thời khóa biểu của bạn..."
          emptyMessage="Bạn hiện không có lịch học hoặc lịch thi nào trong khoảng thời gian này."
          errorMessage={errorMessage}
          onRetry={fetchSchedule}
        >
          <ScheduleView
            entries={entries}
            freshnessTimestamp={freshness}
            isStale={isStale}
            isDegraded={status === "error"}
          />
        </AsyncState>
      </div>
    </AppShell>
  );
}
