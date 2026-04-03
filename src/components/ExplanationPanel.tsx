"use client";

import { Question } from "@/lib/types";

interface ExplanationPanelProps {
  question: Question;
  wasCorrect: boolean;
}

export default function ExplanationPanel({ question, wasCorrect }: ExplanationPanelProps) {
  return (
    <div
      className="rounded-xl p-6 mt-4 animate-in fade-in slide-in-from-bottom-2 duration-300"
      style={{
        backgroundColor: wasCorrect ? "var(--success-bg)" : "var(--error-bg)",
        border: `1px solid ${wasCorrect ? "var(--success)" : "var(--error)"}`,
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        {wasCorrect ? (
          <>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <span className="font-semibold" style={{ color: "var(--success)" }}>Correct!</span>
          </>
        ) : (
          <>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--error)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
            <span className="font-semibold" style={{ color: "var(--error)" }}>
              Incorrect — Answer: {question.correctAnswer}. {question.options[question.correctAnswer]}
            </span>
          </>
        )}
      </div>

      <div className="text-sm leading-relaxed" style={{ color: "var(--text-primary)" }}>
        {question.explanation}
      </div>

      {/* Respondent stats */}
      {question.respondentStats && (
        <div className="mt-4 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
          <p className="text-xs font-medium mb-2" style={{ color: "var(--text-muted)" }}>
            How others answered:
          </p>
          <div className="flex flex-wrap gap-3">
            {Object.entries(question.respondentStats).map(([key, pct]) => (
              <div key={key} className="flex items-center gap-1.5">
                <span className="text-xs font-bold" style={{ color: "var(--text-secondary)" }}>{key}.</span>
                <div className="w-20 h-2 rounded-full overflow-hidden" style={{ backgroundColor: "var(--bg-secondary)" }}>
                  <div
                    className="h-full rounded-full transition-all"
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
