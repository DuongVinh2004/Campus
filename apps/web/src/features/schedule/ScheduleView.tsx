import React, { useState } from "react";
import { buildIcs } from "../../lib/ics";
import {
  Calendar,
  Clock,
  Building,
  FileText,
  AlertTriangle,
  Download,
  CalendarCheck2,
} from "lucide-react";

export interface ScheduleEntry {
  id: string;
  courseCode: string;
  courseName: string;
  dayOfWeek: string;
  date?: string;
  time: string;
  /** ISO 8601 start and end; required for the entry to appear in the .ics export. */
  startsAt?: string;
  endsAt?: string;
  room: string;
  lecturer: string;
  type: "class" | "exam";
}

export interface ScheduleViewProps {
  entries?: ScheduleEntry[];
  freshnessTimestamp?: string;
  isStale?: boolean;
  isDegraded?: boolean;
}

export function ScheduleView({
  entries = [],
  freshnessTimestamp,
  isStale = false,
  isDegraded = false,
}: ScheduleViewProps) {
  const [filter, setFilter] = useState<"all" | "class" | "exam">("all");

  const filteredEntries = entries.filter((item) => {
    if (filter === "all") return true;
    return item.type === filter;
  });

  // Next upcoming priority item
  const nextEvent = filteredEntries[0] || null;

  // Group entries by day
  const groupedByDay = filteredEntries.reduce<Record<string, ScheduleEntry[]>>((acc, entry) => {
    const key = entry.dayOfWeek || "Chung";
    if (!acc[key]) acc[key] = [];
    acc[key].push(entry);
    return acc;
  }, {});

  // Check for overlaps within same day
  const hasOverlap = (dayEntries: ScheduleEntry[], current: ScheduleEntry) => {
    return dayEntries.some(
      (other) => other.id !== current.id && other.time === current.time
    );
  };

  const handleExportIcs = () => {
    if (typeof window === "undefined") return;
    const { text: ics } = buildIcs(
      entries.flatMap((e) =>
        e.startsAt && e.endsAt
          ? [{
              id: e.id,
              title: `${e.courseName} (${e.courseCode})`,
              startsAt: e.startsAt,
              endsAt: e.endsAt,
              location: e.room,
              description: `Giảng viên: ${e.lecturer} - Loại: ${e.type === "exam" ? "Lịch thi" : "Lịch học"}`,
            }]
          : [],
      ),
    );

    try {
      const blob = new Blob([ics], { type: "text/calendar;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `lich_hoc_huce_${new Date().toISOString().split("T")[0]}.ics`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // Fallback
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header with Timezone & Provenance Info */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
            Thời khóa biểu & Lịch thi sinh viên
          </h2>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--text-secondary)]">
            <span>
              Múi giờ: <strong className="font-semibold text-[var(--text-primary)]">ICT (UTC+7)</strong>
            </span>
            <span>•</span>
            <span>
              Nguồn: <strong className="font-semibold text-[var(--text-primary)]">Cổng thông tin đào tạo Đại học Xây dựng Hà Nội (HUCE)</strong>
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {freshnessTimestamp && (
            <div className="inline-flex items-center gap-2 rounded-full border border-[var(--border-color)] bg-[var(--surface-card)] px-3.5 py-1.5 text-xs text-[var(--text-secondary)] shadow-xs">
              <span
                className="h-2 w-2 rounded-full"
                style={{
                  backgroundColor: isStale || isDegraded ? "var(--color-status-warning)" : "var(--color-status-success)",
                }}
              />
              <span>
                Đồng bộ lúc:{" "}
                <strong className="font-semibold text-[var(--text-primary)]">
                  {(() => {
                    const d = new Date(freshnessTimestamp);
                    return isNaN(d.getTime())
                      ? freshnessTimestamp
                      : d.toLocaleTimeString("vi-VN", {
                          timeZone: "Asia/Ho_Chi_Minh",
                          hour: "2-digit",
                          minute: "2-digit",
                        }) +
                        " " +
                        d.toLocaleDateString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
                  })()}
                </strong>
              </span>
            </div>
          )}

          <button
            type="button"
            onClick={handleExportIcs}
            className="fluent-btn-secondary text-xs"
          >
            <Download className="h-3.5 w-3.5 text-[var(--text-secondary)]" />
            <span>Xuất lịch iCal (.ics)</span>
          </button>
        </div>
      </div>

      {/* Priority 1: Next Event Spotlight Hero */}
      {nextEvent && (
        <section
          aria-labelledby="heading-next-spotlight"
          className="fluent-card relative overflow-hidden border border-[var(--color-primary-border)] bg-[var(--color-primary-subtle)] p-5 shadow-xs"
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[var(--color-primary)] text-[var(--color-on-primary)] shadow-xs">
                <Clock className="h-6 w-6" />
              </div>
              <div>
                <div className="mb-1 flex items-center gap-2">
                  <span className="rounded-md bg-[var(--color-primary-light)] px-2 py-0.5 text-[11px] font-bold tracking-wider uppercase text-[var(--color-primary)]">
                    {nextEvent.type === "exam" ? "Lịch thi kế tiếp" : "Tiết học kế tiếp"}
                  </span>
                  <span className="text-xs font-medium text-[var(--text-secondary)]">
                    {nextEvent.dayOfWeek}
                  </span>
                </div>
                <h3
                  id="heading-next-spotlight"
                  className="text-base font-bold text-[var(--text-primary)] sm:text-lg"
                >
                  Sự kiện kế tiếp: {nextEvent.courseName} ({nextEvent.courseCode})
                </h3>
                <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
                  <span className="inline-flex items-center gap-1 font-semibold text-[var(--text-primary)]">
                    <Building className="h-3.5 w-3.5 text-[var(--text-secondary)]" /> {nextEvent.room}
                  </span>
                  <span>•</span>
                  <time dateTime={nextEvent.time} className="font-medium">
                    {nextEvent.time}
                  </time>
                  <span>•</span>
                  <span>{nextEvent.lecturer}</span>
                </div>
              </div>
            </div>

            <div className="hidden sm:block">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-primary-border)] bg-[var(--surface-card)] px-3 py-1 text-xs font-medium text-[var(--color-primary)] shadow-xs">
                <CalendarCheck2 className="h-3.5 w-3.5" /> Ca học sắp diễn ra
              </span>
            </div>
          </div>
        </section>
      )}

      {/* Filter Control Bar */}
      <div
        role="group"
        aria-label="Bộ lọc phân loại lịch"
        className="inline-flex self-start rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] p-1"
      >
        <button
          type="button"
          onClick={() => setFilter("all")}
          aria-pressed={filter === "all"}
          className={`rounded-lg px-4 py-1.5 text-xs font-medium transition ${
            filter === "all"
              ? "bg-[var(--surface-card)] font-semibold text-[var(--color-primary)] shadow-xs"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          Tất cả
        </button>
        <button
          type="button"
          onClick={() => setFilter("class")}
          aria-pressed={filter === "class"}
          className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-xs font-medium transition ${
            filter === "class"
              ? "bg-[var(--surface-card)] font-semibold text-[var(--color-primary)] shadow-xs"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <Calendar className="h-3.5 w-3.5" />
          <span>Lịch học</span>
        </button>
        <button
          type="button"
          onClick={() => setFilter("exam")}
          aria-pressed={filter === "exam"}
          className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-xs font-medium transition ${
            filter === "exam"
              ? "bg-[var(--surface-card)] font-semibold text-[var(--color-primary)] shadow-xs"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          }`}
        >
          <FileText className="h-3.5 w-3.5" />
          <span>Lịch thi</span>
        </button>
      </div>

      {/* Agenda Grouped Content Area */}
      {filteredEntries.length === 0 ? (
        <div
          role="status"
          className="campus-empty-state border border-dashed border-[var(--border-color)]"
        >
          <Calendar aria-hidden="true" />
          <div>
            <p className="mb-1 text-sm font-bold text-[var(--text-primary)]">
              Chưa có lịch học hoặc lịch thi nào.
            </p>
            <p className="text-xs text-[var(--text-secondary)]">
              Lịch học mới sẽ tự động cập nhật khi có thông báo chính thức từ phòng Đào tạo.
            </p>
          </div>
        </div>
      ) : (
        <div
          role="region"
          aria-label="Lịch học sinh viên"
          tabIndex={0}
          className="flex flex-col gap-6 overflow-x-auto fluent-card p-5 border border-[var(--border-color)] bg-[var(--surface-card)]"
        >
          {Object.entries(groupedByDay).map(([day, dayEntries]) => (
            <div key={day} className="flex flex-col gap-3">
              <h4 className="flex items-center gap-2 border-b border-[var(--border-color)] pb-2 text-sm font-bold text-[var(--color-primary)]">
                <span>{day}</span>
                <span className="text-xs font-normal text-[var(--text-secondary)]">
                  ({dayEntries.length} ca)
                </span>
              </h4>

              <div className="flex flex-col gap-2.5">
                {dayEntries.map((row) => {
                  const overlapping = hasOverlap(dayEntries, row);
                  return (
                    <article
                      key={row.id}
                      className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3.5 transition-colors sm:p-4 ${
                        overlapping
                          ? "border-rose-200 bg-rose-50/70 dark:border-rose-900/60 dark:bg-rose-950/20"
                          : "border-[var(--border-color)] bg-[var(--surface-subtle)] hover:bg-[var(--surface-card)]"
                      }`}
                    >
                      <div className="flex flex-col gap-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-bold text-[var(--color-primary)] text-sm">
                            {row.courseCode}
                          </span>
                          <span className="font-semibold text-[var(--text-primary)] text-sm">
                            {row.courseName}
                          </span>
                          {overlapping && (
                            <span className="inline-flex items-center gap-1 rounded bg-rose-100 px-2 py-0.5 text-[11px] font-bold text-rose-800 dark:bg-rose-950/80 dark:text-rose-300">
                              <AlertTriangle className="h-3 w-3 text-rose-600" />
                              <span>Trùng ca học</span>
                            </span>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5 text-[var(--text-secondary)]" />
                            <time dateTime={row.time}>{row.time}</time>
                          </span>
                          <span>•</span>
                          <span className="inline-flex items-center gap-1 font-medium text-[var(--text-primary)]">
                            <Building className="h-3.5 w-3.5 text-[var(--text-secondary)]" /> {row.room}
                          </span>
                          <span>•</span>
                          <span>{row.lecturer}</span>
                        </div>
                      </div>

                      <span
                        className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                          row.type === "exam"
                            ? "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-400"
                            : "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-400"
                        }`}
                      >
                        {row.type === "exam" ? "Lịch thi" : "Lịch học"}
                      </span>
                    </article>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
