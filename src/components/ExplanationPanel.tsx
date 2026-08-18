"use client";

import { Question } from "@/lib/types";
import ImageZoom from "@/components/ImageZoom";

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
        <div className="quiz-explanation text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          {highlightKeyTerms(question.explanation)}
        </div>
      )}

      {/* Secondary images (explanation diagrams) */}
      {question.imageUrls && question.imageUrls.length > 0 && (
        <div className="mt-4 flex gap-2 overflow-x-auto pb-2" style={{ scrollbarWidth: "thin" }}>
          {question.imageUrls.map((url, idx) => (
            <div
              key={idx}
              className="shrink-0"
              style={{
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-lg)",
                maxWidth: question.imageUrls!.length === 1 ? "100%" : "260px",
                width: question.imageUrls!.length === 1 ? "100%" : undefined,
              }}
            >
              <ImageZoom src={url} alt={`Explanation image ${idx + 1} for question ${question.id}`} />
            </div>
          ))}
        </div>
      )}

      {/* Reviewer's second opinion — its own colour, and never the app's key */}
      {question.review && (
        <div
          className={`mt-4 p-3 rounded-lg review-note ${question.review.agrees ? "review-agrees" : "review-differs"}`}
        >
          <p className="text-xs font-semibold mb-1">
            {question.review.answerMissing
              ? `Careful — this recall looks incomplete. The reviewer's answer is ${question.review.answer}, which is not among the options above, so the option holding the right answer was probably lost when the question was recalled.`
              : question.review.agrees
                ? "Reviewer agrees with this answer"
                : `Reviewer disagrees — they answer ${question.review.answer}. The exam key above is ${question.correctAnswer}.`}
            <span className="ml-2 font-normal opacity-75">
              ({question.review.confidence} confidence)
            </span>
          </p>
          <p className="text-sm leading-relaxed">{question.review.explanation}</p>
          {question.review.concern && (
            <p className="text-xs mt-1.5 opacity-90">{question.review.concern}</p>
          )}
        </div>
      )}

      {/* Provenance for reviewer-answered recalls */}
      {question.reviewerAnswered && (
        <div className="mt-4 p-3 rounded-lg review-note review-differs">
          <p className="text-xs font-semibold mb-1">
            The source never answered this one — the key above is a reviewer&apos;s
            <span className="ml-1 font-normal opacity-75">
              ({question.reviewConfidence} confidence)
            </span>
          </p>
          {question.sourceHint && (
            <p className="text-xs opacity-90">
              What the compiler wrote instead: &ldquo;{question.sourceHint}&rdquo;
            </p>
          )}
          {question.reviewConcern && (
            <p className="text-xs mt-1 opacity-90">{question.reviewConcern}</p>
          )}
        </div>
      )}

      {/* Reference images, for questions whose own figure is doubtful or absent */}
      {question.referenceLinks && question.referenceLinks.length > 0 && (
        <div className="mt-4 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
          <p className="text-xs font-medium mb-2" style={{ color: "var(--text-muted)" }}>
            {question.imageUrl
              ? "Not sure the image above is the right one? See this finding here:"
              : "This question refers to a picture the source didn't include. See the finding here:"}
            {question.figureFinding ? ` ${question.figureFinding}.` : ""}
          </p>
          <ul className="flex flex-col gap-1.5">
            {question.referenceLinks.map((link) => (
              <li key={link.url}>
                <a
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm underline underline-offset-2"
                  style={{ color: "var(--accent, #2563eb)" }}
                >
                  {link.title}
                </a>
                {link.source && (
                  <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>
                    {link.source}
                  </span>
                )}
                {link.shows && (
                  <span className="block text-xs" style={{ color: "var(--text-muted)" }}>
                    {link.shows}
                  </span>
                )}
              </li>
            ))}
          </ul>
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
