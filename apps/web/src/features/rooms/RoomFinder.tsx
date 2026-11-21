"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Building2,
  Calendar,
  Clock,
  Search,
  CheckCircle2,
  AlertCircle,
  Wrench,
  X,
  RefreshCw,
  AlertTriangle,
  XCircle,
  Users,
  Info,
  Layers,
} from "lucide-react";
import { defaultBookingSlot, formatHold } from "./slots";
import {
  roomsApi,
  problemMessage,
  ApiClientError,
  type Room,
  type RoomList,
  type Availability,
  MAX_AVAILABILITY_BATCH,
  type Booking,
  type BookingPreview,
  type BusyInterval,
  type RoomKind,
} from "@/lib/campus-ops-api";
import { useT, type MessageKey } from "@/lib/i18n";

// Labels are message keys, translated where they are shown (this file's text lives in lib/i18n).
const FEATURE_KEYS: Record<string, MessageKey> = {
  MAY_CHIEU: "rooms.22", DIEU_HOA: "rooms.23", SAN_KHAU: "rooms.24", MAY_TINH: "rooms.25", MAN_HINH: "rooms.26", BANG_TRANG: "rooms.27",
};
const FEATURE_PLAIN: Record<string, string> = { WIFI: "Wi‑Fi", MICRO: "Micro" };

const KIND_KEYS: Record<RoomKind, MessageKey> = {
  lecture: "rooms.7", lab: "rooms.8", meeting: "rooms.9", study: "rooms.10", hall: "rooms.11",
};

function getHcmToday(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function addDays(dateStr: string, days: number): string {
  try {
    const [y, m, d] = dateStr.split("-").map(Number);
    const date = new Date(Date.UTC(y, m - 1, d));
    date.setUTCDate(date.getUTCDate() + days);
    return date.toISOString().slice(0, 10);
  } catch {
    return dateStr;
  }
}

function formatHcmDateTime(isoString: string): string {
  try {
    return new Intl.DateTimeFormat("vi-VN", {
      timeZone: "Asia/Ho_Chi_Minh",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(isoString));
  } catch {
    return isoString;
  }
}

function parseTimeToMinutes(timeOrIso: string): number {
  if (timeOrIso.includes("T")) {
    try {
      const parts = new Intl.DateTimeFormat("vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(new Date(timeOrIso)).split(":");
      return Number(parts[0]) * 60 + Number(parts[1]);
    } catch {
      return 0;
    }
  }
  const [h, m] = timeOrIso.split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
}

const TIME_OPTIONS: string[] = (() => {
  const opts: string[] = [];
  for (let h = 7; h <= 21; h++) {
    for (let m = 0; m < 60; m += 15) {
      if (h === 21 && m > 0) break;
      opts.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
    }
  }
  return opts;
})();

function isRoomBusy(busyList: BusyInterval[] | undefined, start: string, end: string): boolean {
  if (!busyList || busyList.length === 0) return false;
  const sMin = parseTimeToMinutes(start);
  const eMin = parseTimeToMinutes(end);
  return busyList.some((b) => {
    const bStart = parseTimeToMinutes(b.starts_at);
    const bEnd = parseTimeToMinutes(b.ends_at);
    return sMin < bEnd && eMin > bStart;
  });
}

export function RoomFinder() {
  const t = useT();
  const [roomList, setRoomList] = useState<RoomList | null>(null);
  const [roomsLoading, setRoomsLoading] = useState(true);
  const [roomsError, setRoomsError] = useState<string | null>(null);

  const [q, setQ] = useState("");
  const [building, setBuilding] = useState("");
  const [kind, setKind] = useState<RoomKind | "">("");
  const [minCapacity, setMinCapacity] = useState<string>("");
  const [initialSlot] = useState(() => defaultBookingSlot());
  const [date, setDate] = useState(initialSlot.date);
  const [start, setStart] = useState(initialSlot.start);
  const [end, setEnd] = useState(initialSlot.end);

  const [availabilityMap, setAvailabilityMap] = useState<Record<string, Availability>>({});
  const availReqIdRef = useRef(0);

  const [dialogRoom, setDialogRoom] = useState<Room | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const [purpose, setPurpose] = useState("");
  const [attendees, setAttendees] = useState(1);
  const [preview, setPreview] = useState<BookingPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [networkUncertain, setNetworkUncertain] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [bookingSuccessCode, setBookingSuccessCode] = useState<string | null>(null);

  const [myBookings, setMyBookings] = useState<Booking[]>([]);
  const [mineLoading, setMineLoading] = useState(false);
  const [mineError, setMineError] = useState<string | null>(null);
  const [cancellingCode, setCancellingCode] = useState<string | null>(null);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const isTimeInvalid = end <= start;

  const loadAvailability = useCallback(async (rooms: Room[], targetDate: string) => {
    const reqId = ++availReqIdRef.current;
    const nextMap: Record<string, Availability> = {};
    // One request per MAX_AVAILABILITY_BATCH rooms (a page load used to send one per room).
    for (let i = 0; i < rooms.length; i += MAX_AVAILABILITY_BATCH) {
      if (availReqIdRef.current !== reqId) return;
      const res = await roomsApi.availabilityMany(rooms.slice(i, i + MAX_AVAILABILITY_BATCH).map((r) => r.id), targetDate).catch(() => null);
      if (availReqIdRef.current !== reqId) return;
      res?.items.forEach((item) => {
        nextMap[item.room.id] = { room: item.room, date: res.date, open: res.open, close: res.close, busy: item.busy, limits: res.limits };
      });
    }

    if (availReqIdRef.current === reqId) {
      setAvailabilityMap(nextMap);
    }
  }, []);

  const fetchRooms = useCallback(async () => {
    setRoomsLoading(true);
    setRoomsError(null);
    try {
      const res = await roomsApi.list({
        building: building || undefined,
        kind: kind || undefined,
        min_capacity: minCapacity ? Number(minCapacity) : undefined,
        q: q.trim() || undefined,
      });
      setRoomList(res);
      loadAvailability(res.items, date);
    } catch (err) {
      setRoomsError(problemMessage(err));
    } finally {
      setRoomsLoading(false);
    }
  }, [building, kind, minCapacity, q, date, loadAvailability]);

  const fetchMine = useCallback(async () => {
    setMineLoading(true);
    setMineError(null);
    try {
      const res = await roomsApi.mine();
      setMyBookings(res.items || []);
    } catch (err) {
      setMineError(problemMessage(err));
    } finally {
      setMineLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRooms();
  }, [fetchRooms]);

  useEffect(() => {
    fetchMine();
  }, [fetchMine]);

  const handleDateChange = (newDate: string) => {
    setDate(newDate);
    if (roomList?.items) {
      loadAvailability(roomList.items, newDate);
    }
  };

  const openBookingDialog = (room: Room, btn: HTMLButtonElement) => {
    triggerRef.current = btn;
    setDialogRoom(room);
    setPurpose("");
    setAttendees(1);
    setPreview(null);
    setPreviewError(null);
    setConfirmError(null);
    setNetworkUncertain(false);
    setBookingSuccessCode(null);
    setIdempotencyKey(roomsApi.newKey());
  };

  const closeBookingDialog = useCallback(() => {
    setDialogRoom(null);
    setPreview(null);
    setBookingSuccessCode(null);
    setTimeout(() => {
      triggerRef.current?.focus();
    }, 0);
  }, []);

  useEffect(() => {
    if (!dialogRoom) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeBookingDialog();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [dialogRoom, closeBookingDialog]);

  const handlePreview = async () => {
    if (!dialogRoom) return;
    if (purpose.trim().length < 3 || purpose.trim().length > 200) {
      setPreviewError(t("rooms.28"));
      return;
    }
    if (attendees < 1 || attendees > dialogRoom.capacity) {
      setPreviewError(t("rooms3.1", { max: dialogRoom.capacity }));
      return;
    }
    setPreviewLoading(true);
    setPreviewError(null);
    setConfirmError(null);
    setNetworkUncertain(false);
    try {
      const res = await roomsApi.preview({
        room_id: dialogRoom.id,
        date,
        start,
        end,
        purpose: purpose.trim(),
        attendees,
      });
      setPreview(res);
      setIdempotencyKey(roomsApi.newKey());
    } catch (err) {
      setPreviewError(problemMessage(err));
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!preview || !preview.can_confirm) return;
    setConfirmLoading(true);
    setConfirmError(null);
    setNetworkUncertain(false);
    try {
      const res = await roomsApi.confirm(preview.preview_id, idempotencyKey);
      setBookingSuccessCode(res.code);
      window.dispatchEvent(new Event("campus:notifications-changed"));
      fetchRooms();
      fetchMine();
    } catch (err) {
      if (err instanceof ApiClientError && (err.status === 0 || err.status === 504)) {
        setNetworkUncertain(true);
      } else {
        setConfirmError(problemMessage(err));
      }
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleCancelBooking = async (bookingId: string) => {
    setCancelLoading(true);
    setCancelError(null);
    try {
      await roomsApi.cancel(bookingId);
      window.dispatchEvent(new Event("campus:notifications-changed"));
      setCancellingCode(null);
      fetchMine();
      if (roomList?.items) {
        loadAvailability(roomList.items, date);
      }
    } catch (err) {
      setCancelError(problemMessage(err));
    } finally {
      setCancelLoading(false);
    }
  };

  const today = getHcmToday();
  const maxDate = roomList?.limits?.horizon_days ? addDays(today, roomList.limits.horizon_days) : undefined;

  return (
    <div data-testid="room-finder" className="space-y-8">
      <header className="campus-page-heading">
        <div data-eyebrow={t("rooms.29")}>
          <h1 className="text-2xl font-semibold">{t("rooms.1")}</h1>
          <p>{t("rooms.2")}</p>
        </div>
      </header>

      {roomList?.source === "LOCAL_SYNTHETIC" && (
        <div
          role="note"
          className="flex items-center gap-3 rounded-lg border border-[var(--border-color)] bg-[var(--surface-subtle)] p-3 text-sm text-[var(--text-secondary)]"
        >
          <Info className="h-4 w-4 shrink-0 text-[var(--color-primary)]" aria-hidden="true" />
          <span>{t("rooms.3")}</span>
        </div>
      )}

      <section className="campus-panel space-y-4">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">{t("rooms.4")}</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label htmlFor="search-input" className="block text-xs font-medium text-[var(--text-secondary)]">
              {t("rooms2.1")}
            </label>
            <div className="relative mt-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-[var(--text-secondary)]" aria-hidden="true" />
              <input
                id="search-input"
                type="text"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={t("rooms.30")}
                className="min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] pl-9 pr-3 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              />
            </div>
          </div>

          <div>
            <label htmlFor="building-select" className="block text-xs font-medium text-[var(--text-secondary)]">
              {t("rooms2.2")}
            </label>
            <select
              id="building-select"
              value={building}
              onChange={(e) => setBuilding(e.target.value)}
              className="mt-1 min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-3 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
            >
              <option value="">{t("rooms.5")}</option>
              {roomList?.buildings.map((b) => (
                <option key={b} value={b}>
                  {t("rooms3.2", { b })}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="kind-select" className="block text-xs font-medium text-[var(--text-secondary)]">
              {t("rooms2.3")}
            </label>
            <select
              id="kind-select"
              value={kind}
              onChange={(e) => setKind(e.target.value as RoomKind | "")}
              className="mt-1 min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-3 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
            >
              <option value="">{t("rooms.6")}</option>
              <option value="lecture">{t("rooms.7")}</option>
              <option value="lab">{t("rooms.8")}</option>
              <option value="meeting">{t("rooms.9")}</option>
              <option value="study">{t("rooms.10")}</option>
              <option value="hall">{t("rooms.11")}</option>
            </select>
          </div>

          <div>
            <label htmlFor="min-capacity-input" className="block text-xs font-medium text-[var(--text-secondary)]">
              {t("rooms2.4")}
            </label>
            <input
              id="min-capacity-input"
              type="number"
              min="0"
              value={minCapacity}
              onChange={(e) => setMinCapacity(e.target.value)}
              placeholder="VD: 30"
              className="mt-1 min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-3 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 border-t border-[var(--border-color)] pt-4 sm:grid-cols-3">
          <div>
            <label htmlFor="date-input" className="block text-xs font-medium text-[var(--text-secondary)]">
              {t("rooms2.5")}
            </label>
            <div className="relative mt-1">
              <Calendar className="absolute left-3 top-3 h-4 w-4 text-[var(--text-secondary)]" aria-hidden="true" />
              <input
                id="date-input"
                type="date"
                min={today}
                max={maxDate}
                value={date}
                onChange={(e) => handleDateChange(e.target.value)}
                className="min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] pl-9 pr-3 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              />
            </div>
          </div>

          <div>
            <label htmlFor="start-time-select" className="block text-xs font-medium text-[var(--text-secondary)]">
              {t("rooms2.6")}
            </label>
            <div className="relative mt-1">
              <Clock className="absolute left-3 top-3 h-4 w-4 text-[var(--text-secondary)]" aria-hidden="true" />
              <select
                id="start-time-select"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className="min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] pl-9 pr-3 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              >
                {TIME_OPTIONS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="end-time-select" className="block text-xs font-medium text-[var(--text-secondary)]">
              {t("rooms2.7")}
            </label>
            <div className="relative mt-1">
              <Clock className="absolute left-3 top-3 h-4 w-4 text-[var(--text-secondary)]" aria-hidden="true" />
              <select
                id="end-time-select"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className="min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] pl-9 pr-3 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              >
                {TIME_OPTIONS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            {isTimeInvalid && (
              <p className="mt-1 text-xs text-red-600" role="alert">
                {t("rooms2.8")}
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            {t("rooms3.3")} {roomList?.items ? `(${roomList.items.length})` : ""}
          </h2>
        </div>

        {roomsLoading && (
          <div role="status" className="campus-panel py-12 text-center text-sm text-[var(--text-secondary)]">
            <RefreshCw className="mx-auto mb-2 h-6 w-6 animate-spin text-[var(--color-primary)]" aria-hidden="true" />
            <span>{t("rooms.12")}</span>
          </div>
        )}

        {roomsError && !roomsLoading && (
          <div role="alert" className="campus-panel py-8 text-center space-y-3">
            <AlertCircle className="mx-auto h-8 w-8 text-red-600" aria-hidden="true" />
            <p className="text-sm font-medium text-red-600">{roomsError}</p>
            <button
              type="button"
              onClick={fetchRooms}
              className="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
            >
              {t("rooms2.9")}
            </button>
          </div>
        )}

        {!roomsLoading && !roomsError && roomList?.items.length === 0 && (
          <div className="campus-panel py-12 text-center space-y-2">
            <Info className="mx-auto h-8 w-8 text-[var(--text-secondary)]" aria-hidden="true" />
            <p className="text-base font-semibold text-[var(--text-primary)]">{t("rooms.13")}</p>
            <p className="text-sm text-[var(--text-secondary)]">
              {t("rooms2.10")}
            </p>
          </div>
        )}

        {!roomsLoading && !roomsError && roomList && roomList.items.length > 0 && (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
            {roomList.items.map((room) => {
              const avail = availabilityMap[room.id];
              const isMaintenance = room.status === "MAINTENANCE";
              const busy = isMaintenance ? false : isRoomBusy(avail?.busy, start, end);
              const cannotBook = isMaintenance || busy || isTimeInvalid;

              let disabledReason = "";
              if (isMaintenance) {
                disabledReason = t("rooms.31");
              } else if (isTimeInvalid) {
                disabledReason = t("rooms.32");
              } else if (busy) {
                disabledReason = t("rooms.33");
              }

              return (
                <div
                  key={room.id}
                  data-testid={`room-card-${room.room_code}`}
                  data-state={isMaintenance ? "maintenance" : busy ? "busy" : "free"}
                  className="campus-panel campus-room-card flex flex-col justify-between space-y-4"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <span className="text-xs font-semibold text-[var(--color-primary)] uppercase tracking-wider">
                          {room.room_code}
                        </span>
                        <h3 className="text-base font-semibold text-[var(--text-primary)] break-words">
                          {room.display_name}
                        </h3>
                        <p className="text-xs text-[var(--text-secondary)]">
                          {t("rooms3.4", { building: room.building, floor: room.floor })}
                        </p>
                      </div>
                      <span className="inline-flex shrink-0 items-center gap-1 rounded bg-[var(--surface-subtle)] px-2 py-1 text-xs text-[var(--text-secondary)]">
                        <Users className="h-3 w-3" aria-hidden="true" />
                        {t("rooms3.5", { n: room.capacity })}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5 text-xs text-[var(--text-secondary)]">
                      <span className="rounded border border-[var(--border-color)] px-2 py-0.5 font-medium">
                        {KIND_KEYS[room.kind] ? t(KIND_KEYS[room.kind]) : room.kind}
                      </span>
                      {room.features.map((f) => (
                        <span
                          key={f}
                          className="rounded bg-[var(--color-primary-light)] px-2 py-0.5 font-medium text-[var(--color-primary)]"
                        >
                          {FEATURE_KEYS[f] ? t(FEATURE_KEYS[f]) : (FEATURE_PLAIN[f] || f)}
                        </span>
                      ))}
                    </div>

                    <div className="pt-1">
                      {isMaintenance ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800 border border-amber-200">
                          <Wrench className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                          {t("rooms2.11")}
                        </span>
                      ) : busy ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-800 border border-red-200">
                          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                          {t("rooms2.12")}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800 border border-emerald-200">
                          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                          {t("rooms2.13")}
                        </span>
                      )}
                    </div>

                    <div className="space-y-1 pt-2">
                      <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
                        <span>{t("rooms.14")}</span>
                        <div className="flex items-center gap-2">
                          <span className="flex items-center gap-1">
                            <span className="inline-block h-2 w-2 rounded-full bg-[var(--color-primary)]" />
                            {t("rooms2.14")}
                          </span>
                          <span className="flex items-center gap-1">
                            <span className="inline-block h-2 w-2 rounded-full bg-slate-400" />
                            {t("rooms2.15")}
                          </span>
                          <span className="flex items-center gap-1">
                            <span className="inline-block h-2 w-2 rounded-full bg-amber-600" />
                            {t("rooms2.16")}
                          </span>
                        </div>
                      </div>

                      <div className="relative h-5 w-full rounded bg-[var(--surface-subtle)] border border-[var(--border-color)] overflow-hidden">
                        {avail?.busy.map((b, idx) => {
                          const sMin = parseTimeToMinutes(b.starts_at);
                          const eMin = parseTimeToMinutes(b.ends_at);
                          const startClamped = Math.max(420, Math.min(1260, sMin));
                          const endClamped = Math.max(420, Math.min(1260, eMin));
                          if (endClamped <= startClamped) return null;
                          const leftPct = ((startClamped - 420) / 840) * 100;
                          const widthPct = ((endClamped - startClamped) / 840) * 100;

                          let bgClass = "bg-[var(--color-primary)]";
                          if (b.type === "CLASS") bgClass = "bg-slate-400";
                          if (b.type === "EXAM") bgClass = "bg-amber-600";

                          return (
                            <div
                              key={idx}
                              title={`${b.label}: ${b.starts_at} - ${b.ends_at}`}
                              style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                              className={`absolute top-0 bottom-0 ${bgClass} opacity-85`}
                            />
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-[var(--border-color)]">
                    <button
                      type="button"
                      data-testid={`room-book-${room.room_code}`}
                      disabled={cannotBook}
                      title={cannotBook ? disabledReason : t("rooms.34")}
                      onClick={(e) => openBookingDialog(room, e.currentTarget)}
                      className="min-h-[44px] w-full rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                    >
                      {t("rooms2.17")}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {dialogRoom && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="booking-dialog-title"
          data-testid="booking-dialog"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        >
          <div className="campus-panel relative max-h-[90vh] w-full max-w-lg overflow-y-auto space-y-4">
            <div className="flex items-start justify-between border-b border-[var(--border-color)] pb-3">
              <div>
                <h3 id="booking-dialog-title" className="text-lg font-semibold text-[var(--text-primary)]">
                  {t("rooms2.18")}
                </h3>
                <p className="text-xs text-[var(--text-secondary)]">
                  {dialogRoom.display_name} ({dialogRoom.room_code}) · {t("rooms3.6", { date, start, end })}
                </p>
              </div>
              <button
                type="button"
                aria-label={t("rooms.35")}
                onClick={closeBookingDialog}
                className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--text-secondary)] hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>

            {bookingSuccessCode ? (
              <div className="space-y-4 py-4 text-center">
                <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-600" aria-hidden="true" />
                <div className="space-y-1">
                  <h4 className="text-base font-semibold text-[var(--text-primary)]">{t("rooms.15")}</h4>
                  <p className="text-sm text-[var(--text-secondary)]">
                    {t("rooms3.7")} <strong className="text-[var(--text-primary)]">{bookingSuccessCode}</strong>
                  </p>
                </div>
                <button
                  type="button"
                  onClick={closeBookingDialog}
                  className="min-h-[44px] w-full rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                >
                  {t("rooms2.19")}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label htmlFor="purpose-input" className="block text-xs font-medium text-[var(--text-secondary)]">
                    {t("rooms2.20")}
                  </label>
                  <textarea
                    id="purpose-input"
                    rows={3}
                    value={purpose}
                    onChange={(e) => setPurpose(e.target.value)}
                    placeholder={t("rooms.36")}
                    className="mt-1 min-h-[80px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] p-3 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                  />
                </div>

                <div>
                  <label htmlFor="attendees-input" className="block text-xs font-medium text-[var(--text-secondary)]">
                    {t("rooms3.8", { max: dialogRoom.capacity })}
                  </label>
                  <input
                    id="attendees-input"
                    type="number"
                    min="1"
                    max={dialogRoom.capacity}
                    value={attendees}
                    onChange={(e) => setAttendees(Number(e.target.value))}
                    className="mt-1 min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-3 text-sm text-[var(--text-primary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                  />
                </div>

                {previewError && (
                  <div role="alert" className="rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-200">
                    {previewError}
                  </div>
                )}

                {preview && preview.problems.length > 0 && (
                  <div role="alert" className="rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-200 space-y-1">
                    <p className="font-semibold">{t("rooms.16")}</p>
                    <ul className="list-disc pl-4 space-y-0.5">
                      {preview.problems.map((p, idx) => (
                        <li key={idx}>{p}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {preview && preview.can_confirm && (
                  <div className="rounded-lg bg-emerald-50 p-3 text-xs text-emerald-800 border border-emerald-200 space-y-1">
                    <p className="font-semibold">{t("rooms.17")}</p>
                    {preview.notice && <p>{preview.notice}</p>}
                    <p className="text-[11px] text-emerald-700">
                      {formatHold(preview.expires_at)}
                    </p>
                  </div>
                )}

                {networkUncertain && (
                  <div role="alert" className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800 border border-amber-200 space-y-2">
                    <p className="font-semibold">{t("rooms.18")}</p>
                    <p>{t("rooms.19")}</p>
                    <button
                      type="button"
                      onClick={() => {
                        fetchMine();
                        closeBookingDialog();
                      }}
                      className="min-h-[44px] w-full rounded bg-amber-600 px-3 py-2 text-xs font-medium text-white hover:bg-amber-700"
                    >
                      {t("rooms2.21")}
                    </button>
                  </div>
                )}

                {confirmError && (
                  <div role="alert" className="rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-200">
                    {confirmError}
                  </div>
                )}

                <div className="flex flex-col gap-2 pt-2 border-t border-[var(--border-color)]">
                  <button
                    type="button"
                    data-testid="booking-preview-button"
                    disabled={previewLoading || confirmLoading}
                    onClick={handlePreview}
                    className="min-h-[44px] w-full rounded-lg border border-[var(--border-color)] bg-[var(--surface-card)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                  >
                    {previewLoading ? t("rooms.37") : t("rooms.38")}
                  </button>

                  <button
                    type="button"
                    data-testid="booking-confirm-button"
                    disabled={!preview?.can_confirm || confirmLoading}
                    onClick={handleConfirm}
                    className="min-h-[44px] w-full rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                  >
                    {confirmLoading ? t("rooms.39") : t("rooms.40")}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <section data-testid="my-bookings" className="campus-panel space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
          <div className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-[var(--color-primary)]" aria-hidden="true" />
            <h2 className="text-base font-semibold text-[var(--text-primary)]">{t("rooms.20")}</h2>
          </div>
          <button
            type="button"
            onClick={fetchMine}
            aria-label={t("rooms.41")}
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--text-secondary)] hover:bg-[var(--surface-subtle)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
          >
            <RefreshCw className={`h-4 w-4 ${mineLoading ? "animate-spin" : ""}`} aria-hidden="true" />
          </button>
        </div>

        {cancelError && (
          <div role="alert" className="rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-200">
            {cancelError}
          </div>
        )}

        {mineLoading && myBookings.length === 0 && (
          <div role="status" className="py-6 text-center text-sm text-[var(--text-secondary)]">
            {t("rooms2.22")}
          </div>
        )}

        {mineError && (
          <div role="alert" className="py-4 text-center space-y-2">
            <p className="text-sm text-red-600">{mineError}</p>
            <button
              type="button"
              onClick={fetchMine}
              className="min-h-[44px] px-4 py-1.5 rounded-lg border border-[var(--border-color)] text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-subtle)]"
            >
              {t("rooms2.9")}
            </button>
          </div>
        )}

        {!mineLoading && !mineError && myBookings.length === 0 && (
          <div className="py-8 text-center text-sm text-[var(--text-secondary)]">
            {t("rooms2.23")}
          </div>
        )}

        {!mineError && myBookings.length > 0 && (
          <div className="divide-y divide-[var(--border-color)]">
            {myBookings.map((b) => {
              const isConfirmed = b.status === "CONFIRMED";
              return (
                <div key={b.id} className="py-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-sm text-[var(--text-primary)]">
                        {t("rooms3.9")} {b.code}
                      </span>
                      {isConfirmed ? (
                        <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800 border border-emerald-200">
                          <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                          {t("rooms2.24")}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 border border-slate-200">
                          <XCircle className="h-3 w-3" aria-hidden="true" />
                          {t("rooms2.25")}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[var(--text-primary)] font-medium">
                      {b.room_name} ({b.room_code}) · {t("rooms3.10", { b: b.building })}
                    </p>
                    <p className="text-xs text-[var(--text-secondary)]">
                      {formatHcmDateTime(b.starts_at)} - {formatHcmDateTime(b.ends_at)}
                    </p>
                    <p className="text-xs text-[var(--text-secondary)] italic break-words">
                      {t("rooms3.11", { purpose: b.purpose, n: b.attendees })}
                    </p>
                  </div>

                  {b.can_cancel && isConfirmed && (
                    <div className="shrink-0">
                      {cancellingCode === b.code ? (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-[var(--text-secondary)]">{t("rooms.21")}</span>
                          <button
                            type="button"
                            disabled={cancelLoading}
                            onClick={() => handleCancelBooking(b.id)}
                            className="min-h-[44px] px-3 py-1.5 rounded-lg bg-red-600 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                          >
                            {t("rooms2.26")}
                          </button>
                          <button
                            type="button"
                            disabled={cancelLoading}
                            onClick={() => setCancellingCode(null)}
                            className="min-h-[44px] px-3 py-1.5 rounded-lg border border-[var(--border-color)] text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--surface-subtle)]"
                          >
                            {t("rooms2.27")}
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          data-testid={`booking-cancel-${b.code}`}
                          onClick={() => setCancellingCode(b.code)}
                          className="min-h-[44px] px-3 py-1.5 rounded-lg border border-red-300 bg-red-50 text-xs font-medium text-red-700 hover:bg-red-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
                        >
                          {t("rooms2.28")}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
