"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { clearLegacyLocalToken, sessionLoginHref } from "../features/chat/local-session";
import { LearningSessionNotice, PreservedActivity, useLearningSession } from "../features/learning/learning-session";
import { ChatDraftActor, chatDraftActorScope } from "../features/chat/route-drafts";
import { useUnreadNotifications } from "../lib/use-unread-notifications";

import React, { type ReactNode, createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Bell,
  BookOpen,
  Building2,
  Bot,
  ClipboardList,
  FolderOpen,
  CalendarDays,
  ChevronRight,
  ExternalLink,
  FilePlus2,
  FileText,
  GraduationCap,
  HelpCircle,
  House,
  LayoutDashboard,
  Menu,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
} from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { LanguageToggle } from "./LanguageToggle";
import { useT, type MessageKey } from "../lib/i18n";
import { CERTIFICATE_DEMO } from "../lib/data/api/certificate-gateway";
import { SERVICE_DEMO } from "../lib/data/api/service-gateway";
import { AccessibleDialog } from "./shared/AccessibleDialog";
import { useOptionalUnifiedAssistant } from "../lib/unified-assistant-runtime";
import { PanelResizeHandle } from "./shared/PanelResizeHandle";

export type Role = "student" | "lecturer" | "staff" | "admin" | "guest" | "contributor";
const ChatMenuContext = createContext<{ target: HTMLElement | null; close: () => void }>({ target: null, close: () => {} });
export const useChatMenu = () => useContext(ChatMenuContext);

export interface AppShellProps {
  children?: ReactNode;
  activeNav?: string;
  userRole?: Role;
  publicKnowledge?: boolean;
  checkSessionOnResume?: boolean;
}

type NavigationItem = {
  key: string;
  label: MessageKey; // a message key, shown through t()
  href: string;
  icon: typeof House;
  roles: Role[];
  external?: boolean;
};

const navigation: NavigationItem[] = [
  { key: "learning", label: "nav.learning", href: "/learning", icon: BookOpen, roles: ["student", "lecturer", "admin"] },
  { key: "home", label: "nav.home", href: "/", icon: House, roles: ["student", "guest", "staff", "admin"] },
  { key: "chat", label: "nav.assistant", href: "/chat", icon: Bot, roles: ["student", "guest"] },
  { key: "services", label: "nav.services", href: "/services", icon: ClipboardList, roles: ["student"] },
  { key: "tickets", label: "nav.tickets", href: "/tickets", icon: FolderOpen, roles: ["student", "staff", "admin"] },
  { key: "schedule", label: "nav.schedule", href: "/schedule", icon: CalendarDays, roles: ["student"] },
  { key: "rooms", label: "nav.rooms", href: "/rooms", icon: Building2, roles: ["student", "staff", "admin"] },
  { key: "staff", label: "nav.staff", href: "/staff", icon: LayoutDashboard, roles: ["staff", "admin"] },
  { key: "knowledge", label: "nav.knowledge", href: "/knowledge", icon: BookOpen, roles: ["staff", "admin"] },
  { key: "admin", label: "nav.admin", href: "/admin", icon: Settings2, roles: ["admin"] },
];
const knowledgeNavigation: NavigationItem[] = [
  { key: "learning", label: "nav.learning", href: "/learning", icon: BookOpen, roles: ["student", "lecturer", "admin"] },
  { key: "chat", label: "nav.assistantSourced", href: "/chat", icon: Bot, roles: ["student", "guest", "staff", "admin", "contributor"] },
  { key: "documents", label: "nav.documents", href: "/knowledge/documents", icon: FilePlus2, roles: ["admin", "contributor"] },
  { key: "crawl", label: "nav.crawl", href: "/knowledge/crawl", icon: RefreshCw, roles: ["admin"] },
  { key: "services", label: "nav.servicesAcademic", href: "/services", icon: ClipboardList, roles: ["student", "guest", "admin"] },
  { key: "tickets", label: "nav.myTickets", href: "/tickets", icon: FolderOpen, roles: ["student"] },
  { key: "schedule", label: "nav.schedule", href: "/schedule", icon: CalendarDays, roles: ["student"] },
  { key: "rooms", label: "nav.rooms", href: "/rooms", icon: Building2, roles: ["student", "staff"] },
  { key: "staff", label: "nav.staffQueue", href: "/staff", icon: LayoutDashboard, roles: ["staff"] },
  { key: "notifications", label: "nav.notifications", href: "/notifications", icon: Bell, roles: ["student", "staff", "admin"] },
  { key: "admin", label: "nav.adminOverview", href: "/admin", icon: Settings2, roles: ["admin"] },
  { key: "knowledge", label: "nav.knowledgeSources", href: "/knowledge/sources", icon: BookOpen, roles: ["admin"] },
  { key: "privacy", label: "nav.privacy", href: "/privacy", icon: ShieldCheck, roles: ["student", "guest", "admin"] },
];

const publicNavigation: NavigationItem[] = [
  { key: "chat", label: "nav.askAi", href: "/chat", icon: Sparkles, roles: ["student", "guest", "staff", "admin"] },
  { key: "schedule", label: "nav.studentPortal", href: "https://sinhvien.huce.edu.vn", icon: CalendarDays, roles: ["student", "guest", "staff", "admin"], external: true },
  { key: "tickets", label: "nav.oneStop", href: "https://motcua.huce.edu.vn", icon: FileText, roles: ["student", "guest", "staff", "admin"], external: true },
  { key: "rooms", label: "nav.library", href: "https://thuvien.huce.edu.vn", icon: Building2, roles: ["student", "guest", "staff", "admin"], external: true },
];

const makeTitles = (t: (key: MessageKey) => string): Record<string, string> => ({
  learning: t("shellx.1"),
  home: "Tổng quan",
  chat: t("shellx.2"),
  services: t("shellx.3"),
  tickets: t("shellx.4"),
  schedule: t("shellx.5"),
  rooms: t("shellx.6"),
  staff: t("shellx.7"),
  knowledge: t("shellx.8"),
  documents: t("shellx.9"),
  crawl: "Nguồn tự động",
  admin: t("shellx.10"),
  privacy: t("shellx.44"),
  notifications: t("shellx.43"),
  memory: t("shellx.11"),
});

export function CampusBrand({ href = "/" }: { href?: string }) {
  const t = useT();
  return (
    <Link href={href} className="campus-brand" aria-label="Campus 24/7 — Trang chủ">
      <span className="campus-brand-mark">
        <GraduationCap size={24} strokeWidth={1.7} aria-hidden="true" />
      </span>
      <span className="campus-brand-text">
        <strong className="campus-brand-title">
          Campus<span className="campus-brand-number">24/7</span>
        </strong>
        <small className="campus-brand-sub">{t("shellx.12")}</small>
      </span>
    </Link>
  );
}

export function AppShell({
  children,
  activeNav = "home",
  userRole: suppliedRole,
  publicKnowledge = false,
  checkSessionOnResume = false,
}: AppShellProps) {
  const t = useT();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [navigationWidth, setNavigationWidth] = useState(224);
  const [navigationCollapsed, setNavigationCollapsed] = useState(activeNav === "chat" && process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM !== "true");
  const [desktopActions, setDesktopActions] = useState<HTMLDivElement | null>(null);
  const [mobileActions, setMobileActions] = useState<HTMLDivElement | null>(null);
  const runtime = useOptionalUnifiedAssistant();
  const [localActor, setLocalActor] = useState<{ user_id?: string; subject_id?: string; display_name?: string; student_code?: string; roles: string[] } | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const currentActor = localActor ?? runtime?.actor;
  const actorRoles = currentActor?.roles ?? [];
  const inferredRole: Role = actorRoles.some(role => ["KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"].includes(role))
    ? "admin" : actorRoles.includes("KNOWLEDGE_CONTRIBUTOR") ? "contributor"
    : actorRoles.includes("LECTURER") ? "lecturer" : actorRoles.includes("SUPPORT_OFFICER") ? "staff"
    : runtime?.capabilities?.audience === "staff" ? "staff" : "student";
  const userRole: Role = localActor ? inferredRole : suppliedRole ?? inferredRole;
  const shellRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);
  const chat = activeNav === "chat";
  const isPublic = publicKnowledge && !CERTIFICATE_DEMO;

  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport || !chat) return;
    const update = () => {
      shellRef.current?.style.setProperty("--campus-viewport-height", `${viewport.height}px`);
      shellRef.current?.setAttribute("data-keyboard-open", String(window.innerHeight - viewport.height > 150));
    };
    update(); viewport.addEventListener("resize", update);
    return () => viewport.removeEventListener("resize", update);
  }, [chat]);

  const operational = process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM === "true";
  const unreadCount = useUnreadNotifications(operational && !!localActor);
  const session = useLearningSession(operational && activeNav !== "learning" ? localActor?.user_id || localActor?.subject_id || "" : "", localActor?.roles, checkSessionOnResume);
  useEffect(() => {
    if (!operational) return;
    let active = true;
    void fetch(`${CAMPUS_API_BASE_URL}/v1/users/me`, { credentials: "include", cache: "no-store" })
      .then(response => {
        if (active) setSessionExpired(response.status === 401);
        return response.ok ? response.json() : null;
      })
      .then(actor => { if (active) setLocalActor(previous => checkSessionOnResume && previous ? previous : actor); })
      .catch(() => { if (active) setLocalActor(previous => checkSessionOnResume && previous ? previous : null); });
    return () => { active = false; };
  }, [operational, checkSessionOnResume]);
  const navItems = operational ? knowledgeNavigation.filter(item => item.roles.includes(userRole)) : isPublic
    ? publicNavigation
    : navigation
        .filter((item) => item.roles.includes(userRole))
        .map((item) =>
          SERVICE_DEMO && ["tickets", "staff"].includes(item.key)
            ? { ...item, href: "/services" }
            : SERVICE_DEMO && item.key === "knowledge"
            ? { ...item, href: "/knowledge/sources" }
            : item
        );

  useEffect(() => {
    setMobileOpen(false);
  }, [activeNav]);

  useEffect(() => {
    clearLegacyLocalToken();
  }, []);

  const closeMenu = useCallback(() => {
    setMobileOpen(false);
  }, []);

  const renderNavList = (isMobile = false) => (
    <>
      <div className="campus-sidebar-brand">
        <CampusBrand href={isPublic ? "/chat" : "/"} />
      </div>

      <div className="campus-workspace-label">
        <span className="campus-dot" aria-hidden="true" />
        <span>
          {isPublic
            ? t("shellx.13")
            : userRole === "staff"
            ? t("shellx.14")
            : userRole === "admin"
            ? t("shellx.15")
            : userRole === "lecturer"
            ? t("shellx.16")
            : t("shellx.17")}
        </span>
      </div>

      <nav
        role="navigation"
        aria-label={isMobile ? t("shellx.18") : t("shellx.19")}
        className="campus-navigation"
      >
        {navItems.filter(item => operational || isPublic || chat || item.key !== "rooms").map((item) => {
          const isActive = activeNav === item.key;
          if (item.external) {
            return (
              <a
                key={item.key}
                href={item.href}
                target="_blank"
                rel="noreferrer"
                aria-label={t(item.label)}
                onClick={closeMenu}
                className="campus-nav-item"
              >
                <item.icon size={19} strokeWidth={1.7} aria-hidden="true" />
                <span className="campus-nav-label">{t(item.label)}</span>
                <ExternalLink size={14} className="campus-external-icon" aria-hidden="true" />
              </a>
            );
          }
          return (
            <Link
              key={item.key}
              href={item.href}
              onClick={closeMenu}
              aria-label={t(item.label)}
              title={t(item.label)}
              aria-current={isActive ? "page" : undefined}
              className={"campus-nav-item" + (isActive ? " is-active" : "")}
            >
              <item.icon size={19} strokeWidth={1.7} aria-hidden="true" />
              <span className="campus-nav-label">{t(item.label)}</span>
              {item.key === "chat" && (
                <span className="campus-ai-label" aria-hidden="true">
                  AI
                </span>
              )}
              {item.key === "notifications" && unreadCount > 0 && (
                <span className="campus-ai-label" data-testid="notification-badge" aria-label={`${unreadCount} thông báo chưa đọc`}>
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </Link>
          );
        })}

        {chat && <div ref={isMobile ? setMobileActions : setDesktopActions} className="flex flex-col gap-1" aria-label={t("shellx.20")} />}
        {!operational && !isPublic && !chat && (
          <>
            <span className="campus-nav-divider" aria-hidden="true" />
            {navItems.filter(item => item.key === "rooms").map(item => <Link key={item.key} href={item.href} onClick={closeMenu} aria-current={activeNav === item.key ? "page" : undefined} className={"campus-nav-item" + (activeNav === item.key ? " is-active" : "")}><item.icon size={19} aria-hidden="true" /><span>{t(item.label)}</span></Link>)}
            <Link
              href="/notifications"
              onClick={closeMenu}
              aria-label={t("shellx.43")}
              aria-current={activeNav === "notifications" ? "page" : undefined}
              className={"campus-nav-item" + (activeNav === "notifications" ? " is-active" : "")}
            >
              <Bell size={19} strokeWidth={1.7} aria-hidden="true" />
              <span className="campus-nav-label">{t("shellx.43")}</span>
            </Link>
            <Link
              href="/privacy"
              onClick={closeMenu}
              aria-label={t("shellx.44")}
              aria-current={activeNav === "privacy" ? "page" : undefined}
              className={"campus-nav-item" + (activeNav === "privacy" ? " is-active" : "")}
            >
              <ShieldCheck size={19} strokeWidth={1.7} aria-hidden="true" />
              <span className="campus-nav-label">{t("shellx.44")}</span>
            </Link>
          </>
        )}
      </nav>

      <div className="campus-sidebar-bottom">
        <div className="campus-help-card">
          <span className="campus-help-icon">
            <HelpCircle size={21} aria-hidden="true" />
          </span>
          <strong>{t("shellx.21")}</strong>
          <p>{t("shellx.22")}</p>
          <Link href="/chat" onClick={closeMenu}>
            {t("shellx.23")} <ArrowRight size={15} aria-hidden="true" />
          </Link>
        </div>

        <Link href="/login" onClick={closeMenu} className="campus-account" aria-label={currentActor ? `Đổi tài khoản: ${currentActor.display_name || currentActor.student_code || t("shellx.45")}` : "Đăng nhập"} title={currentActor ? `${currentActor.display_name || t("shellx.45")}${currentActor.student_code ? ` · ${currentActor.student_code}` : ""} · Đổi tài khoản` : "Đăng nhập"}>
          <span className="campus-avatar">
            <GraduationCap size={19} aria-hidden="true" />
          </span>
          <span className="campus-account-info">
            <strong>
              {runtime?.actor ? runtime.actor.display_name || runtime.actor.student_code || t("shellx.45") : userRole === "guest"
                ? t("shellx.24")
                : userRole === "staff"
                ? t("shellx.25")
                : userRole === "admin"
                ? t("shellx.26")
                : t("shellx.27")}
            </strong>
            <small>
              {currentActor ? `${currentActor.student_code || t("shellx.45")} · Đổi tài khoản` : t("shellx.28")}
            </small>
          </span>
          <ChevronRight size={15} aria-hidden="true" />
        </Link>
      </div>
    </>
  );

  return (
    <><LearningSessionNotice state={session.state} onCheck={() => void session.check()}
      title={t("shellx.29")} destination={typeof window === "undefined" ? "/chat" : window.location.pathname + window.location.search}
      destinationLabel={t("shellx.30")} />
    <PreservedActivity mode={session.state === "ready" ? "visible" : "hidden"}>
    <ChatDraftActor value={chatDraftActorScope(localActor)}>
    <ChatMenuContext.Provider value={{ target: mobileOpen ? mobileActions : desktopActions, close: closeMenu }}>
    <div ref={shellRef} className={"campus-app" + (chat ? " campus-app-chat" : "")} data-campus-ui="v2">
      <a href="#main-content" className="skip-link">
        {t("shellx.31")}
      </a>

      <aside className="campus-sidebar" aria-label={t("shellx.32")} data-collapsed={navigationCollapsed} style={{ width: navigationCollapsed ? 64 : navigationWidth }}>
        <button type="button" className="campus-nav-collapse" aria-label={navigationCollapsed ? t("shellx.33") : t("shellx.34")} title={navigationCollapsed ? t("shellx.33") : t("shellx.34")} onClick={() => setNavigationCollapsed(value => !value)}>{navigationCollapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button>
        {renderNavList(false)}
        {!navigationCollapsed && <PanelResizeHandle label={t("shellx.35")} width={navigationWidth} onChange={setNavigationWidth} min={180} max={360} defaultWidth={224} />}
      </aside>

      <div className="campus-workspace">
        {chat && <button ref={menuRef} type="button" className="campus-menu-trigger campus-icon-button m-2 shrink-0 self-start" aria-label={t("shellx.36")} aria-expanded={mobileOpen} aria-controls="campus-mobile-navigation" onClick={() => setMobileOpen(true)}><Menu size={20} aria-hidden="true" /></button>}
        {!chat && <header className="campus-toolbar" role="banner">
          <div className="campus-toolbar-heading">
            <button
              ref={menuRef}
              type="button"
              className="campus-icon-button campus-menu-trigger"
              aria-label={t("shellx.36")}
              aria-expanded={mobileOpen}
              aria-controls="campus-mobile-navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={21} aria-hidden="true" />
            </button>
            <span className="campus-breadcrumb-brand">Campus 24/7</span>
            <ChevronRight size={14} className="campus-breadcrumb-chevron" aria-hidden="true" />
            <span className="campus-breadcrumb-title">{makeTitles(t)[activeNav] || t("shellx.37")}</span>
          </div>

          <div className="campus-toolbar-actions">
            <form
              action="/chat"
              method="GET"
              role="search"
              aria-label={t("shell.searchForm")}
              className="campus-toolbar-search"
            >
              <Search size={16} aria-hidden="true" />
              <input aria-label={t("shell.searchLabel")} name="q" placeholder={t("shell.searchPlaceholder")} />
              <kbd aria-hidden="true">↵</kbd>
            </form>

            <LanguageToggle className="campus-theme-toggle" />
            <ThemeToggle className="campus-theme-toggle" />

            <Link href="/notifications" className="campus-icon-button relative" aria-label={unreadCount > 0 ? `Mở thông báo, ${unreadCount} chưa đọc` : t("shellx.38")}>
              <Bell size={19} aria-hidden="true" />
              {unreadCount > 0 && <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-[var(--color-primary)] px-1 text-center text-[10px] font-bold leading-4 text-[var(--color-on-primary)]" aria-hidden="true">{unreadCount > 99 ? "99+" : unreadCount}</span>}
            </Link>

            <span className="campus-toolbar-divider" aria-hidden="true" />
            <span className="campus-institution">
              <strong>HUCE</strong>
              <small>{t("shellx.39")}</small>
            </span>
          </div>
        </header>}

        {sessionExpired && <p role="alert" className="shrink-0 border-b p-3 text-sm">
          Phiên đăng nhập đã hết hạn. <a className="underline" href={sessionLoginHref()}>Đăng nhập lại</a>.
        </p>}
        <main id="main-content" role="main" className={chat ? "campus-chat-content" : "campus-content"}>
          {children}
        </main>

        {!chat && (
          <footer className="campus-footer" role="contentinfo">
            <span>
              © 2026 Campus 24/7 <span aria-hidden="true">·</span> {t("shellx.39")}
            </span>
            {!operational && <Link href="/privacy">
              Thông tin & quyền riêng tư <ArrowRight size={13} aria-hidden="true" />
            </Link>}
          </footer>
        )}
      </div>

      {!operational && !isPublic && <nav className="campus-bottom-navigation" aria-label={t("shellx.40")}>
        {navItems.filter(item => userRole === "student" ? ["home", "chat", "services", "tickets", "schedule"].includes(item.key) : ["home", "staff", "tickets", "knowledge", "documents", "crawl", "admin"].includes(item.key)).map(item => <Link key={item.key} href={item.href} aria-current={activeNav === item.key ? "page" : undefined}><item.icon size={20} aria-hidden="true" /><span>{t(item.label)}</span></Link>)}
      </nav>}

      <AccessibleDialog
        open={mobileOpen}
        onClose={closeMenu}
        labelledBy="campus-mobile-title"
        className="campus-mobile-dialog"
      >
        <div className="campus-mobile-header">
          <h2 id="campus-mobile-title" className="sr-only">
            {t("shellx.41")}
          </h2>
          <button
            type="button"
            className="campus-mobile-close campus-icon-button"
            onClick={closeMenu}
            aria-label={t("shellx.42")}
          >
            <X size={21} aria-hidden="true" />
          </button>
        </div>
        <div id="campus-mobile-navigation" className="campus-mobile-nav-inner">
          {mobileOpen && renderNavList(true)}
        </div>
      </AccessibleDialog>
    </div>
    </ChatMenuContext.Provider>
    </ChatDraftActor>
    </PreservedActivity></>
  );
}
