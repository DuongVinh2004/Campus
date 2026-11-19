// Typed client for the durable campus operations API (rooms, timetable, notifications, tickets, staff, admin).
// All calls use the same-origin entry point and the session cookie; state-changing calls that must not be
// repeated carry an Idempotency-Key.
import { CAMPUS_API_BASE_URL } from "./api/base-url";
import { ApiClient, ApiClientError } from "./api/client";

export { ApiClientError };

const client = () => new ApiClient({ baseUrl: CAMPUS_API_BASE_URL });
const newKey = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `k-${Date.now()}-${Math.random().toString(16).slice(2)}`);

export function problemMessage(error: unknown, fallback = "Không thực hiện được. Vui lòng thử lại."): string {
  if (error instanceof ApiClientError) return error.problem.detail || error.message || fallback;
  return fallback;
}

// ---------------------------------------------------------------- rooms
export type RoomKind = "lecture" | "lab" | "meeting" | "study" | "hall";
export interface Room {
  id: string; room_code: string; display_name: string; building: string; floor: number; capacity: number;
  kind: RoomKind; features: string[]; status: "ACTIVE" | "MAINTENANCE"; source: string;
}
export interface BookingLimits { open: string; close: string; min_minutes: number; max_minutes: number; step_minutes: number; horizon_days: number; max_active_bookings: number }
export interface RoomList { items: Room[]; buildings: string[]; source: string; limits: BookingLimits }
export interface BusyInterval { starts_at: string; ends_at: string; type: "BOOKING" | "CLASS" | "EXAM"; label: string }
export interface Availability { room: Room; date: string; open: string; close: string; busy: BusyInterval[]; limits: BookingLimits }
export interface BookingPreviewRequest { room_id: string; date: string; start: string; end: string; purpose: string; attendees: number }
export interface BookingPreview {
  preview_id: string; can_confirm: boolean; problems: string[]; conflicts: BusyInterval[]; expires_at: string; notice: string;
  summary: { room_id: string; room_code: string; room_name: string; starts_at: string; ends_at: string; purpose: string; attendees: number };
}
export interface Booking {
  id: string; booking_id: string; code: string; room_id: string; room_code: string; room_name: string; building: string;
  starts_at: string; ends_at: string; purpose: string; attendees: number; status: "CONFIRMED" | "CANCELLED";
  created_at: string; cancelled_at: string | null; can_cancel: boolean; replayed?: boolean;
}

export const roomsApi = {
  list: (params: { building?: string; kind?: string; min_capacity?: number; q?: string } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== 0) qs.set(k, String(v)); });
    return client().get<RoomList>(`/v1/rooms${qs.size ? `?${qs}` : ""}`);
  },
  availability: (roomId: string, date: string) => client().get<Availability>(`/v1/rooms/${encodeURIComponent(roomId)}/availability?date=${encodeURIComponent(date)}`),
  preview: (body: BookingPreviewRequest) => client().post<BookingPreview>("/v1/rooms/book/preview", body),
  // The key is per confirmation attempt; reuse the same key when retrying after a network failure.
  confirm: (previewId: string, idempotencyKey: string = newKey()) =>
    client().post<Booking>("/v1/rooms/book", { preview_id: previewId }, { "Idempotency-Key": idempotencyKey }),
  mine: () => client().get<{ items: Booking[] }>("/v1/rooms/bookings/mine"),
  cancel: (bookingId: string, reason = "") => client().post<Booking>(`/v1/rooms/bookings/${encodeURIComponent(bookingId)}/cancel`, { reason }),
  newKey,
};

// ------------------------------------------------------------- schedule
export type ScheduleKind = "CLASS" | "EXAM" | "PERSONAL";
export interface ScheduleItem {
  id: string; kind: ScheduleKind; course_code: string; course_name: string; starts_at: string; ends_at: string;
  location_label: string; instructor_display_name: string; note: string; source_system: string; editable: boolean;
}
export interface ScheduleResponse { items: ScheduleItem[]; page: { next_cursor: string | null; has_more: boolean; limit: number }; sources: string[] }
export interface PersonalEventInput { title: string; starts_at: string; ends_at: string; location?: string; note?: string }

export const scheduleApi = {
  list: (fromIso: string, toIso: string) =>
    client().get<ScheduleResponse>(`/v1/students/me/schedule?from=${encodeURIComponent(fromIso)}&to=${encodeURIComponent(toIso)}`),
  create: (body: PersonalEventInput) => client().post<ScheduleItem>("/v1/students/me/schedule/events", body),
  update: (id: string, body: PersonalEventInput) => client().put<ScheduleItem>(`/v1/students/me/schedule/events/${encodeURIComponent(id)}`, body),
  remove: (id: string) => client().delete<{ id: string; deleted: boolean }>(`/v1/students/me/schedule/events/${encodeURIComponent(id)}`),
};

// -------------------------------------------------------- notifications
export interface AppNotification { id: string; kind: string; title: string; body: string; link: string; created_at: string; read: boolean }
export interface NotificationList { items: AppNotification[]; unread_count: number }

export const notificationsApi = {
  list: (opts: { unreadOnly?: boolean; limit?: number } = {}) =>
    client().get<NotificationList>(`/v1/notifications?unread_only=${opts.unreadOnly ? "true" : "false"}&limit=${opts.limit ?? 50}`),
  markRead: (id: string) => client().post<{ updated: number }>(`/v1/notifications/${encodeURIComponent(id)}/read`, {}),
  markAllRead: () => client().post<{ updated: number }>("/v1/notifications/read-all", {}),
};

// -------------------------------------------------------------- tickets
export type TicketStatus = "SUBMITTED" | "IN_REVIEW" | "NEED_INFO" | "RESOLVED" | "REJECTED" | "CANCELLED";
export type ServiceKind = "STUDENT_CERTIFICATE" | "GRADE_APPEAL" | "GENERAL_SUPPORT";
export const TICKET_STATUS_LABEL: Record<TicketStatus, string> = {
  SUBMITTED: "Đã gửi, chờ tiếp nhận", IN_REVIEW: "Đang xử lý", NEED_INFO: "Cần bổ sung thông tin",
  RESOLVED: "Đã giải quyết", REJECTED: "Từ chối", CANCELLED: "Đã hủy",
};
export const SERVICE_KIND_LABEL: Record<ServiceKind, string> = {
  STUDENT_CERTIFICATE: "Giấy xác nhận sinh viên đang học", GRADE_APPEAL: "Phúc khảo kết quả học tập", GENERAL_SUPPORT: "Hỗ trợ thủ tục học vụ",
};
export interface Ticket {
  id: string; code: string; service_kind: ServiceKind; service_label: string; title: string; summary: string;
  fields: Record<string, string>; status: TicketStatus; priority: string; owner_display: string; owner_code: string;
  assignee_display: string | null; created_at: string; updated_at: string; due_at: string | null; overdue: boolean; replayed?: boolean;
}
export interface TicketEvent { id: string; kind: "CREATED" | "CLAIMED" | "STAFF_REPLY" | "STUDENT_REPLY" | "STATUS_CHANGE" | "NOTE"; actor_role: string; actor_role_label?: string; actor_kind?: "student" | "staff" | "system"; is_mine?: boolean; actor_display: string; body: string; visibility: "PUBLIC" | "INTERNAL"; created_at: string }
export interface TicketDetail extends Ticket { events: TicketEvent[]; allowed_actions: Array<"claim" | "reply" | "status" | "note" | "cancel"> }
export interface SubmitTicketInput { service_kind: ServiceKind; title?: string; summary: string; fields?: Record<string, string> }
export interface StaffQueue { items: Ticket[]; counts: Record<TicketStatus, number>; overdue: number }

export const ticketsApi = {
  mine: () => client().get<{ items: Ticket[] }>("/v1/tickets"),
  detail: (id: string) => client().get<TicketDetail>(`/v1/tickets/${encodeURIComponent(id)}`),
  submit: (body: SubmitTicketInput, idempotencyKey: string = newKey()) => client().post<Ticket>("/v1/tickets", body, { "Idempotency-Key": idempotencyKey }),
  reply: (id: string, text: string) => client().post<TicketDetail>(`/v1/tickets/${encodeURIComponent(id)}/reply`, { body: text }),
  cancel: (id: string, reason = "") => client().post<TicketDetail>(`/v1/tickets/${encodeURIComponent(id)}/cancel`, { reason }),
  newKey,
};

export const staffApi = {
  queue: (opts: { status?: string; mine?: boolean; q?: string } = {}) => {
    const qs = new URLSearchParams();
    if (opts.status) qs.set("status", opts.status);
    if (opts.mine) qs.set("mine", "true");
    if (opts.q) qs.set("q", opts.q);
    return client().get<StaffQueue>(`/v1/staff/tickets${qs.size ? `?${qs}` : ""}`);
  },
  detail: (id: string) => client().get<TicketDetail>(`/v1/staff/tickets/${encodeURIComponent(id)}`),
  claim: (id: string) => client().post<TicketDetail>(`/v1/staff/tickets/${encodeURIComponent(id)}/claim`, {}),
  reply: (id: string, text: string, setStatus?: "IN_REVIEW" | "NEED_INFO" | "RESOLVED" | "REJECTED") =>
    client().post<TicketDetail>(`/v1/staff/tickets/${encodeURIComponent(id)}/reply`, { body: text, ...(setStatus ? { set_status: setStatus } : {}) }),
  setStatus: (id: string, status: "IN_REVIEW" | "NEED_INFO" | "RESOLVED" | "REJECTED", reason: string) =>
    client().post<TicketDetail>(`/v1/staff/tickets/${encodeURIComponent(id)}/status`, { status, reason }),
  note: (id: string, text: string) => client().post<TicketDetail>(`/v1/staff/tickets/${encodeURIComponent(id)}/note`, { body: text }),
};

// ---------------------------------------------------------------- admin
export interface AdminOverview {
  tickets: { by_status: Partial<Record<TicketStatus, number>>; overdue: number; total: number };
  bookings: { by_status: Record<string, number>; upcoming: number };
  rooms: { by_status: Record<string, number>; total: number };
  schedule_entries: number;
  recent_audit: Array<{ at: string; actor: string; action: string; resource: string }>;
  data_sources: { rooms: string; timetable: string; note: string };
}
export const adminApi = { overview: () => client().get<AdminOverview>("/v1/admin/overview") };

export const OPS_ENABLED = process.env.NEXT_PUBLIC_CAMPUS_OPERATIONS === "true";
