"use client";

interface QuestionCounterProps {
  current: number;
  total: number;
  correct: number;
  onOpenNavigator?: () => void;
}

export default function QuestionCounter({ current, total, correct, onOpenNavigator }: QuestionCounterProps) {
  const accuracy = current > 0 ? Math.round((correct / current) * 100) : 0;
  const pct = total > 0 ? Math.round(((current + 1) / total) * 100) : 0;

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
      <div className="flex items-center justify-between gap-2">
        {onOpenNavigator ? (
          <>
            {/* The sidebar navigator is xl-only, so below that the counter
                itself is the way into the question list. */}
            <button
              onClick={onOpenNavigator}
              aria-haspopup="dialog"
              className="xl:hidden h-8 px-2.5 flex items-center gap-1.5 text-sm font-semibold shrink-0 hover:opacity-80"
              style={{
                border: "1px solid var(--border)",
                backgroundColor: "var(--bg-card)",
                color: "var(--text-secondary)",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <span>
                Q{current + 1}
                <span className="font-normal" style={{ color: "var(--text-muted)" }}> of {total}</span>
              </span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="18 15 12 9 6 15" />
              </svg>
            </button>
            <span className="hidden xl:inline text-sm font-semibold" style={{ color: "var(--text-secondary)" }}>
              Questions {current + 1} of {total}
            </span>
          </>
        ) : (
          <span className="text-sm font-semibold" style={{ color: "var(--text-secondary)" }}>
            Questions {current + 1} of {total}
          </span>
        )}

        {current > 0 && (
          <span className="text-sm shrink-0" style={{ color: "var(--text-muted)" }}>
            {accuracy}% correct
          </span>
        )}
      </div>
    </div>
  );
}
