"use client";

import Link from "next/link";

interface QuizHeaderProps {
  title: string;
  backHref?: string;
  onBack?: () => void;
}

export default function QuizHeader({ title, backHref = "/", onBack }: QuizHeaderProps) {
  const backIcon = (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );

  return (
    <header
      className="sticky top-0 z-40 h-12 sm:h-14 flex items-center px-3 sm:px-4 gap-2 backdrop-blur-md"
      style={{
        backgroundColor: "color-mix(in srgb, var(--bg-primary) 85%, transparent)",
        borderBottom: "1px solid var(--border-subtle)",
      }}
    >
      {onBack ? (
        <button
          onClick={onBack}
          className="w-11 h-11 rounded-full flex items-center justify-center shrink-0 hover:opacity-70"
          style={{ color: "var(--text-primary)" }}
        >
          {backIcon}
        </button>
      ) : (
        <Link
          href={backHref}
          className="w-11 h-11 rounded-full flex items-center justify-center shrink-0 hover:opacity-70"
          style={{ color: "var(--text-primary)" }}
        >
          {backIcon}
        </Link>
      )}
      <h1 className="text-sm sm:text-base font-semibold truncate" style={{ color: "var(--text-primary)" }}>
        {title}
      </h1>
    </header>
  );
}
