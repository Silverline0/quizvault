"use client";

interface QuestionNavigatorProps {
  total: number;
  currentIndex: number;
  answeredMap: Map<number, boolean>;
  onJump: (index: number) => void;
  onMarkPreviousAnswered?: () => void;
}

export default function QuestionNavigator({ total, currentIndex, answeredMap, onJump, onMarkPreviousAnswered }: QuestionNavigatorProps) {
  return (
    <div
      className="hidden xl:block w-56 shrink-0 p-4 sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto"
      style={{ backgroundColor: "var(--bg-card)", border: "1px solid var(--border)" }}
    >
      {/* Header with legend inline */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
          Questions
        </h3>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2" style={{ backgroundColor: "var(--accent)", borderRadius: "1px" }} title="Current" />
          <span className="w-2 h-2" style={{ backgroundColor: "var(--success)", borderRadius: "1px" }} title="Correct" />
          <span className="w-2 h-2" style={{ backgroundColor: "var(--error)", borderRadius: "1px" }} title="Wrong" />
          <span className="w-2 h-2" style={{ backgroundColor: "var(--border)", borderRadius: "1px" }} title="Unanswered" />
        </div>
      </div>

      {/* Question grid */}
      <div className="grid grid-cols-5 gap-1.5">
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
              className="w-9 h-8 text-xs font-semibold flex items-center justify-center transition-all hover:scale-105"
              style={{
                backgroundColor: bgColor,
                border: `1px solid ${borderColor}`,
                color: textColor,
              }}
              title={`Question ${i + 1}`}
            >
              {i + 1}
            </button>
          );
        })}
      </div>

      {/* Mark previous as done — subtle, at bottom */}
      {onMarkPreviousAnswered && currentIndex > 0 && (
        <button
          onClick={onMarkPreviousAnswered}
          className="w-full mt-3 py-1.5 px-3 text-xs font-medium transition-opacity hover:opacity-70"
          style={{
            color: "var(--text-muted)",
            borderTop: "1px solid var(--border)",
          }}
        >
          Mark 1–{currentIndex} as done
        </button>
      )}
    </div>
  );
}
