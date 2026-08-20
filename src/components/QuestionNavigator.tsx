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
      className="hidden xl:block w-52 shrink-0 sticky top-11"
      // 44px header + the 16px the quiz container pads with. Sized to its
      // resting position so it never runs past the viewport; once stuck at
      // top-11 it simply leaves that 16px as a gap.
      style={{ height: "calc(100vh - 3.75rem)" }}
    >
      <div className="h-full flex flex-col p-3" style={{ backgroundColor: "var(--bg-card)", borderLeft: "1px solid var(--border)" }}>
        {/* Header with legend + mark done */}
        <div className="flex items-center justify-between mb-2 shrink-0">
          <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
            Questions
          </span>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2" style={{ backgroundColor: "var(--accent)" }} title="Current" />
            <span className="w-2 h-2" style={{ backgroundColor: "var(--success)" }} title="Correct" />
            <span className="w-2 h-2" style={{ backgroundColor: "var(--error)" }} title="Wrong" />
          </div>
        </div>

        {/* Mark previous — compact, at top */}
        {onMarkPreviousAnswered && currentIndex > 0 && (
          <button
            onClick={onMarkPreviousAnswered}
            className="w-full mb-2 py-1.5 text-xs font-medium shrink-0 hover:opacity-70"
            style={{ color: "var(--accent)", borderBottom: "1px solid var(--border)" }}
          >
            Mark 1-{currentIndex} done
          </button>
        )}

        {/* Scrollable question grid */}
        <div className="flex-1 overflow-y-auto min-h-0">
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
                  className="w-full aspect-square text-[10px] font-semibold flex items-center justify-center transition-all hover:scale-105"
                  style={{
                    backgroundColor: bgColor,
                    border: `1px solid ${borderColor}`,
                    color: textColor,
                  }}
                >
                  {i + 1}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
