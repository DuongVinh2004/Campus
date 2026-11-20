"use client";
import React from "react";
import Link from "next/link";
import { useT } from "../../lib/i18n";
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
  const t = useT();
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
          <AsyncState status="loading" loadingMessage={t("homex.1")} />
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
            errorMessage={props.errorMessage || t("homex.2")}
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
          message: t("homex.3"),
          affectedServices: [t("homex.4"), t("homex.5")],
          impact: t("homex.6"),
          safeNextAction: t("homex.7"),
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
    { title: t("homex.8"), description: t("homex.9"), action: t("homex.10"), href: isAuthenticated ? "/tickets" : "/login?redirect=/tickets", icon: ClipboardListIcon, disabled: isTicketsUnavailable },
    { title: t("homex.11"), description: t("homex.12"), action: t("homex.13"), href: isAuthenticated ? "/tickets" : "/login?redirect=/tickets", icon: SearchIcon, disabled: isTicketsUnavailable },
    { title: t("homex.14"), description: t("homex.15"), action: t("homex.16"), href: isAuthenticated ? "/schedule" : "/login?redirect=/schedule", icon: CalendarIcon, disabled: isScheduleUnavailable },
    { title: t("homex.17"), description: t("homex.18"), action: t("homex.19"), href: "/rooms", icon: BuildingIcon, disabled: isRoomsUnavailable },
  ];
  return <AppShell activeNav="home" userRole={isAuthenticated ? "student" : "guest"}>
    <div className="campus-home">
      {systemStatus && <CapabilityBanner status={systemStatus} />}
      <header className="campus-home-intro"><h1>{t("homex.20")}</h1><p>{t("homex.21")}</p></header>
      <section className="campus-home-assistant" aria-labelledby="home-assistant-title">
        <h2 id="home-assistant-title"><SparklesIcon size={20} />{t("homex.22")}</h2>
        <form action="/chat" method="GET" role="search" aria-label={t("homex.23")}>
          <label htmlFor="home-question">{t("homex.46")}</label>
          <div className="campus-home-search"><SearchIcon size={20} /><input id="home-question" name="q" disabled={isChatUnavailable} aria-label={t("homex.24")} placeholder={isChatUnavailable ? t("homex.25") : t("homex.26")} /><button type="submit" className="fluent-btn-primary" disabled={isChatUnavailable}>{isChatUnavailable ? t("homex.27") : t("homex.28")}<ArrowRightIcon size={17} /></button></div>
        </form>
        <div className="campus-home-suggestions"><span>{t("homex.29")}</span>{["Điều kiện xét học bổng khuyến khích học tập?", "Quy chế đăng ký học phần bổ sung?"].map(question => isChatUnavailable ? <span key={question}>{question}</span> : <Link key={question} href={`/chat?q=${encodeURIComponent(question)}`}>{question}</Link>)}</div>
      </section>
      <section className="campus-home-services" aria-labelledby="essential-services-title"><h2 id="essential-services-title">{t("homex.30")}</h2><div className="campus-service-cards">{services.map(service => {
        const content = <><div><service.icon size={20} /><ArrowRightIcon size={18} /></div><h3>{service.title}</h3><p>{service.description}</p><span>{service.disabled ? t("homex.27") : service.action}</span></>;
        return service.disabled ? <button type="button" disabled key={service.title} className="campus-service-card text-left" aria-label={service.title} aria-disabled="true">{content}</button> : <Link key={service.title} href={service.href} className="campus-service-card">{content}</Link>;
      })}</div></section>
      <div className="campus-overview-grid">
        <section aria-labelledby="heading-next-schedule"><h2 id="heading-next-schedule"><CalendarIcon size={19} />{t("homex.31")}</h2><div className="campus-overview-body">
          {!isAuthenticated ? <p>{t("homex.32")}</p> : schedule ? <div><strong>{schedule.courseName} ({schedule.courseCode})</strong><p>{schedule.room} · {schedule.timeSlot}</p><p>{schedule.lecturer} · {schedule.syncTime}</p></div> : <><strong>{isScheduleEmpty ? t("homex.33") : t("homex.34")}</strong><p>{t("homex.35")}</p></>}
          <Link href={isAuthenticated ? "/schedule" : "/login?redirect=/schedule"}>{isAuthenticated ? t("homex.36") : t("homex.37")}</Link>
        </div></section>
        <section aria-labelledby="heading-open-tickets"><h2 id="heading-open-tickets"><ClipboardListIcon size={19} />{t("homex.38")}</h2><div className="campus-overview-body">
          {!isAuthenticated ? <p>{t("homex.39")}</p> : tickets.length ? tickets.map(ticket => <div key={ticket.id} className="campus-overview-ticket"><div><strong>{ticket.title}</strong><small>{ticket.code} · {ticket.updatedAt}</small></div><span>{ticket.statusText}</span></div>) : <><strong>{t("homex.40")}</strong><p>{t("homex.41")}</p></>}
          <Link href={isAuthenticated ? "/tickets" : "/login?redirect=/tickets"}>{isAuthenticated ? t("homex.42") : t("homex.43")}</Link>
        </div></section>
      </div>
      <div className="campus-home-privacy"><ShieldCheckIcon size={18} /><p>{t("homex.44")} <Link href="/privacy">{t("homex.45")}</Link></p></div>
    </div>
  </AppShell>;
}
