"use client";

import { useState } from "react";
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

/** A labelled rule that separates one kind of claim from another. */
function SectionLabel({ children, note }: { children: React.ReactNode; note?: string }) {
  return (
    <div className="flex items-center gap-2.5 mt-6 mb-2.5">
      <span
        className="text-[10.5px] font-bold uppercase tracking-wider shrink-0"
        style={{ color: "var(--text-muted)" }}
      >
        {children}
      </span>
      <span className="flex-1 h-px" style={{ backgroundColor: "var(--border)" }} />
      {note && (
        <span className="text-[10.5px] shrink-0" style={{ color: "var(--text-muted)" }}>{note}</span>
      )}
    </div>
  );
}

/** One line of the verdict: what was chosen, and what the exam marks. */
function VerdictRow({ label, letter, text, tone }: {
  label: string;
  letter: string;
  text?: string;
  tone: "success" | "error";
}) {
  const bg = tone === "success" ? "var(--success-bg)" : "var(--error-bg)";
  const ink = tone === "success" ? "var(--success-ink)" : "var(--error-ink)";
  const edge = tone === "success" ? "var(--success)" : "var(--error)";
  return (
    <div className="flex items-start gap-2.5">
      <span
        className="text-[10.5px] font-bold uppercase tracking-wider shrink-0 pt-1.5 w-[86px]"
        style={{ color: "var(--text-muted)" }}
      >
        {label}
      </span>
      <span
        className="w-6 h-6 shrink-0 flex items-center justify-center text-xs font-bold"
        style={{ backgroundColor: bg, color: ink, border: `1px solid ${edge}`, borderRadius: "var(--radius-lg)" }}
      >
        {letter}
      </span>
      <span className="text-sm leading-relaxed pt-0.5 min-w-0" style={{ color: "var(--text-primary)" }}>
        {text}
      </span>
    </div>
  );
}

interface ExplanationPanelProps {
  question: Question;
  wasCorrect: boolean;
  /** Which option was chosen, so the verdict can state it rather than imply it. */
  selectedAnswer?: string | null;
  /**
   * Take the answer back. Only passed for a question answered in this sitting,
   * where a mis-tap is still a live memory and the record can be removed
   * exactly. Absent means no undo is offered.
   */
  onUndo?: () => void;
}

export default function ExplanationPanel({ question, wasCorrect, selectedAnswer, onUndo }: ExplanationPanelProps) {
  const [concernOpen, setConcernOpen] = useState(false);
  const accentColor = wasCorrect ? "var(--success)" : "var(--error)";
  const review = question.review;

  // A reviewer who lands on a different letter changes how everything below
  // should be read, so it is announced before either explanation rather than
  // discovered underneath them.
  const contested = review && !review.agrees;
  const answerMissing = review?.answerMissing === true;
  // Promotion recalls carry the compiler's own words, typos and all.
  const verbatim = question.source.startsWith("promotion") && !question.reviewerAnswered;

  return (
    <div
      className="rounded-xl p-5 mt-4 animate-slide-up overflow-hidden"
      style={{
        backgroundColor: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderLeft: `4px solid ${accentColor}`,
      }}
    >
      {/* Verdict — both answers stated plainly, rather than one long red line */}
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0 flex flex-col gap-2">
          {selectedAnswer ? (
            <VerdictRow
              label="You answered"
              letter={selectedAnswer}
              text={question.options[selectedAnswer]}
              tone={wasCorrect ? "success" : "error"}
            />
          ) : (
            <span className="text-sm font-bold" style={{ color: accentColor }}>
              {wasCorrect ? "Correct" : "Incorrect"}
            </span>
          )}
          {!wasCorrect && (
            <VerdictRow
              label={question.reviewerAnswered ? "Reviewer key" : "Exam key"}
              letter={question.correctAnswer}
              text={question.options[question.correctAnswer]}
              tone="success"
            />
          )}
        </div>
        {onUndo && (
          <button
            onClick={onUndo}
            title="Take this answer back — it will not count in your progress"
            className="shrink-0 h-8 px-2.5 flex items-center gap-1.5 text-xs font-semibold transition-opacity hover:opacity-70"
            style={{
              border: "1px solid var(--border)",
              backgroundColor: "var(--bg-primary)",
              color: "var(--text-secondary)",
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
            </svg>
            Undo
          </button>
        )}
      </div>

      {/* Contested — hoisted above both explanations */}
      {contested && !answerMissing && (
        <div className="mt-4 p-3 rounded-lg review-note review-differs">
          <div className="flex items-center gap-2 mb-1.5">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
              <line x1="12" y1="4" x2="12" y2="21" /><line x1="6" y1="21" x2="18" y2="21" /><line x1="4" y1="7" x2="20" y2="7" />
              <path d="M4 7l-2.6 6.2a3 3 0 0 0 5.2 0z" /><path d="M20 7l2.6 6.2a3 3 0 0 1-5.2 0z" />
            </svg>
            <span className="text-xs font-bold">This one is contested</span>
            <span className="ml-auto text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 shrink-0 opacity-75" style={{ border: "1px solid currentColor" }}>
              {review!.confidence}
            </span>
          </div>
          <p className="text-sm leading-relaxed">
            An independent reviewer answers <b>{review!.answer}</b>
            {selectedAnswer === review!.answer ? " — the option you chose" : ""}. The key above is{" "}
            <b>{question.correctAnswer}</b>, and the exam is what marks you, so that is what counts.
            Read both arguments before deciding what to remember.
          </p>
        </div>
      )}

      {/* The recall lost the option that held the right answer */}
      {answerMissing && (
        <div
          className="mt-4 p-3 rounded-lg"
          style={{ backgroundColor: "var(--warning-bg)", border: "1px solid var(--warning)" }}
        >
          <div className="flex items-center gap-2 mb-1.5" style={{ color: "var(--warning)" }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span className="text-xs font-bold">This recall looks incomplete</span>
          </div>
          <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            The reviewer&apos;s answer is <b>{review!.answer}</b>, which is not among the options above — so
            the option holding the right answer was probably lost when the question was written down.
            It cannot be answered correctly as it stands.
          </p>
        </div>
      )}

      {/* The exam's own words */}
      {question.explanation && (
        <>
          <SectionLabel note={verbatim ? "verbatim" : undefined}>
            {question.reviewerAnswered ? "Reviewer's explanation" : "The exam's explanation"}
          </SectionLabel>
          <div className="quiz-explanation text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            {highlightKeyTerms(question.explanation)}
          </div>
          {verbatim && (
            <p className="text-xs mt-2 leading-relaxed" style={{ color: "var(--text-muted)" }}>
              Copied straight from the recall document, typos and all — nothing here was rewritten, so
              you can see exactly what the source said.
            </p>
          )}
        </>
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

      {/* Second opinion — never overwrites the key, only argues with it */}
      {review && (
        <>
          <SectionLabel note={contested ? undefined : `${review.confidence} confidence`}>
            Second opinion
          </SectionLabel>
          <div className={`p-3 rounded-lg review-note ${review.agrees ? "review-agrees" : "review-differs"}`}>
            {review.agrees && (
              <p className="text-xs font-semibold mb-1.5">Reviewer agrees with the key above.</p>
            )}
            <p className="text-sm leading-relaxed">{review.explanation}</p>
            {review.concern && (
              <>
                <button
                  onClick={() => setConcernOpen((v) => !v)}
                  className="mt-2.5 flex items-center gap-1.5 text-[11.5px] font-bold opacity-85 hover:opacity-100"
                >
                  <svg
                    width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"
                    style={{ transform: `rotate(${concernOpen ? 90 : 0}deg)`, transition: "transform 0.2s ease" }}
                  >
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                  Where the reviewer hesitates
                </button>
                {concernOpen && (
                  <p className="text-xs mt-2 pt-2 leading-relaxed opacity-90" style={{ borderTop: "1px solid currentColor" }}>
                    {review.concern}
                  </p>
                )}
              </>
            )}
          </div>
        </>
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

      {/* Everything that lets the reader settle it for themselves */}
      {(question.pageScanUrl || (question.referenceLinks && question.referenceLinks.length > 0)) && (
        <>
          <SectionLabel>Check the source yourself</SectionLabel>
          {question.pageScanUrl && (
            <a
              href={question.pageScanUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 h-8 px-2.5 text-xs font-bold mb-2"
              style={{ border: "1px solid var(--accent)", backgroundColor: "var(--accent-light)", color: "var(--accent)" }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
              </svg>
              Open the source page{question.pdfPage ? ` (p.${question.pdfPage})` : ""}
            </a>
          )}
          {question.referenceLinks && question.referenceLinks.length > 0 && (
            <>
              <p className="text-xs mb-2 leading-relaxed" style={{ color: "var(--text-muted)" }}>
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
                      style={{ color: "var(--accent)" }}
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
            </>
          )}
        </>
      )}

      {/* Respondent stats */}
      {question.respondentStats && (
        <>
          <SectionLabel>How others answered</SectionLabel>
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
        </>
      )}
    </div>
  );
}
