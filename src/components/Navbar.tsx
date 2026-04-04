"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

type Theme = "light" | "dark" | "sepia";
const THEME_CYCLE: Theme[] = ["light", "dark", "sepia"];
const THEME_ICONS: Record<Theme, React.ReactNode> = {
  light: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>,
  dark: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/></svg>,
  sepia: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a7 7 0 0 0 0 20z"/></svg>,
};

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/search", label: "Search" },
  { href: "/exam", label: "Exam" },
  { href: "/review", label: "Review" },
  { href: "/stats", label: "Stats" },
  { href: "/settings", label: "Settings" },
];

export default function Navbar() {
  const [theme, setTheme] = useState<Theme>("light");
  const pathname = usePathname();

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
    <nav
      className="sticky top-0 z-50 backdrop-blur-md"
      style={{
        backgroundColor: "color-mix(in srgb, var(--bg-primary) 85%, transparent)",
        borderBottom: "1px solid var(--border-subtle)",
      }}
    >
      <div className="max-w-5xl mx-auto px-3 sm:px-4 h-11 sm:h-12 flex items-center justify-between">
        <Link href="/" className="shrink-0">
          <span className="text-sm sm:text-base font-bold tracking-tight" style={{ color: "var(--accent)" }}>Quiz</span>
          <span className="text-sm sm:text-base font-display italic" style={{ color: "var(--text-primary)" }}> Vault</span>
        </Link>

        <div className="flex items-center gap-0">
          {NAV_LINKS.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className="px-2 sm:px-2.5 py-1 text-xs sm:text-sm font-medium transition-colors"
                style={{
                  color: isActive ? "var(--accent)" : "var(--text-muted)",
                  borderBottom: isActive ? "2px solid var(--accent)" : "2px solid transparent",
                }}
              >
                {link.label}
              </Link>
            );
          })}
          <button
            onClick={cycleTheme}
            className="w-8 h-8 flex items-center justify-center ml-1 text-sm transition-all hover:scale-105"
            style={{ color: "var(--text-muted)" }}
            title={`Switch theme`}
          >
            {THEME_ICONS[theme]}
          </button>
        </div>
      </div>
    </nav>
  );
}
