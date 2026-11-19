"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  BookOpen,
  Calendar,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  Edit2,
  GraduationCap,
  MapPin,
  Plus,
  RefreshCw,
  Trash2,
  User,
  X,
} from "lucide-react";
import {
  PersonalEventInput,
  problemMessage,
  scheduleApi,
  ScheduleItem,
  ScheduleKind,
} from "@/lib/campus-ops-api";

// Múi giờ Việt Nam cố định UTC+7 (không DST)
const VN_OFFSET_MS = 7 * 60 * 60 * 1000;

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function getVnParts(d: Date) {
  const vn = new Date(d.getTime() + VN_OFFSET_MS);
  return {
    year: vn.getUTCFullYear(),
    month: vn.getUTCMonth(),
    date: vn.getUTCDate(),
    day: vn.getUTCDay(),
    hours: vn.getUTCHours(),
    minutes: vn.getUTCMinutes(),
  };
}

function getVnMondayEpoch(refDate: Date): number {
  const { year, month, date, day } = getVnParts(refDate);
  const diffFromMonday = day === 0 ? 6 : day - 1;
  const mondayDate = date - diffFromMonday;
  return Date.UTC(year, month, mondayDate, 0, 0, 0) - VN_OFFSET_MS;
}

function formatIsoWithVnOffset(epochMs: number): string {
  const vn = new Date(epochMs + VN_OFFSET_MS);
  const y = vn.getUTCFullYear();
  const m = pad(vn.getUTCMonth() + 1);
  const d = pad(vn.getUTCDate());
  const h = pad(vn.getUTCHours());
  const min = pad(vn.getUTCMinutes());
  const s = pad(vn.getUTCSeconds());
  return `${y}-${m}-${d}T${h}:${min}:${s}+07:00`;
}

function formatVnTime(isoString: string): string {
  const d = new Date(isoString);
  const vn = new Date(d.getTime() + VN_OFFSET_MS);
  return `${pad(vn.getUTCHours())}:${pad(vn.getUTCMinutes())}`;
}

function formatVnDate(isoString: string): string {
  const d = new Date(isoString);
  const vn = new Date(d.getTime() + VN_OFFSET_MS);
  return `${pad(vn.getUTCDate())}/${pad(vn.getUTCMonth() + 1)}`;
}

function getVnDateKey(isoString: string): string {
  const d = new Date(isoString);
  const vn = new Date(d.getTime() + VN_OFFSET_MS);
  return `${vn.getUTCFullYear()}-${pad(vn.getUTCMonth() + 1)}-${pad(vn.getUTCDate())}`;
}

function calcDaysLeft(targetIso: string): number {
  const now = new Date();
  const target = new Date(targetIso);
  const nowVn = new Date(now.getTime() + VN_OFFSET_MS);
  const targetVn = new Date(target.getTime() + VN_OFFSET_MS);
  const nowDateUtc = Date.UTC(nowVn.getUTCFullYear(), nowVn.getUTCMonth(), nowVn.getUTCDate());
  const targetDateUtc = Date.UTC(targetVn.getUTCFullYear(), targetVn.getUTCMonth(), targetVn.getUTCDate());
  return Math.round((targetDateUtc - nowDateUtc) / 86400000);
}

const DAY_NAMES = [
  "Thứ Hai",
  "Thứ Ba",
  "Thứ Tư",
  "Thứ Năm",
  "Thứ Sáu",
  "Thứ Bảy",
  "Chủ nhật",
];

export function WeekSchedule() {
  const [refDate, setRefDate] = useState<Date>(() => new Date());
  const [scheduleItems, setScheduleItems] = useState<ScheduleItem[]>([]);
  const [upcomingItems, setUpcomingItems] = useState<ScheduleItem[]>([]);
  const [sources, setSources] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Dialog state
  const [isDialogOpen, setIsDialogOpen] = useState<boolean>(false);
  const [editingItem, setEditingItem] = useState<ScheduleItem | null>(null);
  const [formTitle, setFormTitle] = useState("");
  const [formDate, setFormDate] = useState("");
  const [formStartTime, setFormStartTime] = useState("");
  const [formEndTime, setFormEndTime] = useState("");
  const [formLocation, setFormLocation] = useState("");
  const [formNote, setFormNote] = useState("");
  const [timeError, setTimeError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Card inline deletion state
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const dialogTriggerRef = useRef<HTMLElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  const mondayEpoch = getVnMondayEpoch(refDate);
  const nextMondayEpoch = mondayEpoch + 7 * 86400000;

  // Tính số tuần ISO & nhãn tuần
  const thuEpoch = mondayEpoch + 3 * 86400000;
  const thuVn = new Date(thuEpoch + VN_OFFSET_MS);
  const thuYear = thuVn.getUTCFullYear();
  const jan4Utc = Date.UTC(thuYear, 0, 4);
  const jan4Day = new Date(jan4Utc).getUTCDay() || 7;
  const week1MonUtc = jan4Utc - (jan4Day - 1) * 86400000;
  const thuUtc = Date.UTC(thuYear, thuVn.getUTCMonth(), thuVn.getUTCDate());
  const weekNumber = Math.floor((thuUtc - week1MonUtc) / 86400000 / 7) + 1;

  const monVn = new Date(mondayEpoch + VN_OFFSET_MS);
  const sunVn = new Date(mondayEpoch + 6 * 86400000 + VN_OFFSET_MS);
  const weekLabel = `Tuần ${weekNumber} · ${pad(monVn.getUTCDate())}/${pad(monVn.getUTCMonth() + 1)} – ${pad(sunVn.getUTCDate())}/${pad(sunVn.getUTCMonth() + 1)}/${sunVn.getUTCFullYear()}`;

  // Chuẩn bị 7 ngày
  const nowParts = getVnParts(new Date());
  const todayKey = `${nowParts.year}-${pad(nowParts.month + 1)}-${pad(nowParts.date)}`;

  const weekDays = DAY_NAMES.map((name, idx) => {
    const dayEpoch = mondayEpoch + idx * 86400000;
    const vn = new Date(dayEpoch + VN_OFFSET_MS);
    const key = `${vn.getUTCFullYear()}-${pad(vn.getUTCMonth() + 1)}-${pad(vn.getUTCDate())}`;
    const dateFormatted = `${pad(vn.getUTCDate())}/${pad(vn.getUTCMonth() + 1)}`;
    const events = scheduleItems
      .filter((item) => getVnDateKey(item.starts_at) === key)
      .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());
    return {
      dayName: name,
      key,
      dateFormatted,
      isToday: key === todayKey,
      events,
    };
  });

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const fromIso = formatIsoWithVnOffset(mondayEpoch);
      const toIso = formatIsoWithVnOffset(nextMondayEpoch);

      const now = new Date();
      const in30DaysEpoch = now.getTime() + 30 * 86400000;
      const upcomingFromIso = formatIsoWithVnOffset(now.getTime());
      const upcomingToIso = formatIsoWithVnOffset(in30DaysEpoch);

      const [weekRes, upcomingRes] = await Promise.all([
        scheduleApi.list(fromIso, toIso),
        scheduleApi.list(upcomingFromIso, upcomingToIso),
      ]);

      setScheduleItems(weekRes.items || []);
      setSources(weekRes.sources || []);

      const sortedUpcoming = (upcomingRes.items || []).slice().sort(
        (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
      );
      setUpcomingItems(sortedUpcoming);
    } catch (err) {
      setErrorMessage(problemMessage(err, "Không thể tải lịch học. Vui lòng thử lại."));
    } finally {
      setIsLoading(false);
    }
  }, [mondayEpoch, nextMondayEpoch]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // Điều hướng tuần
  const handlePrevWeek = () => {
    setRefDate((prev) => new Date(prev.getTime() - 7 * 86400000));
  };
  const handleNextWeek = () => {
    setRefDate((prev) => new Date(prev.getTime() + 7 * 86400000));
  };
  const handleToday = () => {
    setRefDate(new Date());
  };

  // Quản lý Dialog
  const openCreateDialog = (e: React.MouseEvent<HTMLElement>) => {
    dialogTriggerRef.current = e.currentTarget;
    setEditingItem(null);
    setFormTitle("");
    const parts = getVnParts(new Date());
    setFormDate(`${parts.year}-${pad(parts.month + 1)}-${pad(parts.date)}`);
    setFormStartTime("08:00");
    setFormEndTime("09:30");
    setFormLocation("");
    setFormNote("");
    setTimeError(null);
    setFormError(null);
    setIsDialogOpen(true);
  };

  const openEditDialog = (item: ScheduleItem, e: React.MouseEvent<HTMLElement>) => {
    dialogTriggerRef.current = e.currentTarget;
    setEditingItem(item);
    setFormTitle(item.course_name);
    setFormDate(getVnDateKey(item.starts_at));
    setFormStartTime(formatVnTime(item.starts_at));
    setFormEndTime(formatVnTime(item.ends_at));
    setFormLocation(item.location_label || "");
    setFormNote(item.note || "");
    setTimeError(null);
    setFormError(null);
    setIsDialogOpen(true);
  };

  const closeDialog = useCallback(() => {
    setIsDialogOpen(false);
    setEditingItem(null);
    setTimeError(null);
    setFormError(null);
    setTimeout(() => {
      dialogTriggerRef.current?.focus();
    }, 0);
  }, []);

  useEffect(() => {
    if (!isDialogOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeDialog();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isDialogOpen, closeDialog]);

  const handleStartTimeChange = (val: string) => {
    setFormStartTime(val);
    if (formEndTime && val && formEndTime <= val) {
      setTimeError("Giờ kết thúc phải sau giờ bắt đầu");
    } else {
      setTimeError(null);
    }
  };

  const handleEndTimeChange = (val: string) => {
    setFormEndTime(val);
    if (formStartTime && val && val <= formStartTime) {
      setTimeError("Giờ kết thúc phải sau giờ bắt đầu");
    } else {
      setTimeError(null);
    }
  };

  const handleSaveEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTitle.trim()) {
      setFormError("Vui lòng nhập tên sự kiện.");
      return;
    }
    if (formTitle.trim().length > 120) {
      setFormError("Tên sự kiện tối đa 120 ký tự.");
      return;
    }
    if (!formDate || !formStartTime || !formEndTime) {
      setFormError("Vui lòng nhập đầy đủ ngày và thời gian.");
      return;
    }
    if (formEndTime <= formStartTime) {
      setTimeError("Giờ kết thúc phải sau giờ bắt đầu");
      return;
    }

    setIsSaving(true);
    setFormError(null);
    try {
      const starts_at = `${formDate}T${formStartTime}:00+07:00`;
      const ends_at = `${formDate}T${formEndTime}:00+07:00`;
      const body: PersonalEventInput = {
        title: formTitle.trim(),
        starts_at,
        ends_at,
        location: formLocation.trim() || undefined,
        note: formNote.trim() || undefined,
      };

      if (editingItem) {
        await scheduleApi.update(editingItem.id, body);
      } else {
        await scheduleApi.create(body);
      }

      window.dispatchEvent(new Event("campus:notifications-changed"));
      closeDialog();
      await loadData();
    } catch (err) {
      setFormError(problemMessage(err, "Không thể lưu sự kiện. Vui lòng thử lại."));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteItem = async (id: string) => {
    setIsDeleting(true);
    try {
      await scheduleApi.remove(id);
      window.dispatchEvent(new Event("campus:notifications-changed"));
      setDeletingId(null);
      await loadData();
    } catch (err) {
      setErrorMessage(problemMessage(err, "Không thể xóa sự kiện. Vui lòng thử lại."));
    } finally {
      setIsDeleting(false);
    }
  };

  const nextItems = upcomingItems.slice(0, 4);
  const examItems = upcomingItems.filter((i) => i.kind === "EXAM");

  return (
    <div className="campus-page min-w-0 space-y-6">
      {/* Tiêu đề trang */}
      <header className="campus-page-heading">
        <div data-eyebrow="Thời khóa biểu · Học kỳ I 2026–2027">
          <h1 className="text-2xl font-semibold">Lịch học</h1>
          <p>Thời khóa biểu, lịch thi và kế hoạch học tập theo tuần.</p>
        </div>
        <nav>
          <button
            type="button"
            data-testid="add-event-button"
            onClick={openCreateDialog}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-[var(--color-primary)] px-4 py-2.5 text-sm font-medium text-[var(--color-on-primary)] transition-colors hover:bg-[var(--color-primary-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
          >
            <Plus className="h-4 w-4 shrink-0" aria-hidden="true" />
            Thêm sự kiện
          </button>
        </nav>
      </header>

      {/* Banner dữ liệu mô phỏng nếu có LOCAL_SYNTHETIC */}
      {sources.includes("LOCAL_SYNTHETIC") && (
        <div
          role="note"
          className="flex items-start gap-3 rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4 text-sm text-[var(--text-secondary)]"
        >
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" aria-hidden="true" />
          <p className="min-w-0 break-words leading-relaxed">
            Lịch học và lịch thi là dữ liệu mô phỏng nội bộ, chưa kết nối Cổng đào tạo HUCE.
          </p>
        </div>
      )}

      {/* Bố cục chính: Lịch tuần + Panel Sắp tới */}
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-4">
        {/* Phân vùng Lịch tuần */}
        <section data-testid="week-schedule" className="space-y-4 lg:col-span-3 min-w-0">
          {/* Thanh điều hướng tuần */}
          <div className="campus-panel flex flex-wrap items-center justify-between gap-4 p-4">
            <div className="flex items-center gap-2">
              <button
                type="button"
                data-testid="week-prev"
                onClick={handlePrevWeek}
                className="inline-flex min-h-[44px] items-center gap-1 rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-3 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              >
                <ChevronLeft className="h-4 w-4 shrink-0" aria-hidden="true" />
                Tuần trước
              </button>
              <button
                type="button"
                data-testid="week-today"
                onClick={handleToday}
                className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-3.5 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              >
                Hôm nay
              </button>
              <button
                type="button"
                data-testid="week-next"
                onClick={handleNextWeek}
                className="inline-flex min-h-[44px] items-center gap-1 rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-3 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              >
                Tuần sau
                <ChevronRight className="h-4 w-4 shrink-0" aria-hidden="true" />
              </button>
            </div>

            <div className="text-sm font-semibold text-[var(--text-primary)] sm:text-base">
              {weekLabel}
            </div>
          </div>

          {/* Trạng thái Đang tải */}
          {isLoading && (
            <div
              role="status"
              className="campus-panel flex flex-col items-center justify-center p-12 text-center text-sm text-[var(--text-secondary)]"
            >
              <RefreshCw className="mb-3 h-6 w-6 animate-spin text-[var(--color-primary)]" aria-hidden="true" />
              <span>Đang tải lịch học…</span>
            </div>
          )}

          {/* Trạng thái Lỗi */}
          {!isLoading && errorMessage && (
            <div
              role="alert"
              className="campus-panel flex flex-col items-center justify-center p-8 text-center space-y-3"
            >
              <AlertCircle className="h-8 w-8 text-red-500" aria-hidden="true" />
              <p className="max-w-md text-sm font-medium text-red-600">{errorMessage}</p>
              <button
                type="button"
                onClick={() => void loadData()}
                className="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-[var(--color-primary)] px-5 py-2 text-sm font-medium text-[var(--color-on-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              >
                Thử lại
              </button>
            </div>
          )}

          {/* Trạng thái Thành công & Rỗng */}
          {!isLoading && !errorMessage && (
            <>
              {scheduleItems.length === 0 && (
                <div className="campus-empty-state p-6 text-center" role="status">
                  <Calendar className="mx-auto h-10 w-10 text-[var(--color-primary)]" aria-hidden="true" />
                  <p className="mt-2 text-sm font-medium text-[var(--text-primary)]">
                    Không có lịch học hoặc sự kiện trong tuần này.
                  </p>
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">
                    Dùng nút chuyển tuần để xem thời gian khác, hoặc nhấn &quot;Thêm sự kiện&quot; để tạo lịch cá nhân.
                  </p>
                </div>
              )}

              {/* Lưới 7 ngày: Desktop 7 cột, Mobile danh sách theo ngày (agenda) */}
              <div className="campus-timetable">
                {weekDays.map((day) => (
                  <div
                    key={day.key}
                    data-today={day.isToday ? "true" : undefined}
                    className="campus-timetable-day min-w-0"
                  >
                    {/* Tiêu đề ngày */}
                    <div className="campus-timetable-date">
                      <span className="campus-timetable-dow">{day.dayName}</span>
                      <span className="campus-timetable-dom">{day.dateFormatted}</span>
                      {day.isToday && <span className="campus-timetable-today">Hôm nay</span>}
                    </div>

                    {/* Danh sách thẻ sự kiện trong ngày */}
                    {day.events.length === 0 ? (
                      <p className="campus-timetable-empty">Không có lịch</p>
                    ) : (
                      <div className="campus-timetable-events">
                        {day.events.map((item) => {
                          const isPersonal = item.kind === "PERSONAL";
                          const isExam = item.kind === "EXAM";
                          const isClass = item.kind === "CLASS";

                          return (
                            <div
                              key={item.id}
                              data-testid={`schedule-event-${item.id}`}
                              data-kind={item.kind}
                              className="campus-timetable-event text-xs space-y-1.5 min-w-0 break-words"
                            >
                              {/* Huy hiệu loại & Giờ */}
                              <div className="flex flex-wrap items-center justify-between gap-1">
                                {isClass && (
                                  <span className="inline-flex items-center gap-1 rounded bg-[var(--color-primary-light)] px-1.5 py-0.5 font-medium text-[var(--color-primary)]">
                                    <BookOpen className="h-3 w-3 shrink-0" aria-hidden="true" />
                                    Lớp học
                                  </span>
                                )}
                                {isExam && (
                                  <span className="inline-flex items-center gap-1 rounded border border-[var(--border-color)] bg-[var(--surface-card)] px-1.5 py-0.5 font-medium text-[var(--text-primary)]">
                                    <GraduationCap className="h-3 w-3 shrink-0 text-amber-500" aria-hidden="true" />
                                    Lịch thi
                                  </span>
                                )}
                                {isPersonal && (
                                  <span className="inline-flex items-center gap-1 rounded border border-[var(--border-color)] bg-[var(--surface-card)] px-1.5 py-0.5 font-medium text-[var(--text-secondary)]">
                                    <User className="h-3 w-3 shrink-0" aria-hidden="true" />
                                    Cá nhân
                                  </span>
                                )}

                                <span className="font-semibold text-[var(--text-secondary)] whitespace-nowrap">
                                  {formatVnTime(item.starts_at)} – {formatVnTime(item.ends_at)}
                                </span>
                              </div>

                              {/* Tên môn / Sự kiện */}
                              <div className="min-w-0">
                                <h4 className="font-semibold text-[var(--text-primary)] leading-snug break-words">
                                  {item.course_name}
                                </h4>
                                {item.course_code && (
                                  <span className="font-mono text-[11px] text-[var(--text-secondary)]">
                                    {item.course_code}
                                  </span>
                                )}
                              </div>

                              {/* Địa điểm */}
                              {item.location_label && (
                                <div className="flex items-center gap-1 text-[var(--text-secondary)]">
                                  <MapPin className="h-3 w-3 shrink-0" aria-hidden="true" />
                                  <span className="truncate">{item.location_label}</span>
                                </div>
                              )}

                              {/* Giảng viên / Ghi chú */}
                              {item.instructor_display_name && (
                                <div className="flex items-center gap-1 text-[var(--text-secondary)]">
                                  <User className="h-3 w-3 shrink-0" aria-hidden="true" />
                                  <span className="truncate">{item.instructor_display_name}</span>
                                </div>
                              )}
                              {item.note && (
                                <p className="italic text-[var(--text-secondary)] line-clamp-2">
                                  {item.note}
                                </p>
                              )}

                              {/* Hành động sửa / xóa cho sự kiện cá nhân */}
                              {isPersonal && item.editable && (
                                <>
                                  {deletingId === item.id ? (
                                    <div className="mt-2 space-y-1.5 border-t border-[var(--border-color)] pt-2">
                                      <p className="text-[11px] font-medium text-red-600">
                                        Xác nhận xóa sự kiện này?
                                      </p>
                                      <div className="flex items-center gap-2">
                                        <button
                                          type="button"
                                          disabled={isDeleting}
                                          onClick={() => void handleDeleteItem(item.id)}
                                          className="inline-flex min-h-[44px] items-center justify-center rounded bg-red-600 px-3 py-1 text-xs font-semibold text-white hover:bg-red-700 focus-visible:outline-2 focus-visible:outline-[var(--color-focus)] disabled:opacity-50"
                                        >
                                          {isDeleting ? "Đang xóa…" : "Xác nhận xóa"}
                                        </button>
                                        <button
                                          type="button"
                                          disabled={isDeleting}
                                          onClick={() => setDeletingId(null)}
                                          className="inline-flex min-h-[44px] items-center justify-center rounded border border-[var(--border-color)] bg-[var(--surface-card)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                                        >
                                          Hủy
                                        </button>
                                      </div>
                                    </div>
                                  ) : (
                                    <div className="mt-2 flex items-center justify-end gap-2 border-t border-[var(--border-color)] pt-2">
                                      <button
                                        type="button"
                                        onClick={(e) => openEditDialog(item, e)}
                                        className="inline-flex min-h-[44px] items-center gap-1 rounded border border-[var(--border-color)] bg-[var(--surface-card)] px-2.5 py-1 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                                      >
                                        <Edit2 className="h-3 w-3 shrink-0" aria-hidden="true" />
                                        Sửa
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => setDeletingId(item.id)}
                                        className="inline-flex min-h-[44px] items-center gap-1 rounded border border-[var(--border-color)] bg-[var(--surface-card)] px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                                      >
                                        <Trash2 className="h-3 w-3 shrink-0" aria-hidden="true" />
                                        Xóa
                                      </button>
                                    </div>
                                  )}
                                </>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </section>

        {/* Panel Sắp tới */}
        <aside
          data-testid="upcoming-panel"
          className="campus-panel space-y-6 lg:col-span-1 min-w-0"
        >
          <div>
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">Sắp tới</h2>
            <p className="mt-1 text-xs text-[var(--text-secondary)]">Kế hoạch trong 30 ngày tới</p>
          </div>

          {/* 4 mục kế tiếp */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase text-[var(--text-secondary)]">
              Mục kế tiếp
            </h3>
            {nextItems.length === 0 ? (
              <p className="text-xs italic text-[var(--text-secondary)]">
                Không có sự kiện sắp tới.
              </p>
            ) : (
              <ul className="space-y-2.5">
                {nextItems.map((item) => (
                  <li
                    key={item.id}
                    className="rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] p-2.5 text-xs space-y-1 min-w-0 break-words"
                  >
                    <div className="flex items-center justify-between gap-1 text-[var(--text-secondary)]">
                      <span className="font-semibold text-[var(--text-primary)]">
                        {formatVnDate(item.starts_at)}
                      </span>
                      <span>
                        {formatVnTime(item.starts_at)} – {formatVnTime(item.ends_at)}
                      </span>
                    </div>
                    <p className="font-medium text-[var(--text-primary)] leading-tight">
                      {item.course_name}
                    </p>
                    {item.location_label && (
                      <div className="flex items-center gap-1 text-[var(--text-secondary)]">
                        <MapPin className="h-3 w-3 shrink-0" aria-hidden="true" />
                        <span className="truncate">{item.location_label}</span>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Lịch thi sắp tới */}
          <div className="border-t border-[var(--border-color)] pt-4 space-y-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold uppercase text-[var(--text-secondary)]">
              <GraduationCap className="h-4 w-4 text-[var(--color-primary)]" aria-hidden="true" />
              <span>Lịch thi sắp tới</span>
            </div>

            {examItems.length === 0 ? (
              <p className="text-xs italic text-[var(--text-secondary)]">
                Chưa có lịch thi trong 30 ngày tới.
              </p>
            ) : (
              <ul className="space-y-2.5">
                {examItems.map((exam) => {
                  const daysLeft = calcDaysLeft(exam.starts_at);
                  const countdownText =
                    daysLeft <= 0 ? "Hôm nay · còn 0 ngày" : `còn ${daysLeft} ngày`;

                  return (
                    <li
                      key={exam.id}
                      className="rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] p-2.5 text-xs space-y-1.5 min-w-0 break-words"
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-semibold text-[var(--text-primary)]">
                          {exam.course_name}
                        </span>
                        <span className="shrink-0 rounded-full bg-[var(--color-primary-light)] px-2 py-0.5 text-[11px] font-semibold text-[var(--color-primary)]">
                          {countdownText}
                        </span>
                      </div>

                      <div className="text-[var(--text-secondary)]">
                        {exam.course_code && (
                          <span className="mr-2 font-mono">{exam.course_code}</span>
                        )}
                        <span>
                          {formatVnDate(exam.starts_at)} ({formatVnTime(exam.starts_at)} –{" "}
                          {formatVnTime(exam.ends_at)})
                        </span>
                      </div>

                      {exam.location_label && (
                        <div className="flex items-center gap-1 text-[var(--text-secondary)]">
                          <MapPin className="h-3 w-3 shrink-0" aria-hidden="true" />
                          <span className="truncate">{exam.location_label}</span>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </aside>
      </div>

      {/* Dialog Thêm / Sửa sự kiện cá nhân */}
      {isDialogOpen && (
        <div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="event-dialog-title"
          data-testid="event-dialog"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        >
          <div className="w-full max-w-lg rounded-xl border border-[var(--border-color)] bg-[var(--surface-card)] p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <h2 id="event-dialog-title" className="text-lg font-semibold text-[var(--text-primary)]">
                {editingItem ? "Sửa sự kiện cá nhân" : "Thêm sự kiện cá nhân"}
              </h2>
              <button
                type="button"
                onClick={closeDialog}
                aria-label="Đóng hộp thoại"
                className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--text-secondary)] hover:bg-[var(--surface-subtle)] hover:text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>

            <form noValidate onSubmit={(e) => void handleSaveEvent(e)} className="space-y-4">
              {/* Tên sự kiện */}
              <div>
                <label
                  htmlFor="event-title"
                  className="block text-sm font-medium text-[var(--text-primary)]"
                >
                  Tên sự kiện <span className="text-red-500">*</span>
                </label>
                <input
                  id="event-title"
                  type="text"
                  maxLength={120}
                  required
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="Ví dụ: Ôn tập nhóm, Nộp đồ án..."
                  className="mt-1 block min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] px-3 py-2 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                />
              </div>

              {/* Ngày */}
              <div>
                <label
                  htmlFor="event-date"
                  className="block text-sm font-medium text-[var(--text-primary)]"
                >
                  Ngày <span className="text-red-500">*</span>
                </label>
                <input
                  id="event-date"
                  type="date"
                  required
                  value={formDate}
                  onChange={(e) => setFormDate(e.target.value)}
                  className="mt-1 block min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] px-3 py-2 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                />
              </div>

              {/* Giờ bắt đầu & Giờ kết thúc */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="event-start-time"
                    className="block text-sm font-medium text-[var(--text-primary)]"
                  >
                    Giờ bắt đầu <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="event-start-time"
                    type="time"
                    required
                    value={formStartTime}
                    onChange={(e) => handleStartTimeChange(e.target.value)}
                    className="mt-1 block min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] px-3 py-2 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                  />
                </div>
                <div>
                  <label
                    htmlFor="event-end-time"
                    className="block text-sm font-medium text-[var(--text-primary)]"
                  >
                    Giờ kết thúc <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="event-end-time"
                    type="time"
                    required
                    value={formEndTime}
                    onChange={(e) => handleEndTimeChange(e.target.value)}
                    className="mt-1 block min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] px-3 py-2 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                  />
                  {timeError && (
                    <p className="mt-1 text-xs font-medium text-red-600">{timeError}</p>
                  )}
                </div>
              </div>

              {/* Địa điểm */}
              <div>
                <label
                  htmlFor="event-location"
                  className="block text-sm font-medium text-[var(--text-primary)]"
                >
                  Địa điểm
                </label>
                <input
                  id="event-location"
                  type="text"
                  value={formLocation}
                  onChange={(e) => setFormLocation(e.target.value)}
                  placeholder="Ví dụ: Thư viện, Tầng 3 H1..."
                  className="mt-1 block min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] px-3 py-2 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                />
              </div>

              {/* Ghi chú */}
              <div>
                <label
                  htmlFor="event-note"
                  className="block text-sm font-medium text-[var(--text-primary)]"
                >
                  Ghi chú
                </label>
                <textarea
                  id="event-note"
                  value={formNote}
                  onChange={(e) => setFormNote(e.target.value)}
                  placeholder="Nội dung cần chuẩn bị hoặc lưu ý..."
                  rows={3}
                  className="mt-1 block w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] px-3 py-2 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
                />
              </div>

              {formError && (
                <p role="alert" className="text-xs font-medium text-red-600">
                  {formError}
                </p>
              )}

              {/* Nút hành động */}
              <div className="flex items-center justify-end gap-3 border-t border-[var(--border-color)] pt-3">
                <button
                  type="button"
                  onClick={closeDialog}
                  className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  data-testid="event-save-button"
                  disabled={isSaving}
                  className="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-[var(--color-primary)] px-5 py-2 text-sm font-medium text-[var(--color-on-primary)] hover:bg-[var(--color-primary-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)] disabled:opacity-50"
                >
                  {isSaving ? "Đang lưu…" : editingItem ? "Cập nhật" : "Lưu sự kiện"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
