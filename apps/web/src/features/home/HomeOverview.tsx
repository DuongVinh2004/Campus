import React from "react";
import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import {
  SparklesIcon,
  CalendarIcon,
  ClipboardListIcon,
  BuildingIcon,
  ClockIcon,
  SearchIcon,
  ArrowRightIcon,
  ShieldCheckIcon,
} from "../../components/Icons";
import { CapabilityBanner, type SystemOperationalStatus } from "../operations/CapabilityBanner";
import { AsyncState, type AsyncStatus } from "../../components/AsyncState";

export interface UserSession {
  isAuthenticated: boolean;
  userId?: string;
  name?: string;
  role?: string;
}

export interface DashboardScheduleItem {
  id: string;
  courseName: string;
  courseCode: string;
  room: string;
  timeSlot: string;
  lecturer: string;
  syncTime: string;
  source?: string;
}

export interface DashboardTicketSummary {
  id: string;
  code: string;
  title: string;
  statusText: string;
  updatedAt: string;
  source?: string;
}

export interface HomePageProps {
  params?: Record<string, string | string[]>;
  searchParams?: Record<string, string | string[] | undefined> | Promise<Record<string, string | string[] | undefined>>;
  user?: UserSession | null;
  systemStatus?: SystemOperationalStatus | null;
  schedule?: DashboardScheduleItem | null;
  tickets?: DashboardTicketSummary[];
  status?: AsyncStatus;
  errorMessage?: string;
  onRetry?: () => void;
  unavailableCapabilities?: string[];
}

export default function HomeOverview(props: HomePageProps) {
  const searchParams =
    props?.searchParams && typeof props.searchParams.then === "function"
      ? (React as any).use(props.searchParams)
      : props?.searchParams || {};

  const currentStatus = props?.status || (searchParams?.status as AsyncStatus) || "success";

  // Authoritative identity resolution
  const isAnonymous = props.user
    ? !props.user.isAuthenticated
    : searchParams?.auth === "anonymous";
  const isAuthenticated = !isAnonymous;

  // Async state handling (Loading, Error, Outage)
  if (currentStatus === "loading") {
    return (
      <AppShell activeNav="home" userRole={isAuthenticated ? "student" : "guest"}>
        <div className="py-10">
          <AsyncState status="loading" loadingMessage="Đang đồng bộ trạng thái học vụ..." />
        </div>
      </AppShell>
    );
  }

  if (currentStatus === "error") {
    return (
      <AppShell activeNav="home" userRole={isAuthenticated ? "student" : "guest"}>
        <div className="py-10">
          <AsyncState
            status="error"
            errorMessage={props.errorMessage || "Không thể kết nối máy chủ dữ liệu học vụ"}
            onRetry={props.onRetry}
          />
        </div>
      </AppShell>
    );
  }

  // Authoritative operational status resolution
  const systemStatus: SystemOperationalStatus | null = props.systemStatus || (
    searchParams?.status === "degraded"
      ? {
          mode: "degraded",
          message: "Hệ thống đang hoạt động ở chế độ suy giảm một phần tính năng.",
          affectedServices: ["Thời khóa biểu", "Tra cứu phòng"],
          impact: "Dữ liệu lịch học có thể bị trễ và không phản ánh thay đổi tức thời.",
          safeNextAction: "Vui lòng đối chiếu với thông báo trực tiếp từ Khoa.",
        }
      : null
  );

  // Capability availability checks
  const unavailableCaps = [
    ...(props.unavailableCapabilities || []),
    ...(searchParams?.unavailable_capability ? String(searchParams.unavailable_capability).split(",") : []),
  ];
  const isChatUnavailable = unavailableCaps.includes("chat");
  const isRoomsUnavailable = unavailableCaps.includes("rooms");
  const isScheduleUnavailable = unavailableCaps.includes("schedule");
  const isTicketsUnavailable = unavailableCaps.includes("tickets");

  const isScheduleEmpty = searchParams?.empty_schedule === "true";
  const isTicketsEmpty = searchParams?.empty_tickets === "true";

  // Authoritative schedule item: never fabricate private data when unauthenticated
  const schedule: DashboardScheduleItem | null = !isAuthenticated
    ? null
    : props.schedule !== undefined
    ? props.schedule
    : isScheduleEmpty
    ? null
    : null;

  // Authoritative ticket summaries: never fabricate private data when unauthenticated
  const tickets: DashboardTicketSummary[] = !isAuthenticated
    ? []
    : props.tickets !== undefined
    ? props.tickets
    : isTicketsEmpty
    ? []
    : [];

  const services = [
    { title: "Xin giấy xác nhận", description: "Đăng ký cấp giấy xác nhận sinh viên và các giấy tờ học vụ.", action: "Gửi yêu cầu", href: isAuthenticated ? "/tickets" : "/login?redirect=/tickets", icon: ClipboardListIcon, disabled: isTicketsUnavailable },
    { title: "Theo dõi hồ sơ", description: "Tra cứu tiến độ giải quyết các yêu cầu một cửa đã gửi.", action: "Tra cứu hồ sơ", href: isAuthenticated ? "/tickets" : "/login?redirect=/tickets", icon: SearchIcon, disabled: isTicketsUnavailable },
    { title: "Xem lịch học", description: "Tra cứu thời khóa biểu giảng đường và lịch thi.", action: "Xem thời khóa biểu", href: isAuthenticated ? "/schedule" : "/login?redirect=/schedule", icon: CalendarIcon, disabled: isScheduleUnavailable },
    { title: "Tìm phòng học", description: "Tra cứu vị trí phòng học và khu giảng đường trong khuôn viên.", action: "Tra cứu vị trí", href: "/rooms", icon: BuildingIcon, disabled: isRoomsUnavailable },
  ];
  return <AppShell activeNav="home" userRole={isAuthenticated ? "student" : "guest"}>
    <div className="campus-home">
      {systemStatus && <CapabilityBanner status={systemStatus} />}
      <header className="campus-home-intro"><h1>Chào bạn, hôm nay cần hỗ trợ gì?</h1><p>Thông tin học vụ và dịch vụ sinh viên trong cùng một không gian.</p></header>
      <section className="campus-home-assistant" aria-labelledby="home-assistant-title">
        <h2 id="home-assistant-title"><SparklesIcon size={20} />Trợ lý học vụ</h2>
        <form action="/chat" method="GET" role="search" aria-label="Tìm kiếm quy chế và thủ tục học vụ">
          <label htmlFor="home-question">Đặt câu hỏi cho Trợ lý học vụ</label>
          <div className="campus-home-search"><SearchIcon size={20} /><input id="home-question" name="q" disabled={isChatUnavailable} aria-label="Hỏi Trợ lý AI về quy chế, tín chỉ, lịch thi" placeholder={isChatUnavailable ? "Tạm ngừng phục vụ: Trợ lý đang bảo trì…" : "Nhập câu hỏi về quy chế, học bổng hoặc thủ tục…"} /><button type="submit" className="fluent-btn-primary" disabled={isChatUnavailable}>{isChatUnavailable ? "Tạm ngừng phục vụ" : "Hỏi trợ lý"}<ArrowRightIcon size={17} /></button></div>
        </form>
        <div className="campus-home-suggestions"><span>Gợi ý câu hỏi:</span>{["Điều kiện xét học bổng khuyến khích học tập?", "Quy chế đăng ký học phần bổ sung?"].map(question => isChatUnavailable ? <span key={question}>{question}</span> : <Link key={question} href={`/chat?q=${encodeURIComponent(question)}`}>{question}</Link>)}</div>
      </section>
      <section className="campus-home-services" aria-labelledby="essential-services-title"><h2 id="essential-services-title">Dịch vụ thiết yếu</h2><div className="campus-service-cards">{services.map(service => {
        const content = <><div><service.icon size={20} /><ArrowRightIcon size={18} /></div><h3>{service.title}</h3><p>{service.description}</p><span>{service.disabled ? "Tạm ngừng phục vụ" : service.action}</span></>;
        return service.disabled ? <button type="button" disabled key={service.title} className="campus-service-card text-left" aria-label={service.title} aria-disabled="true">{content}</button> : <Link key={service.title} href={service.href} className="campus-service-card">{content}</Link>;
      })}</div></section>
      <div className="campus-overview-grid">
        <section aria-labelledby="heading-next-schedule"><h2 id="heading-next-schedule"><CalendarIcon size={19} />Lịch học kế tiếp</h2><div className="campus-overview-body">
          {!isAuthenticated ? <p>Vui lòng đăng nhập để xem lịch học cá nhân.</p> : schedule ? <div><strong>{schedule.courseName} ({schedule.courseCode})</strong><p>{schedule.room} · {schedule.timeSlot}</p><p>{schedule.lecturer} · {schedule.syncTime}</p></div> : <><strong>{isScheduleEmpty ? "Chưa có lịch học mới trong ca tiếp theo." : "Lịch học chưa được tích hợp"}</strong><p>Đối chiếu lịch học và thay đổi mới nhất trên cổng sinh viên của trường.</p></>}
          <Link href={isAuthenticated ? "/schedule" : "/login?redirect=/schedule"}>{isAuthenticated ? "Xem toàn bộ lịch" : "Đăng nhập để xem lịch"}</Link>
        </div></section>
        <section aria-labelledby="heading-open-tickets"><h2 id="heading-open-tickets"><ClipboardListIcon size={19} />Hồ sơ của tôi</h2><div className="campus-overview-body">
          {!isAuthenticated ? <p>Vui lòng đăng nhập để theo dõi hồ sơ một cửa.</p> : tickets.length ? tickets.map(ticket => <div key={ticket.id} className="campus-overview-ticket"><div><strong>{ticket.title}</strong><small>{ticket.code} · {ticket.updatedAt}</small></div><span>{ticket.statusText}</span></div>) : <><strong>Bạn chưa có hồ sơ nào.</strong><p>Yêu cầu đã gửi và tiến độ xử lý sẽ xuất hiện tại đây khi có dữ liệu hồ sơ.</p></>}
          <Link href={isAuthenticated ? "/tickets" : "/login?redirect=/tickets"}>{isAuthenticated ? "Xem tất cả yêu cầu" : "Đăng nhập để xem hồ sơ"}</Link>
        </div></section>
      </div>
      <div className="campus-home-privacy"><ShieldCheckIcon size={18} /><p>Mọi yêu cầu cấp giấy tờ đều có bản xem trước để bạn kiểm tra trước khi xác nhận. <Link href="/privacy">Chính sách quyền riêng tư</Link></p></div>
    </div>
  </AppShell>;
}
