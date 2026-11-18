"use client";

import React from "react";
import { Sun, Moon } from "lucide-react";
import { useTheme } from "@/lib/theme";

export function ThemeToggle({
  className = "",
  showLabel = false,
}: {
  className?: string;
  showLabel?: boolean;
}) {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`inline-flex min-h-11 min-w-11 items-center gap-2 rounded-lg border border-slate-200 p-2 text-slate-600 transition-all duration-200 hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800 ${
        showLabel ? "w-full justify-start px-3 text-sm" : "justify-center"
      } ${className}`}
      title={theme === "dark" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
      aria-label={theme === "dark" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
      aria-pressed={theme === "dark"}
    >
      {theme === "dark" ? (
        <Sun className="w-4 h-4 text-amber-400 transition-transform hover:rotate-45" />
      ) : (
        <Moon className="h-4 w-4 text-slate-700 transition-transform hover:-rotate-12 dark:text-slate-300" />
      )}
      {showLabel && <span>{theme === "dark" ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}</span>}
    </button>
  );
}
