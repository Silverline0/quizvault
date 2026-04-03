"use client";

interface ProgressBarProps {
  current: number;
  total: number;
  correct: number;
}

export default function ProgressBar({ current, total, correct }: ProgressBarProps) {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  const accuracy = current > 0 ? Math.round((correct / current) * 100) : 0;

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
          {current} / {total} questions
        </span>
        <span className="text-sm" style={{ color: current > 0 ? "var(--success)" : "var(--text-muted)" }}>
          {current > 0 ? `${accuracy}% accuracy` : ""}
        </span>
      </div>
      <div className="w-full h-2 rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-secondary)" }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: "var(--accent)" }}
        />
      </div>
    </div>
  );
}
