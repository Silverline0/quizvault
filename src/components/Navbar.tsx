"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Manifest } from "@/lib/types";

type Theme = "light" | "dark" | "sepia";
const THEME_CYCLE: Theme[] = ["light", "dark", "sepia"];
const THEME_ICONS: Record<Theme, React.ReactNode> = {
  light: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>,
  dark: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/></svg>,
  sepia: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a7 7 0 0 0 0 20z"/></svg>,
};

const NAV_LINKS = [
  { href: "/", label: "Home", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg> },
  { href: "/search", label: "Search", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> },
  { href: "/exam", label: "Mock Exam", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> },
  { href: "/review", label: "Review Mistakes", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg> },
  { href: "/stats", label: "Statistics", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg> },
  { href: "/settings", label: "Settings", icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg> },
];

export default function Navbar() {
  const [theme, setTheme] = useState<Theme>("light");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [manifest, setManifest] = useState<Manifest | null>(null);
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

  // Load manifest for quick quiz access
  useEffect(() => {
    fetch("/data/manifest.json").then(r => r.json()).then(setManifest).catch(() => {});
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

  // Close sidebar on route change
  useEffect(() => { setSidebarOpen(false); }, [pathname]);

  // Group question sets by category
  const categories = manifest?.categories || [];
  const setsByCategory: Record<string, Manifest["questionSets"]> = {};
  if (manifest) {
    for (const qs of manifest.questionSets) {
      const cat = qs.category || "other";
      if (!setsByCategory[cat]) setsByCategory[cat] = [];
      setsByCategory[cat].push(qs);
    }
  }

  return (
    <>
      {/* Top bar — minimal */}
      <nav
        className="sticky top-0 z-50 backdrop-blur-md"
        style={{
          backgroundColor: "color-mix(in srgb, var(--bg-primary) 85%, transparent)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div className="max-w-7xl mx-auto px-3 sm:px-4 h-10 sm:h-12 flex items-center justify-between">
          {/* Left: hamburger + logo */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSidebarOpen(true)}
              className="w-9 h-9 flex items-center justify-center hover:opacity-70"
              style={{ color: "var(--text-primary)" }}
              aria-label="Open menu"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <Link href="/" className="shrink-0">
              <span className="text-sm sm:text-base font-bold tracking-tight" style={{ color: "var(--accent)" }}>Quiz</span>
              <span className="text-sm sm:text-base font-display italic" style={{ color: "var(--text-primary)" }}> Vault</span>
            </Link>
          </div>

          {/* Right: theme toggle */}
          <button
            onClick={cycleTheme}
            className="w-9 h-9 flex items-center justify-center hover:scale-105 transition-transform"
            style={{ color: "var(--text-muted)" }}
            title="Switch theme"
          >
            {THEME_ICONS[theme]}
          </button>
        </div>
      </nav>

      {/* Sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-[60] animate-fade-in"
          style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar drawer */}
      <aside
        className="fixed top-0 left-0 z-[70] h-full w-72 sm:w-80 overflow-y-auto transition-transform duration-300"
        style={{
          backgroundColor: "var(--bg-card)",
          borderRight: "1px solid var(--border)",
          transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)",
          boxShadow: sidebarOpen ? "var(--shadow-lg)" : "none",
        }}
      >
        {/* Sidebar header */}
        <div className="flex items-center justify-between p-4" style={{ borderBottom: "1px solid var(--border)" }}>
          <Link href="/" onClick={() => setSidebarOpen(false)}>
            <span className="text-base font-bold tracking-tight" style={{ color: "var(--accent)" }}>Quiz</span>
            <span className="text-base font-display italic" style={{ color: "var(--text-primary)" }}> Vault</span>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="w-8 h-8 flex items-center justify-center hover:opacity-70"
            style={{ color: "var(--text-muted)" }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Navigation links */}
        <div className="p-3">
          <p className="text-xs font-semibold uppercase tracking-wider px-3 mb-2" style={{ color: "var(--text-muted)" }}>
            Navigation
          </p>
          {NAV_LINKS.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setSidebarOpen(false)}
                className="flex items-center gap-3 px-3 py-2.5 mb-0.5 transition-colors"
                style={{
                  color: isActive ? "var(--accent)" : "var(--text-secondary)",
                  backgroundColor: isActive ? "var(--accent-light)" : "transparent",
                }}
              >
                {link.icon}
                <span className="text-sm font-medium">{link.label}</span>
              </Link>
            );
          })}
        </div>

        {/* Quick access quizzes */}
        {manifest && categories.length > 0 && (
          <div className="p-3" style={{ borderTop: "1px solid var(--border)" }}>
            <p className="text-xs font-semibold uppercase tracking-wider px-3 mb-2" style={{ color: "var(--text-muted)" }}>
              Quick Access
            </p>
            {categories.map((cat) => {
              const sets = setsByCategory[cat.id] || [];
              if (sets.length === 0) return null;
              return (
                <div key={cat.id} className="mb-2">
                  <p className="text-xs font-semibold px-3 py-1" style={{ color: "var(--text-secondary)" }}>
                    {cat.name}
                  </p>
                  {sets.map((qs) => (
                    <Link
                      key={qs.id}
                      href={`/quiz/${qs.id}?mode=sequential`}
                      onClick={() => setSidebarOpen(false)}
                      className="flex items-center justify-between px-3 py-2 hover:opacity-80 transition-opacity"
                      style={{ color: "var(--text-muted)" }}
                    >
                      <span className="text-xs truncate">{qs.name}</span>
                      <span className="text-xs shrink-0 ml-2" style={{ color: "var(--text-muted)" }}>
                        {qs.questionCount}
                      </span>
                    </Link>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </aside>
    </>
  );
}
