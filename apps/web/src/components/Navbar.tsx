"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  GraduationCap,
  LogOut,
  ChevronDown,
  FileText,
  Home,
  LayoutDashboard,
  Menu,
  X,
  FileSearch,
  MessageCircle,
} from "lucide-react";
import { useStore } from "@/lib/store";
import { ThemeToggle } from "./ThemeToggle";

export function Navbar() {
  const pathname = usePathname();
  const { currentUser, logout } = useStore();
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const accountTriggerRef = React.useRef<HTMLButtonElement>(null);
  const accountPanelRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (userDropdownOpen) accountPanelRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
  }, [userDropdownOpen]);

  React.useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (userDropdownOpen) accountTriggerRef.current?.focus();
        setUserDropdownOpen(false);
        setMobileMenuOpen(false);
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [userDropdownOpen]);

  if (!currentUser) return null;

  const isStudent = currentUser.role === "student";

  const affiliation = currentUser.department || currentUser.major || currentUser.classYear;

  /* ── Navigation items based on role ── */
  const navItems = isStudent
    ? [
        { href: "/student", label: "Dịch vụ sinh viên", icon: Home },
        { href: "/student/assistant", label: "Trợ lý học vụ", icon: MessageCircle },
        { href: "/my-requests", label: "Hồ sơ của tôi", icon: FileText },
      ]
    : [
        { href: "/dashboard", label: "Hàng chờ hồ sơ", icon: LayoutDashboard },
        { href: "/reviews", label: "Rà soát học phần", icon: FileSearch },
      ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[var(--border-subtle)] bg-white/85 dark:bg-[#252525]/85 backdrop-blur-xl transition-colors">
      <div className={`${isStudent ? "max-w-[1120px]" : "max-w-7xl"} mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4`}>
        {/* ── Left: Brand ── */}
        <Link href={isStudent ? "/student" : "/dashboard"} className="flex min-h-11 items-center gap-2.5 shrink-0 group">
          <div className="w-8 h-8 rounded-[4px] bg-[#0078D4] flex items-center justify-center text-white shadow-sm group-hover:bg-[#005a9e] transition-colors">
            <GraduationCap className="w-4.5 h-4.5" />
          </div>
          <span className="font-bold text-[15px] text-[#2F2F2F] dark:text-white tracking-tight">
            Campus 24/7
          </span>
        </Link>

        {/* ── Center: Navigation (desktop) ── */}
        <nav className="hidden lg:flex items-center gap-1" aria-label="Điều hướng chính">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/reviews" || item.href === "/student"
                ? pathname.startsWith(item.href) && pathname !== "/student/assistant"
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={`flex min-h-11 items-center gap-2 px-3.5 py-2 rounded-[4px] text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-[#0078D4] text-white font-semibold shadow-xs"
                    : "text-slate-600 dark:text-slate-300 hover:text-[#0078D4] dark:hover:text-white hover:bg-black/[0.04] dark:hover:bg-white/[0.06]"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* ── Right: Compact utilities ── */}
        <div className="flex items-center gap-2">
          {/* User profile button */}
          <div className="relative" onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget)) setUserDropdownOpen(false);
          }}>
            <button
              ref={accountTriggerRef}
              type="button"
              aria-expanded={userDropdownOpen}
              aria-controls="account-panel"
              aria-label={`Tài khoản ${currentUser.name}`}
              onClick={() => { setUserDropdownOpen(!userDropdownOpen); setMobileMenuOpen(false); }}
              className="relative z-50 flex min-h-11 items-center gap-2 px-2 py-1.5 rounded-[4px] border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              <div
                className={`w-7 h-7 rounded-[4px] flex items-center justify-center text-white text-[11px] font-bold ${
                  isStudent
                    ? "bg-[#0078D4]"
                    : "bg-[#5C2D91]"
                }`}
              >
                {isStudent ? "SV" : "CB"}
              </div>

              <div className="hidden sm:block text-left">
                <div className="text-[13px] font-semibold text-gray-800 dark:text-gray-200 leading-tight">
                  {currentUser.name}
                </div>
                <div className="text-[11px] text-gray-500 dark:text-gray-400">
                  {isStudent ? currentUser.mssv || currentUser.id : currentUser.id}
                </div>
              </div>

              <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
            </button>

            {userDropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setUserDropdownOpen(false)}
                />
                <div id="account-panel" ref={accountPanelRef} role="region" aria-label="Tùy chọn tài khoản" className="fixed left-4 right-4 top-[72px] max-h-[calc(100dvh-88px)] overflow-y-auto overscroll-contain rounded-[4px] bg-white dark:bg-[#252525] border border-gray-200 dark:border-gray-700 shadow-lg z-50 p-2 text-[13px] sm:absolute sm:left-auto sm:right-0 sm:top-full sm:mt-2 sm:w-80">
                  {/* Current user */}
                  <div className="p-3 rounded-[4px] bg-gray-50 dark:bg-gray-800/60 mb-2">
                    <div className="mb-2 text-xs font-medium text-gray-500 dark:text-gray-400">Tài khoản đang đăng nhập</div>
                    <div className="font-semibold text-gray-900 dark:text-white break-words">
                      {currentUser.name}
                    </div>
                    <div className="text-[12px] text-gray-500 dark:text-gray-400 mt-0.5 break-words">
                      {currentUser.email}
                    </div>
                    <div className="text-[12px] text-gray-600 dark:text-gray-300 mt-1 break-words">
                      {isStudent ? "Mã sinh viên" : "Mã cán bộ"}: {isStudent ? currentUser.mssv || currentUser.id : currentUser.id}
                    </div>
                    <div className="text-[12px] text-gray-600 dark:text-gray-300 mt-0.5 break-words">
                      {isStudent ? "Sinh viên" : "Cán bộ"}{affiliation ? ` · ${affiliation}` : ""}
                    </div>
                  </div>

                  {/* App Settings */}
                  <div className="flex items-center justify-between px-2 py-2 mb-2 border-b border-gray-100 dark:border-gray-800">
                    <ThemeToggle showLabel />
                  </div>

                  {/* Logout */}
                  <div className="border-t border-gray-100 dark:border-gray-800 pt-1.5 mt-1">
                    <Link
                      href="/login"
                      onClick={() => {
                        logout();
                        setUserDropdownOpen(false);
                      }}
                      className="w-full min-h-11 text-left px-3 py-2 rounded-[4px] flex items-center gap-2 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 font-medium transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>Đăng xuất</span>
                    </Link>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Mobile menu toggle */}
          <button
            type="button"
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-menu"
            onClick={() => { setMobileMenuOpen(!mobileMenuOpen); setUserDropdownOpen(false); }}
            className="lg:hidden flex min-h-11 min-w-11 items-center justify-center p-2 rounded-[4px] border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label="Menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {mobileMenuOpen && (
        <nav id="mobile-menu" className="lg:hidden border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-[#252525] px-4 py-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/reviews" || item.href === "/student"
                ? pathname.startsWith(item.href) && pathname !== "/student/assistant"
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2.5 px-3 py-2.5 rounded-[4px] text-[14px] font-medium min-h-[44px] ${
                  isActive
                    ? "bg-[#0078D4] text-white"
                    : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                }`}
              >
                <Icon className="w-4.5 h-4.5" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      )}
    </header>
  );
}
