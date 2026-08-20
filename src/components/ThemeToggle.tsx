"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "sepia";

const THEME_CYCLE: Theme[] = ["light", "dark", "sepia"];

const THEME_ICONS: Record<Theme, React.ReactNode> = {
  light: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>,
  dark: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/></svg>,
  sepia: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a7 7 0 0 0 0 20z"/></svg>,
};

/**
 * Cycles light → dark → sepia.
 *
 * The quiz screen and the site chrome both carry one of these, and a
 * MutationObserver on `data-theme` keeps every mounted copy showing the same
 * icon no matter which one was pressed.
 */
export default function ThemeToggle({ className = "w-9 h-9" }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const saved = localStorage.getItem("theme") as Theme | null;
    const preferred = saved || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    setTheme(preferred);
    document.documentElement.setAttribute("data-theme", preferred);

    const observer = new MutationObserver(() => {
      const current = document.documentElement.getAttribute("data-theme") as Theme;
      if (current) setTheme(current);
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  const cycleTheme = () => {
    const idx = THEME_CYCLE.indexOf(theme);
    const next = THEME_CYCLE[(idx + 1) % THEME_CYCLE.length];
    setTheme(next);
    localStorage.setItem("theme", next);
    document.documentElement.setAttribute("data-theme", next);
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content",
      next === "dark" ? "#0c0c14" : next === "sepia" ? "#f0e8d8" : "#7c3aed"
    );
  };

  return (
    <button
      onClick={cycleTheme}
      className={`${className} flex items-center justify-center shrink-0 hover:scale-105 transition-transform`}
      style={{ color: "var(--text-muted)" }}
      title={`Theme: ${theme}`}
      aria-label="Switch theme"
    >
      {THEME_ICONS[theme]}
    </button>
  );
}
