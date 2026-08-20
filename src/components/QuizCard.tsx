"use client";

import { Question } from "@/lib/types";
import { useCallback, useEffect, useState } from "react";
import { triggerHaptic, getSetting } from "@/lib/settings";
import ImageZoom from "@/components/ImageZoom";

interface QuizCardProps {
  question: Question;
  onAnswer: (selected: string, correct: boolean) => void;
  showResult: boolean;
  selectedAnswer: string | null;
}

export default function QuizCard({ question, onAnswer, showResult, selectedAnswer }: QuizCardProps) {
  const [glowKey, setGlowKey] = useState<string | null>(null);
  const [showScan, setShowScan] = useState(false);

  useEffect(() => {
    setGlowKey(null);
    setShowScan(false);
  }, [question.id, question.source]);

  const handleSelect = useCallback(
    (key: string) => {
      if (showResult) return;
      const correct = key === question.correctAnswer;
      onAnswer(key, correct);
      triggerHaptic(correct ? "success" : "error");

      // Trigger glow animation on correct answer
      if (correct) {
        setGlowKey(key);
      }
    },
    [showResult, onAnswer, question.correctAnswer]
  );

  // Keyboard shortcuts
  useEffect(() => {
    if (showResult) return;
    const settings = typeof window !== "undefined" ? getSetting("keyMap") : null;
    const handler = (e: KeyboardEvent) => {
      if (!settings) return;
      const keyUpper = e.key.toUpperCase();
      if (keyUpper === settings.optionA.toUpperCase() && question.options["A"]) handleSelect("A");
      else if (keyUpper === settings.optionB.toUpperCase() && question.options["B"]) handleSelect("B");
      else if (keyUpper === settings.optionC.toUpperCase() && question.options["C"]) handleSelect("C");
      else if (keyUpper === settings.optionD.toUpperCase() && question.options["D"]) handleSelect("D");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [showResult, handleSelect, question.options]);

  const optionKeys = Object.keys(question.options).sort();
  const showHints = typeof window !== "undefined" ? getSetting("showKeyboardHints") : true;

  const scanButton = question.pageScanUrl ? (
    <button
      type="button"
      onClick={() => setShowScan((v) => !v)}
      className="inline-flex items-center gap-1.5 h-8 px-2.5 text-xs font-semibold transition-colors hover:opacity-80"
      style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg-card)", color: "var(--text-secondary)" }}
    >
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" />
      </svg>
      {showScan ? "Hide" : "See"} the original PDF page
      {question.pdfPage ? ` (p.${question.pdfPage})` : ""}
    </button>
  ) : null;

  const caveat = question.figureConfidence ? (
    <p className="px-3 py-2 text-xs leading-relaxed figure-caveat">
      {question.figureConfidence === "low"
        ? "This figure was matched to the question by position and may belong to a neighbouring one — check it against the stem before relying on it."
        : "This figure was matched by position, not named in the question. Usually right, but worth a sanity-check against the stem."}
    </p>
  ) : null;

  return (
    <div>
      {/* Question text — full width */}
      <h2
        className="quiz-question text-lg md:text-2xl font-semibold leading-snug mb-4"
        style={{ color: "var(--text-primary)", textWrap: "pretty" }}
      >
        {question.question}
      </h2>

      {/* Figure. On a laptop it sits beside its caveat and source link rather
          than stacking above them, which keeps all four options above the fold. */}
      {question.imageUrl && (
        <div className="mb-5 md:flex md:gap-4 md:items-start">
          <div
            className="md:w-[300px] md:shrink-0"
            style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}
          >
            <ImageZoom src={question.imageUrl} alt={`Clinical image for question ${question.id}`} />
            <div className="md:hidden">{caveat}</div>
          </div>
          <div className="md:flex-1 md:min-w-0 mt-2 md:mt-0 flex flex-col gap-2 items-start">
            <div className="hidden md:block w-full">{caveat}</div>
            {scanButton}
          </div>
        </div>
      )}

      {/* No figure, but a source page to check anyway */}
      {!question.imageUrl && scanButton && <div className="mb-5">{scanButton}</div>}

      {showScan && question.pageScanUrl && (
        <div className="mb-5" style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
          <ImageZoom
            src={question.pageScanUrl}
            alt={`Source PDF page ${question.pdfPage} for question ${question.id}`}
          />
        </div>
      )}

      {/* Secondary images (explanation diagrams, etc.) */}
      {question.imageUrls && question.imageUrls.length > 0 && (
        <div className="mb-5 flex gap-2 overflow-x-auto pb-2" style={{ scrollbarWidth: "thin" }}>
          {question.imageUrls.map((url, idx) => (
            <div
              key={idx}
              className="shrink-0"
              style={{
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-lg)",
                maxWidth: question.imageUrls!.length === 1 ? "100%" : "280px",
                width: question.imageUrls!.length === 1 ? "100%" : undefined,
              }}
            >
              <ImageZoom src={url} alt={`Additional image ${idx + 1} for question ${question.id}`} />
            </div>
          ))}
        </div>
      )}

      {/* Options — one column, so A→B→C→D reads top to bottom and a long
          surgical option is not squeezed into half a line. */}
      <div className="flex flex-col gap-2.5">
        {optionKeys.map((key) => {
          const isSelected = selectedAnswer === key;
          const isCorrect = key === question.correctAnswer;
          const isGlowing = glowKey === key;

          let borderColor = "var(--border)";
          let bgColor = "var(--bg-card)";
          let chipBg = "var(--bg-secondary)";
          let chipInk = "var(--text-muted)";
          let chipBorder = "transparent";
          let shadow = "var(--shadow-sm)";
          let opacity = 1;
          let mark: React.ReactNode = null;

          if (showResult) {
            if (isCorrect) {
              borderColor = "var(--success)";
              bgColor = "var(--success-bg)";
              chipBg = "var(--success-bg)";
              chipInk = "var(--success-ink)";
              chipBorder = "var(--success)";
              shadow = isGlowing ? "0 0 20px color-mix(in srgb, var(--success) 30%, transparent)" : "var(--shadow-sm)";
              mark = (
                <span className="w-5 h-5 rounded-full shrink-0 mt-0.5 flex items-center justify-center" style={{ backgroundColor: "var(--success)" }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
                </span>
              );
            } else if (isSelected) {
              borderColor = "var(--error)";
              bgColor = "var(--error-bg)";
              chipBg = "var(--error-bg)";
              chipInk = "var(--error-ink)";
              chipBorder = "var(--error)";
              mark = (
                <span className="w-5 h-5 rounded-full shrink-0 mt-0.5 flex items-center justify-center" style={{ backgroundColor: "var(--error)" }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                </span>
              );
            } else {
              // Neither yours nor the answer — step it back so the two that
              // matter carry the eye.
              opacity = 0.45;
            }
          } else if (isSelected) {
            borderColor = "var(--accent)";
            bgColor = "var(--accent-light)";
            chipBg = "var(--accent-light)";
            chipInk = "var(--accent)";
            chipBorder = "var(--accent)";
            shadow = "var(--shadow-glow)";
          }

          return (
            <button
              key={key}
              onClick={() => handleSelect(key)}
              disabled={showResult}
              className="option-card w-full text-left px-3.5 py-3 flex items-start gap-3"
              style={{
                border: `2px solid ${borderColor}`,
                backgroundColor: bgColor,
                boxShadow: shadow,
                opacity,
                cursor: showResult ? "default" : "pointer",
              }}
            >
              <span
                className="w-7 h-7 shrink-0 flex items-center justify-center text-sm font-bold"
                style={{ backgroundColor: chipBg, color: chipInk, border: `1px solid ${chipBorder}`, borderRadius: "var(--radius-lg)" }}
              >
                {key}
              </span>
              <span className="quiz-option flex-1 min-w-0 text-sm md:text-base leading-relaxed pt-0.5" style={{ color: "var(--text-primary)", textWrap: "pretty" }}>
                {question.options[key]}
              </span>
              {mark}
            </button>
          );
        })}
      </div>

      {/* Keyboard hint */}
      {!showResult && showHints && (
        <p className="text-xs mt-3 text-center hidden md:block" style={{ color: "var(--text-muted)" }}>
          Press{" "}
          {optionKeys.map((k) => (
            <kbd key={k} className="px-1.5 py-0.5 rounded text-xs font-mono mx-0.5" style={{ backgroundColor: "var(--bg-secondary)" }}>
              {k}
            </kbd>
          ))}
          {" "}to select
        </p>
      )}
    </div>
  );
}
