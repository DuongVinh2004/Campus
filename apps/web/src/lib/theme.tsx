"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Theme = "light" | "dark";
const STORAGE_KEY = "campus247_theme_v2";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({ theme: "light", toggleTheme: () => undefined });

function readStored(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "dark" || value === "light" ? value : null;
  } catch {
    return null; // private window or blocked storage: the choice lasts for this page only
  }
}

function apply(theme: Theme): void {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

/**
 * The colour theme, kept apart from the data store so it works in every build (the operational build has no data store).
 * The first paint is set by the inline script in the root layout; this provider only follows the person's choice afterwards.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    const initial = readStored() ?? (query?.matches ? "dark" : "light");
    apply(initial);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(initial);
    const follow = (event: MediaQueryListEvent) => {
      if (readStored()) return; // an explicit choice wins over the system setting
      const next = event.matches ? "dark" : "light";
      apply(next);
      setTheme(next);
    };
    query?.addEventListener?.("change", follow);
    return () => query?.removeEventListener?.("change", follow);
  }, []);

  const toggleTheme = useCallback(() => {
    const next: Theme = document.documentElement.classList.contains("dark") ? "light" : "dark";
    apply(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* the theme still changes for this page */
    }
    setTheme(next);
  }, []);

  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
