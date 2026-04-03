"use client";

interface QuestionNavigatorProps {
  total: number;
  currentIndex: number;
  answeredMap: Map<number, boolean>; // index -> correct
  onJump: (index: number) => void;
  onMarkPreviousAnswered?: () => void;
}

export default function QuestionNavigator({ total, currentIndex, answeredMap, onJump, onMarkPreviousAnswered }: QuestionNavigatorProps) {
  return (
    <div
      className="hidden xl:block w-56 shrink-0 rounded-xl p-4 sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto"
      style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
    >
      <h3 className="text-xs font-semibold mb-3 uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
        Questions
      </h3>
      <div className="grid grid-cols-5 gap-2">
        {Array.from({ length: total }, (_, i) => {
          const isCurrent = i === currentIndex;
          const answered = answeredMap.has(i);
          const correct = answeredMap.get(i);

          let bgColor = "transparent";
          let borderColor = "var(--border)";
          let textColor = "var(--text-muted)";

          if (isCurrent) {
            bgColor = "var(--accent-light)";
            borderColor = "var(--accent)";
            textColor = "var(--accent)";
          } else if (answered && correct) {
            bgColor = "var(--success-bg)";
            borderColor = "var(--success)";
            textColor = "var(--success)";
          } else if (answered && !correct) {
            bgColor = "var(--error-bg)";
            borderColor = "var(--error)";
            textColor = "var(--error)";
          }

          return (
            <button
              key={i}
              onClick={() => onJump(i)}
              className="w-9 h-9 rounded-lg text-xs font-semibold flex items-center justify-center transition-all hover:scale-105"
              style={{
                backgroundColor: bgColor,
                border: `2px solid ${borderColor}`,
                color: textColor,
              }}
              title={`Question ${i + 1}`}
            >
              {i + 1}
            </button>
          );
        })}
      </div>

      {/* Mark previous as answered */}
      {onMarkPreviousAnswered && currentIndex > 0 && (
        <button
          onClick={onMarkPreviousAnswered}
          className="w-full mt-3 py-2 px-3 rounded-lg text-xs font-medium transition-opacity hover:opacity-80"
          style={{
            backgroundColor: "var(--accent-light)",
            color: "var(--accent)",
            border: "1px solid var(--accent)",
          }}
        >
          Mark 1–{currentIndex} as done
        </button>
      )}

      {/* Legend */}
      <div className="mt-4 pt-3 space-y-1.5" style={{ borderTop: "1px solid var(--border)" }}>
        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
          <span className="w-3 h-3 rounded-sm" style={{ border: "2px solid var(--accent)", backgroundColor: "var(--accent-light)" }} />
          Current
        </div>
        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
          <span className="w-3 h-3 rounded-sm" style={{ border: "2px solid var(--success)", backgroundColor: "var(--success-bg)" }} />
          Correct
        </div>
        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
          <span className="w-3 h-3 rounded-sm" style={{ border: "2px solid var(--error)", backgroundColor: "var(--error-bg)" }} />
          Wrong
        </div>
        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
          <span className="w-3 h-3 rounded-sm" style={{ border: "2px solid var(--border)" }} />
          Unanswered
        </div>
      </div>
    </div>
  );
}
