"use client";

import React from "react";
import { Languages } from "lucide-react";
import { useLanguage } from "@/lib/i18n";

/** Switches the interface between Vietnamese and English. The button names the language it will switch TO. */
export function LanguageToggle({ className = "" }: { className?: string }) {
  const { language, setLanguage, t } = useLanguage();
  const label = language === "vi" ? t("lang.switchToEnglish") : t("lang.switchToVietnamese");
  return (
    <button
      type="button"
      onClick={() => setLanguage(language === "vi" ? "en" : "vi")}
      className={`inline-flex min-h-11 min-w-11 items-center justify-center gap-1 rounded-lg border border-slate-200 p-2 text-sm text-slate-600 transition-all duration-200 hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800 ${className}`}
      title={label}
      aria-label={label}
      lang={language === "vi" ? "en" : "vi"}
    >
      <Languages className="h-4 w-4" aria-hidden="true" />
      <span aria-hidden="true">{language === "vi" ? "EN" : "VI"}</span>
    </button>
  );
}
