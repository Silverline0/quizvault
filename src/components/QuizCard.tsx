"use client";

import { Question } from "@/lib/types";
import { useCallback, useEffect, useState } from "react";
import { isBookmarked, toggleBookmark, isFlagged, toggleFlagged } from "@/lib/store";
import { triggerHaptic, getSetting } from "@/lib/settings";
import ImageZoom from "@/components/ImageZoom";

interface QuizCardProps {
  question: Question;
  onAnswer: (selected: string, correct: boolean) => void;
  showResult: boolean;
  selectedAnswer: string | null;
}

export default function QuizCard({ question, onAnswer, showResult, selectedAnswer }: QuizCardProps) {
  const [bookmarked, setBookmarked] = useState(false);
  const [flagged, setFlagged] = useState(false);
  const [glowKey, setGlowKey] = useState<string | null>(null);
  const [showScan, setShowScan] = useState(false);

  useEffect(() => {
    setBookmarked(isBookmarked(question.id, question.source));
    setFlagged(isFlagged(question.id, question.source));
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

  const handleBookmark = () => {
    toggleBookmark(question.id, question.source);
    setBookmarked(!bookmarked);
    triggerHaptic("light");
  };

  const handleFlag = () => {
    toggleFlagged(question.id, question.source);
    setFlagged(!flagged);
    triggerHaptic("light");
  };

  const optionKeys = Object.keys(question.options).sort();
  const showHints = typeof window !== "undefined" ? getSetting("showKeyboardHints") : true;

  return (
    <div>
      {/* Action buttons row — compact, right-aligned */}
      <div className="flex items-center justify-end gap-0.5 mb-1">
        <button
          onClick={handleFlag}
          className="w-8 h-8 flex items-center justify-center transition-transform hover:scale-110"
          style={{ color: flagged ? "var(--error)" : "var(--text-muted)" }}
          title={flagged ? "Unflag" : "Flag for discussion"}
        >
          <svg width="14" height="14" viewBox="0 0 24 24"
            fill={flagged ? "var(--error)" : "none"}
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" /><line x1="4" y1="22" x2="4" y2="15" />
          </svg>
        </button>
        <button
          onClick={handleBookmark}
          className="w-8 h-8 flex items-center justify-center transition-transform hover:scale-110"
          style={{ color: bookmarked ? "var(--warning)" : "var(--text-muted)" }}
          title={bookmarked ? "Remove bookmark" : "Bookmark"}
        >
          <svg width="14" height="14" viewBox="0 0 24 24"
            fill={bookmarked ? "var(--warning)" : "none"}
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
          </svg>
        </button>
      </div>

      {/* Question text — full width */}
      <h2
        className="quiz-question text-lg md:text-2xl lg:text-3xl font-semibold leading-snug mb-3"
        style={{ color: "var(--text-primary)" }}
      >
        {question.question}
      </h2>

      {/* Question image with zoom */}
      {question.imageUrl && (
        <div className="mb-5" style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-lg)" }}>
          <ImageZoom src={question.imageUrl} alt={`Clinical image for question ${question.id}`} />
          {question.figureConfidence && (
            <p className="px-3 py-2 text-xs figure-caveat" style={{ borderTop: "1px solid var(--border)" }}>
              {question.figureConfidence === "low"
                ? "This figure was matched to the question by position and may belong to a neighbouring one — check it against the stem before relying on it."
                : "This figure was matched by position, not named in the question. Usually right, but worth a sanity-check against the stem."}
            </p>
          )}
        </div>
      )}

      {/* Scan of the source page, so a doubtful figure can be settled by eye */}
      {question.pageScanUrl && (
        <div className="mb-5">
          <button
            type="button"
            onClick={() => setShowScan((v) => !v)}
            className="text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
            style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
          >
            {showScan ? "Hide" : "See"} the original PDF page
            {question.pdfPage ? ` (p.${question.pdfPage})` : ""}
          </button>
          {showScan && (
            <div className="mt-2" style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-lg)" }}>
              <ImageZoom
                src={question.pageScanUrl}
                alt={`Source PDF page ${question.pdfPage} for question ${question.id}`}
              />
            </div>
          )}
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

      {/* Options — 2x2 grid on desktop, single column on mobile */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 lg:gap-4 md:min-h-[200px]">
        {optionKeys.map((key) => {
          const isSelected = selectedAnswer === key;
          const isCorrect = key === question.correctAnswer;
          const isGlowing = glowKey === key;

          let borderColor = "var(--border)";
          let bgColor = "var(--bg-card)";
          let letterBg = "var(--bg-secondary)";
          let letterColor = "var(--text-muted)";
          let shadow = "var(--shadow-sm)";
          let radioContent: React.ReactNode = (
            <span className="w-6 h-6 rounded-full shrink-0" style={{ border: "2px solid var(--border)" }} />
          );

          if (showResult) {
            if (isCorrect) {
              borderColor = "var(--success)";
              bgColor = "var(--success-bg)";
              letterBg = "var(--success)";
              letterColor = "white";
              shadow = isGlowing ? "0 0 20px color-mix(in srgb, var(--success) 30%, transparent)" : "var(--shadow-sm)";
              radioContent = (
                <span className="w-6 h-6 rounded-full shrink-0 flex items-center justify-center" style={{ backgroundColor: "var(--success)" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>
                </span>
              );
            } else if (isSelected && !isCorrect) {
              borderColor = "var(--error)";
              bgColor = "var(--error-bg)";
              letterBg = "var(--error)";
              letterColor = "white";
              radioContent = (
                <span className="w-6 h-6 rounded-full shrink-0 flex items-center justify-center" style={{ backgroundColor: "var(--error)" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                </span>
              );
            }
          } else if (isSelected) {
            borderColor = "var(--accent)";
            bgColor = "var(--accent-light)";
            letterBg = "var(--accent)";
            letterColor = "white";
            shadow = "var(--shadow-glow)";
            radioContent = (
              <span className="w-6 h-6 rounded-full shrink-0 flex items-center justify-center" style={{ backgroundColor: "var(--accent)" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>
              </span>
            );
          }

          return (
            <button
              key={key}
              onClick={() => handleSelect(key)}
              disabled={showResult}
              className="option-card w-full text-left px-4 py-3.5 flex items-center gap-3"
              style={{
                border: `2px solid ${borderColor}`,
                backgroundColor: bgColor,
                boxShadow: shadow,
                cursor: showResult ? "default" : "pointer",
              }}
            >
              {/* Radio circle on left */}
              {radioContent}
              {/* Letter + text */}
              <span className="quiz-option flex-1 text-sm md:text-base leading-relaxed" style={{ color: "var(--text-primary)" }}>
                <span className="font-semibold" style={{ color: letterColor === "white" ? letterColor : "var(--text-muted)" }}>{key}.</span>{" "}
                {question.options[key]}
              </span>
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
