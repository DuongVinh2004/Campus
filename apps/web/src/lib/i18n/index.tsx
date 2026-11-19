"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { en } from "./en";
import { vi, type MessageKey } from "./vi";

export type Language = "vi" | "en";
export type { MessageKey };
export const LANGUAGE_COOKIE = "lang";
const MESSAGES: Record<Language, Record<MessageKey, string>> = { vi, en };

/** Text for a key in a language, with `{name}` placeholders filled from `params`. Vietnamese is the fallback. */
export function interpolate(text: string, params?: Record<string, string | number>): string {
  return params ? text.replace(/\{(\w+)\}/g, (whole, name: string) => (name in params ? String(params[name]) : whole)) : text;
}

export function translate(language: Language, key: MessageKey, params?: Record<string, string | number>): string {
  return interpolate(MESSAGES[language]?.[key] ?? vi[key], params);
}

export function parseLanguage(value: string | null | undefined): Language {
  return value === "en" ? "en" : "vi";
}

function readCookie(): Language {
  try {
    const match = document.cookie.split("; ").find((part) => part.startsWith(`${LANGUAGE_COOKIE}=`));
    return parseLanguage(match?.slice(LANGUAGE_COOKIE.length + 1));
  } catch {
    return "vi";
  }
}

function writeCookie(language: Language): void {
  try {
    document.cookie = `${LANGUAGE_COOKIE}=${language}; path=/; max-age=31536000; samesite=lax`;
  } catch {
    /* the language still changes for this page */
  }
}

interface LanguageContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: MessageKey, params?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextValue>({
  language: "vi", setLanguage: () => undefined, t: (key, params) => translate("vi", key, params),
});

/**
 * The interface language. Vietnamese is the default; the choice is kept in the `lang` cookie and applied to `<html lang>`.
 * It is read in the browser after the first paint (the pages stay static), so an English reader may see Vietnamese for an instant.
 */
export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>("vi");

  useEffect(() => {
    const stored = readCookie();
    document.documentElement.lang = stored;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLanguageState(stored);
  }, []);

  const setLanguage = useCallback((next: Language) => {
    document.documentElement.lang = next;
    writeCookie(next);
    setLanguageState(next);
  }, []);

  const value = useMemo<LanguageContextValue>(
    () => ({ language, setLanguage, t: (key, params) => translate(language, key, params) }), [language, setLanguage]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage(): LanguageContextValue {
  return useContext(LanguageContext);
}

export function useT(): LanguageContextValue["t"] {
  return useContext(LanguageContext).t;
}
