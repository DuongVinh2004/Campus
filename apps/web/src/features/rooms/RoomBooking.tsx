import React, { useState } from "react";
import {
  Building,
  Clock,
  CheckCircle2,
  ArrowRight,
  Accessibility,
  Tv,
  Calendar,
} from "lucide-react";
import { ActionOutcome, type ActionState } from "../../components/ActionOutcome";

export interface RoomSlot {
  id: string;
  name: string;
  capacity: number;
  timeSlot: string;
  isAvailable: boolean;
  conflictReason?: string;
  accessibility?: string;
  equipment?: string;
}

export interface RoomBookingProps {
  rooms?: RoomSlot[];
  actionOutcomeState?: ActionState;
  idempotencyKey?: string;
  onBook?: (roomId: string) => void;
  onReconcile?: (idempotencyKey: string) => void;
}

export function RoomBooking({
  rooms = [],
  actionOutcomeState,
  idempotencyKey = "idem-room-default",
  onBook,
  onReconcile,
}: RoomBookingProps) {
  const [filterCapacity, setFilterCapacity] = useState<number>(0);
  const [selectedRoom, setSelectedRoom] = useState<RoomSlot | null>(null);
  const [bookingDate, setBookingDate] = useState<string>(() => {
    const d = new Date();
    return d.toISOString().split("T")[0];
  });
  const [bookingShift, setBookingShift] = useState<string>("morning");
  const [bookingPurpose, setBookingPurpose] = useState<string>("");

  const SHIFTS: Record<string, { label: string; time: string }> = {
    morning: { label: "Ca sáng", time: "07:00 - 11:30" },
    afternoon: { label: "Ca chiều", time: "13:00 - 17:00" },
    evening: { label: "Ca tối", time: "18:00 - 21:00" },
  };

  const filteredRooms = rooms.filter((room) => room.capacity >= filterCapacity);

  const handleConfirm = () => {
    if (selectedRoom) {
      onBook?.(selectedRoom.id);
      setSelectedRoom(null);
      setBookingPurpose("");
    }
  };

  if (selectedRoom) {
    return (
      <section
        aria-labelledby="booking-preview-heading"
        className="flex flex-col gap-6 fluent-card border border-[var(--border-color)] bg-[var(--surface-card)] p-6 sm:p-8"
      >
        <div className="border-b border-[var(--border-color)] pb-4">
          <div className="mb-1.5 flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-primary-light)] text-[var(--color-primary)]">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <h2
              id="booking-preview-heading"
              className="text-lg font-bold tracking-tight text-[var(--text-primary)] sm:text-xl"
            >
              Xác nhận đăng ký mượn phòng học
            </h2>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Bạn hãy kiểm tra lại thông tin phòng và thời gian mượn trước khi gửi yêu cầu nhé
          </p>
        </div>

        {/* Structured Booking Preview */}
        <dl className="grid grid-cols-1 gap-4 rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] p-4 text-xs sm:p-5">
          <div>
            <dt className="font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
              Phòng đăng ký
            </dt>
            <dd className="mt-1 text-base font-bold text-[var(--text-primary)]">
              {selectedRoom.name} ({selectedRoom.capacity} chỗ ngồi) - Khu giảng đường HUCE
            </dd>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                Thời gian mượn (Giờ Việt Nam, UTC+7)
              </dt>
              <dd className="mt-1 font-bold text-[var(--text-primary)]">
                {selectedRoom.timeSlot}
              </dd>
            </div>

            <div>
              <dt className="font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
                Hỗ trợ tiếp cận & Cơ sở vật chất
              </dt>
              <dd className="mt-1 text-[var(--text-secondary)]">
                {selectedRoom.accessibility || "Tiêu chuẩn"} ·{" "}
                {selectedRoom.equipment || "Tiêu chuẩn"}
              </dd>
            </div>
          </div>

          <div>
            <dt className="font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
              Quy trình phê duyệt
            </dt>
            <dd className="mt-1 leading-relaxed text-[var(--text-secondary)]">
              Yêu cầu mượn phòng cần được Ban Quản lý Giảng đường xét duyệt (dự kiến phản hồi trong 24 giờ làm việc).
            </dd>
          </div>

          <div>
            <dt className="font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
              Quy định hủy mượn phòng
            </dt>
            <dd className="mt-1 leading-relaxed text-[var(--text-secondary)]">
              Bạn có thể hủy đăng ký trước giờ bắt đầu tối thiểu 2 giờ mà không bị tính điểm phạt vi phạm quy chế cơ sở vật chất.
            </dd>
          </div>
        </dl>

        {/* Action Controls */}
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => setSelectedRoom(null)}
            className="fluent-btn-secondary text-xs"
          >
            Quay lại danh sách phòng
          </button>

          <button
            type="button"
            onClick={handleConfirm}
            className="fluent-btn-primary text-xs"
          >
            <span>Xác nhận đặt phòng</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </section>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Ambiguous or Completed Action Outcome Banner */}
      {actionOutcomeState && (
        <ActionOutcome
          state={actionOutcomeState}
          idempotencyKey={idempotencyKey}
          actionTitle="Đăng ký mượn phòng học"
          onReconcile={onReconcile}
        />
      )}

      {/* Header and Filter */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="mb-1.5 flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-primary-light)] text-[var(--color-primary)]">
              <Building className="h-5 w-5" />
            </div>
            <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
              Tra cứu & Đăng ký mượn phòng học
            </h2>
          </div>
          <p className="text-xs text-[var(--text-secondary)]">
            Tra cứu phòng học trống, giảng đường lớn và phòng tự học phục vụ sinh hoạt học thuật HUCE
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <label
            htmlFor="capacity-filter"
            className="text-xs font-semibold text-[var(--text-primary)]"
          >
            Sức chứa tối thiểu:
          </label>
          <select
            id="capacity-filter"
            value={filterCapacity}
            onChange={(e) => setFilterCapacity(Number(e.target.value))}
            className="fluent-input min-h-[38px] cursor-pointer text-xs"
          >
            <option value={0}>Tất cả quy mô</option>
            <option value={50}>Từ 50+ chỗ ngồi</option>
            <option value={100}>Hội trường 100+ chỗ</option>
          </select>
        </div>
      </div>

      {/* Date + Shift Selector Bar */}
      <div className="fluent-card flex flex-wrap items-end gap-4 border border-[var(--border-color)] bg-[var(--surface-card)] p-4 shadow-xs sm:p-5">
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="booking-date"
            className="text-[11px] font-bold text-[var(--text-secondary)] uppercase tracking-wider"
          >
            Ngày mượn
          </label>
          <input
            id="booking-date"
            type="date"
            value={bookingDate}
            onChange={(e) => setBookingDate(e.target.value)}
            min={new Date().toISOString().split("T")[0]}
            className="fluent-input min-h-[38px] cursor-pointer text-xs"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-[11px] font-bold text-[var(--text-secondary)] uppercase tracking-wider">
            Ca mượn
          </span>
          <div className="flex gap-1.5">
            {Object.entries(SHIFTS).map(([key, shift]) => (
              <button
                key={key}
                type="button"
                onClick={() => setBookingShift(key)}
                className={`rounded-xl px-3.5 py-1.5 text-xs transition ${
                  bookingShift === key
                    ? "border border-[var(--color-primary)] bg-[var(--color-primary-light)] font-bold text-[var(--color-primary)] shadow-xs"
                    : "border border-[var(--border-color)] bg-[var(--surface-card)] font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-subtle)]"
                }`}
              >
                <div>{shift.label}</div>
                <div className="text-[10px] opacity-70">{shift.time}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="flex min-w-[200px] flex-1 flex-col gap-1.5">
          <label
            htmlFor="booking-purpose"
            className="text-[11px] font-bold text-[var(--text-secondary)] uppercase tracking-wider"
          >
            Mục đích mượn
          </label>
          <input
            id="booking-purpose"
            type="text"
            value={bookingPurpose}
            onChange={(e) => setBookingPurpose(e.target.value)}
            placeholder="VD: Họp nhóm đồ án, Sinh hoạt CLB..."
            className="fluent-input min-h-[38px] text-xs"
          />
        </div>
      </div>

      {/* Room Grid */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
        {filteredRooms.map((room) => {
          const shortName = room.name.replace("Phòng ", "");
          return (
            <article
              key={room.id}
              className="fluent-card flex flex-col justify-between border border-[var(--border-color)] bg-[var(--surface-card)] p-5 transition hover:border-[var(--color-primary-border)] sm:p-6"
            >
              <div className="flex flex-col gap-4">
                <div className="flex items-start justify-between gap-2.5">
                  <div>
                    <h3 className="text-base font-bold text-[var(--text-primary)]">
                      {room.name} ({room.capacity} chỗ)
                    </h3>
                    <div className="mt-0.5 text-xs font-medium text-[var(--text-secondary)]">
                      Khu giảng đường HUCE
                    </div>
                  </div>

                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ${
                      room.isAvailable
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-400"
                        : "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-400"
                    }`}
                  >
                    {room.isAvailable ? "Còn trống" : "Trùng lịch"}
                  </span>
                </div>

                <div className="flex items-center gap-2 rounded-xl border border-[var(--border-color)] bg-[var(--surface-subtle)] p-2.5 text-xs text-[var(--text-primary)]">
                  <Clock className="h-4 w-4 text-[var(--text-secondary)]" />
                  <span>
                    Ca mượn: <strong className="font-semibold">{room.timeSlot}</strong>
                  </span>
                </div>

                {/* Accessibility and Equipment Facts */}
                <div className="flex flex-col gap-1 text-xs text-[var(--text-secondary)]">
                  {room.accessibility && (
                    <div className="flex items-center gap-1.5">
                      <Accessibility className="h-3.5 w-3.5 shrink-0 text-[var(--text-secondary)]" />
                      <div>
                        <span className="font-semibold text-[var(--text-primary)]">
                          Tiếp cận:
                        </span>{" "}
                        {room.accessibility}
                      </div>
                    </div>
                  )}
                  {room.equipment && (
                    <div className="flex items-center gap-1.5">
                      <Tv className="h-3.5 w-3.5 shrink-0 text-[var(--text-secondary)]" />
                      <div>
                        <span className="font-semibold text-[var(--text-primary)]">
                          Thiết bị:
                        </span>{" "}
                        {room.equipment}
                      </div>
                    </div>
                  )}
                </div>

                {!room.isAvailable && room.conflictReason && (
                  <div
                    role="alert"
                    className="rounded-xl border border-rose-200 bg-rose-50 p-2.5 text-xs leading-relaxed text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300"
                  >
                    Lý do: {room.conflictReason}
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => setSelectedRoom(room)}
                disabled={!room.isAvailable}
                aria-label={
                  room.isAvailable
                    ? `Đăng ký mượn ${shortName}`
                    : `Đã có lịch - ${shortName}`
                }
                className={`mt-5 min-h-[42px] w-full text-xs font-semibold shadow-xs transition ${
                  room.isAvailable
                    ? "fluent-btn-primary cursor-pointer"
                    : "bg-[var(--surface-subtle)] text-[var(--text-secondary)] cursor-not-allowed border border-[var(--border-color)] rounded-xl opacity-60"
                }`}
              >
                {room.isAvailable ? "Đăng ký mượn phòng" : "Không khả dụng"}
              </button>
            </article>
          );
        })}
      </div>
    </div>
  );
}
