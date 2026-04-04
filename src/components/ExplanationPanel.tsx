"use client";

import { Question } from "@/lib/types";

// Medical terms to auto-highlight in explanations
const MEDICAL_TERM_PATTERNS = [
  // Disease names (capitalized multi-word)
  /\b(?:Sturge-Weber|Marfan|Down|Turner|Treacher Collins|Pierre Robin|Crouzon|Apert|Goldenhar|Axenfeld-Rieger|Peters|Duane|Brown|Möbius|Marcus Gunn|Horner|Adie|Argyll Robertson|Parinaud|Weber|Wallenberg|Foster Kennedy|Claude|Benedikt|Millard-Gubler)\s*(?:syndrome|anomaly|disease)?\b/gi,
  // Drug names ending in common suffixes
  /\b\w+(?:olol|prine|mab|nib|cillin|mycin|floxacin|cycline|pam|lam|zole|statin|sartan|dipine|pril|lukast|gliptin|tide|platin|rubicin)\b/gi,
  // Anatomical structures
  /\b(?:optic nerve|optic chiasm|optic disc|macula|fovea|retina|cornea|sclera|uvea|iris|ciliary body|choroid|vitreous|lens|conjunctiva|Bruch.s membrane|Descemet.s membrane|Bowman.s layer|trabecular meshwork|Schlemm.s canal|lamina cribrosa)\b/gi,
  // Clinical signs
  /\b(?:cherry[- ]red spot|cotton[- ]wool spots?|Kayser-Fleischer rings?|Bitot.s spots?|Roth spots?|Brushfield spots?|Lisch nodules?|drusen|papilledema|proptosis|ptosis|enophthalmos|exophthalmos|anisocoria|leukocoria)\b/gi,
];

function highlightKeyTerms(text: string): React.ReactNode {
  // Build a combined regex from all patterns
  const combined = new RegExp(
    MEDICAL_TERM_PATTERNS.map(p => p.source).join('|'),
    'gi'
  );

  const parts = text.split(combined);
  const matches = text.match(combined);

  if (!matches) return text;

  const result: React.ReactNode[] = [];
  parts.forEach((part, i) => {
    result.push(part);
    if (i < matches.length) {
      result.push(
        <span key={i} className="key-term">{matches[i]}</span>
      );
    }
  });
  return result;
}

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

      {/* Explanation text with key term highlighting */}
      {question.explanation && (
        <div className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          {highlightKeyTerms(question.explanation)}
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
