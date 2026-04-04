"use client";

interface SessionSummaryProps {
  questionsAnswered: number;
  correctCount: number;
  startTime: number;
  onClose: () => void;
  onContinue?: () => void;
}

export default function SessionSummary({
  questionsAnswered,
  correctCount,
  startTime,
  onClose,
  onContinue,
}: SessionSummaryProps) {
  const duration = Math.round((Date.now() - startTime) / 1000);
  const minutes = Math.floor(duration / 60);
  const seconds = duration % 60;
  const accuracy = questionsAnswered > 0 ? Math.round((correctCount / questionsAnswered) * 100) : 0;
  const avgTime = questionsAnswered > 0 ? Math.round(duration / questionsAnswered) : 0;

  if (questionsAnswered === 0) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in"
      style={{ backgroundColor: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm rounded-2xl p-6 animate-scale-in"
        style={{ backgroundColor: "var(--bg-card)", boxShadow: "var(--shadow-lg)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-center mb-4" style={{ color: "var(--text-primary)" }}>
          Session Summary
        </h2>

        <div className="grid grid-cols-2 gap-3 mb-5">
          <div className="text-center p-3 rounded-xl" style={{ backgroundColor: "var(--bg-secondary)" }}>
            <div className="text-2xl font-bold font-display" style={{ color: "var(--accent)" }}>
              {questionsAnswered}
            </div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Questions</div>
          </div>
          <div className="text-center p-3 rounded-xl" style={{ backgroundColor: "var(--bg-secondary)" }}>
            <div className="text-2xl font-bold font-display" style={{ color: accuracy >= 70 ? "var(--success)" : "var(--error)" }}>
              {accuracy}%
            </div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Accuracy</div>
          </div>
          <div className="text-center p-3 rounded-xl" style={{ backgroundColor: "var(--bg-secondary)" }}>
            <div className="text-2xl font-bold font-display" style={{ color: "var(--text-primary)" }}>
              {minutes}:{seconds.toString().padStart(2, "0")}
            </div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Duration</div>
          </div>
          <div className="text-center p-3 rounded-xl" style={{ backgroundColor: "var(--bg-secondary)" }}>
            <div className="text-2xl font-bold font-display" style={{ color: "var(--text-primary)" }}>
              {avgTime}s
            </div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>Avg/Question</div>
          </div>
        </div>

        <div className="flex gap-2">
          {onContinue && (
            <button
              onClick={onContinue}
              className="flex-1 py-3 rounded-xl text-sm font-bold"
              style={{ backgroundColor: "var(--bg-secondary)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
            >
              Continue
            </button>
          )}
          <button
            onClick={onClose}
            className="flex-1 py-3 rounded-xl text-sm font-bold text-white"
            style={{ backgroundColor: "var(--text-primary)" }}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
