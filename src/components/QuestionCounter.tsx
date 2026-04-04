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
  const pct = total > 0 ? Math.round(((current + 1) / total) * 100) : 0;
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="mb-2">
      {/* Progress bar */}
      <div className="w-full h-1 mb-2 overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
        <div
          className="h-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: "var(--accent)" }}
        />
      </div>

      {/* Text row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold" style={{ color: "var(--text-secondary)" }}>
            Questions {current + 1} of {total}
          </span>

          {/* Mobile menu for mark-as-done */}
          {onMarkPreviousAnswered && current > 0 && (
            <div className="relative xl:hidden">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="w-6 h-6 flex items-center justify-center hover:opacity-70"
                style={{ color: "var(--text-muted)" }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <circle cx="12" cy="5" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="12" cy="19" r="2" />
                </svg>
              </button>
              {showMenu && (
                <div
                  className="absolute top-full left-0 z-50 p-1 shadow-lg animate-fade-in min-w-48"
                  style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
                >
                  <button
                    onClick={() => { onMarkPreviousAnswered(); setShowMenu(false); }}
                    className="w-full text-left px-3 py-2.5 text-xs font-medium hover:opacity-80"
                    style={{ color: "var(--accent)" }}
                  >
                    Mark Q1-{current} as done
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {current > 0 && (
          <span className="text-sm" style={{ color: "var(--text-muted)" }}>
            {accuracy}% correct
          </span>
        )}
      </div>
    </div>
  );
}
