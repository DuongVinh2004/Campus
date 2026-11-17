"use client";
import { CAMPUS_API_BASE_URL } from "@/lib/api/base-url";
import { clearLegacyLocalToken, sessionLoginHref } from "../features/chat/local-session";

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
} from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { CERTIFICATE_DEMO } from "../lib/data/api/certificate-gateway";
import { SERVICE_DEMO } from "../lib/data/api/service-gateway";
import { AccessibleDialog } from "./shared/AccessibleDialog";
import { useOptionalUnifiedAssistant } from "../lib/unified-assistant-runtime";
import { PanelResizeHandle } from "./shared/PanelResizeHandle";

export type Role = "student" | "staff" | "admin" | "guest";
const ChatMenuContext = createContext<{ target: HTMLElement | null; close: () => void }>({ target: null, close: () => {} });
export const useChatMenu = () => useContext(ChatMenuContext);

export interface AppShellProps {
  children?: ReactNode;
  activeNav?: string;
  userRole?: Role;
  publicKnowledge?: boolean;
}

type NavigationItem = {
  key: string;
  label: string;
  href: string;
  icon: typeof House;
  roles: Role[];
  external?: boolean;
};

const navigation: NavigationItem[] = [
  { key: "home", label: "Tổng quan", href: "/", icon: House, roles: ["student", "guest", "staff", "admin"] },
  { key: "chat", label: "Trợ lý", href: "/chat", icon: Bot, roles: ["student", "guest"] },
  { key: "services", label: "Dịch vụ", href: "/services", icon: ClipboardList, roles: ["student"] },
  { key: "tickets", label: "Hồ sơ", href: "/tickets", icon: FolderOpen, roles: ["student", "staff", "admin"] },
  { key: "schedule", label: "Lịch học", href: "/schedule", icon: CalendarDays, roles: ["student"] },
  { key: "rooms", label: "Phòng học", href: "/rooms", icon: Building2, roles: ["student", "staff", "admin"] },
  { key: "staff", label: "Cán bộ", href: "/staff", icon: LayoutDashboard, roles: ["staff", "admin"] },
  { key: "knowledge", label: "Tri thức", href: "/knowledge", icon: BookOpen, roles: ["staff", "admin"] },
  { key: "admin", label: "Quản trị", href: "/admin", icon: Settings2, roles: ["admin"] },
];
const knowledgeNavigation: NavigationItem[] = [
  { key: "chat", label: "Hỏi đáp có nguồn", href: "/chat", icon: Bot, roles: ["student", "guest", "staff", "admin"] },
  { key: "services", label: "Dịch vụ học vụ", href: "/services", icon: ClipboardList, roles: ["student", "guest", "admin"] },
  { key: "tickets", label: "Hồ sơ của tôi", href: "/tickets", icon: FolderOpen, roles: ["student"] },
  { key: "schedule", label: "Lịch học", href: "/schedule", icon: CalendarDays, roles: ["student"] },
  { key: "rooms", label: "Phòng học", href: "/rooms", icon: Building2, roles: ["student"] },
  { key: "knowledge", label: "Quản trị nguồn", href: "/knowledge/sources", icon: BookOpen, roles: ["admin"] },
  { key: "privacy", label: "Quyền riêng tư", href: "/privacy", icon: ShieldCheck, roles: ["student", "guest", "admin"] },
];

const publicNavigation: NavigationItem[] = [
  { key: "chat", label: "Hỏi đáp AI", href: "/chat", icon: Sparkles, roles: ["student", "guest", "staff", "admin"] },
  { key: "schedule", label: "Cổng sinh viên", href: "https://sinhvien.huce.edu.vn", icon: CalendarDays, roles: ["student", "guest", "staff", "admin"], external: true },
  { key: "tickets", label: "Một cửa HUCE", href: "https://motcua.huce.edu.vn", icon: FileText, roles: ["student", "guest", "staff", "admin"], external: true },
  { key: "rooms", label: "Thư viện HUCE", href: "https://thuvien.huce.edu.vn", icon: Building2, roles: ["student", "guest", "staff", "admin"], external: true },
];

const titles: Record<string, string> = {
  home: "Tổng quan",
  chat: "Trợ lý học vụ",
  services: "Dịch vụ sinh viên",
  tickets: "Thủ tục & yêu cầu",
  schedule: "Lịch học & lịch thi",
  rooms: "Không gian học tập",
  staff: "Bàn làm việc cán bộ",
  knowledge: "Quản lý tri thức",
  admin: "Quản trị hệ thống",
  privacy: "Quyền riêng tư",
  notifications: "Thông báo",
  memory: "Ghi nhớ cá nhân",
};

export function CampusBrand({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="campus-brand" aria-label="Campus 24/7 — Trang chủ">
      <span className="campus-brand-mark">
        <GraduationCap size={24} strokeWidth={1.7} aria-hidden="true" />
      </span>
      <span className="campus-brand-text">
        <strong className="campus-brand-title">
          Campus<span className="campus-brand-number">24/7</span>
        </strong>
        <small className="campus-brand-sub">ĐH Xây dựng Hà Nội</small>
      </span>
    </Link>
  );
}

export function AppShell({
  children,
  activeNav = "home",
  userRole: suppliedRole,
  publicKnowledge = false,
}: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [navigationWidth, setNavigationWidth] = useState(224);
  const [navigationCollapsed, setNavigationCollapsed] = useState(activeNav === "chat" && process.env.NEXT_PUBLIC_KNOWLEDGE_PLATFORM !== "true");
  const [desktopActions, setDesktopActions] = useState<HTMLDivElement | null>(null);
  const [mobileActions, setMobileActions] = useState<HTMLDivElement | null>(null);
  const runtime = useOptionalUnifiedAssistant();
  const [localActor, setLocalActor] = useState<{ display_name?: string; student_code?: string; roles: string[] } | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const currentActor = localActor ?? runtime?.actor;
  const userRole: Role = localActor ? localActor.roles.some(role => ["KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"].includes(role)) ? "admin" : "student" : suppliedRole ?? (runtime?.actor?.roles.some(role => ["KNOWLEDGE_ADMIN", "SYSTEM_ADMIN"].includes(role)) ? "admin" : runtime?.capabilities?.audience === "staff" ? "staff" : "student");
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
  useEffect(() => {
    if (!operational) return;
    let active = true;
    void fetch(`${CAMPUS_API_BASE_URL}/v1/users/me`, { credentials: "include", cache: "no-store" })
      .then(response => {
        if (active) setSessionExpired(response.status === 401);
        return response.ok ? response.json() : null;
      })
      .then(actor => { if (active) setLocalActor(actor); }).catch(() => { if (active) setLocalActor(null); });
    return () => { active = false; };
  }, [operational]);
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
            ? "CỔNG THÔNG TIN CÔNG KHAI"
            : userRole === "staff"
            ? "KHÔNG GIAN CÁN BỘ"
            : userRole === "admin"
            ? "KHÔNG GIAN QUẢN TRỊ"
            : "KHÔNG GIAN SINH VIÊN"}
        </span>
      </div>

      <nav
        role="navigation"
        aria-label={isMobile ? "Điều hướng di động" : "Điều hướng chính"}
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
                aria-label={item.label}
                onClick={closeMenu}
                className="campus-nav-item"
              >
                <item.icon size={19} strokeWidth={1.7} aria-hidden="true" />
                <span className="campus-nav-label">{item.label}</span>
                <ExternalLink size={14} className="campus-external-icon" aria-hidden="true" />
              </a>
            );
          }
          return (
            <Link
              key={item.key}
              href={item.href}
              onClick={closeMenu}
              aria-label={item.label}
              title={item.label}
              aria-current={isActive ? "page" : undefined}
              className={"campus-nav-item" + (isActive ? " is-active" : "")}
            >
              <item.icon size={19} strokeWidth={1.7} aria-hidden="true" />
              <span className="campus-nav-label">{item.label}</span>
              {item.key === "chat" && (
                <span className="campus-ai-label" aria-hidden="true">
                  AI
                </span>
              )}
            </Link>
          );
        })}

        {chat && <div ref={isMobile ? setMobileActions : setDesktopActions} className="flex flex-col gap-1" aria-label="Công cụ hội thoại" />}
        {!operational && !isPublic && !chat && (
          <>
            <span className="campus-nav-divider" aria-hidden="true" />
            {navItems.filter(item => item.key === "rooms").map(item => <Link key={item.key} href={item.href} onClick={closeMenu} aria-current={activeNav === item.key ? "page" : undefined} className={"campus-nav-item" + (activeNav === item.key ? " is-active" : "")}><item.icon size={19} aria-hidden="true" /><span>{item.label}</span></Link>)}
            <Link
              href="/notifications"
              onClick={closeMenu}
              aria-label="Thông báo"
              aria-current={activeNav === "notifications" ? "page" : undefined}
              className={"campus-nav-item" + (activeNav === "notifications" ? " is-active" : "")}
            >
              <Bell size={19} strokeWidth={1.7} aria-hidden="true" />
              <span className="campus-nav-label">Thông báo</span>
            </Link>
            <Link
              href="/privacy"
              onClick={closeMenu}
              aria-label="Quyền riêng tư"
              aria-current={activeNav === "privacy" ? "page" : undefined}
              className={"campus-nav-item" + (activeNav === "privacy" ? " is-active" : "")}
            >
              <ShieldCheck size={19} strokeWidth={1.7} aria-hidden="true" />
              <span className="campus-nav-label">Quyền riêng tư</span>
            </Link>
          </>
        )}
      </nav>

      <div className="campus-sidebar-bottom">
        <div className="campus-help-card">
          <span className="campus-help-icon">
            <HelpCircle size={21} aria-hidden="true" />
          </span>
          <strong>Cần một chút trợ giúp?</strong>
          <p>Hỏi trợ lý để tìm đúng thông tin và bước tiếp theo.</p>
          <Link href="/chat" onClick={closeMenu}>
            Mở trợ lý học vụ <ArrowRight size={15} aria-hidden="true" />
          </Link>
        </div>

        <Link href="/login" onClick={closeMenu} className="campus-account" aria-label={currentActor ? `Đổi tài khoản: ${currentActor.display_name || currentActor.student_code || "Đã đăng nhập"}` : "Đăng nhập"} title={currentActor ? `${currentActor.display_name || "Đã đăng nhập"}${currentActor.student_code ? ` · ${currentActor.student_code}` : ""} · Đổi tài khoản` : "Đăng nhập"}>
          <span className="campus-avatar">
            <GraduationCap size={19} aria-hidden="true" />
          </span>
          <span className="campus-account-info">
            <strong>
              {runtime?.actor ? runtime.actor.display_name || runtime.actor.student_code || "Đã đăng nhập" : userRole === "guest"
                ? "Chào mừng bạn"
                : userRole === "staff"
                ? "Không gian cán bộ"
                : userRole === "admin"
                ? "Không gian quản trị"
                : "Tài khoản của bạn"}
            </strong>
            <small>
              {currentActor ? `${currentActor.student_code || "Đã đăng nhập"} · Đổi tài khoản` : "Đăng nhập để tiếp tục"}
            </small>
          </span>
          <ChevronRight size={15} aria-hidden="true" />
        </Link>
      </div>
    </>
  );

  return (
    <ChatMenuContext.Provider value={{ target: mobileOpen ? mobileActions : desktopActions, close: closeMenu }}>
    <div ref={shellRef} className={"campus-app" + (chat ? " campus-app-chat" : "")} data-campus-ui="v2">
      <a href="#main-content" className="skip-link">
        Bỏ qua tới nội dung chính
      </a>

      <aside className="campus-sidebar" aria-label="Thanh bên ứng dụng" data-collapsed={navigationCollapsed} style={{ width: navigationCollapsed ? 64 : navigationWidth }}>
        <button type="button" className="campus-nav-collapse" aria-label={navigationCollapsed ? "Mở rộng menu" : "Thu gọn menu"} title={navigationCollapsed ? "Mở rộng menu" : "Thu gọn menu"} onClick={() => setNavigationCollapsed(value => !value)}>{navigationCollapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button>
        {renderNavList(false)}
        {!navigationCollapsed && <PanelResizeHandle label="Đổi độ rộng menu" width={navigationWidth} onChange={setNavigationWidth} min={180} max={360} defaultWidth={224} />}
      </aside>

      <div className="campus-workspace">
        {chat && <button ref={menuRef} type="button" className="campus-menu-trigger campus-icon-button m-2 shrink-0 self-start" aria-label="Mở điều hướng" aria-expanded={mobileOpen} aria-controls="campus-mobile-navigation" onClick={() => setMobileOpen(true)}><Menu size={20} aria-hidden="true" /></button>}
        {!chat && <header className="campus-toolbar" role="banner">
          <div className="campus-toolbar-heading">
            <button
              ref={menuRef}
              type="button"
              className="campus-icon-button campus-menu-trigger"
              aria-label="Mở điều hướng"
              aria-expanded={mobileOpen}
              aria-controls="campus-mobile-navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={21} aria-hidden="true" />
            </button>
            <span className="campus-breadcrumb-brand">Campus 24/7</span>
            <ChevronRight size={14} className="campus-breadcrumb-chevron" aria-hidden="true" />
            <span className="campus-breadcrumb-title">{titles[activeNav] || "Không gian học vụ"}</span>
          </div>

          <div className="campus-toolbar-actions">
            <form
              action="/chat"
              method="GET"
              role="search"
              aria-label="Tìm nhanh trong Campus"
              className="campus-toolbar-search"
            >
              <Search size={16} aria-hidden="true" />
              <input aria-label="Tìm quy chế hoặc thủ tục" name="q" placeholder="Tìm thông tin học vụ…" />
              <kbd aria-hidden="true">↵</kbd>
            </form>

            <ThemeToggle className="campus-theme-toggle" />

            {!operational && <Link href="/notifications" className="campus-icon-button" aria-label="Mở thông báo">
              <Bell size={19} aria-hidden="true" />
            </Link>}

            <span className="campus-toolbar-divider" aria-hidden="true" />
            <span className="campus-institution">
              <strong>HUCE</strong>
              <small>Đại học Xây dựng Hà Nội</small>
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
              © 2026 Campus 24/7 <span aria-hidden="true">·</span> Đại học Xây dựng Hà Nội
            </span>
            {!operational && <Link href="/privacy">
              Thông tin & quyền riêng tư <ArrowRight size={13} aria-hidden="true" />
            </Link>}
          </footer>
        )}
      </div>

      {!operational && !isPublic && <nav className="campus-bottom-navigation" aria-label="Điều hướng nhanh">
        {navItems.filter(item => userRole === "student" ? ["home", "chat", "services", "tickets", "schedule"].includes(item.key) : ["home", "staff", "tickets", "knowledge", "admin"].includes(item.key)).map(item => <Link key={item.key} href={item.href} aria-current={activeNav === item.key ? "page" : undefined}><item.icon size={20} aria-hidden="true" /><span>{item.label}</span></Link>)}
      </nav>}

      <AccessibleDialog
        open={mobileOpen}
        onClose={closeMenu}
        labelledBy="campus-mobile-title"
        className="campus-mobile-dialog"
      >
        <div className="campus-mobile-header">
          <h2 id="campus-mobile-title" className="sr-only">
            Điều hướng Campus 24/7
          </h2>
          <button
            type="button"
            className="campus-mobile-close campus-icon-button"
            onClick={closeMenu}
            aria-label="Đóng điều hướng"
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
  );
}
