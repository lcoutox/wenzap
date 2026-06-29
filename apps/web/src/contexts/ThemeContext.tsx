"use client";

import { createContext, useContext, useEffect, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "wenzap_theme";
const DEFAULT_THEME: ThemePreference = "dark";

interface ThemeContextValue {
  theme: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getSystemTheme(): ResolvedTheme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolve(pref: ThemePreference): ResolvedTheme {
  return pref === "system" ? getSystemTheme() : pref;
}

function applyTheme(resolved: ResolvedTheme) {
  document.documentElement.dataset.theme = resolved;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemePreference>(DEFAULT_THEME);
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>("dark");

  // Sync with localStorage on mount (after hydration)
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as ThemePreference | null;
    const pref = stored ?? DEFAULT_THEME;
    const resolved = resolve(pref);
    setThemeState(pref);
    setResolvedTheme(resolved);
    applyTheme(resolved);
  }, []);

  // Listen to system preference changes when theme === "system"
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      const resolved = getSystemTheme();
      setResolvedTheme(resolved);
      applyTheme(resolved);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  const setTheme = (pref: ThemePreference) => {
    localStorage.setItem(STORAGE_KEY, pref);
    const resolved = resolve(pref);
    setThemeState(pref);
    setResolvedTheme(resolved);
    applyTheme(resolved);
  };

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
