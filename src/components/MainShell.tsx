"use client";

import { usePathname } from "next/navigation";

/**
 * The page container.
 *
 * Every screen but the quiz sits in a padded, 1024px-capped column. The quiz
 * screen opts out: its header is `sticky top-0` and the shell's `py-8` left a
 * 32px gap above it, and its sidebar navigator needs the full width rather than
 * a column narrower than the breakpoint that reveals it.
 */
export default function MainShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const onQuizScreen = pathname?.startsWith("/quiz/") ?? false;

  return (
    <main className={onQuizScreen ? "w-full" : "max-w-5xl mx-auto px-4 py-8"}>
      {children}
    </main>
  );
}
