"use client";

import { useState } from "react";

interface QuestionCounterProps {
  current: number;
  total: number;
  correct: number;
  onMarkPreviousAnswered?: () => void;
}

export default function QuestionCounter({ current, total, correct, onMarkPreviousAnswered }: QuestionCounterProps) {
  const accuracy = current > 0 ? Math.round((correct / current) * 100) : 0;
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold" style={{ color: "var(--accent)" }}>
          Questions {current + 1} of {total}
        </span>

        {/* Menu button — visible on mobile (xl:hidden) when there are previous questions */}
        {onMarkPreviousAnswered && current > 0 && (
          <div className="relative xl:hidden">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="w-6 h-6 rounded-full flex items-center justify-center hover:opacity-70"
              style={{ color: "var(--text-muted)" }}
              title="Options"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <circle cx="12" cy="5" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="12" cy="19" r="2" />
              </svg>
            </button>
            {showMenu && (
              <div
                className="absolute top-8 left-0 z-50 rounded-xl p-1 shadow-lg animate-fade-in min-w-48"
                style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
              >
                <button
                  onClick={() => { onMarkPreviousAnswered(); setShowMenu(false); }}
                  className="w-full text-left px-3 py-2.5 rounded-lg text-xs font-medium hover:opacity-80 transition-opacity"
                  style={{ color: "var(--accent)" }}
                >
                  Mark Q1–{current} as done
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {current > 0 && (
        <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
          {accuracy}% correct
        </span>
      )}
    </div>
  );
}
