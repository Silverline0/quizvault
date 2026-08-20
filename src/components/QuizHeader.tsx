"use client";

import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";

interface QuizHeaderProps {
  title: string;
  backHref?: string;
  onBack?: () => void;
  /** Per-question actions. Omitted on screens that have no current question. */
  flagged?: boolean;
  bookmarked?: boolean;
  onToggleFlag?: () => void;
  onToggleBookmark?: () => void;
}

/**
 * The quiz screen's only chrome.
 *
 * `Navbar` stands down on `/quiz/*` so this is a single 44px bar rather than
 * two stacked sticky ones, which cost ~80px of a phone's viewport before the
 * question began. Flag and bookmark live here at full 44px touch size instead
 * of as 32px icons above the stem.
 */
export default function QuizHeader({
  title,
  backHref = "/",
  onBack,
  flagged,
  bookmarked,
  onToggleFlag,
  onToggleBookmark,
}: QuizHeaderProps) {
  const backIcon = (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );

  return (
    <header
      className="sticky top-0 z-40 h-11 flex items-center px-1 sm:px-2 gap-1 backdrop-blur-md"
      style={{
        backgroundColor: "color-mix(in srgb, var(--bg-primary) 85%, transparent)",
        borderBottom: "1px solid var(--border-subtle)",
      }}
    >
      {onBack ? (
        <button
          onClick={onBack}
          aria-label="Back"
          className="w-11 h-11 flex items-center justify-center shrink-0 hover:opacity-70"
          style={{ color: "var(--text-primary)" }}
        >
          {backIcon}
        </button>
      ) : (
        <Link
          href={backHref}
          aria-label="Back"
          className="w-11 h-11 flex items-center justify-center shrink-0 hover:opacity-70"
          style={{ color: "var(--text-primary)" }}
        >
          {backIcon}
        </Link>
      )}

      <h1 className="text-sm sm:text-base font-semibold truncate flex-1 min-w-0" style={{ color: "var(--text-primary)" }}>
        {title}
      </h1>

      {onToggleFlag && (
        <button
          onClick={onToggleFlag}
          className="w-11 h-11 flex items-center justify-center shrink-0 transition-transform hover:scale-110"
          style={{ color: flagged ? "var(--error)" : "var(--text-muted)" }}
          title={flagged ? "Unflag" : "Flag for discussion"}
          aria-pressed={flagged}
        >
          <svg width="17" height="17" viewBox="0 0 24 24"
            fill={flagged ? "var(--error)" : "none"}
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" /><line x1="4" y1="22" x2="4" y2="15" />
          </svg>
        </button>
      )}

      {onToggleBookmark && (
        <button
          onClick={onToggleBookmark}
          className="w-11 h-11 flex items-center justify-center shrink-0 transition-transform hover:scale-110"
          style={{ color: bookmarked ? "var(--warning)" : "var(--text-muted)" }}
          title={bookmarked ? "Remove bookmark" : "Bookmark"}
          aria-pressed={bookmarked}
        >
          <svg width="17" height="17" viewBox="0 0 24 24"
            fill={bookmarked ? "var(--warning)" : "none"}
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
          </svg>
        </button>
      )}

      {/* The site chrome is hidden here, so the theme control has to travel with
          it — a long session is exactly when someone reaches for sepia or dark. */}
      <ThemeToggle className="w-11 h-11" />
    </header>
  );
}
