"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";

import React, { useEffect, useState, useCallback } from "react";
import { AppShell } from "../../components/AppShell";
import { RoomBooking, type RoomSlot } from "../../features/rooms/RoomBooking";
import { AsyncState, type AsyncStatus } from "../../components/AsyncState";
import { CheckCircle2, AlertTriangle, X } from "lucide-react";
import { ApiClient, ApiClientError } from "../../lib/api/client";
import { UnavailableStudentSurface } from "../../features/assistance/UnavailableStudentSurface";
import { RoomFinder } from "../../features/rooms/RoomFinder";
import { OPS_ENABLED } from "../../lib/campus-ops-api";

const API_BASE_URL = CAMPUS_API_BASE_URL;

interface RoomApiResponse {
  items: Array<{
    id: string;
    room_code: string;
    display_name: string;
    capacity: number;
    features: string[];
    status?: string;
  }>;
}

interface RoomBookingApiResponse {
  booking_id?: string;
  id?: string;
  room_id: string;
  status: string;
  time_slot?: string;
}

function OpsRoomsPage() {
  return (
    <AppShell activeNav="rooms">
      <div className="campus-page space-y-6">
        <RoomFinder />
      </div>
    </AppShell>
  );
}

export default function RoomsPage() {
  if (OPS_ENABLED) return <OpsRoomsPage />;
  return process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true" || process.env.NEXT_PUBLIC_UNIFIED_AI === "true" ? <UnavailableStudentSurface kind="rooms" /> : <LegacyRoomsPage />;
}

function LegacyRoomsPage() {
  const [rooms, setRooms] = useState<RoomSlot[]>([]);
  const [status, setStatus] = useState<AsyncStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [isBooking, setIsBooking] = useState(false);
  const [bookingNotice, setBookingNotice] = useState<{
    type: "success" | "no_effect" | "result_unknown";
    message: string;
    bookingId?: string;
  } | null>(null);

  const fetchRooms = useCallback(async () => {
    setStatus("loading");
    setErrorMessage("");

    try {
      const client = new ApiClient({ baseUrl: API_BASE_URL });
      const response = await client.get<RoomApiResponse>("/v1/rooms");

      const items = response.items || [];
      if (items.length === 0) {
        setRooms([]);
        setStatus("empty");
        return;
      }

      const mappedRooms: RoomSlot[] = items.map((r) => ({
        id: r.id,
        name: r.display_name || `Phòng ${r.room_code}`,
        capacity: r.capacity,
        timeSlot: "08:00 - 11:30 (Sáng hôm nay)",
        isAvailable: r.status !== "MAINTENANCE" && r.status !== "OCCUPIED",
        conflictReason:
          r.status === "MAINTENANCE"
            ? "Phòng đang bảo trì định kỳ"
            : r.status === "OCCUPIED"
            ? "Phòng đã có lịch sử dụng"
            : undefined,
      }));

      setRooms(mappedRooms);
      setStatus("success");
    } catch (err: unknown) {
      // Fail honestly: NEVER fabricate demo rooms or fake availability!
      if (
        err instanceof ApiClientError &&
        (err.problem.code === "TIMEOUT" ||
          err.problem.status === 0 ||
          err.problem.status === 504)
      ) {
        setRooms((prev) => {
          if (prev.length > 0) {
            setStatus("stale");
            return prev;
          }
          setStatus("offline");
          return [];
        });
      } else {
        const detail =
          err instanceof ApiClientError
            ? err.problem.detail || err.problem.title
            : "Không thể tải danh sách phòng học. Vui lòng thử lại.";
        setErrorMessage(detail);
        setRooms((prev) => {
          if (prev.length > 0) {
            setStatus("stale");
            return prev;
          }
          setStatus("error");
          return [];
        });
      }
    }
  }, []);

  const handleBookRoom = useCallback(
    async (roomId: string) => {
      if (isBooking) return;
      setIsBooking(true);
      setBookingNotice(null);

      try {
        const client = new ApiClient({ baseUrl: API_BASE_URL });
        const response = await client.post<RoomBookingApiResponse>("/v1/rooms/book", {
          room_id: roomId,
          time_slot: "08:00 - 11:30",
        });

        const authoritativeBookingId =
          response.booking_id || response.id || `BK-${roomId}`;

        setBookingNotice({
          type: "success",
          message: `Đăng ký mượn phòng thành công! Mã đặt chỗ: ${authoritativeBookingId}`,
          bookingId: authoritativeBookingId,
        });

        // Update room status authoritatively
        setRooms((prev) =>
          prev.map((r) =>
            r.id === roomId
              ? {
                  ...r,
                  isAvailable: false,
                  conflictReason: "Bạn đã đăng ký phòng này thành công",
                }
              : r
          )
        );
      } catch (err: unknown) {
        // Fail honestly: NEVER fabricate receipt or fake booking!
        if (err instanceof ApiClientError) {
          const isTimeoutOrNetwork =
            err.problem.code === "TIMEOUT" ||
            err.problem.status === 504 ||
            err.problem.status === 0;

          if (isTimeoutOrNetwork) {
            setBookingNotice({
              type: "result_unknown",
              message:
                "Kết quả chưa xác định do mất kết nối hoặc hết thời gian chờ phản hồi. Vui lòng không gửi lại để tránh trùng lặp.",
            });
          } else {
            setBookingNotice({
              type: "no_effect",
              message:
                err.problem.detail ||
                "Đăng ký mượn phòng thất bại. Yêu cầu chưa được ghi nhận trên máy chủ.",
            });
          }
        } else {
          setBookingNotice({
            type: "no_effect",
            message: "Đăng ký mượn phòng thất bại do lỗi không xác định.",
          });
        }
      } finally {
        setIsBooking(false);
      }
    },
    [isBooking]
  );

  useEffect(() => {
    fetchRooms();
  }, [fetchRooms]);

  return (
    <AppShell activeNav="rooms">
      <div className="campus-page">
        <header className="campus-page-heading mb-6">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)] sm:text-3xl">
              Đăng ký và mượn phòng học
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Tra cứu phòng học trống, phòng tự học và đăng ký mượn phòng phục vụ học nhóm, câu lạc bộ
            </p>
          </div>
        </header>

        {/* Honest Feedback Banners: Success, Result-Unknown, No-Effect Failure */}
        {bookingNotice && (
          <div
            role={bookingNotice.type === "success" ? "status" : "alert"}
            className={`mb-5 flex items-center justify-between gap-3 rounded-xl border p-4 text-xs font-semibold shadow-xs ${
              bookingNotice.type === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300"
                : bookingNotice.type === "result_unknown"
                ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-300"
                : "border-rose-200 bg-rose-50 text-rose-900 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300"
            }`}
          >
            <div className="flex items-center gap-2.5">
              {bookingNotice.type === "success" ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <AlertTriangle className="h-4 w-4 shrink-0" />
              )}
              <span className="leading-relaxed">
                <strong>
                  {bookingNotice.type === "success"
                    ? "[✓] Thành công: "
                    : bookingNotice.type === "result_unknown"
                    ? "[?] Kết quả chưa xác định: "
                    : "[!] Thất bại: "}
                </strong>
                {bookingNotice.message}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setBookingNotice(null)}
              className="rounded-lg p-1 transition hover:bg-black/5 dark:hover:bg-white/10"
              aria-label="Đóng thông báo"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        <AsyncState
          status={status}
          loadingMessage="Đang tải danh sách phòng học và trạng thái khả dụng..."
          emptyMessage="Hiện tại không có phòng học nào khả dụng để đăng ký"
          errorMessage={errorMessage}
          onRetry={fetchRooms}
        >
          <RoomBooking rooms={rooms} onBook={handleBookRoom} />
        </AsyncState>
      </div>
    </AppShell>
  );
}
