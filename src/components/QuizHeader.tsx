"use client";

import Link from "next/link";

interface QuizHeaderProps {
  title: string;
  backHref?: string;
}

export default function QuizHeader({ title, backHref = "/" }: QuizHeaderProps) {
  return (
    <header
      className="sticky top-0 z-40 h-14 flex items-center px-4 gap-3 backdrop-blur-md"
      style={{
        backgroundColor: "color-mix(in srgb, var(--bg-primary) 85%, transparent)",
        borderBottom: "1px solid var(--border-subtle)",
      }}
    >
      <Link
        href={backHref}
        className="w-9 h-9 rounded-full flex items-center justify-center transition-colors hover:opacity-70"
        style={{ color: "var(--text-primary)" }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
      </Link>
      <h1 className="text-base font-semibold truncate" style={{ color: "var(--text-primary)" }}>
        {title}
      </h1>
    </header>
  );
}
