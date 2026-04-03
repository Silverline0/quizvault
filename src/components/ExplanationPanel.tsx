"use client";

import { Question } from "@/lib/types";

interface ExplanationPanelProps {
  question: Question;
  wasCorrect: boolean;
}

export default function ExplanationPanel({ question, wasCorrect }: ExplanationPanelProps) {
  const accentColor = wasCorrect ? "var(--success)" : "var(--error)";

  return (
    <div
      className="rounded-xl p-5 mt-4 animate-slide-up overflow-hidden"
      style={{
        backgroundColor: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderLeft: `4px solid ${accentColor}`,
      }}
    >
      {/* Result header */}
      <div className="flex items-center gap-2 mb-3">
        {wasCorrect ? (
          <>
            <span className="w-6 h-6 rounded-full flex items-center justify-center" style={{ backgroundColor: "var(--success)" }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </span>
            <span className="font-bold text-sm" style={{ color: "var(--success)" }}>Correct!</span>
          </>
        ) : (
          <>
            <span className="w-6 h-6 rounded-full flex items-center justify-center" style={{ backgroundColor: "var(--error)" }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </span>
            <span className="font-bold text-sm" style={{ color: "var(--error)" }}>
              Incorrect — Answer: {question.correctAnswer}. {question.options[question.correctAnswer]}
            </span>
          </>
        )}
      </div>

      {/* Explanation text */}
      {question.explanation && (
        <div className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          {question.explanation}
        </div>
      )}

      {/* Respondent stats */}
      {question.respondentStats && (
        <div className="mt-4 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
          <p className="text-xs font-medium mb-2" style={{ color: "var(--text-muted)" }}>
            How others answered:
          </p>
          <div className="flex flex-wrap gap-3">
            {Object.entries(question.respondentStats).map(([key, pct]) => (
              <div key={key} className="flex items-center gap-1.5">
                <span className="text-xs font-bold" style={{ color: "var(--text-secondary)" }}>{key}.</span>
                <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-secondary)" }}>
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: key === question.correctAnswer ? "var(--success)" : "var(--text-muted)",
                    }}
                  />
                </div>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>{pct}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
